from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from crawl_dir.src.pipeline.artifact_io import sha256_file
from crawl_dir.src.process_visual_pages import derive_visual_run


class ProcessVisualPagesTests(unittest.TestCase):
    def _base_run(self, root: Path) -> Path:
        family = "research"
        document_id = "nested--study"
        run_id = "base-run"
        source = root / "raw" / family / "nested" / "study.pdf"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"%PDF-test-source")
        run = root / "runs" / family / document_id / run_id
        (run / "pages").mkdir(parents=True)
        for page in range(1, 5):
            page_dir = run / "pages" / f"page-{page:03d}"
            page_dir.mkdir()
            (page_dir / "source.pdf").write_bytes(f"page-{page}".encode())
            (page_dir / "page-manifest.json").write_text(json.dumps({
                "page": page,
                "page_type": "table" if page in {2, 3} else "narrative",
            }))
        (run / "run-manifest.json").write_text(json.dumps({
            "schema_version": 1,
            "run_id": run_id,
            "family": family,
            "document_id": document_id,
            "document_version": "2026",
            "plan_year": None,
            "source": "raw/research/nested/study.pdf",
            "source_sha256": sha256_file(source),
        }))
        (run / "qc-report.json").write_text(json.dumps({"page_count": 4}))
        return run

    def test_derives_new_run_and_records_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = self._base_run(root)
            output = base.parent / "visual-run"
            calls = []

            def fake_process(**kwargs):
                calls.append(kwargs)
                (output / "candidate").mkdir(parents=True)
                (output / "pages").mkdir()
                for page in range(1, 5):
                    page_dir = output / "pages" / f"page-{page:03d}"
                    page_dir.mkdir()
                    (page_dir / "page-manifest.json").write_text(json.dumps({
                        "page": page,
                        "tool_id": "visual" if page in {2, 3} else "native",
                    }))
                (output / "run-manifest.json").write_text(json.dumps({
                    "run_id": "visual-run",
                    "pipeline": "scanned-page-html-correction",
                }))
                return output

            page_report = {
                "pages": [
                    {
                        "page": page,
                        "page_type": "table" if page in {2, 3} else "narrative",
                        "content_types": ["text", "table"] if page in {2, 3} else ["text"],
                        "table_detected": page in {2, 3},
                        "figure_detected": False,
                        "scanned_page": False,
                        "visual_review_recommended": False,
                        "signals": {},
                    }
                    for page in range(1, 5)
                ]
            }

            with patch(
                "crawl_dir.src.process_visual_pages.process_scanned_document",
                side_effect=fake_process,
            ), patch(
                "crawl_dir.src.process_visual_pages.classify_pdf_pages",
                return_value=page_report,
            ):
                result = derive_visual_run(
                    base_run=base,
                    pages=[3, 2, 3],
                    output_run="visual-run",
                    provider="anthropic",
                )

            self.assertEqual(result, output.resolve())
            self.assertEqual(calls[0]["additional_visual_pages"], [2, 3])
            self.assertEqual(calls[0]["document"], "nested/study.pdf")
            manifest = json.loads((output / "run-manifest.json").read_text())
            self.assertEqual(manifest["pipeline"], "derived-visual-correction")
            self.assertEqual(manifest["parent_run_id"], "base-run")
            self.assertEqual(manifest["page_content"], "candidate/page-content.json")
            self.assertEqual(manifest["visual_reconstruction_pages"], [2, 3])
            self.assertEqual(manifest["derivation"]["provider"], "anthropic")
            page_two = json.loads(
                (output / "pages/page-002/page-manifest.json").read_text()
            )
            self.assertEqual(page_two["page_type"], "table")
            self.assertTrue(page_two["visual_correction_applied"])
            page_one = json.loads(
                (output / "pages/page-001/page-manifest.json").read_text()
            )
            self.assertFalse(page_one["visual_correction_applied"])

    def test_rejects_page_outside_parent_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = self._base_run(Path(directory))
            with self.assertRaisesRegex(ValueError, "outside 1..4"):
                derive_visual_run(
                    base_run=base,
                    pages=[5],
                    output_run="visual-run",
                )

    def test_rejects_output_path_instead_of_run_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = self._base_run(Path(directory))
            with self.assertRaisesRegex(ValueError, "simple run name"):
                derive_visual_run(
                    base_run=base,
                    pages=[2],
                    output_run="../visual-run",
                )

    def test_non_anthropic_provider_requires_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = self._base_run(Path(directory))
            with self.assertRaisesRegex(ValueError, "--model is required"):
                derive_visual_run(
                    base_run=base,
                    pages=[2],
                    output_run="visual-run",
                    provider="nous",
                )


if __name__ == "__main__":
    unittest.main()
