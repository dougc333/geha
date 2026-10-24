from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

try:
    from aws_data_workflow.server import AwsDocumentStore
except ImportError:  # pragma: no cover - dependency-aware local test suite
    AwsDocumentStore = None


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def list_objects_v2(self, **_kwargs):
        return {
            "Contents": [{"Key": key} for key in sorted(self.objects)],
            "IsTruncated": False,
        }

    def upload_file(self, filename, _bucket, key, ExtraArgs=None):
        if ExtraArgs != {"ServerSideEncryption": "AES256"}:
            raise AssertionError("Uploads must request server-side encryption")
        self.objects[key] = Path(filename).read_bytes()

    def download_file(self, _bucket, key, filename):
        Path(filename).write_bytes(self.objects[key])


class FakeTable:
    def __init__(self) -> None:
        self.items: dict[str, dict] = {}

    def scan(self, **_kwargs):
        return {"Items": list(self.items.values())}

    def put_item(self, *, Item):
        self.items[Item["id"]] = Item


@unittest.skipIf(AwsDocumentStore is None, "server dependencies are not installed")
class AwsDocumentStoreTests(unittest.TestCase):
    def test_records_and_artifacts_survive_task_replacement(self) -> None:
        s3 = FakeS3()
        table = FakeTable()
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = AwsDocumentStore(
                Path(first_dir),
                bucket="artifacts",
                table_name="jobs",
                s3_client=s3,
                table=table,
            )
            document = first.directory("doc-example")
            document.mkdir(parents=True)
            (document / "source.pdf").write_bytes(b"pdf bytes")
            first.save({
                "id": "doc-example",
                "filename": "example.pdf",
                "stage": "queued",
                "createdAt": "2026-10-23T00:00:00+00:00",
            })
            (document / "chunks.jsonl").write_text('{"chunk_id":"one"}\n', encoding="utf-8")
            first.save({**first.get("doc-example"), "stage": "complete"})
            self.assertNotIn("documents/doc-example/job.json", s3.objects)

            replacement = AwsDocumentStore(
                Path(second_dir),
                bucket="artifacts",
                table_name="jobs",
                s3_client=s3,
                table=table,
            )

            self.assertEqual(replacement.get("doc-example")["stage"], "complete")
            self.assertEqual(
                (replacement.directory("doc-example") / "source.pdf").read_bytes(),
                b"pdf bytes",
            )
            self.assertTrue((replacement.directory("doc-example") / "chunks.jsonl").is_file())


if __name__ == "__main__":
    unittest.main()
