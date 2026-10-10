"""Fast unit tests for the RAG components used by the corpus agent."""

import unittest
from types import SimpleNamespace

from rag_client_class import RagClient
from reranking_models_class import RerankingModels


class FakeChain:
    def invoke(self, values):
        return f"answer: {values['question']}"


class RagComponentTests(unittest.TestCase):
    def test_reranker_passthrough_returns_document_text(self):
        docs = [SimpleNamespace(page_content="one"), SimpleNamespace(page_content="two")]
        self.assertEqual(RerankingModels().rerank(docs, "question", model="none"), ["one", "two"])

    def test_format_context_applies_limit(self):
        self.assertEqual(RagClient.format_context(["one", "two", "three"], limit=2), "one\ntwo")

    def test_generate_returns_answer_and_context(self):
        client = RagClient.__new__(RagClient)
        client.retriever = SimpleNamespace(
            invoke=lambda query: [SimpleNamespace(page_content=f"evidence for {query}")]
        )
        client.reranker = RerankingModels()
        client.chain = FakeChain()

        result = client.generate("What is covered?", reranker_model="none")

        self.assertEqual(result["response"], "answer: What is covered?")
        self.assertEqual(result["contexts"], "evidence for What is covered?")


if __name__ == "__main__":
    unittest.main()
