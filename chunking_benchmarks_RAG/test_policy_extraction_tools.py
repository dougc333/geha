"""Tests for review-only Docling and HTML extraction tools."""

import tempfile
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from chunking_benchmarks_RAG import policy_extraction_tools as tools


class PolicyExtractionToolTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.policy_dir = Path(self.temp_dir.name) / "coverage-policies"
        self.policy_dir.mkdir()
        self.pdf = self.policy_dir / "geha-coverage-policy-nplate.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\n")
        self.policy_patch = patch.object(tools, "POLICY_DIR", self.policy_dir)
        self.review_patch = patch.object(tools, "REVIEW_DIR", self.policy_dir / "review")
        self.policy_patch.start()
        self.review_patch.start()
        self.addCleanup(self.policy_patch.stop)
        self.addCleanup(self.review_patch.stop)

    def test_rejects_paths_and_missing_pdf(self):
        for filename in ("../secret.pdf", "/tmp/secret.pdf", "nplate.md"):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                tools.extract_docling_policy(filename)
        with self.assertRaises(FileNotFoundError):
            tools.extract_html_policy_tables("missing.pdf")

    @patch.object(tools.subprocess, "run")
    def test_pdf_page_tool_renders_numbered_pngs_and_reuses_them(self, run):
        def fake_run(command, **kwargs):
            if command[0] == "pdfinfo":
                return SimpleNamespace(stdout="Title: Policy\nPages: 3\n")
            self.assertEqual(command[0], "pdftoppm")
            Path(command[-1]).with_suffix(".png").write_bytes(tools.PNG_SIGNATURE + b"image")
            return SimpleNamespace(stdout="")

        run.side_effect = fake_run
        args = {"pdf_filename": self.pdf.name, "first_page": 2, "last_page": 3, "dpi": 150}
        result = tools.pdf_page_screenshots.invoke(args)
        self.assertEqual(result["page_count"], 3)
        self.assertEqual([page["page"] for page in result["pages"]], [2, 3])
        self.assertTrue(all(page["status"] == "staged" for page in result["pages"]))
        self.assertEqual(
            [Path(page["png"]).name for page in result["pages"]],
            ["page-0002.png", "page-0003.png"],
        )
        self.assertTrue(all(Path(page["png"]).is_file() for page in result["pages"]))

        run.reset_mock()
        repeated = tools.pdf_page_screenshots.invoke(args)
        self.assertTrue(all(page["status"] == "already_staged" for page in repeated["pages"]))
        self.assertEqual(run.call_count, 1)  # pdfinfo only; no re-render

    @patch.object(tools.subprocess, "run")
    def test_pdf_page_tool_rejects_out_of_range_pages(self, run):
        run.return_value = SimpleNamespace(stdout="Pages: 2\n")
        with self.assertRaisesRegex(ValueError, "page range"):
            tools.render_policy_pdf_pages(self.pdf.name, first_page=3)
        with self.assertRaisesRegex(ValueError, "dpi"):
            tools.render_policy_pdf_pages(self.pdf.name, dpi=600)

    @patch.object(tools, "ocr_table_converter")
    @patch.object(tools, "native_text_converter")
    @patch.object(tools, "extract_pdf")
    def test_html_tool_stages_non_revision_tables(self, extract, native, ocr):
        extract.return_value = {
            "pdf": self.pdf.name,
            "status": "ok",
            "tables_written": 2,
            "tables_excluded": 1,
            "outputs": [{"heading": "Billing codes", "html": "billing.html"}],
        }
        result = tools.html_table_extract.invoke({"pdf_filename": self.pdf.name})
        self.assertEqual(result["tables_written"], 2)
        self.assertEqual(result["tables_excluded"], 1)
        self.assertEqual(result["outputs"][0]["heading"], "Billing codes")
        self.assertTrue(result["output_dir"].endswith("nplate/html_tables"))
        extract.assert_called_once_with(
            self.pdf,
            Path(result["output_dir"]),
            native.return_value,
            ocr.return_value,
        )

    @patch.object(tools, "native_text_converter")
    def test_docling_tool_does_not_overwrite_staged_artifacts(self, converter):
        output_dir = tools.REVIEW_DIR / self.pdf.stem
        output_dir.mkdir(parents=True)
        (output_dir / f"{self.pdf.stem}.docling.md").write_text("existing")
        (output_dir / f"{self.pdf.stem}.docling_chunks.md").write_text("existing")
        result = tools.docling_extract.invoke({"pdf_filename": self.pdf.name})
        self.assertEqual(result["status"], "already_staged")
        converter.assert_not_called()

    @patch("docling_core.transforms.chunker.tokenizer.huggingface.HuggingFaceTokenizer.from_pretrained")
    @patch("docling.chunking.HybridChunker")
    @patch.object(tools, "require_embedded_text")
    @patch.object(tools, "native_text_converter")
    def test_docling_tool_stages_markdown_and_chunks(
        self, converter, require_text, chunker_class, tokenizer
    ):
        document = SimpleNamespace(
            export_to_markdown=lambda: "# Nplate\n\nPolicy text",
            tables=[object()],
        )
        converter.return_value.convert.return_value.document = document
        chunker_class.return_value.chunk.return_value = ["criteria A", "criteria B"]
        chunker_class.return_value.contextualize.side_effect = lambda chunk: chunk

        result = tools.docling_extract.invoke({"pdf_filename": self.pdf.name})

        require_text.assert_called_once_with(document, self.pdf.name)
        tokenizer.assert_called_once_with(
            model_name="BAAI/bge-small-en-v1.5", max_tokens=700
        )
        self.assertEqual(result["status"], "staged")
        self.assertEqual(result["chunk_count"], 2)
        self.assertEqual(result["table_count"], 1)
        self.assertEqual(Path(result["markdown_path"]).read_text(), "# Nplate\n\nPolicy text")
        self.assertIn("## Chunk 2\n\ncriteria B", Path(result["chunks_path"]).read_text())

    def test_tool_names_and_input_schema(self):
        for tool, name in (
            (tools.docling_extract, "docling_extract"),
            (tools.html_table_extract, "html_table_extract"),
            (tools.pdf_page_screenshots, "pdf_page_screenshots"),
        ):
            self.assertEqual(tool.name, name)
            self.assertEqual(tool.args["pdf_filename"]["type"], "string")

    @patch("docling_core.transforms.chunker.tokenizer.huggingface.HuggingFaceTokenizer.from_pretrained")
    @patch("docling.chunking.HybridChunker")
    @patch.object(tools, "require_embedded_text")
    @patch.object(tools, "native_text_converter")
    def test_review_chunk_manifest_has_heading_and_source_page(
        self, converter, _require_text, chunker_class, _tokenizer
    ):
        document = SimpleNamespace(export_to_markdown=lambda: "# Policy", tables=[])
        converter.return_value.convert.return_value.document = document
        chunk = SimpleNamespace(meta=SimpleNamespace(
            headings=["Biliary Tract Cancer"],
            doc_items=[SimpleNamespace(prov=[SimpleNamespace(page_no=2)])],
        ))
        chunker_class.return_value.chunk.return_value = [chunk]
        chunker_class.return_value.contextualize.return_value = "Biliary criteria"

        result = tools.stage_docling_chunks_for_review(self.pdf, self.policy_dir / "qc-run")

        self.assertEqual(result["chunks"][0]["pages"], [2])
        self.assertEqual(result["chunks"][0]["headings"], ["Biliary Tract Cancer"])
        manifest = json.loads(Path(result["manifest_path"]).read_text())
        self.assertEqual(manifest["chunks"][0]["text"], "Biliary criteria")


if __name__ == "__main__":
    unittest.main()
