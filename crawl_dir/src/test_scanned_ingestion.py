from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pymupdf
from PIL import Image

from .pipeline.scanned_ingestion import (
    ExternalResourceHtmlError,
    detect_visual_figure_pages,
    _raw_chunks,
    _sanitize_external_resources,
    generate_initial_html_with_claude,
    html_to_markdown,
    image_only_pages,
    process_scanned_document,
)
from .pipeline.artifact_io import resolve_raw_document
from .ingestion_mcp import (
    download_public_pdf,
    ingest_native_pdf_with_visual_figures,
    list_public_pdfs,
)
from .pipeline.page_segmentation import segment_page_with_claude
from .pipeline.figure_segmentation import (
    extract_native_figure_evidence,
    generate_page_html_with_corrected_figures,
)
from .pipeline.runner import _split_pages


def _fake_anthropic(text: str, calls: list[dict]) -> SimpleNamespace:
    """Stand-in for the anthropic module: beta.messages.stream returns ``text``."""
    message = SimpleNamespace(stop_reason="end_turn", stop_details=None,
                              content=[SimpleNamespace(type="text", text=text)])

    class Stream:
        def __enter__(self):
            return SimpleNamespace(get_final_message=lambda: message)

        def __exit__(self, *_exc):
            return False

    class FakeAnthropic:
        def __init__(self, **_kwargs):
            self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

        @staticmethod
        def _stream(**kwargs):
            calls.append(kwargs)
            return Stream()

    return SimpleNamespace(Anthropic=FakeAnthropic)


class ScannedIngestionTests(unittest.TestCase):
    def test_native_figure_evidence_clips_pdf_words_and_preserves_signs(self):
        root = Path(tempfile.mkdtemp())
        source_pdf = root / "source.pdf"
        source_png = root / "source.png"
        document = pymupdf.open()
        page = document.new_page(width=200, height=100)
        page.insert_text((20, 30), "Figure 1 +7% 57%")
        page.insert_text((120, 80), "outside")
        document.save(source_pdf)
        document.close()
        Image.new("RGB", (400, 200), "white").save(source_png)

        evidence = extract_native_figure_evidence(
            source_pdf, source_png, [0, 0, 220, 100]
        )

        self.assertTrue(evidence["authoritative"])
        self.assertIn("Figure 1 +7% 57%", evidence["literal_text"])
        self.assertNotIn("outside", evidence["literal_text"])
        self.assertEqual(evidence["numeric_tokens"], ["1", "+7%", "57%"])

    def test_figure_crop_loop_records_title_attempts_and_errors(self):
        root = Path(tempfile.mkdtemp())
        segment_dir = root / "segments"
        segment_dir.mkdir()
        source = root / "source.png"
        crop = segment_dir / "figure-01-chart.png"
        Image.new("RGB", (400, 300), "white").save(source)
        Image.new("RGB", (200, 120), "white").save(crop)
        segmentation = {
            "regions": [{
                "id": "chart", "kind": "chart", "title": "Figure 1 Benefits",
                "pixel_box": [0, 0, 200, 120], "image": crop.name,
            }],
        }
        reviews = iter([
            {"verdict": "mismatch", "errors": [{
                "category": "text_overlap", "source_evidence": "clear labels",
                "html_evidence": "overlap", "correction": "separate labels",
            }]},
            {"verdict": "match", "errors": []},
        ])

        def render(_html, output):
            Image.new("RGB", (200, 120), "white").save(output)

        with patch(
            "crawl_dir.src.pipeline.scanned_ingestion.generate_initial_html_with_claude",
            return_value="<html><body>chart</body></html>",
        ), patch(
            "crawl_dir.src.pipeline.scanned_ingestion._render_html", side_effect=render,
        ), patch(
            "crawl_dir.src.pipeline.scanned_ingestion.review_chart_html_with_claude",
            side_effect=lambda *_args: next(reviews),
        ), patch(
            "crawl_dir.src.pipeline.scanned_ingestion.correct_with_claude",
            return_value="<html><body>corrected chart</body></html>",
        ), patch(
            "crawl_dir.src.pipeline.figure_segmentation._assemble_page_html",
            return_value="<html><body>assembled page</body></html>",
        ):
            result = generate_page_html_with_corrected_figures(
                source, segmentation, segment_dir, "test-model"
            )

        batch = json.loads((segment_dir / "batch.json").read_text())
        self.assertEqual(result, "<html><body>assembled page</body></html>")
        self.assertEqual(batch["status"], "passed")
        self.assertEqual(batch["max_iterations_per_figure"], 6)
        self.assertEqual(batch["figures"][0]["title"], "Figure 1 Benefits")
        self.assertEqual(len(batch["figures"][0]["iterations"]), 2)
        self.assertEqual(batch["figures"][0]["iterations"][0]["error_count"], 1)

    def test_figure_crop_loop_stops_a_cycle_and_keeps_best_candidate(self):
        root = Path(tempfile.mkdtemp())
        segment_dir = root / "segments"
        segment_dir.mkdir()
        source = root / "source.png"
        crop = segment_dir / "figure-01-chart.png"
        Image.new("RGB", (400, 300), "white").save(source)
        Image.new("RGB", (200, 120), "white").save(crop)
        segmentation = {
            "regions": [{
                "id": "chart", "kind": "chart", "title": "Figure 1 Benefits",
                "pixel_box": [0, 0, 200, 120], "image": crop.name,
            }],
        }
        first = "<html><body>first</body></html>"
        second = "<html><body>second</body></html>"
        reviews = iter([
            {"verdict": "mismatch", "errors": [
                {"category": "layout", "source_evidence": "a",
                 "html_evidence": "b", "correction": "c"},
                {"category": "layout", "source_evidence": "d",
                 "html_evidence": "e", "correction": "f"},
            ]},
            {"verdict": "mismatch", "errors": [
                {"category": "layout", "source_evidence": "g",
                 "html_evidence": "h", "correction": "i"},
            ]},
        ])
        corrections = iter([second, first])

        def render(_html, output):
            Image.new("RGB", (200, 120), "white").save(output)

        with patch(
            "crawl_dir.src.pipeline.scanned_ingestion.generate_initial_html_with_claude",
            return_value=first,
        ), patch(
            "crawl_dir.src.pipeline.scanned_ingestion._render_html", side_effect=render,
        ), patch(
            "crawl_dir.src.pipeline.scanned_ingestion.review_chart_html_with_claude",
            side_effect=lambda *_args: next(reviews),
        ), patch(
            "crawl_dir.src.pipeline.scanned_ingestion.correct_with_claude",
            side_effect=lambda *_args: next(corrections),
        ), patch(
            "crawl_dir.src.pipeline.figure_segmentation._assemble_page_html",
            return_value="<html><body>assembled page</body></html>",
        ):
            generate_page_html_with_corrected_figures(
                source, segmentation, segment_dir, "test-model"
            )

        batch = json.loads((segment_dir / "batch.json").read_text())
        figure = batch["figures"][0]
        self.assertEqual(len(figure["iterations"]), 2)
        self.assertEqual(figure["cycle_detected"]["repeats_iteration"], 1)
        self.assertEqual(figure["selected_iteration"], 2)
        self.assertEqual((segment_dir / "figure-01/final.html").read_text(), second)

    def test_detects_numbered_figure_pages_for_hybrid_visual_extraction(self):
        path = Path(tempfile.mkdtemp()) / "figures.pdf"
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "Narrative introduction")
        document.new_page().insert_text((72, 72), "Figure 1 Employee benefit interest")
        document.new_page().insert_text((72, 72), "Appendix")
        document.save(path)
        document.close()

        self.assertEqual(detect_visual_figure_pages(path), [2])

    def test_page_split_cache_is_reused_by_later_runs(self):
        root = Path(tempfile.mkdtemp())
        source = root / "source.pdf"
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "Page one")
        document.new_page().insert_text((72, 72), "Page two")
        document.save(source)
        document.close()
        cache_root = root / "cache" / "page-splits"

        first = _split_pages(source, root / "run-1" / "pages", cache_root=cache_root)
        second = _split_pages(source, root / "run-2" / "pages", cache_root=cache_root)

        self.assertFalse(first[0]["split_cache_hit"])
        self.assertTrue(second[0]["split_cache_hit"])
        self.assertEqual(len(first), 2)
        self.assertEqual(first[0]["split_cache_key"], second[0]["split_cache_key"])
        self.assertEqual(
            (root / "run-1/pages/page-001/source.pdf").stat().st_ino,
            (root / "run-2/pages/page-001/source.pdf").stat().st_ino,
        )

    def test_research_family_resolves_canonical_pdf(self):
        root = Path(tempfile.mkdtemp())
        source = root / "raw" / "research" / "report.pdf"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"%PDF-1.7\n")

        self.assertEqual(
            resolve_raw_document(root, "research", "report.pdf"),
            source.resolve(),
        )

    def test_detects_only_image_only_pages(self):
        path = Path(tempfile.mkdtemp()) / "mixed.pdf"
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "embedded text")
        document.new_page()
        document.save(path)
        document.close()
        self.assertEqual(image_only_pages(path), [2])

    def test_verified_html_converts_table_and_heading(self):
        markdown = html_to_markdown(
            "<html><body><h1>Policy</h1><p>Covered service.</p>"
            "<table><tr><th>Code</th><th>Name</th></tr>"
            "<tr><td>J1234</td><td>Drug</td></tr></table></body></html>"
        )
        self.assertIn("# Policy", markdown)
        self.assertIn("Covered service.", markdown)
        self.assertIn("| Code | Name |", markdown)
        self.assertIn("| J1234 | Drug |", markdown)

    def test_chunk_builder_preserves_section_headings(self):
        chunks = _raw_chunks([
            (1, "# Bill of Lading\n\nHeader fields\n\n#### SHIPPER\n\nFrutas del Sol")
        ], {1: []})

        self.assertEqual([chunk["headings"] for chunk in chunks], [
            ["Bill of Lading"], ["SHIPPER"],
        ])

    def test_public_pdf_download_requires_confirmation(self):
        with patch("crawl_dir.src.ingestion_mcp.download_one") as download:
            result = download_public_pdf("geha-coverage-policy-datroway.pdf", confirm=False)
        download.assert_not_called()
        self.assertEqual(result["status"], "approval_required")
        self.assertTrue(result["url"].startswith("https://www.geha.com/"))
        self.assertTrue(result["destination"].endswith(
            "coverage-policies/geha-coverage-policy-datroway.pdf"))

    def test_public_pdf_listing_filters_all_manifest_documents(self):
        self.assertEqual(list_public_pdfs()["count"], 54)
        result = list_public_pdfs(query="datroway", family="coverage-policies")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["documents"][0]["title"], "Datroway")

    def test_native_visual_figure_tool_previews_ey_routing_before_model_calls(self):
        source = Path(tempfile.mkdtemp()) / "ey-report.pdf"
        source.write_bytes(b"%PDF-1.7\n")
        with patch("crawl_dir.src.ingestion_mcp.resolve_raw_document",
                   return_value=source), \
             patch("crawl_dir.src.ingestion_mcp.image_only_pages", return_value=[]), \
             patch("crawl_dir.src.ingestion_mcp.pdf_page_count", return_value=29), \
             patch("crawl_dir.src.ingestion_mcp.detect_visual_figure_pages",
                   return_value=[4, 5, 24]), \
             patch("crawl_dir.src.ingestion_mcp.process_scanned_document") as process:
            result = ingest_native_pdf_with_visual_figures(
                family="research",
                document="ey-report.pdf",
                document_version="2025",
                data_classification="public",
                plan_year=2025,
                confirm=False,
            )

        process.assert_not_called()
        self.assertEqual(result["status"], "approval_required")
        self.assertEqual(result["page_count"], 29)
        self.assertEqual(result["visual_figure_pages"], [4, 5, 24])
        self.assertIn("Docling native structure", result["routing"])

    def test_image_only_page_initial_candidate_comes_from_vision_model(self):
        source = Path(tempfile.mkdtemp()) / "source.png"
        Image.new("RGB", (40, 40), "white").save(source)
        calls: list[dict] = []
        fake = _fake_anthropic(
            "```html\n<html><body><h1>Datroway</h1></body></html>\n```", calls)

        with patch.dict("sys.modules", {"anthropic": fake}):
            candidate = generate_initial_html_with_claude(source, "test-vision-model")

        self.assertEqual(candidate, "<html><body><h1>Datroway</h1></body></html>")
        self.assertEqual(calls[0]["model"], "test-vision-model")
        self.assertEqual(calls[0]["fallbacks"], "default")
        content = calls[0]["messages"][0]["content"]
        self.assertEqual(content[1]["type"], "image")
        self.assertEqual(content[1]["source"]["media_type"], "image/png")

    def test_external_resources_are_removed_without_losing_semantic_text(self):
        unsafe = (
            "<html><head><link rel='stylesheet' href='https://example.com/a.css'></head>"
            "<body><a href='https://example.com/policy'>Policy</a>"
            "<img src='https://example.com/logo.png' alt='External logo'>"
            "<p>Covered service</p></body></html>"
        )
        with self.assertRaises(ExternalResourceHtmlError):
            from .pipeline.scanned_ingestion import _clean_html
            _clean_html(unsafe)

        cleaned, removed = _sanitize_external_resources(unsafe)

        self.assertNotIn("https://", cleaned)
        self.assertNotIn("<img", cleaned)
        self.assertNotIn("<link", cleaned)
        self.assertNotIn("<a", cleaned)
        self.assertIn("Policy", cleaned)
        self.assertIn("Covered service", cleaned)
        self.assertEqual(len(removed), 3)

    def test_repeated_external_resource_signature_stops_correction_oscillation(self):
        root = Path(tempfile.mkdtemp())
        raw = root / "raw" / "coverage-policies"
        raw.mkdir(parents=True)
        source = raw / "scanned.pdf"
        document = pymupdf.open()
        document.new_page()
        document.save(source)
        document.close()
        safe = "<html><body><p>Printed policy URL</p></body></html>"
        unsafe = (
            "<html><body><a href='https://example.com/policy'>"
            "https://example.com/policy</a></body></html>"
        )
        correction_calls = []
        events = []

        def render_source(_source, output, _dpi):
            Image.new("RGB", (800, 1000), "white").save(output)
            return output

        def render_html(_source, output):
            Image.new("RGB", (800, 1000), "white").save(output)
            return output

        def corrector(*_args):
            correction_calls.append(True)
            raise ExternalResourceHtmlError(unsafe)

        with patch("crawl_dir.src.pipeline.scanned_ingestion._render_html", render_html):
            run = process_scanned_document(
                root=root, family="coverage-policies", document="scanned.pdf",
                document_version="test-v1", requested_run_id="oscillation-run",
                initial_generator=lambda _image, _model: safe,
                source_renderer=render_source,
                reviewer=lambda *_args: {"verdict": "mismatch", "errors": [{
                    "category": "wrong_text", "source_evidence": "A",
                    "html_evidence": "B", "correction": "Use A",
                }]},
                corrector=corrector, max_corrections=6, event_sink=events.append,
            )

        final_html = (run / "pages" / "page-001" / "final.html").read_text()
        self.assertEqual(len(correction_calls), 2)
        self.assertNotIn("<a", final_html)
        self.assertNotIn("href", final_html)
        self.assertEqual(
            len([event for event in events
                 if event["type"] == "external_resource_recurrence_stopped"]),
            1,
        )

    def test_page_segmentation_saves_normalized_boxes_crops_and_overlay(self):
        directory = Path(tempfile.mkdtemp())
        source = directory / "source.png"
        Image.new("RGB", (1000, 500), "white").save(source)
        payload = {
            "page_type": "dense_form",
            "segmentation_recommended": True,
            "reason": "Ruled form with independent sections.",
            "regions": [
                {"id": "header", "label": "Header", "kind": "header",
                 "reading_order": 1, "x1": 0, "y1": 0, "x2": 1000, "y2": 200},
                {"id": "cargo-grid", "label": "Cargo grid", "kind": "table",
                 "reading_order": 2, "x1": 0, "y1": 200, "x2": 1000, "y2": 1000},
            ],
        }

        calls: list[dict] = []
        with patch.dict("sys.modules", {"anthropic": _fake_anthropic(json.dumps(payload), calls)}):
            result = segment_page_with_claude(source, directory / "segments", "test-model")

        schema = calls[0]["output_config"]["format"]["schema"]
        self.assertNotIn("minimum", json.dumps(schema))

        self.assertEqual(len(result["regions"]), 2)
        self.assertEqual(result["regions"][0]["pixel_box"], [0, 0, 1000, 100])
        self.assertTrue((directory / "segments" / "regions.json").is_file())
        self.assertTrue((directory / "segments" / "regions-overlay.png").is_file())
        self.assertTrue((directory / "segments" / "region-02-cargo-grid.png").is_file())

    def test_image_only_document_finalizes_tables_from_verified_html(self):
        root = Path(tempfile.mkdtemp())
        raw = root / "raw" / "forms"
        raw.mkdir(parents=True)
        source = raw / "bill.pdf"
        document = pymupdf.open()
        document.new_page()
        document.save(source)
        document.close()
        html = (
            "<html><body><h1>Bill of Lading</h1>"
            "<table><tr><th>Container</th><th>Packages</th></tr>"
            "<tr><td>MRDN4455667</td><td>20</td></tr></table>"
            "<p>Freight collect and shipment details verified from the source page.</p>"
            "</body></html>"
        )

        def render_source(_source, output, _dpi):
            Image.new("RGB", (800, 1000), "white").save(output)
            return output

        def render_html(_source, output):
            Image.new("RGB", (800, 1000), "white").save(output)
            return output

        with patch("crawl_dir.src.pipeline.scanned_ingestion._render_html", render_html):
            run = process_scanned_document(
                root=root, family="forms", document="bill.pdf",
                document_version="test-v1", requested_run_id="test-run",
                initial_generator=lambda _image, _model: html,
                source_renderer=render_source,
                reviewer=lambda *_args: {"verdict": "match", "errors": []},
                max_corrections=0,
            )

        qc = json.loads((run / "qc-report.json").read_text())
        findings = json.loads(
            (run / "iterations" / "iteration-001" / "findings.json").read_text()
        )
        table = json.loads((run / "candidate" / "tables" / "table-001.json").read_text())
        self.assertEqual(qc["table_count"], 1)
        self.assertEqual(findings["table_extraction"]["strategy"], "verified_html")
        self.assertEqual(table["extraction_source"], "visually_verified_html")
        self.assertEqual(table["rows"][0]["Container"], "MRDN4455667")

    def test_mixed_document_routes_native_extraction_only_to_native_page(self):
        root = Path(tempfile.mkdtemp())
        raw = root / "raw" / "coverage-policies"
        raw.mkdir(parents=True)
        source = raw / "mixed.pdf"
        document = pymupdf.open()
        document.new_page()
        document.new_page().insert_text((72, 72), "Embedded policy revision history text")
        document.save(source)
        document.close()
        html = (
            "<html><body><h1>Scanned benefit table</h1>"
            "<table><tr><th>Code</th><th>Description</th></tr>"
            "<tr><td>J9011</td><td>Datroway injection benefit code</td></tr></table>"
            "</body></html>"
        )

        def render_source(_source, output, _dpi):
            Image.new("RGB", (800, 1000), "white").save(output)
            return output

        def render_html(_source, output):
            Image.new("RGB", (800, 1000), "white").save(output)
            return output

        native_calls = []

        def native_tables(pdf_path, _fragments, _tables, **kwargs):
            with pymupdf.open(pdf_path) as page_pdf:
                native_calls.append({
                    "pages": page_pdf.page_count,
                    "text": page_pdf[0].get_text().strip(),
                    "source_page_map": kwargs["source_page_map"],
                })
            return [], {"status": "ok", "outputs": []}

        with (
            patch("crawl_dir.src.pipeline.scanned_ingestion._render_html", render_html),
            patch("crawl_dir.src.pipeline.scanned_ingestion.extract_logical_tables", native_tables),
        ):
            run = process_scanned_document(
                root=root, family="coverage-policies", document="mixed.pdf",
                document_version="test-v1", requested_run_id="mixed-run",
                initial_generator=lambda _image, _model: html,
                source_renderer=render_source,
                reviewer=lambda *_args: {"verdict": "match", "errors": []},
                max_corrections=0,
            )

        self.assertEqual(len(native_calls), 1)
        self.assertEqual(native_calls[0]["pages"], 1)
        self.assertIn("Embedded policy", native_calls[0]["text"])
        self.assertEqual(native_calls[0]["source_page_map"], {1: 2})
        self.assertTrue((run / "pages" / "page-002" / "final.html").is_file())
        findings = json.loads(
            (run / "iterations" / "iteration-001" / "findings.json").read_text()
        )
        self.assertEqual(findings["table_extraction"]["strategy"], "hybrid")
        self.assertEqual(findings["table_extraction"]["verified_html"]["table_count"], 1)

    def test_native_export_converts_external_links_to_text_and_traces_tool(self):
        root = Path(tempfile.mkdtemp())
        raw = root / "raw" / "coverage-policies"
        raw.mkdir(parents=True)
        source = raw / "native-links.pdf"
        document = pymupdf.open()
        document.new_page().insert_text((72, 72), "Native policy references")
        document.save(source)
        document.close()
        unsafe = (
            '<!doctype html><html><body><p>Reference: '
            '<a href="https://example.com/policy">Policy citation '
            'https://example.com/policy</a></p></body></html>'
        )
        events = []

        with (
            patch(
                "crawl_dir.src.pipeline.scanned_ingestion._native_page_exports",
                side_effect=ExternalResourceHtmlError(unsafe),
            ),
            patch(
                "crawl_dir.src.pipeline.scanned_ingestion.extract_logical_tables",
                return_value=([], {"status": "ok", "outputs": []}),
            ),
        ):
            run = process_scanned_document(
                root=root,
                family="coverage-policies",
                document="native-links.pdf",
                document_version="test-v1",
                requested_run_id="native-link-run",
                max_corrections=0,
                event_sink=events.append,
            )

        final_html = (run / "pages" / "page-001" / "final.html").read_text()
        self.assertNotIn("<a", final_html)
        self.assertNotIn("href=", final_html)
        self.assertIn("Policy citation https://example.com/policy", final_html)
        tool_events = [
            event for event in events
            if event.get("type") == "tool_selected"
            and event.get("tool") == "sanitize_external_links_to_text"
        ]
        self.assertEqual(len(tool_events), 1)
        sanitized = [
            event for event in events
            if event.get("type") == "external_resources_sanitized"
        ]
        self.assertEqual(sanitized[0]["mode"], "links_to_plain_text")
        self.assertEqual(sanitized[0]["removed_count"], 1)
        native_ready = [event for event in events if event.get("type") == "native_page_ready"]
        self.assertEqual(len(native_ready), 1)
        self.assertEqual(native_ready[0]["mode"], "native")
        self.assertEqual(native_ready[0]["tool_id"], "native_pdf_text_structure")

if __name__ == "__main__":
    unittest.main()
