from __future__ import annotations

import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from .backend import DEFAULT_DOCUMENT, DemoRun, LayoutToolRouter, documents
from crawl_dir.src.pipeline.figure_segmentation import segment_charts_and_figures
from .bill_of_lading_workflow import (
    GRAPH_PROGRAM,
    SEGMENT_MAX_ITERATIONS,
    _deterministic_page_html,
    _discard_css_findings,
    _failed_cells,
    review_bill_of_lading,
    segment_bill_of_lading_with_schema,
    verify_segment_html,
)


class DemoBackendTests(unittest.TestCase):
    def test_css_findings_are_ignored_deterministically(self):
        text, ignored = _discard_css_findings([
            "The heading is not bold and has the wrong border.",
            "The value BL232472785 is missing.",
        ])
        self.assertEqual(text, ["The value BL232472785 is missing."])
        self.assertEqual(len(ignored), 1)

        text, ignored = _discard_css_findings(
            ["Missing text: NUMBER OF ORIGINAL B/L'S: THREE (3)"],
            "<div>NUMBER OF ORIGINAL B/L'S: THREE (3)</div>",
            {"legal": "NUMBER OF ORIGINAL B/L'S: THREE (3)"},
        )
        self.assertEqual(text, [])
        self.assertEqual(len(ignored), 1)

    def test_document_catalog_contains_all_demo_documents(self):
        response = asyncio.run(documents(None))
        payload = json.loads(response.text)
        by_title = {item["title"]: item for item in payload["documents"]}

        self.assertEqual(payload["default"], DEFAULT_DOCUMENT)
        self.assertEqual(by_title["Datroway"]["image_only_pages"], [1, 2, 3])
        self.assertEqual(by_title["Elrexfio"]["image_only_pages"], [1, 2])
        self.assertEqual(by_title["Bendamustine"]["page_count"], 3)
        self.assertEqual(by_title["Bendamustine"]["image_only_pages"], [])
        self.assertEqual(by_title["EY workforce benefits"]["page_count"], 29)
        self.assertEqual(by_title["EY workforce benefits"]["image_only_pages"], [])
        self.assertEqual(
            by_title["EY workforce benefits"]["visual_reconstruction_pages"],
            list(range(1, 30)),
        )

    def test_router_selects_named_cell_ocr_skill(self):
        run = DemoRun("test-run")
        segmenter, generator = LayoutToolRouter(
            run, "dense_form", "bill_of_lading_schema_graph"
        ).choose()

        self.assertIs(segmenter, segment_bill_of_lading_with_schema)
        self.assertIsNotNone(generator)
        self.assertEqual(run.events[-1]["tool"], "bill_of_lading_named_cell_ocr")
        considered = run.events[0]["tools"]
        specialist = next(
            tool for tool in considered if tool["id"] == "bill_of_lading_named_cell_ocr"
        )
        self.assertTrue(specialist["available"])
        self.assertEqual(Path(specialist["program"]), GRAPH_PROGRAM)
        self.assertEqual(len(considered), 4)
        self.assertNotIn("bill_of_lading_schema_graph", {tool["id"] for tool in considered})

    def test_router_selects_native_pdf_text_for_ey_report(self):
        run = DemoRun("test-native-run")

        segmenter, generator = LayoutToolRouter(run, "native_text_report").choose()

        self.assertIsNone(segmenter)
        self.assertIsNone(generator)
        self.assertEqual(run.events[-1]["tool"], "native_pdf_text_structure")
        considered = run.events[0]["tools"]
        native = next(tool for tool in considered
                      if tool["id"] == "native_pdf_text_structure")
        specialist = next(tool for tool in considered
                          if tool["id"] == "bill_of_lading_named_cell_ocr")
        self.assertTrue(native["available"])
        self.assertFalse(specialist["available"])

    def test_router_selects_hybrid_visual_figures_for_ey_report(self):
        run = DemoRun("test-hybrid-run")

        segmenter, generator = LayoutToolRouter(run, "hybrid_figure_report").choose()

        self.assertIs(segmenter, segment_charts_and_figures)
        self.assertIsNotNone(generator)
        self.assertEqual(run.events[-1]["tool"], "chart_figure_crop_html_correction")
        self.assertIn("each chart/figure", run.events[-1]["reason"])
        considered = run.events[0]["tools"]
        hybrid = next(tool for tool in considered
                      if tool["id"] == "chart_figure_crop_html_correction")
        self.assertTrue(hybrid["available"])

    def test_bill_of_lading_schema_creates_eight_named_blocks(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            Image.new("RGB", (2066, 3341), "white").save(source)

            result = segment_bill_of_lading_with_schema(source, root / "segments", "unused")

            self.assertEqual(result["tool_id"], "bill_of_lading_named_cell_ocr")
            self.assertEqual(len(result["regions"]), 8)
            self.assertEqual(result["regions"][1]["label"], "Shipment parties and references")
            self.assertIn("shipper", result["regions"][1]["schema_cells"])
            self.assertTrue((root / "segments" / "regions-overlay.png").is_file())
            self.assertTrue((root / "segments" / "schema.json").is_file())
            self.assertTrue(result["regions"][1]["cells"][0]["image"].endswith("shipper.png"))
            self.assertEqual(result["schema"]["source_canvas"], {"width": 2136, "height": 3584})

    def test_review_errors_map_to_named_cells(self):
        extracted = {2: {"booking_ref": "BKG5917532", "shipper": "FRUTAS DEL SOL S.A."}}
        errors = [{
            "source_evidence": "BOOKING REF. BKG5917532",
            "html_evidence": "BKG5917532",
            "correction": "Add the BOOKING REF. label",
        }]

        self.assertEqual(_failed_cells(errors, extracted), {2: {"booking_ref"}})

    def test_bill_of_lading_review_discards_findings_that_say_content_matches(self):
        import unittest.mock

        raw = {
            "verdict": "mismatch",
            "errors": [{
                "category": "wrong_text",
                "source_evidence": "DATE OF ISSUE 2026-03-13",
                "html_evidence": "DATE OF ISSUE 2026-03-13",
                "correction": "No wrong text; matches exactly.",
            }],
        }
        with unittest.mock.patch(
            "crawl_dir.src.pipeline.scanned_ingestion.review_with_claude", return_value=raw
        ):
            result = review_bill_of_lading(Path("source"), Path("html"), "", "model")

        self.assertEqual(result["verdict"], "match")
        self.assertEqual(result["errors"], [])

    def test_deterministic_bill_of_lading_html_contains_named_cells_and_sections(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.png"
            Image.new("RGB", (2066, 3341), "white").save(source)
            segmentation = segment_bill_of_lading_with_schema(
                source, root / "segments", "unused"
            )
            extracted = {
                int(block["reading_order"]): {
                    cell["id"]: f"value for {cell['id']}" for cell in block["cells"]
                }
                for block in segmentation["regions"]
            }

            document = _deterministic_page_html(segmentation, extracted)

            self.assertIn('data-section="Shipment parties and references"', document)
            self.assertIn('data-cell="shipper"', document)
            self.assertIn("value for shipper", document)

    def test_segment_html_loop_records_every_iteration_in_batch_json(self):
        import unittest.mock

        class FakeGraph:
            def __init__(self):
                self.reviews = 0

            @staticmethod
            def openai_client():
                return object()

            @staticmethod
            def block_document(_number, _cells):
                return "<html><body><section data-cell='shipper'>value</section></body></html>"

            @staticmethod
            def render_html(_source, destination, width, height):
                Image.new("RGB", (width, height), "white").save(destination)

            def review_visual(self, **_kwargs):
                self.reviews += 1
                if self.reviews == 1:
                    return {"verdict": "mismatch", "errors": ["shipper text is wrong"]}
                return {"verdict": "match", "errors": []}

        with TemporaryDirectory() as temporary:
            segment_dir = Path(temporary)
            Image.new("RGB", (200, 100), "white").save(segment_dir / "region-01.png")
            segmentation = {
                "regions": [{
                    "reading_order": 1,
                    "label": "Header",
                    "image": "region-01.png",
                }],
                "schema": {"blocks": [{
                    "block": 1,
                    "box": {"x": 0, "y": 0, "width": 200, "height": 100},
                }]},
            }
            fake_graph = FakeGraph()
            events = []
            with (
                unittest.mock.patch(
                    "crawl_dir.demo.bill_of_lading_workflow._graph_module",
                    return_value=fake_graph,
                ),
                unittest.mock.patch(
                    "crawl_dir.demo.bill_of_lading_workflow._extract_block_cells",
                    return_value={"shipper": "value"},
                ),
            ):
                result = verify_segment_html(
                    segmentation, segment_dir, {1: {"shipper": "value"}}, "test-model",
                    event_sink=events.append,
                )

            batch = json.loads((segment_dir / "batch.json").read_text())
            self.assertEqual(result["status"], "passed")
            self.assertEqual(batch["max_iterations_per_segment"], SEGMENT_MAX_ITERATIONS)
            self.assertEqual(batch["summary"]["total_iterations"], 2)
            self.assertEqual(batch["segments"][0]["iterations"][0]["error_count"], 1)
            self.assertEqual(batch["segments"][0]["iterations"][1]["error_count"], 0)
            self.assertTrue((segment_dir / "segment-01" / "iteration-01.html").is_file())
            self.assertTrue((segment_dir / "segment-01" / "iteration-02.html").is_file())
            self.assertTrue((segment_dir / "segment-01" / "final.html").is_file())
            self.assertEqual(
                len([event for event in events if event["type"] == "html_rendered"]), 2
            )
            self.assertEqual(
                batch["segments"][0]["iterations"][0]["render_tool"]["cost_usd"], 0.0
            )

    def test_segment_html_loop_stops_after_six_total_iterations(self):
        import unittest.mock

        class AlwaysMismatchGraph:
            @staticmethod
            def openai_client():
                return object()

            @staticmethod
            def block_document(_number, _cells):
                return "<html><body><section data-cell='shipper'>value</section></body></html>"

            @staticmethod
            def render_html(_source, destination, width, height):
                Image.new("RGB", (width, height), "white").save(destination)

            @staticmethod
            def review_visual(**_kwargs):
                return {"verdict": "mismatch", "errors": ["still mismatched"]}

        with TemporaryDirectory() as temporary:
            segment_dir = Path(temporary)
            Image.new("RGB", (200, 100), "white").save(segment_dir / "region-01.png")
            segmentation = {
                "regions": [{
                    "reading_order": 1,
                    "label": "Header",
                    "image": "region-01.png",
                }],
                "schema": {"blocks": [{
                    "block": 1,
                    "box": {"x": 0, "y": 0, "width": 200, "height": 100},
                }]},
            }
            with (
                unittest.mock.patch(
                    "crawl_dir.demo.bill_of_lading_workflow._graph_module",
                    return_value=AlwaysMismatchGraph(),
                ),
                unittest.mock.patch(
                    "crawl_dir.demo.bill_of_lading_workflow._extract_block_cells",
                    return_value={"shipper": "value"},
                ),
            ):
                result = verify_segment_html(
                    segmentation, segment_dir, {1: {"shipper": "value"}}, "test-model"
                )

            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["summary"]["total_iterations"], 6)
            self.assertEqual(len(result["segments"][0]["iterations"]), 6)


if __name__ == "__main__":
    unittest.main()
