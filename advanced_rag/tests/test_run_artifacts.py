from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from aws_data_workflow.run_artifacts import (
    append_run_error,
    copy_page_markdown_checkpoints,
    create_run_directory,
    finalize_run_directory,
)


class RunArtifactTests(unittest.TestCase):
    def test_retry_copies_only_nonempty_engine_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            previous = root / "previous"
            next_run = root / "next"
            for page, content in ((1, "# Page 1\n"), (2, "")):
                page_dir = previous / "pages" / f"page-{page:03d}"
                page_dir.mkdir(parents=True)
                (page_dir / "deepseek.md").write_text(content, encoding="utf-8")

            copied = copy_page_markdown_checkpoints(
                previous,
                next_run,
                ocr_engine="deepseek",
            )
            self.assertEqual(copied, 1)
            self.assertEqual(
                (next_run / "pages" / "page-001" / "deepseek.md").read_text(),
                "# Page 1\n",
            )
            self.assertFalse((next_run / "pages" / "page-002" / "deepseek.md").exists())

    def test_writes_document_ingestion_compatible_run_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "report.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            writer.add_blank_page(width=612, height=792)
            with source.open("wb") as stream:
                writer.write(stream)
            working = root / "documents" / "doc-test"
            page = working / "pages" / "page-001"
            page.mkdir(parents=True)
            (working / "document.md").write_text("# Report\n", encoding="utf-8")
            (working / "chunks.jsonl").write_text('{"text":"Report"}\n', encoding="utf-8")
            (page / "docling.md").write_text("Docling\n", encoding="utf-8")
            (page / "deepseek.md").write_text("DeepSeek\n", encoding="utf-8")
            (working / "pages" / "manifest.json").write_text(
                json.dumps({"pages": [{"page": 1, "markdown_source": "deepseek"}]}),
                encoding="utf-8",
            )
            run_id, run_dir = create_run_directory(
                root / "runs",
                filename="Example Report.pdf",
                source=source,
                ocr_engine="deepseek",
            )
            self.assertTrue((run_dir / "pages" / "page-001" / "source.pdf").is_file())
            self.assertTrue((run_dir / "pages" / "page-002" / "source.pdf").is_file())
            self.assertEqual(
                len(PdfReader(run_dir / "pages" / "page-002" / "source.pdf").pages),
                1,
            )
            append_run_error(
                run_dir,
                document_id="doc-test",
                stage="extracting",
                ocr_engine="deepseek",
                error=RuntimeError("page-002 failed"),
            )
            errors = json.loads((run_dir / "errors.json").read_text())
            self.assertEqual(errors["errors"][0]["stage"], "extracting")
            self.assertEqual(errors["errors"][0]["message"], "page-002 failed")
            record = {
                "id": "doc-test",
                "filename": "Example Report.pdf",
                "runId": run_id,
                "createdAt": "2026-10-20T00:00:00Z",
            }
            result = {
                "pages": {"page_count": 1, "ocr_pages": 1, "issue_count": 0},
                "visuals": {"issue_count": 0},
            }
            finalize_run_directory(
                run_dir,
                working_dir=working,
                source=source,
                record=record,
                result=result,
                ocr_engine="deepseek",
            )
            self.assertTrue((run_dir / "input" / "source.pdf").is_file())
            self.assertTrue((run_dir / "candidate" / "document.md").is_file())
            self.assertEqual(
                (run_dir / "pages" / "page-001" / "page.md").read_text(),
                "DeepSeek\n",
            )
            self.assertTrue((run_dir / "pages" / "page-001" / "source.pdf").is_file())
            self.assertTrue((run_dir / "run-manifest.json").is_file())
            self.assertTrue((run_dir / "qc-report.json").is_file())

    def test_run_copies_prepared_pages_without_splitting_again(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "report.pdf"
            prepared = root / "prepared"
            prepared_page = prepared / "page-001"
            prepared_page.mkdir(parents=True)
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            with source.open("wb") as stream:
                writer.write(stream)
            (prepared_page / "source.pdf").write_bytes(source.read_bytes())

            _, run_dir = create_run_directory(
                root / "runs",
                filename="Prepared.pdf",
                source=source,
                ocr_engine="llamaparse",
                prepared_pages=prepared,
            )

            self.assertTrue((run_dir / "pages" / "page-001" / "source.pdf").is_file())
            self.assertEqual(
                (run_dir / "pages" / "page-001" / "source.pdf").read_bytes(),
                (prepared_page / "source.pdf").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()

