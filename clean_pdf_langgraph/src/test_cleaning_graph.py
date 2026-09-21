"""Small deterministic checks for the deliberately naive first pass."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .cleaning_graph import PDF_DIR, compare_node, preflight_outputs, run_one
from .paths import FIRST_PASS_DIR
from .extractors import naive_pdf_extract, render_pdf_pages


class FirstPassTests(unittest.TestCase):
    def test_pdfplumber_keeps_numeric_dataframe_headers(self) -> None:
        sample = PDF_DIR / "geha-coverage-policy-ziihera.pdf"
        with tempfile.TemporaryDirectory() as temporary:
            result = naive_pdf_extract(sample, Path(temporary))
            self.assertGreater(result["page_count"], 0)
            self.assertGreater(len(result["pdfplumber_tables"]), 0)
            self.assertTrue(result["pdfplumber_tables"][0]["markdown"].startswith("| 0 "))

    def test_page_rendering_uses_installed_pdf_library(self) -> None:
        sample = PDF_DIR / "geha-coverage-policy-ziihera.pdf"
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            images = render_pdf_pages(sample, output_dir, page_count=3)
            self.assertEqual(len(images), 3)
            self.assertTrue(all(Path(image).read_bytes().startswith(b"\x89PNG") for image in images))
            with self.assertRaises(FileExistsError):
                render_pdf_pages(sample, output_dir, page_count=3)

    def test_existing_outputs_fail_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "example.pdf"
            (source.parent / "example.docling.md").write_text("old")
            with self.assertRaises(FileExistsError):
                preflight_outputs(source, source.parent)

    def test_source_and_review_outputs_are_in_separate_directories(self) -> None:
        self.assertEqual(PDF_DIR.name, "coverage-policies")
        self.assertTrue((PDF_DIR / "geha-coverage-policy-ziihera.pdf").is_file())
        self.assertFalse(FIRST_PASS_DIR.is_relative_to(PDF_DIR))

    def test_run_one_reads_shared_pdf_and_writes_locally(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch("src.cleaning_graph.FIRST_PASS_DIR", Path(temporary)), \
                    patch("src.cleaning_graph.build_graph") as build_graph:
                build_graph.return_value.invoke.return_value = {"status": "pending"}
                run_one("geha-coverage-policy-ziihera.pdf", use_vision=False)
                state = build_graph.return_value.invoke.call_args.args[0]
            self.assertEqual(Path(state["pdf_path"]).parent, PDF_DIR)
            self.assertEqual(Path(state["output_dir"]).parent, Path(temporary))

    def test_empty_extraction_cannot_pass_review(self) -> None:
        result = compare_node({
            "pdfplumber_tables": [], "docling_tables": [], "docling_chunks": [],
            "use_vision": False, "page_images": [], "vision_model": "gpt-4o",
        })
        self.assertEqual(result["status"], "needs_human_review")
        self.assertEqual(result["reviewed_units"], 0)
        self.assertEqual(len(result["issues"]), 1)

    def test_vision_failure_is_reported_once_without_error_body(self) -> None:
        table = {"extractor": "pdfplumber", "number": 1, "page": 1, "markdown": "| 0 |"}
        with patch("src.cleaning_graph.images_for_pages", return_value=[Path("page.png")]), \
                patch("src.cleaning_graph.compare_unit", side_effect=ValueError("secret key")) as compare:
            result = compare_node({
                "pdfplumber_tables": [table, {**table, "number": 2}],
                "docling_tables": [], "docling_chunks": [], "use_vision": True,
                "page_images": ["page.png"], "vision_model": "gpt-4o",
            })
        self.assertEqual(compare.call_count, 1)
        self.assertEqual(result["uncertain_units"], 2)
        self.assertEqual(len(result["issues"]), 1)
        self.assertNotIn("secret key", result["issues"][0]["explanation"])


if __name__ == "__main__":
    unittest.main()
