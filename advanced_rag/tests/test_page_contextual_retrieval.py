from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aws_data_workflow.page_contextual_retrieval import (
    PROMPT_VERSION,
    contextual_retrieval_prompt,
    contextualize_pages,
    discover_page_chunks,
)


class PageContextualRetrievalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.pages = self.root / "pages"
        for page, text in ((1, "First page evidence"), (2, "Second page evidence")):
            page_dir = self.pages / f"page-{page:03d}"
            page_dir.mkdir(parents=True)
            (page_dir / "docling.md").write_text(text, encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_prompt_keeps_document_in_cacheable_system_block(self) -> None:
        prompt = contextual_retrieval_prompt("STABLE DOCUMENT", "CHANGING PAGE")
        self.assertEqual(prompt["system"][1]["cache_control"], {"type": "ephemeral"})
        self.assertIn("STABLE DOCUMENT", prompt["system"][1]["text"])
        self.assertNotIn("STABLE DOCUMENT", prompt["message"])
        self.assertIn("CHANGING PAGE", prompt["message"])

    def test_prefers_normalized_docling_page(self) -> None:
        normalized = self.pages / "page-001" / "docling.normalized.md"
        normalized.write_text("Normalized table", encoding="utf-8")
        chunks = discover_page_chunks(self.pages, preferred_engine="llamaparse")
        self.assertEqual(chunks[0]["text"], "Normalized table")
        self.assertEqual(chunks[0]["source_markdown"], "pages/page-001/docling.normalized.md")

    def test_checkpoints_and_reuses_every_completed_page(self) -> None:
        calls: list[tuple[str, str]] = []

        def generate(document: str, chunk: str) -> dict[str, object]:
            calls.append((document, chunk))
            return {
                "context": f"Context for {chunk}",
                "input_tokens": 10,
                "output_tokens": 4,
                "cache_creation_input_tokens": 100 if len(calls) == 1 else 0,
                "cache_read_input_tokens": 0 if len(calls) == 1 else 100,
            }

        output = self.root / "contextual"
        result = contextualize_pages(
            document_id="doc-test",
            filename="test.pdf",
            pages_dir=self.pages,
            output_dir=output,
            generate_context=generate,
        )
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["completed_pages"], 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], calls[1][0])
        self.assertIn("First page evidence", calls[0][0])
        self.assertIn("Second page evidence", calls[0][0])
        records = [
            json.loads(line)
            for line in (output / "contextual-pages.jsonl").read_text().splitlines()
        ]
        self.assertEqual(records[0]["contextual_retrieval_prompt_version"], PROMPT_VERSION)
        self.assertEqual(records[1]["prompt_cache"]["cache_read_input_tokens"], 100)

        contextualize_pages(
            document_id="doc-test",
            filename="test.pdf",
            pages_dir=self.pages,
            output_dir=output,
            generate_context=lambda _document, _chunk: self.fail("checkpoint must be reused"),
        )


if __name__ == "__main__":
    unittest.main()
