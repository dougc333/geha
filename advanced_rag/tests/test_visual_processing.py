from __future__ import annotations

import json
import unittest
from io import BytesIO

import pandas as pd
from PIL import Image

from aws_data_workflow.visual_processing import (
    extract_split_pdf_markdown,
    extract_page_artifacts,
    figure_markdown,
    make_nous_deepseek_markdown_extractor,
    make_nous_deepseek_vision_describer,
    validate_figure_spec,
    validate_table_frame,
)


class VisualProcessingTests(unittest.TestCase):
    def test_valid_table_has_no_structural_issues(self) -> None:
        frame = pd.DataFrame([["Small", "57%"], ["Large", "67%"]], columns=["Group", "More"])
        self.assertEqual(validate_table_frame(frame), [])

    def test_sparse_table_requires_review(self) -> None:
        frame = pd.DataFrame([[None], [None]], columns=[""])
        issues = validate_table_frame(frame)
        self.assertIn("table_has_fewer_than_two_columns", issues)
        self.assertIn("table_headers_are_empty", issues)

    def test_default_numeric_table_headers_require_review(self) -> None:
        frame = pd.DataFrame([["Question", "Answer"]])
        self.assertIn("table_headers_are_default", validate_table_frame(frame))

    def test_year_headers_are_not_treated_as_pandas_defaults(self) -> None:
        frame = pd.DataFrame([[1, 2, 3]], columns=["2022", "2023", "2024"])
        self.assertNotIn("table_headers_are_default", validate_table_frame(frame))

    def test_figure_spec_preserves_native_numbers_and_renders_table(self) -> None:
        spec = {
            "title": "Benefits",
            "figure_type": "chart",
            "summary": "More benefits by company size.",
            "series": [{"name": "More", "points": [{"label": "Small", "value": "57%"}]}],
            "notes": [],
        }
        self.assertEqual(validate_figure_spec(spec, "Small 57%"), [])
        markdown = figure_markdown(spec)
        self.assertIn("| More | Small | 57% |", markdown)

    def test_nous_adapter_sends_png_and_parses_structured_result(self) -> None:
        captured = {}
        response_body = {
            "choices": [{"message": {"content": json.dumps({
                "title": "Benefits",
                "figure_type": "chart",
                "summary": "More benefits by company size.",
                "legend": ["More"],
                "series": [],
                "notes": [],
                "literal_text": ["57%"],
            })}}]
        }

        class FakeResponse(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse(json.dumps(response_body).encode("utf-8"))

        describe = make_nous_deepseek_vision_describer(
            "secret-test-key",
            urlopen=fake_urlopen,
        )
        result = describe(b"png-bytes", "Figure 1", "57%")
        payload = json.loads(captured["request"].data)
        image_url = payload["messages"][0]["content"][1]["image_url"]["url"]

        self.assertEqual(payload["model"], "deepseek/deepseek-v4.1-flash-1017")
        self.assertTrue(image_url.startswith("data:image/png;base64,"))
        self.assertEqual(captured["timeout"], 120)
        self.assertEqual(result["title"], "Benefits")

    def test_nous_page_extractor_returns_markdown(self) -> None:
        captured = {}
        response_body = {
            "choices": [{"message": {"content": "# Page title\n\n| A | B |\n|---|---|\n| 1 | 2 |"}}]
        }

        class FakeResponse(BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                self.close()

        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data)
            captured["timeout"] = timeout
            return FakeResponse(json.dumps(response_body).encode("utf-8"))

        extract = make_nous_deepseek_markdown_extractor(
            "secret-test-key",
            urlopen=fake_urlopen,
        )
        markdown = extract(b"png-bytes", 2, "draft")
        self.assertIn("# Page title", markdown)
        self.assertEqual(captured["timeout"], 180)
        self.assertEqual(captured["payload"]["messages"][0]["content"][0]["type"], "text")

    def test_page_artifacts_save_source_and_both_markdown_versions(self) -> None:
        class ImageReference:
            pil_image = Image.new("RGB", (20, 20), "white")

        class Page:
            image = ImageReference()

        class Document:
            pages = {1: Page()}

            @staticmethod
            def export_to_markdown(*, page_no):
                return f"Docling page {page_no}"

        with self.subTest("page artifact manifest"):
            import tempfile
            from pathlib import Path

            with tempfile.TemporaryDirectory() as temporary:
                manifest = extract_page_artifacts(
                    Document(),
                    Path(temporary),
                    extract_markdown=lambda _image, page, _draft: f"# DeepSeek page {page}\n",
                )
                record = manifest["pages"][0]
                self.assertEqual(record["markdown_source"], "deepseek")
                self.assertTrue((Path(temporary) / record["source_image"]).is_file())
                self.assertTrue((Path(temporary) / record["deepseek_markdown"]).is_file())

    def test_page_artifacts_accept_llamaparse_page_markdown(self) -> None:
        class Page:
            image = None

        class Document:
            pages = {1: Page()}

            @staticmethod
            def export_to_markdown(*, page_no):
                return f"Docling page {page_no}"

        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            manifest = extract_page_artifacts(
                Document(),
                Path(temporary),
                markdown_engine="llamaparse",
                page_markdown_overrides={1: "# LlamaParse page 1"},
            )
            record = manifest["pages"][0]
            self.assertEqual(record["markdown_source"], "llamaparse")
            self.assertIsNone(record["deepseek_markdown"])
            self.assertTrue((Path(temporary) / record["llamaparse_markdown"]).is_file())
            self.assertEqual(manifest["summary"]["ocr_pages"], 1)

    def test_extracts_each_split_page_pdf_independently(self) -> None:
        import pymupdf
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            pages_dir = Path(temporary)
            for number, text in ((1, "First page"), (2, "Second page")):
                path = pages_dir / f"page-{number:03d}" / "source.pdf"
                path.parent.mkdir(parents=True)
                document = pymupdf.open()
                page = document.new_page()
                page.insert_text((72, 72), text)
                document.save(path)
                document.close()
            calls = []

            def extract(image_bytes, page_number, draft):
                calls.append((page_number, draft, image_bytes[:8]))
                return f"# Extracted page {page_number}\n"

            output = extract_split_pdf_markdown(pages_dir, extract)
            self.assertEqual(sorted(output), [1, 2])
            self.assertEqual([call[0] for call in calls], [1, 2])
            self.assertIn("First page", calls[0][1])
            self.assertEqual(calls[0][2], b"\x89PNG\r\n\x1a\n")

    def test_split_page_failure_is_logged_and_later_pages_continue(self) -> None:
        import pymupdf
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            pages_dir = Path(temporary)
            for number in (1, 2, 3):
                path = pages_dir / f"page-{number:03d}" / "source.pdf"
                path.parent.mkdir(parents=True)
                document = pymupdf.open()
                document.new_page().insert_text((72, 72), f"Page {number}")
                document.save(path)
                document.close()
            errors = []

            def extract(_image_bytes, page_number, _draft):
                if page_number == 2:
                    raise ValueError("empty response")
                return f"# OCR page {page_number}\n"

            output = extract_split_pdf_markdown(
                pages_dir,
                extract,
                output_filename="deepseek.md",
                on_error=lambda page, error: errors.append((page, str(error))),
            )
            self.assertEqual(sorted(output), [1, 3])
            self.assertEqual(errors, [(2, "empty response")])
            self.assertTrue((pages_dir / "page-001" / "deepseek.md").is_file())
            self.assertFalse((pages_dir / "page-002" / "deepseek.md").exists())

    def test_split_page_extraction_reuses_checkpoint(self) -> None:
        import pymupdf
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            pages_dir = Path(temporary)
            page_dir = pages_dir / "page-001"
            page_dir.mkdir(parents=True)
            document = pymupdf.open()
            document.new_page().insert_text((72, 72), "Page 1")
            document.save(page_dir / "source.pdf")
            document.close()
            (page_dir / "deepseek.md").write_text("# Cached page\n", encoding="utf-8")

            output = extract_split_pdf_markdown(
                pages_dir,
                lambda *_args: self.fail("checkpointed page should not call extractor"),
                output_filename="deepseek.md",
            )
            self.assertEqual(output, {1: "# Cached page\n"})


if __name__ == "__main__":
    unittest.main()
