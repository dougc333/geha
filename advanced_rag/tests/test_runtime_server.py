from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from aws_data_workflow.runtime_server import QueryRunStore, RuntimeIndex, create_app


class FakeTable:
    def __init__(self) -> None:
        self.items = []

    def put_item(self, *, Item):
        self.items.append(Item)

    def scan(self):
        return {"Items": list(self.items)}


class RuntimeServerTests(unittest.TestCase):
    def test_search_uses_prebuilt_vectors_without_docling_or_generation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"documents": [
                {"path": "example.pdf", "cluster": "policy"}
            ]}), encoding="utf-8")
            (root / "index.jsonl").write_text(json.dumps({
                "chunk_id": "coverage",
                "source_name": "example.pdf",
                "text": "Preventive care is covered.",
                "contextual_retrieval_text": "Policy coverage. Preventive care is covered.",
                "embedding": [1.0, 0.0],
                "review_status": "approved",
                "pages": [4],
            }) + "\n", encoding="utf-8")
            index = RuntimeIndex(manifest_path=manifest, local_directory=root)
            table = FakeTable()
            app = create_app(
                index=index,
                embed_query=lambda _query: [1.0, 0.0],
                run_store=QueryRunStore(table=table),
            )

            client = TestClient(app)
            health = client.get("/api/health").json()
            search_response = client.post("/api/search", json={
                "query": "Is preventive care covered?"
            })
            result = search_response.json()

            self.assertFalse(health["docling"])
            self.assertFalse(health["generationModel"])
            self.assertEqual(result["route"]["cluster"], "policy")
            self.assertEqual(result["sources"][0]["chunk_id"], "coverage")
            self.assertEqual(
                set(result["latency_ms"]),
                {
                    "route_ms",
                    "query_embedding_ms",
                    "rank_fusion_ms",
                    "retrieval_ms",
                    "persistence_ms",
                    "total_ms",
                },
            )
            self.assertIn("route;dur=", search_response.headers["server-timing"])
            self.assertEqual(len(table.items), 1)

            documents = client.get("/api/documents").json()
            self.assertEqual(documents[0]["filename"], "example.pdf")
            self.assertEqual(documents[0]["stage"], "complete")
            runtime_indexes = client.get("/api/runtime/indexes").json()
            self.assertEqual(runtime_indexes[0]["chunk_id"], "coverage")
            self.assertEqual(runtime_indexes[0]["embedding_dimensions"], 2)

            route_response = client.post("/api/query-router", json={
                "jsonl": '{"query":"Is preventive care covered?"}'
            })
            self.assertEqual(route_response.status_code, 200)
            self.assertEqual(route_response.json()["routes"][0]["cluster"], "policy")
            self.assertEqual(len(client.get("/api/query-router/runs").json()), 1)

            browser = client.get("/")
            self.assertEqual(browser.status_code, 200)
            self.assertIn('<div id="root"></div>', browser.text)


if __name__ == "__main__":
    unittest.main()
