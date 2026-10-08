from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import RetrievedContext
from app.service import RagService


class Retriever:
    def retrieve(self, question):
        return [RetrievedContext("Policy evidence", "gs://demo/policy.pdf", 0.8)]


class Generator:
    def generate(self, prompt):
        return "Grounded answer [1]."


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(RagService(Retriever(), Generator())))

    def test_health_does_not_require_cloud_configuration(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_chat_contract_and_request_id(self):
        response = self.client.post(
            "/api/chat", json={"question": "What does the policy require?"}, headers={"x-request-id": "test-1"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["x-request-id"], "test-1")
        self.assertTrue(response.json()["grounded"])
        self.assertEqual(response.json()["citations"][0]["source_uri"], "gs://demo/policy.pdf")

    def test_question_length_is_validated(self):
        response = self.client.post("/api/chat", json={"question": "x"})
        self.assertEqual(response.status_code, 422)

    def test_request_id_is_sanitized_before_logging(self):
        response = self.client.get("/healthz", headers={"x-request-id": "ok\r\nforged"})
        self.assertEqual(response.headers["x-request-id"], "okforged")


if __name__ == "__main__":
    unittest.main()
