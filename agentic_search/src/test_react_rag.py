"""Unit tests for react_rag.py: fakes only, no API key, model download or PDF."""

import unittest
from types import SimpleNamespace

from langchain_core.messages import AIMessage, ToolMessage

from react_rag import BUDGET_SPENT, NOT_FOUND, ReactRag
from reranking_models_class import RerankingModels


class FakeRetriever:
    def __init__(self):
        self.queries = []

    def invoke(self, query):
        self.queries.append(query)
        return [SimpleNamespace(page_content=f"passage about {query}")]


class FakeModel:
    """Plays back scripted replies; records the tool_choice and messages of each call."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def bind_tools(self, tools, **kwargs):
        model = self

        class Bound:
            def invoke(self, messages):
                model.calls.append({"tool_choice": kwargs.get("tool_choice"), "messages": list(messages)})
                return model.replies.pop(0)

        return Bound()


def search(*queries, id_prefix="c"):
    return AIMessage("", tool_calls=[{"name": "search_documents", "args": {"query": q}, "id": f"{id_prefix}{i}"}
                                     for i, q in enumerate(queries)])


def client():
    return SimpleNamespace(retriever=FakeRetriever(), reranker=RerankingModels(),
                           format_context=lambda contexts, limit=3: "\n".join(list(contexts)[:limit]), llm=None)


class ReactRagTests(unittest.TestCase):
    def test_searches_once_then_answers(self):
        c, llm = client(), FakeModel(search("q"), AIMessage("answer [1]"))
        result = ReactRag(c, llm=llm).generate("q")
        self.assertEqual(c.retriever.queries, ["q"])
        self.assertEqual(result["response"], "answer [1]")
        self.assertEqual(result["retrieved_contexts"], ["passage about q"])
        self.assertEqual(result["searches"], 1)
        self.assertEqual(result["trace"], ["decide: search x1", "search: q (1 new)", "answer"])

    def test_model_chooses_follow_up_searches(self):
        c, llm = client(), FakeModel(search("part a", id_prefix="a"), search("part b", id_prefix="b"),
                                     AIMessage("both parts"))
        result = ReactRag(c, llm=llm).generate("a and b?")
        self.assertEqual(c.retriever.queries, ["part a", "part b"])
        self.assertEqual(result["searches"], 2)
        # The second tool result numbers its passage after the first one, so citations stay unique.
        tool_results = [m for m in llm.calls[-1]["messages"] if isinstance(m, ToolMessage)]
        self.assertEqual([m.content for m in tool_results], ["[1] passage about part a", "[2] passage about part b"])
        self.assertEqual([m.tool_call_id for m in tool_results], ["a0", "b0"])

    def test_budget_forces_an_answer_without_tools(self):
        c, llm = client(), FakeModel(search("q1", id_prefix="a"), search("q2", id_prefix="b"), AIMessage("final"))
        result = ReactRag(c, llm=llm, max_searches=2).generate("q")
        self.assertEqual(c.retriever.queries, ["q1", "q2"])
        self.assertEqual([call["tool_choice"] for call in llm.calls], [None, None, "none"])
        self.assertEqual(result["response"], "final")

    def test_parallel_calls_beyond_budget_get_a_reply_but_no_search(self):
        c, llm = client(), FakeModel(search("q1", "q2"), AIMessage("final"))
        result = ReactRag(c, llm=llm, max_searches=1).generate("q")
        self.assertEqual(c.retriever.queries, ["q1"])
        replies = [m for m in llm.calls[-1]["messages"] if isinstance(m, ToolMessage)]
        self.assertEqual([m.tool_call_id for m in replies], ["c0", "c1"])
        self.assertEqual(replies[1].content, BUDGET_SPENT)
        self.assertEqual(result["searches"], 1)

    def test_loop_ends_when_model_ignores_tool_choice_none(self):
        c, llm = client(), FakeModel(search("q1", id_prefix="a"), search("q2", id_prefix="b"))
        result = ReactRag(c, llm=llm, max_searches=1).generate("q")
        self.assertEqual(c.retriever.queries, ["q1"])
        self.assertEqual(result["response"], NOT_FOUND)

    def test_repeated_passages_keep_their_number(self):
        c, llm = client(), FakeModel(search("q", id_prefix="a"), search("q", id_prefix="b"), AIMessage("done"))
        result = ReactRag(c, llm=llm).generate("q")
        self.assertEqual(result["retrieved_contexts"], ["passage about q"])
        self.assertEqual(result["trace"][3], "search: q (0 new)")
        tool_results = [m.content for m in llm.calls[-1]["messages"] if isinstance(m, ToolMessage)]
        self.assertEqual(tool_results, ["[1] passage about q", "[1] passage about q"])

    def test_answer_without_searching(self):
        c, llm = client(), FakeModel(AIMessage(NOT_FOUND))
        result = ReactRag(c, llm=llm).generate("q")
        self.assertEqual(c.retriever.queries, [])
        self.assertEqual(result["response"], NOT_FOUND)
        self.assertEqual(result["retrieved_contexts"], [])


if __name__ == "__main__":
    unittest.main()
