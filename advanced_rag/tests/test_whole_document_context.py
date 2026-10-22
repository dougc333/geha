from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from aws_data_workflow.contextual_embeddings import read_jsonl
from aws_data_workflow.whole_document_context import (
    build_whole_document_context,
    prepare_whole_document_directory,
)


class WholeDocumentContextTests(unittest.TestCase):
    def test_summary_is_embedded_without_replacing_complete_source(self) -> None:
        embedded: list[str] = []
        record = build_whole_document_context(
            record={
                "chunk_id": "whole-1",
                "text": "Complete application source",
                "metadata": {"storage_strategy": "whole_document"},
            },
            summarize=lambda document: f"Summary of {document}",
            embed_text=lambda text: embedded.append(text) or [0.1, 0.2],
            context_model="summary-model",
            embedding_model="embedding-model",
        )
        self.assertEqual(record["text"], "Complete application source")
        self.assertEqual(
            record["retrieval_context"], "Summary of Complete application source"
        )
        self.assertEqual(embedded, [record["retrieval_context"]])
        self.assertEqual(record["embedding_dimensions"], 2)

    def test_prepares_one_record_from_all_extracted_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            document_dir = Path(temporary) / "doc-form"
            document_dir.mkdir()
            (document_dir / "job.json").write_text(
                json.dumps({
                    "id": "doc-form",
                    "filename": "Revised_KYState_MedicaidKCHIPQHPAppForOnePerson.pdf",
                }),
                encoding="utf-8",
            )
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            with (document_dir / "source.pdf").open("wb") as stream:
                writer.write(stream)
            for page, text in ((1, "Application for One Person"), (2, "Signature")):
                page_dir = document_dir / "pages" / f"page-{page:03d}"
                page_dir.mkdir(parents=True)
                (page_dir / "docling.md").write_text(text, encoding="utf-8")

            result = prepare_whole_document_directory(document_dir)
            records = read_jsonl(document_dir / "chunks.jsonl")

            self.assertEqual(result["pages"], 2)
            self.assertEqual(len(records), 1)
            self.assertIn("Application for One Person\n\nSignature", records[0]["text"])
