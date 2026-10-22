from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from aws_data_workflow.docling_chunking import (
    build_records,
    build_whole_document_record,
    write_jsonl,
)


class FakeChunker:
    def contextualize(self, chunk: SimpleNamespace) -> str:
        return f"Section\n{chunk.text}"


class DoclingChunkingTests(unittest.TestCase):
    def test_records_have_stable_ids_and_metadata(self) -> None:
        chunks = [
            SimpleNamespace(text="first", meta={"headings": ["Section"]}),
            SimpleNamespace(text="second", meta={"headings": ["Section"]}),
        ]
        kwargs = {
            "chunker": FakeChunker(),
            "source": Path("policy.pdf"),
            "document_id": "document-sha",
        }

        first = build_records(chunks, **kwargs)
        second = build_records(chunks, **kwargs)

        self.assertEqual(first, second)
        self.assertEqual(first[0]["chunk_index"], 0)
        self.assertEqual(first[0]["metadata"]["headings"], ["Section"])
        self.assertEqual(first[0]["text"], "Section\nfirst")

    def test_write_jsonl(self) -> None:
        records = [{"chunk_id": "one", "text": "alpha"}]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "chunks.jsonl"
            count = write_jsonl(records, output)

            self.assertEqual(count, 1)
            self.assertEqual(json.loads(output.read_text()), records[0])

    def test_form_is_kept_as_one_whole_document_record(self) -> None:
        records = build_whole_document_record(
            source=Path("application.pdf"),
            document_id="document-sha",
            text="Complete application text",
            classification={
                "document_type": "form_application",
                "route": "whole_document_context",
            },
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["text"], "Complete application text")
        self.assertEqual(
            records[0]["metadata"]["storage_strategy"], "whole_document"
        )


if __name__ == "__main__":
    unittest.main()

