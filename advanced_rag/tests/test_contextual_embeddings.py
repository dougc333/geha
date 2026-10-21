from __future__ import annotations

import unittest

from aws_data_workflow.contextual_embeddings import (
    PROMPT_VERSION,
    build_contextual_embeddings,
    make_bedrock_context_generator,
)


class ContextualEmbeddingTests(unittest.TestCase):
    def test_document_precedes_cache_point_and_dynamic_chunk(self) -> None:
        class FakeClient:
            def __init__(self):
                self.request = None

            def converse(self, **request):
                self.request = request
                return {
                    "output": {"message": {"content": [{"text": "Policy context"}]}},
                    "usage": {
                        "inputTokens": 12,
                        "outputTokens": 3,
                        "cacheReadInputTokens": 1000,
                        "cacheWriteInputTokens": 0,
                    },
                }

        client = FakeClient()
        generate = make_bedrock_context_generator("model", client=client)
        result = generate("STABLE DOCUMENT", "CHANGING CHUNK")

        self.assertEqual(client.request["system"][1]["text"], "<document>\nSTABLE DOCUMENT\n</document>")
        self.assertEqual(
            client.request["system"][2],
            {"cachePoint": {"type": "default"}},
        )
        user_text = client.request["messages"][0]["content"][0]["text"]
        self.assertIn("CHANGING CHUNK", user_text)
        self.assertNotIn("STABLE DOCUMENT", user_text)
        self.assertEqual(result["cache_read_input_tokens"], 1000)

    def test_preserves_evidence_and_embeds_combined_text(self) -> None:
        embedded: list[str] = []

        def generate(document: str, chunk: str) -> str:
            self.assertEqual(document, "Complete policy")
            self.assertEqual(chunk, "Original evidence")
            return "  2026 dental   policy section  "

        def embed(text: str) -> list[float]:
            embedded.append(text)
            return [0.25, 0.75]

        records = build_contextual_embeddings(
            document="Complete policy",
            chunks=[{"chunk_id": "chunk-1", "text": "Original evidence"}],
            generate_context=generate,
            embed_text=embed,
            context_model="context-model",
            embedding_model="embedding-model",
        )

        self.assertEqual(records[0]["text"], "Original evidence")
        self.assertEqual(records[0]["retrieval_context"], "2026 dental policy section")
        self.assertEqual(
            records[0]["contextual_retrieval_text"],
            "2026 dental policy section\n\nOriginal evidence",
        )
        self.assertEqual(embedded, [records[0]["contextual_retrieval_text"]])
        self.assertEqual(records[0]["embedding"], [0.25, 0.75])
        self.assertEqual(records[0]["embedding_dimensions"], 2)
        self.assertEqual(records[0]["prompt_cache"]["cache_read_input_tokens"], 0)

    def test_reuses_matching_checkpoint(self) -> None:
        existing = {
            "chunk-1": {
                "chunk_id": "chunk-1",
                "text": "Evidence",
                "context_model": "context-model",
                "embedding_model": "embedding-model",
                "prompt_version": PROMPT_VERSION,
                "embedding": [1.0],
            }
        }

        records = build_contextual_embeddings(
            document="Document",
            chunks=[{"chunk_id": "chunk-1", "text": "Evidence"}],
            generate_context=lambda _document, _chunk: self.fail("must reuse"),
            embed_text=lambda _text: self.fail("must reuse"),
            context_model="context-model",
            embedding_model="embedding-model",
            existing=existing,
        )

        self.assertIs(records[0], existing["chunk-1"])


if __name__ == "__main__":
    unittest.main()

