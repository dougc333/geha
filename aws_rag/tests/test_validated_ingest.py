import hashlib
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

from support import load

chunker_core = load("validated_chunker_rag_core", "chunker/rag_core.py")
sys.modules["rag_core"] = chunker_core
os.environ["OUT_BUCKET"] = "chunks-test"
chunker_handler = load("validated_chunker_handler", "chunker/handler.py")
sidecar_builder = load("validated_sidecar_builder", "scripts/build_validated_sidecar.py")


class MissingKey(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class FakeS3:
    exceptions = types.SimpleNamespace(NoSuchKey=MissingKey)

    def __init__(self, objects):
        self.objects = dict(objects)
        self.writes = {}

    def get_object(self, *, Bucket, Key):
        try:
            body = self.objects[(Bucket, Key)]
        except KeyError as exc:
            raise MissingKey(Key) from exc
        return {"Body": io.BytesIO(body), "Metadata": {}}

    def put_object(self, *, Bucket, Key, Body, **_):
        self.writes[(Bucket, Key)] = Body


class HandlerValidatedSidecarTest(unittest.TestCase):
    def payload(self, pdf_bytes):
        content = "validated benefit text"
        return {
            "schema_version": 1,
            "source_sha256": hashlib.sha256(pdf_bytes).hexdigest(),
            "validation_status": "validated",
            "page_count": 1,
            "metadata": {"title": "GEHA benefit document"},
            "validation": {"run_id": "run_test_mcp_server"},
            "pages": [{
                "page_number": 1,
                "validation_status": "matched",
                "content": content,
                "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
            }],
        }

    def test_pdf_event_uses_validated_text(self):
        pdf = b"%PDF-test-source"
        key = "geha/medical/example.pdf"
        fake = FakeS3({
            ("raw", key): pdf,
            ("raw", key + ".validated.json"): json.dumps(self.payload(pdf)).encode(),
        })
        old_s3 = chunker_handler.s3
        try:
            chunker_handler.s3 = fake
            chunker_handler.process("raw", key)
        finally:
            chunker_handler.s3 = old_s3
        output = next(iter(fake.writes.values())).decode()
        chunk = json.loads(output)
        self.assertEqual(chunk["content"], "validated benefit text")
        self.assertEqual(chunk["page_number"], 1)
        self.assertEqual(chunk["source"], f"s3://raw/{key}")
        self.assertEqual(chunk["validation"]["run_id"], "run_test_mcp_server")

    def test_required_mode_rejects_pdf_without_sidecar(self):
        key = "geha/medical/example.pdf"
        fake = FakeS3({("raw", key): b"%PDF-test-source"})
        old_s3 = chunker_handler.s3
        old_required = chunker_handler.REQUIRE_VALIDATED_SIDECAR
        try:
            chunker_handler.s3 = fake
            chunker_handler.REQUIRE_VALIDATED_SIDECAR = True
            with self.assertRaisesRegex(ValueError, "missing required validated sidecar"):
                chunker_handler.process("raw", key)
        finally:
            chunker_handler.s3 = old_s3
            chunker_handler.REQUIRE_VALIDATED_SIDECAR = old_required


class SidecarBuilderTest(unittest.TestCase):
    def test_builds_only_from_fully_matched_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pdf = root / "source.pdf"
            pdf.write_bytes(b"%PDF-local-source")
            run = root / "run_test_mcp_server"
            extraction = run / "extraction"
            extraction.mkdir(parents=True)
            (extraction / "page_0001.final.md").write_text("faithful page text\n")
            batch = {
                "run_id": run.name,
                "status": "completed",
                "source_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                "page_count": 1,
                "pages_failed": 0,
                "pages_modified": 0,
                "pages": [{
                    "page": 1,
                    "status": "matched",
                    "extraction_method": "docling_native",
                    "passes": [{"pass": 1, "verdict": "match", "error_count": 0}],
                    "content_changed": False,
                    "final_markdown": "page_0001.final.md",
                }],
            }
            (run / "batch.json").write_text(json.dumps(batch))
            payload = sidecar_builder.build(pdf, run)
            self.assertEqual(payload["validation_status"], "validated")
            self.assertEqual(payload["pages"][0]["content"], "faithful page text")

            batch["pages"][0]["status"] = "needs_human_review"
            (run / "batch.json").write_text(json.dumps(batch))
            with self.assertRaisesRegex(ValueError, "has not passed visual comparison"):
                sidecar_builder.build(pdf, run)


if __name__ == "__main__":
    unittest.main()
