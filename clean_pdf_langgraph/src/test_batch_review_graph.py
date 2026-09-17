"""Batch graph checks without external model calls."""

from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from .batch_review_graph import report_node, resume_pdf, run_batch, run_pdf, vision_node
from .html_vision_review import compare_html_table
from .raw_table_html import combined_raw_html


def artifact(extractor: str, number: int, page: int = 1) -> dict:
    return {
        "extractor": extractor, "number": number, "page": page,
        "markdown": "| 0 | 1 |", "columns": ["0", "1"],
        "rows": [["Drug Name", "HCPCS Code"], ["Ziihera", "J9276"]],
    }


class BatchReviewTests(unittest.TestCase):
    def test_combined_html_has_all_raw_tables(self) -> None:
        source = combined_raw_html(
            "policy.pdf", "pdfplumber",
            [artifact("pdfplumber", 1), artifact("pdfplumber", 2, 2)],
        )
        self.assertEqual(source.count("<table"), 2)
        self.assertIn("<style>", source)
        self.assertIn("<th>0</th>", source)
        self.assertIn("<td>Drug Name</td>", source)
        self.assertIn('data-page="2"', source)

    def test_vision_results_are_separate_by_extractor(self) -> None:
        state = {
            "pdfplumber_tables": [artifact("pdfplumber", 1)],
            "docling_tables": [artifact("docling", 1)],
            "page_images": ["page.png"], "vision_model": "gpt-4o",
            "use_vision": True,
        }
        mismatch = ({"artifact": "pdfplumber table 1", "page": 1,
                     "kind": "numeric_header", "pdf_evidence": "Drug Name",
                     "extracted_evidence": "0", "explanation": "Wrong header"})
        with patch("src.batch_review_graph.images_for_pages", return_value=[Path("page.png")]), \
                patch("src.batch_review_graph.compare_html_table",
                      side_effect=[("mismatch", [mismatch]), ("match", [])]):
            reviews = vision_node(state)["extractor_reviews"]
        self.assertEqual(reviews["pdfplumber"]["status"], "needs_human_review")
        self.assertEqual(reviews["docling"]["status"], "passed")
        self.assertEqual(reviews["pdfplumber"]["issues"][0]["kind"], "numeric_header")

    def test_api_failure_does_not_leak_error_body_or_repeat_calls(self) -> None:
        state = {
            "pdfplumber_tables": [artifact("pdfplumber", 1)],
            "docling_tables": [artifact("docling", 1)],
            "page_images": ["page.png"], "vision_model": "gpt-4o",
            "use_vision": True,
        }
        with patch("src.batch_review_graph.images_for_pages", return_value=[Path("page.png")]), \
                patch("src.batch_review_graph.compare_html_table",
                      side_effect=ValueError("secret key")) as compare:
            reviews = vision_node(state)["extractor_reviews"]
        self.assertEqual(compare.call_count, 1)
        self.assertEqual(reviews["pdfplumber"]["counts"]["uncertain"], 1)
        self.assertEqual(reviews["docling"]["counts"]["uncertain"], 1)
        self.assertNotIn("secret key", str(reviews))

    def test_vision_request_contains_pdf_image_and_html(self) -> None:
        answer = json.dumps({"verdict": "match", "issues": []})
        with patch("src.html_vision_review._image_part", return_value={
            "type": "input_image", "image_url": "data:image/png;base64,AAAA"
        }), patch("openai.OpenAI") as client:
            client.return_value.responses.create.return_value.output_text = answer
            verdict, issues = compare_html_table(
                artifact="pdfplumber table 1", table_html="<table>raw</table>",
                pdf_images=[Path("page.png")], model="gpt-4o",
            )
        self.assertEqual((verdict, issues), ("match", []))
        kwargs = client.return_value.responses.create.call_args.kwargs
        self.assertFalse(kwargs["store"])
        content = kwargs["input"][0]["content"]
        self.assertIn("<table>raw</table>", content[0]["text"])
        self.assertEqual(content[2]["type"], "input_image")

    def test_reports_have_extractor_specific_names(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            state = {
                "pdf_path": str(path / "sample.pdf"), "output_dir": str(path),
                "source_sha256": "abc", "pdfplumber_markdown": str(path / "sample_pdfplumber.md"),
                "docling_markdown": str(path / "sample.docling.md"),
                "pdfplumber_html": str(path / "sample_pdfplumber_tables.html"),
                "docling_html": str(path / "sample_docling_tables.html"),
                "extractor_reviews": {
                    name: {"status": "needs_human_review", "table_count": 0,
                           "verdicts": [], "counts": {"match": 0, "mismatch": 0,
                                                       "uncertain": 0},
                           "issues": [{"artifact": name, "kind": "other", "page": 0,
                                       "pdf_evidence": "", "extracted_evidence": "",
                                       "explanation": "No tables"}]}
                    for name in ("pdfplumber", "docling")
                },
            }
            reports = report_node(state)["error_reports"]
            self.assertTrue(Path(reports["pdfplumber"]).name.endswith("pdfplumber_errors.md"))
            self.assertTrue(Path(reports["docling"]).name.endswith("docling_errors.md"))
            self.assertTrue(all(Path(file).is_file() for file in reports.values()))

    def test_batch_selects_all_top_level_pdfs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_dir = root / "pdfs"
            input_dir.mkdir()
            (input_dir / "b.pdf").touch()
            (input_dir / "a.pdf").touch()
            with patch("src.batch_review_graph.run_pdf") as run_pdf:
                run_pdf.return_value = {
                    "extractor_reviews": {
                        name: {"status": "passed"} for name in ("pdfplumber", "docling")
                    },
                    "pdfplumber_tables": [], "docling_tables": [],
                    "error_reports": {},
                }
                summary = run_batch(input_dir, root / "review", use_vision=False)
            self.assertEqual(run_pdf.call_count, 2)
            self.assertEqual(summary["pdf_count"], 2)
            self.assertEqual([r["pdf"] for r in summary["results"]], ["a.pdf", "b.pdf"])

    def test_human_approval_resumes_without_reextracting(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "sample.pdf"
            pdf.write_bytes(b"sample")
            output = root / "review" / "sample"

            def plumber(source, target):
                markdown = target / "sample_pdfplumber.md"
                markdown.write_text("raw", encoding="utf-8")
                return {"page_count": 1, "pdfplumber_markdown": str(markdown),
                        "pdfplumber_tables": [artifact("pdfplumber", 1)]}

            def docling(source, target):
                paths = {
                    "docling_markdown": target / "sample.docling.md",
                    "docling_chunks_markdown": target / "sample.docling_chunks.md",
                    "docling_tables_markdown": target / "sample_docling_tables.md",
                }
                for path in paths.values():
                    path.write_text("raw", encoding="utf-8")
                return {**{key: str(path) for key, path in paths.items()},
                        "docling_tables": [artifact("docling", 1)],
                        "docling_chunks": []}

            def render(source, target, page_count):
                image = target / "sample_images_1.png"
                image.write_bytes(b"image")
                return [str(image)]

            with patch("src.batch_review_graph.naive_pdf_extract", side_effect=plumber) as first, \
                    patch("src.batch_review_graph.docling_extract", side_effect=docling) as second, \
                    patch("src.batch_review_graph.render_pdf_pages", side_effect=render), \
                    patch("src.batch_review_graph.images_for_pages", return_value=[Path("page.png")]), \
                    patch("src.batch_review_graph.compare_html_table", return_value=("match", [])) as compare:
                paused = run_pdf(pdf, output, vision_model="gpt-4o-mini")
                self.assertIn("__interrupt__", paused)
                self.assertEqual(compare.call_count, 0)
                self.assertTrue(Path(paused["pdfplumber_html"]).is_file())
                self.assertTrue(Path(paused["docling_html"]).is_file())
                self.assertTrue((output / "checkpoint.sqlite").is_file())

                result = resume_pdf(output, approve=True)
                self.assertTrue(result["vision_approved"])
                self.assertEqual(compare.call_count, 2)
                self.assertEqual(first.call_count, 1)
                self.assertEqual(second.call_count, 1)
                self.assertEqual(result["extractor_reviews"]["docling"]["status"], "passed")
                self.assertTrue(Path(result["error_reports"]["docling"]).is_file())
                with self.assertRaises(ValueError):
                    resume_pdf(output, approve=True)

    def test_human_rejection_never_calls_vision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "sample.pdf"
            pdf.write_bytes(b"sample")
            output = root / "review" / "sample"
            with patch("src.batch_review_graph.naive_pdf_extract", return_value={
                "page_count": 1, "pdfplumber_markdown": "plumber.md",
                "pdfplumber_tables": [artifact("pdfplumber", 1)],
            }), patch("src.batch_review_graph.docling_extract", return_value={
                "docling_markdown": "docling.md",
                "docling_chunks_markdown": "chunks.md",
                "docling_tables_markdown": "tables.md",
                "docling_tables": [artifact("docling", 1)],
            }), patch("src.batch_review_graph.render_pdf_pages", return_value=["page.png"]), \
                    patch("src.batch_review_graph.compare_html_table") as compare:
                self.assertIn("__interrupt__", run_pdf(pdf, output))
                result = resume_pdf(output, approve=False)
                self.assertFalse(result["vision_approved"])
                compare.assert_not_called()
                self.assertIn("declined", Path(result["error_reports"]["docling"]).read_text())


if __name__ == "__main__":
    unittest.main()
