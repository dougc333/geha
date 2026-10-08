import hashlib
import io
import json
import sys
import types
import unittest

from support import load

chunk_core = load("geha_chunk_core", "chunker/rag_core.py")
sys.modules["rag_core"] = chunk_core
chunker = load("geha_chunker", "chunker/handler.py")
query_core = load("geha_query_core", "query/core.py")
processor = load("geha_pdf_worker", "processor/pdf_worker.py")


class MissingKey(Exception):
    pass


class FakeS3:
    exceptions = types.SimpleNamespace(NoSuchKey=MissingKey)

    def __init__(self, values):
        self.values = values
        self.writes = {}

    def get_object(self, *, Bucket, Key):
        if (Bucket, Key) not in self.values:
            raise MissingKey(Key)
        return {"Body": io.BytesIO(self.values[(Bucket, Key)])}

    def put_object(self, *, Bucket, Key, Body, **kwargs):
        self.writes[(Bucket, Key)] = (Body, kwargs)


def sidecar(pdf):
    content = "GEHA validated benefits text"
    return {
        "schema_version": 1,
        "source_sha256": hashlib.sha256(pdf).hexdigest(),
        "validation_status": "validated",
        "page_count": 1,
        "metadata": {
            "title": "GEHA Benefits Guide",
            "relative_path": "medical/fehb/guide.pdf",
            "category": "medical",
            "program": "FEHB",
        },
        "validation": {"run_id": "run_test_aws_processor"},
        "pages": [{
            "page_number": 1,
            "validation_status": "matched",
            "content": content,
            "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        }],
    }


class ChunkerTests(unittest.TestCase):
    def test_indexes_only_validated_sidecar_text(self):
        pdf = b"%PDF-source"
        key = "validated/medical/fehb/guide.pdf"
        fake = FakeS3({
            ("documents", key): pdf,
            ("documents", key + ".validated.json"): json.dumps(sidecar(pdf)).encode(),
        })
        previous = chunker.s3
        try:
            chunker.s3 = fake
            chunker.process("documents", key)
        finally:
            chunker.s3 = previous
        body = next(iter(fake.writes.values()))[0].decode()
        row = json.loads(body)
        self.assertEqual(row["content"], "GEHA validated benefits text")
        self.assertEqual(row["metadata"]["program"], "FEHB")

    def test_missing_sidecar_fails_closed(self):
        pdf = b"%PDF-source"
        fake = FakeS3({("documents", "validated/a.pdf"): pdf})
        previous = chunker.s3
        try:
            chunker.s3 = fake
            with self.assertRaisesRegex(ValueError, "missing required validated sidecar"):
                chunker.process("documents", "validated/a.pdf")
        finally:
            chunker.s3 = previous

    def test_altered_pdf_is_rejected(self):
        original = b"%PDF-original"
        key = "validated/a.pdf"
        fake = FakeS3({
            ("documents", key): b"%PDF-altered",
            ("documents", key + ".validated.json"): json.dumps(sidecar(original)).encode(),
        })
        previous = chunker.s3
        try:
            chunker.s3 = fake
            with self.assertRaisesRegex(ValueError, "source PDF SHA-256"):
                chunker.process("documents", key)
        finally:
            chunker.s3 = previous


class QueryCoreTests(unittest.TestCase):
    def test_rrf_rewards_results_found_by_both_retrievers(self):
        both = {"id": 1, "title": "Both"}
        fused = query_core.reciprocal_rank_fusion(
            [both, {"id": 2, "title": "Vector"}],
            [{"id": 3, "title": "Keyword"}, both],
        )
        self.assertEqual(fused[0]["id"], 1)

    def test_prompt_preserves_page_citations(self):
        prompt, citations = query_core.evidence_prompt("What is covered?", [{
            "title": "Policy", "page_number": 7, "source": "s3://x/p.pdf",
            "relative_path": "coverage-policies/p.pdf", "content": "Covered text",
        }])
        self.assertIn("[1] Policy — page 7", prompt)
        self.assertEqual(citations[0]["page"], 7)

    def test_schema_and_query_use_real_bm25_index(self):
        root = __import__("pathlib").Path(__file__).resolve().parents[1]
        schema = (root / "schema.sql").read_text(encoding="utf-8")
        query = (root / "query" / "app.py").read_text(encoding="utf-8")
        self.assertIn("CREATE TABLE IF NOT EXISTS geha_terms", schema)
        self.assertIn("content_len integer", schema)
        self.assertIn("BM25_SQL", query)
        self.assertNotIn("ts_rank_cd", query)
        self.assertIn("c.embedding <=> %s::vector", query)
        self.assertIn("%s::text IS NULL", query)


class ProcessorHelpersTests(unittest.TestCase):
    def test_native_text_quality_gate(self):
        self.assertFalse(processor.usable_embedded_text("Page 1")[0])
        self.assertTrue(processor.usable_embedded_text(
            "This GEHA coverage policy contains enough ordinary words for reliable extraction."
        )[0])

    def test_active_html_is_rejected(self):
        with self.assertRaises(ValueError):
            processor.clean_html_document("<script>alert(1)</script>")


if __name__ == "__main__":
    unittest.main()
