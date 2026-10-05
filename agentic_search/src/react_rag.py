"""ReAct-style agentic search: the model decides when, what and how often to search.

Unlike agentic_rag.py, whose graph fixes the steps and asks the LLM only yes/no questions,
here a tool-calling model drives the loop. It calls `search_documents` as many times as it
needs (for example once per part of a multi-part question) and answers when it has enough.
A search budget bounds the loop; once it is spent the model must answer without tools.

    agent --tool calls?--> search --> agent --> ... --> answer

    python react_rag.py --pdf ../data/2310.11511v1.pdf "How does Self-RAG differ from CRAG?"
"""

from __future__ import annotations

import argparse
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from rag_client_class import RagClient

NOT_FOUND = "I could not find this in the documents."
SYSTEM = (
    "You answer questions using only passages returned by the search_documents tool. "
    "Search before answering. If the passages do not answer the question, search again with a "
    "different or narrower query; for a question with several parts, search for each part. "
    "When you have enough, answer from the passages only and cite them by number, like [2]. "
    f"If nothing relevant turns up, reply exactly: {NOT_FOUND}"
)
BUDGET_SPENT = "Search budget used up. Answer now from the passages found so far."


class search_documents(BaseModel):
    """Search the indexed PDF documents and return the most relevant passages."""

    query: str = Field(description="A focused search query.")


class State(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    passages: list[str]    # every distinct passage found, in the order first seen; [n] cites passages[n-1]
    searches: int
    trace: list[str]


class ReactRag:
    """Wraps a RagClient's retriever and reranker as a tool for a tool-calling chat model."""

    def __init__(self, client: RagClient, *, reranker_model: str = "none", max_searches: int = 4,
                 passages_per_search: int = 3, llm: Any = None) -> None:
        self.client, self.reranker_model = client, reranker_model
        self.max_searches, self.passages_per_search = max_searches, passages_per_search
        llm = llm or client.llm
        self.agent_llm = llm.bind_tools([search_documents])
        # Same tool schema so the history's tool calls stay valid, but the model must answer.
        self.final_llm = llm.bind_tools([search_documents], tool_choice="none")
        self.graph = self._build()

    # nodes
    def _agent(self, s: State) -> State:
        llm = self.final_llm if s["searches"] >= self.max_searches else self.agent_llm
        message = llm.invoke(s["messages"])
        step = (f"decide: search x{len(message.tool_calls)}" if getattr(message, "tool_calls", None)
                else "answer")
        return {"messages": [message], "trace": s["trace"] + [step]}

    def _search(self, s: State) -> State:
        passages, searches, trace, replies = list(s["passages"]), s["searches"], list(s["trace"]), []
        for call in s["messages"][-1].tool_calls:
            if searches >= self.max_searches:
                replies.append(ToolMessage(BUDGET_SPENT, tool_call_id=call["id"]))
                trace.append("search: budget spent")
                continue
            query = call["args"].get("query", "")
            docs = self.client.retriever.invoke(query)
            found = self.client.reranker.rerank(docs, query, model=self.reranker_model)[:self.passages_per_search]
            new = [p for p in dict.fromkeys(found) if p not in passages]
            passages += new
            searches += 1
            lines = [f"[{passages.index(p) + 1}] {p}" for p in found]
            replies.append(ToolMessage("\n\n".join(lines) or "No passages found.", tool_call_id=call["id"]))
            trace.append(f"search: {query} ({len(new)} new)")
        return {"messages": replies, "passages": passages, "searches": searches, "trace": trace}

    # routing
    def _after_agent(self, s: State) -> str:
        # Once the budget is spent the agent was called with tool_choice="none"; stop even if a
        # model ignores that, so the loop always ends.
        wants_search = bool(getattr(s["messages"][-1], "tool_calls", None))
        return "search" if wants_search and s["searches"] < self.max_searches else END

    def _build(self):
        g = StateGraph(State)
        g.add_node("agent", self._agent)
        g.add_node("search", self._search)
        g.add_edge(START, "agent")
        g.add_conditional_edges("agent", self._after_agent, ["search", END])
        g.add_edge("search", "agent")
        return g.compile()

    def generate(self, question: str) -> dict[str, Any]:
        """Same keys as RagClient.generate, plus the number of searches and the agent's trace."""
        s = self.graph.invoke(
            {"messages": [SystemMessage(SYSTEM), HumanMessage(question)], "passages": [], "searches": 0,
             "trace": []},
            {"recursion_limit": 4 * self.max_searches + 10},
        )
        answers = [m for m in s["messages"] if isinstance(m, AIMessage) and not m.tool_calls]
        response = answers[-1].content if answers else NOT_FOUND
        return {"response": response, "contexts": self.client.format_context(s["passages"]),
                "retrieved_contexts": s["passages"][:3], "searches": s["searches"], "trace": s["trace"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--pdf", nargs="+", default=["../data/2306.02707.pdf"])
    parser.add_argument("--reranker-model", default="none", choices=("none", "gpt"))
    parser.add_argument("--max-searches", type=int, default=4)
    args = parser.parse_args()
    agent = ReactRag(RagClient(files=args.pdf), reranker_model=args.reranker_model, max_searches=args.max_searches)
    result = agent.generate(args.question)
    print("\n".join(result["trace"]))
    print(f"\n{result['response']}")


if __name__ == "__main__":
    main()
