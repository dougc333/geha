"""Local tests for PDF/table image comparison request construction."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from chunking_benchmarks_RAG.ocr_pipeline.policy_visual_compare import (
    compare_with_openai,
    render_html_table_png,
)


class VisualCompareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.pdf_png = self.directory / "page.png"
        Image.new("RGB", (10, 10), "white").save(self.pdf_png)

    def test_html_renderer_includes_all_rows_and_correct_header(self):
        path = self.directory / "billing.html"
        path.write_text(
            "<html><h1>Billing codes</h1><table><thead><tr>"
            "<th>Drug Name</th><th>HCPCS Code</th></tr></thead><tbody>"
            "<tr><td>Ziihera</td><td>J9276</td></tr>"
            "<tr><td>Example</td><td>J0000</td></tr></tbody></table></html>",
            encoding="utf-8",
        )
        result = render_html_table_png(path, self.directory / "rendered.png", rows=2)
        self.assertTrue(result.is_file())
        with Image.open(result) as rendered:
            self.assertGreater(rendered.height, 200)
        with self.assertRaisesRegex(ValueError, "row count"):
            render_html_table_png(path, self.directory / "wrong.png", rows=1)

    @patch("openai.OpenAI")
    def test_table_request_sends_two_images_without_storage(self, client_class):
        client_class.return_value.responses.create.return_value = SimpleNamespace(
            output_text=json.dumps({"verdict": "match", "issues": []})
        )
        result = compare_with_openai(
            kind="table", pdf_images=[self.pdf_png],
            extracted_image=self.pdf_png, model="test-vision", heading="Billing",
            identifier="table-1",
        )
        self.assertEqual(result["verdict"], "match")
        kwargs = client_class.return_value.responses.create.call_args.kwargs
        self.assertIs(kwargs["store"], False)
        self.assertEqual(kwargs["text"]["format"]["type"], "json_schema")
        self.assertEqual(sum(item["type"] == "input_image"
                             for item in kwargs["input"][0]["content"]), 2)

    @patch("openai.OpenAI")
    def test_chunk_request_sends_one_page_and_extracted_text(self, client_class):
        client_class.return_value.responses.create.return_value = SimpleNamespace(
            output_text=json.dumps({"verdict": "mismatch", "issues": [{
                "type": "heading_mismatch", "location": "page 1", "pdf_value": "A",
                "extracted_value": "B", "explanation": "Different heading",
            }]})
        )
        result = compare_with_openai(
            kind="chunk", pdf_images=[self.pdf_png], extracted_text="Example text",
            model="test-vision", heading="B", identifier="chunk-2",
        )
        self.assertEqual(result["issues"][0]["type"], "heading_mismatch")
        content = client_class.return_value.responses.create.call_args.kwargs["input"][0]["content"]
        self.assertIn("Example text", content[0]["text"])
        self.assertEqual(sum(item["type"] == "input_image" for item in content), 1)


if __name__ == "__main__":
    unittest.main()
