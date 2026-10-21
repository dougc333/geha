from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aws_data_workflow.form_contextual_retrieval import (
    FormVectorStore,
    contextualize_whole_form,
)


class FormContextualRetrievalTests(unittest.TestCase):
    def test_keeps_form_whole_and_links_vector_to_source_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            document_dir = root / "documents" / "doc-form"
            pages_dir = document_dir / "pages"
            document_dir.mkdir(parents=True)
            (document_dir / "source.pdf").write_bytes(b"complete form")
            for page, text in ((1, "Application for One Person"), (2, "Signature")):
                page_dir = pages_dir / f"page-{page:03d}"
                page_dir.mkdir(parents=True)
                (page_dir / "docling.md").write_text(text, encoding="utf-8")

            embedded: list[str] = []
            store = FormVectorStore(root / "vector-db" / "forms.sqlite3")
            status = contextualize_whole_form(
                document_id="doc-form",
                filename="Revised_KYState_MedicaidKCHIPQHPAppForOnePerson.pdf",
                document_dir=document_dir,
                pages_dir=pages_dir,
                output_dir=document_dir / "contextual-retrieval",
                vector_store=store,
                generate_context=lambda document: f"Context for {len(document)} chars",
                embed_text=lambda text: embedded.append(text) or [0.1, 0.2, 0.3],
            )

            self.assertEqual(status["storage_strategy"], "whole_document")
            self.assertEqual(status["retrieval_units"], 1)
            self.assertEqual(status["source_page_count"], 2)
            self.assertEqual(status["embedding_dimensions"], 3)
            self.assertEqual(len(embedded), 1)
            self.assertTrue(embedded[0].startswith("Context for "))
            self.assertNotIn("Application for One Person", embedded[0])
            rows = store.list()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["source_path"], str(document_dir / "source.pdf"))
            self.assertEqual(rows[0]["source_uri"], "/api/documents/doc-form/source")

            contextualize_whole_form(
                document_id="doc-form",
                filename="Revised_KYState_MedicaidKCHIPQHPAppForOnePerson.pdf",
                document_dir=document_dir,
                pages_dir=pages_dir,
                output_dir=document_dir / "contextual-retrieval",
                vector_store=store,
                generate_context=lambda _document: self.fail("must reuse whole form"),
                embed_text=lambda _text: self.fail("must reuse embedding"),
            )
            self.assertEqual(len(store.list()), 1)


if __name__ == "__main__":
    unittest.main()
