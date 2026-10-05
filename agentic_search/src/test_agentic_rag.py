"""Unit tests for agentic_rag.py: fakes only, no API key, model download or PDF."""

import unittest
from types import SimpleNamespace

from agentic_rag import NOT_FOUND, AgenticRag
from reranking_models_class import RerankingModels


class FakeRetriever:
    def __init__(self):
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        return [SimpleNamespace(page_content=f"passage about {query}")]


class FakeChain:
    def __init__(self):
        self.calls = 0

    def invoke(self, values):
        self.calls += 1
        return f"answer {self.calls} to {values['question']}"


def client():
    return SimpleNamespace(retriever=FakeRetriever(), reranker=RerankingModels(), chain=FakeChain(),
                           format_context=lambda contexts, limit=3: "\n".join(list(contexts)[:limit]), llm=None)


def agent(c, grade=lambda q, p: True, rewrite=lambda q, query: "better " + query, check=lambda ctx, r: True, **kw):
    return AgenticRag(c, grade=grade, rewrite=rewrite, check=check, **kw)


class AgenticRagTests(unittest.TestCase):
    def test_relevant_on_first_try_answers_once(self):
        c = client()
        result = agent(c).generate("q")
        self.assertEqual(c.retriever.queries, ["q"])
        self.assertEqual(c.chain.calls, 1)
        self.assertEqual(result["retrieved_contexts"], ["passage about q"])
        self.assertTrue(result["grounded"])

    def test_rewrites_query_when_nothing_relevant(self):
        c = client()
        result = agent(c, grade=lambda q, p: "better" in p).generate("q")
        self.assertEqual(c.retriever.queries, ["q", "better q"])
        self.assertIn("answer 1", result["response"])

    def test_gives_up_after_max_rewrites(self):
        c = client()
        result = agent(c, grade=lambda q, p: False, max_rewrites=2).generate("q")
        self.assertEqual(len(c.retriever.queries), 3)
        self.assertEqual(c.chain.calls, 0)
        self.assertEqual(result["response"], NOT_FOUND)
        self.assertTrue(result["retrieved_contexts"])

    def test_regenerates_when_answer_not_grounded(self):
        c = client()
        checks = iter([False, True])
        result = agent(c, check=lambda ctx, r: next(checks)).generate("q")
        self.assertEqual(c.chain.calls, 2)
        self.assertIn("answer 2", result["response"])

    def test_regeneration_is_bounded(self):
        c = client()
        result = agent(c, check=lambda ctx, r: False, max_generations=2).generate("q")
        self.assertEqual(c.chain.calls, 2)
        self.assertFalse(result["grounded"])

    def test_answers_from_original_question_not_rewritten_query(self):
        c = client()
        result = agent(c, grade=lambda q, p: "better" in p).generate("q")
        self.assertTrue(result["response"].endswith("to q"))


if __name__ == "__main__":
    unittest.main()
