"""Agentic search over the project's existing retriever, reranker and answer chain.

A LangGraph loop in the style of Corrective RAG (2401.15884) and Self-RAG (2310.11511):

    retrieve -> grade passages -> none relevant? rewrite the query and retrieve again (bounded)
             -> generate -> answer supported by the passages? if not, regenerate (bounded)

    python agentic_rag.py --pdf ../data/2310.11511v1.pdf "What reflection tokens does Self-RAG use?"
"""

from __future__ import annotations

import argparse
from typing import Any, Callable, TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from rag_client_class import RagClient

NOT_FOUND = "I could not find this in the documents."
GRADE = ChatPromptTemplate.from_template(
    "QUESTION: {question}\n\nPASSAGE: {passage}\n\nDoes the passage contain information that helps answer the question?")
REWRITE = ChatPromptTemplate.from_template(
    "The search query {query!r} found nothing relevant for the question {question!r}. "
    "Write one better search query for a document search. Return only the query.")
CHECK = ChatPromptTemplate.from_template(
    "CONTEXT:\n{context}\n\nANSWER:\n{response}\n\nIs every claim in the ANSWER supported by the CONTEXT?")


class Relevant(BaseModel):
    relevant: bool


class Grounded(BaseModel):
    grounded: bool


class State(TypedDict, total=False):
    question: str          # the user's question, never changed
    query: str             # the current search query (rewritten on a miss)
    retrieved: list[str]   # passages before grading
    contexts: list[str]    # passages graded relevant
    response: str
    grounded: bool
    rewrites: int
    generations: int
    trace: list[str]


class AgenticRag:
    """Wraps a RagClient; grade, rewrite and check can be injected for tests."""

    def __init__(self, client: RagClient, *, reranker_model: str = "none", max_rewrites: int = 2,
                 max_generations: int = 2, llm: Any = None,
                 grade: Callable[[str, str], bool] | None = None,
                 rewrite: Callable[[str, str], str] | None = None,
                 check: Callable[[str, str], bool] | None = None) -> None:
        self.client, self.reranker_model = client, reranker_model
        self.max_rewrites, self.max_generations = max_rewrites, max_generations
        llm = llm or getattr(client, "llm", None)
        if grade is None:
            grader = GRADE | llm.with_structured_output(Relevant)
            grade = lambda question, passage: grader.invoke({"question": question, "passage": passage}).relevant
        if rewrite is None:
            rewriter = REWRITE | llm | StrOutputParser()
            rewrite = lambda question, query: rewriter.invoke({"question": question, "query": query}).strip()
        if check is None:
            checker = CHECK | llm.with_structured_output(Grounded)
            check = lambda context, response: checker.invoke({"context": context, "response": response}).grounded
        self.grade, self.rewrite, self.check = grade, rewrite, check
        self.graph = self._build()

    # nodes
    def _retrieve(self, s: State) -> State:
        docs = self.client.retriever.invoke(s["query"])
        passages = self.client.reranker.rerank(docs, s["query"], model=self.reranker_model)
        return {"retrieved": passages, "trace": s["trace"] + [f"retrieve: {s['query']}"]}

    def _grade(self, s: State) -> State:
        keep = [p for p in s["retrieved"] if self.grade(s["question"], p)]
        return {"contexts": keep, "trace": s["trace"] + [f"grade: {len(keep)}/{len(s['retrieved'])} relevant"]}

    def _rewrite(self, s: State) -> State:
        query = self.rewrite(s["question"], s["query"])
        return {"query": query, "rewrites": s["rewrites"] + 1, "trace": s["trace"] + [f"rewrite: {query}"]}

    def _generate(self, s: State) -> State:
        context = self.client.format_context(s["contexts"])
        response = self.client.chain.invoke({"context": context, "question": s["question"]})
        return {"response": response, "generations": s["generations"] + 1, "trace": s["trace"] + ["generate"]}

    def _check(self, s: State) -> State:
        ok = self.check(self.client.format_context(s["contexts"]), s["response"])
        return {"grounded": ok, "trace": s["trace"] + [f"check: {'grounded' if ok else 'not grounded'}"]}

    def _give_up(self, s: State) -> State:
        return {"response": NOT_FOUND, "grounded": True, "trace": s["trace"] + ["give up"]}

    # routing
    def _after_grade(self, s: State) -> str:
        if s["contexts"]:
            return "generate"
        return "rewrite" if s["rewrites"] < self.max_rewrites else "give_up"

    def _after_check(self, s: State) -> str:
        return END if s["grounded"] or s["generations"] >= self.max_generations else "generate"

    def _build(self):
        g = StateGraph(State)
        for name, fn in [("retrieve", self._retrieve), ("grade", self._grade), ("rewrite", self._rewrite),
                         ("generate", self._generate), ("check", self._check), ("give_up", self._give_up)]:
            g.add_node(name, fn)
        g.add_edge(START, "retrieve")
        g.add_edge("retrieve", "grade")
        g.add_conditional_edges("grade", self._after_grade, ["generate", "rewrite", "give_up"])
        g.add_edge("rewrite", "retrieve")
        g.add_edge("generate", "check")
        g.add_conditional_edges("check", self._after_check, ["generate", END])
        g.add_edge("give_up", END)
        return g.compile()

    def generate(self, question: str) -> dict[str, Any]:
        """Same keys as RagClient.generate, plus the agent's trace."""
        s = self.graph.invoke({"question": question, "query": question, "rewrites": 0, "generations": 0, "trace": []})
        passages = s.get("contexts") or s.get("retrieved") or [""]
        return {"response": s["response"], "contexts": self.client.format_context(passages),
                "retrieved_contexts": passages[:3], "grounded": s["grounded"], "trace": s["trace"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--pdf", nargs="+", default=["../data/2306.02707.pdf"])
    parser.add_argument("--reranker-model", default="none", choices=("none", "gpt"))
    args = parser.parse_args()
    agent = AgenticRag(RagClient(files=args.pdf), reranker_model=args.reranker_model)
    result = agent.generate(args.question)
    print("\n".join(result["trace"]))
    print(f"\n{result['response']}")


if __name__ == "__main__":
    main()
