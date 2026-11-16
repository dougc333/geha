"""Unit tests for agentic_rag.py: fakes only, no API key, model download or PDF."""

import unittest
from types import SimpleNamespace

from agentic_rag import (
    NOT_FOUND, AgenticRag, BatchAssessment, least_covered_named_target, queries_too_similar,
)
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
        self.values = []

    def invoke(self, values):
        self.calls += 1
        self.values.append(values)
        return f"answer {self.calls} to {values['question']}"


class Passage(str):
    def __new__(cls, text, paper_title):
        value = super().__new__(cls, text)
        value.metadata = {"paper_title": paper_title}
        return value


def client():
    return SimpleNamespace(retriever=FakeRetriever(), reranker=RerankingModels(), chain=FakeChain(),
                           format_context=lambda contexts, limit=3: "\n".join(list(contexts)[:limit]), llm=None)


def agent(c, grade=lambda q, p: True, rewrite=lambda q, query: "better " + query, check=lambda ctx, r: True, **kw):
    return AgenticRag(c, grade=grade, rewrite=rewrite, check=check, **kw)


class AgenticRagTests(unittest.TestCase):
    def test_detects_semantically_repeated_search_query(self):
        original = "Compare RAG, ReAct, and Self-RAG. Identify when retrieval starts and one limitation."
        repeat = "Compare RAG, ReAct, and Self-RAG in terms of when retrieval is initiated and limitations."
        self.assertTrue(queries_too_similar(original, repeat))
        self.assertFalse(queries_too_similar(original, "ReAct reasoning actions observations limitations"))

    def test_least_covered_named_target_uses_paper_metadata(self):
        passages = [
            Passage("one", "Self-RAG: Learning to Retrieve"),
            Passage("two", "Self-RAG: Learning to Retrieve"),
            Passage("three", "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"),
        ]
        target = least_covered_named_target("Compare RAG, ReAct, and Self-RAG", passages)
        self.assertEqual(target, "ReAct")

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
        self.assertEqual(c.chain.values[1]["previous_response"], "answer 1 to q")
        self.assertIn("failed the grounding check", c.chain.values[1]["revision_instruction"])

    def test_regeneration_is_bounded(self):
        c = client()
        result = agent(c, check=lambda ctx, r: False, max_generations=2).generate("q")
        self.assertEqual(c.chain.calls, 2)
        self.assertFalse(result["grounded"])

    def test_answers_from_original_question_not_rewritten_query(self):
        c = client()
        result = agent(c, grade=lambda q, p: "better" in p).generate("q")
        self.assertTrue(result["response"].endswith("to q"))

    def test_batch_assessment_is_one_call_per_retrieval_round(self):
        c = client()
        decisions = iter([
            BatchAssessment(relevant_indices=[1], complete=False, missing=["reflection tokens"],
                            next_query="Self-RAG reflection tokens"),
            BatchAssessment(relevant_indices=[1], complete=True),
        ])
        calls = []

        def assess(question, query, passages, accumulated):
            calls.append((query, len(passages), len(accumulated)))
            return next(decisions)

        result = AgenticRag(c, assess=assess, check=lambda ctx, r: True).generate("compare RAG and Self-RAG")
        self.assertEqual(c.retriever.queries, ["compare RAG and Self-RAG", "Self-RAG reflection tokens"])
        self.assertEqual(calls, [("compare RAG and Self-RAG", 1, 0), ("Self-RAG reflection tokens", 1, 1)])
        self.assertTrue(result["complete"])
        self.assertEqual(c.chain.calls, 1)

    def test_batch_assessment_discloses_incomplete_evidence(self):
        c = client()
        decision = BatchAssessment(relevant_indices=[1], complete=False, missing=["reported latency"])
        result = AgenticRag(c, assess=lambda *args: decision, check=lambda ctx, r: True).generate("q")
        self.assertIn("Evidence remains incomplete: reported latency", result["response"])
        self.assertFalse(result["complete"])

    def test_empty_next_query_gets_deterministic_corrective_search(self):
        c = client()
        decisions = iter([
            BatchAssessment(relevant_indices=[1], complete=False, missing=["ReAct limitations"]),
            BatchAssessment(relevant_indices=[1], complete=True),
        ])
        result = AgenticRag(
            c, assess=lambda *args: next(decisions), check=lambda ctx, r: True
        ).generate("compare RAG and ReAct")
        self.assertEqual(c.retriever.queries, [
            "compare RAG and ReAct",
            "ReAct: ReAct limitations",
        ])
        self.assertEqual(result["retrieval_rounds"], 2)
        self.assertTrue(result["complete"])

    def test_repeated_next_query_gets_deterministic_corrective_search(self):
        c = client()
        decisions = iter([
            BatchAssessment(
                relevant_indices=[1], complete=False, missing=["ReAct limitations"],
                next_query="compare RAG and ReAct",
            ),
            BatchAssessment(relevant_indices=[1], complete=True),
        ])
        result = AgenticRag(
            c, assess=lambda *args: next(decisions), check=lambda ctx, r: True
        ).generate("compare RAG and ReAct")
        self.assertEqual(c.retriever.queries[1], "ReAct: ReAct limitations")
        self.assertEqual(result["retrieval_rounds"], 2)

    def test_paraphrased_next_query_gets_targeted_corrective_search(self):
        c = client()
        decisions = iter([
            BatchAssessment(
                relevant_indices=[1], complete=False, missing=["comparison and limitations"],
                next_query="Compare RAG and ReAct in terms of their limitations",
            ),
            BatchAssessment(relevant_indices=[1], complete=True),
        ])
        result = AgenticRag(
            c, assess=lambda *args: next(decisions), check=lambda ctx, r: True
        ).generate("Compare RAG and ReAct and identify their limitations")
        self.assertTrue(c.retriever.queries[1].startswith("ReAct:"))
        self.assertEqual(result["retrieval_rounds"], 2)


if __name__ == "__main__":
    unittest.main()
