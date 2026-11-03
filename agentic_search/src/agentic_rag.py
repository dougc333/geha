"""Agentic search over the project's existing retriever, reranker and answer chain.

A LangGraph loop in the style of Corrective RAG (2401.15884) and Self-RAG (2310.11511):

    retrieve -> assess relevance + completeness in one batched call
             -> missing evidence? targeted query and retrieve again (bounded)
             -> generate -> answer supported by the passages? if not, regenerate (bounded)

    python agentic_rag.py --pdf ../data/2310.11511v1.pdf "What reflection tokens does Self-RAG use?"
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
from typing import Any, Callable, TypedDict

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

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


class BatchAssessment(BaseModel):
    """One decision call for every passage returned by a retrieval round."""

    relevant_indices: list[int] = Field(default_factory=list)
    complete: bool = False
    missing: list[str] = Field(default_factory=list)
    next_query: str = ""


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
    complete: bool
    missing: list[str]
    next_query: str
    searched: list[str]


def least_covered_named_target(question: str, passages: list[str]) -> str:
    """Return the question's named system with the weakest paper-title coverage.

    Comparison questions often retrieve many chunks for one named system and
    none for another. Mixed-case names (ReAct), acronyms (CRAG/RAG), and
    hyphenated model names (Self-RAG/DeepSeek-V3) are useful deterministic
    targets when a model emits an empty or repeated corrective query.
    """
    patterns = (
        r"\b[A-Z][a-z]+[A-Z][A-Za-z0-9-]*\b",  # ReAct, ChatGPT
        r"\b[A-Z][A-Za-z0-9]*-[A-Za-z0-9-]+\b",  # Self-RAG, DeepSeek-V3
        r"\b[A-Z]{2,}(?:-[A-Za-z0-9]+)*\b",  # RAG, CRAG
    )
    targets: list[str] = []
    for pattern in patterns:
        for target in re.findall(pattern, question):
            if target not in targets:
                targets.append(target)
    if not targets:
        return ""
    titles = [
        str(getattr(passage, "metadata", {}).get("paper_title") or "").casefold()
        for passage in passages
    ]
    return min(targets, key=lambda target: sum(target.casefold() in title for title in titles))


def queries_too_similar(left: str, right: str) -> bool:
    """Detect exact or lightly paraphrased repeats that add no search diversity."""
    normalize = lambda value: " ".join(re.findall(r"[a-z0-9]+", value.casefold()))
    first, second = normalize(left), normalize(right)
    if not first or not second:
        return first == second
    first_tokens, second_tokens = set(first.split()), set(second.split())
    union = first_tokens | second_tokens
    jaccard = len(first_tokens & second_tokens) / len(union) if union else 1.0
    return jaccard >= 0.70 or difflib.SequenceMatcher(None, first, second).ratio() >= 0.82


class AgenticRag:
    """Bounded corrective RAG over any compatible retriever and answer chain.

    ``assess`` is the preferred production path: it grades the entire retrieval
    batch and checks evidence completeness in one model call.  ``grade`` and
    ``rewrite`` remain for the original local-PDF workflow and backwards tests.
    """

    def __init__(self, client: Any, *, reranker_model: str = "none", max_rewrites: int = 1,
                 max_generations: int = 2, llm: Any = None,
                 grade: Callable[[str, str], bool] | None = None,
                 rewrite: Callable[[str, str], str] | None = None,
                 check: Callable[[str, str], bool] | None = None,
                 assess: Callable[[str, str, list[str], list[str]], Any] | None = None) -> None:
        self.client, self.reranker_model = client, reranker_model
        self.max_rewrites, self.max_generations = max_rewrites, max_generations
        self.assess = assess
        llm = llm or getattr(client, "llm", None)
        if assess is None and grade is None:
            grader = GRADE | llm.with_structured_output(Relevant)
            grade = lambda question, passage: grader.invoke({"question": question, "passage": passage}).relevant
        if assess is None and rewrite is None:
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
        return {"retrieved": passages, "searched": s.get("searched", []) + [s["query"]],
                "trace": s["trace"] + [f"retrieve: {s['query']} ({len(passages)} passages)"]}

    def _grade(self, s: State) -> State:
        if self.assess is not None:
            decision = BatchAssessment.model_validate(
                self.assess(s["question"], s["query"], s["retrieved"], s.get("contexts", []))
            )
            # Model indices are one-based because the prompt labels passages [1], [2], ... .
            keep = [s["retrieved"][i - 1] for i in decision.relevant_indices
                    if 1 <= i <= len(s["retrieved"])]
            accumulated = list(dict.fromkeys(s.get("contexts", []) + keep))
            complete = bool(decision.complete and not decision.missing and accumulated)
            next_query = decision.next_query.strip()
            searched = s.get("searched", [])
            if (not complete and s["rewrites"] < self.max_rewrites
                    and (not next_query or any(queries_too_similar(next_query, query) for query in searched))):
                # Structured model output is not perfectly reliable.  An empty
                # or repeated next_query must not silently turn corrective RAG
                # into a single-search pipeline, so derive a deterministic
                # fallback from the first unmet evidence requirement.
                named_target = least_covered_named_target(s["question"], accumulated)
                missing = decision.missing[0] if decision.missing else "additional supporting evidence"
                target = f"{named_target}: {missing}" if named_target else missing
                next_query = target[:2000]
                if any(queries_too_similar(next_query, query) for query in searched):
                    focus = named_target or "uncovered"
                    next_query = f"{focus} paper evidence details limitations"[:2000]
            return {
                "contexts": accumulated,
                "complete": complete,
                "missing": decision.missing,
                "next_query": next_query,
                "trace": s["trace"] + [
                    f"assess batch: {len(keep)}/{len(s['retrieved'])} relevant; "
                    f"{len(accumulated)} accumulated; {'complete' if complete else 'incomplete'}"
                ],
            }
        keep = [p for p in s["retrieved"] if self.grade(s["question"], p)]
        accumulated = list(dict.fromkeys(s.get("contexts", []) + keep))
        return {"contexts": accumulated,
                "trace": s["trace"] + [f"grade: {len(keep)}/{len(s['retrieved'])} relevant"]}

    def _rewrite(self, s: State) -> State:
        query = s.get("next_query", "").strip()
        if not query:
            query = self.rewrite(s["question"], s["query"])
        return {"query": query, "rewrites": s["rewrites"] + 1, "trace": s["trace"] + [f"rewrite: {query}"]}

    def _generate(self, s: State) -> State:
        context = self.client.format_context(s["contexts"])
        values = {"context": context, "question": s["question"]}
        if s.get("response"):
            values.update({
                "previous_response": s["response"],
                "revision_instruction": (
                    "The previous answer failed the grounding check. Remove every unsupported claim, "
                    "use only the supplied evidence, and use only exact citations present in the evidence."
                ),
            })
        response = self.client.chain.invoke(values)
        return {"response": response, "generations": s["generations"] + 1, "trace": s["trace"] + ["generate"]}

    def _check(self, s: State) -> State:
        ok = self.check(self.client.format_context(s["contexts"]), s["response"])
        return {"grounded": ok, "trace": s["trace"] + [f"check: {'grounded' if ok else 'not grounded'}"]}

    def _give_up(self, s: State) -> State:
        return {"response": NOT_FOUND, "grounded": True, "complete": False,
                "missing": s.get("missing", ["No relevant supporting evidence found"]),
                "trace": s["trace"] + ["give up"]}

    # routing
    def _after_grade(self, s: State) -> str:
        if self.assess is not None:
            if s.get("complete") and s.get("contexts"):
                return "generate"
            next_query = s.get("next_query", "").strip()
            not_repeated = not any(
                queries_too_similar(next_query, query) for query in s.get("searched", [])
            )
            if next_query and not_repeated and s["rewrites"] < self.max_rewrites:
                return "rewrite"
            return "generate" if s.get("contexts") else "give_up"
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
        citations = [getattr(p, "metadata", {}) for p in passages if getattr(p, "metadata", None)]
        response = s["response"]
        if self.assess is not None and not s.get("complete", False):
            missing = "; ".join(s.get("missing", [])) or "evidence sufficiency could not be established"
            response += f"\n\nEvidence remains incomplete: {missing}."
        searches = s.get("searched", [])
        return {"response": response, "contexts": self.client.format_context(passages),
                "retrieved_contexts": list(passages), "citations": citations,
                "grounded": s["grounded"], "complete": s.get("complete"),
                "missing": s.get("missing", []), "trace": s["trace"],
                "searches": searches, "retrieval_rounds": len(searches),
                "generation_attempts": s.get("generations", 0)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--pdf", nargs="+", default=["../data/2306.02707.pdf"])
    parser.add_argument("--aws", action="store_true", help="search the deployed AWS paper corpus")
    parser.add_argument("--aws-url", default=os.getenv("AWS_RAG_URL") or os.getenv("CHATBOT_URL"))
    parser.add_argument("--api-key", default=os.getenv("CHATBOT_API_KEY"))
    parser.add_argument("--document-id", action="append", dest="document_ids")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--region", default=os.getenv("AWS_REGION", "us-west-2"))
    parser.add_argument("--nova-model", default=os.getenv("AGENTIC_NOVA_MODEL", "amazon.nova-lite-v1:0"))
    parser.add_argument("--reranker-model", default="none", choices=("none", "gpt"))
    args = parser.parse_args()
    if args.aws:
        from aws_retriever import AwsAgentClient, AwsRagRetriever, BedrockNova
        nova = BedrockNova(region=args.region, model_id=args.nova_model)
        client = AwsAgentClient(
            AwsRagRetriever(args.aws_url, args.api_key, document_ids=args.document_ids, top_k=args.top_k),
            nova,
        )
        agent = AgenticRag(client, assess=nova.assess, check=nova.grounded)
    else:
        from rag_client_class import RagClient
        agent = AgenticRag(RagClient(files=args.pdf), reranker_model=args.reranker_model)
    result = agent.generate(args.question)
    print("\n".join(result["trace"]))
    print(
        f"\nmetrics: retrieval_rounds={result['retrieval_rounds']} "
        f"generation_attempts={result['generation_attempts']} "
        f"complete={result['complete']} grounded={result['grounded']}"
    )
    print(f"\n{result['response']}")


if __name__ == "__main__":
    main()
