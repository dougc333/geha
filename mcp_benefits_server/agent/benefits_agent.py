"""A LangGraph agent that answers GEHA dental benefit questions using only the MCP server's tools.

The agent never sees tool code: it connects to one MCP deployment, lists the tools that
deployment offers (production by default), and calls them. Locally the server runs as a
subprocess over stdio; once deployed, point --server-url at its HTTPS endpoint instead.

    # local model (free; needs `ollama serve` and a tool-calling model pulled)
    python benefits_agent.py --model ollama:qwen2.5:7b "What do I pay for a crown, D2740?"
    # hosted models (paid per call)
    python benefits_agent.py --model claude "..."      # needs ANTHROPIC_API_KEY
    python benefits_agent.py --model openai "..."      # needs OPENAI_API_KEY
    # a deployed server
    python benefits_agent.py --server-url https://<function-url>/mcp "..."

Run with uv so nothing is installed into the repo's environment:
    uv run --no-project --python 3.12 --with langchain-mcp-adapters --with langgraph \
        --with langchain-ollama python benefits_agent.py ...
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Callable

import httpx
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

SERVER = Path(__file__).resolve().parents[1] / "src" / "server.py"
SYSTEM = """You are a GEHA 2026 dental benefits assistant for federal members.
Use the tools for every fact: rate codes, premiums, procedure classes and policy criteria come
only from tool results, never from memory or your own arithmetic. Cite the source each tool
returns. If no tool can answer, say so plainly. You cannot see member records unless a tool
offers them, and you never submit an enrollment change without the member's explicit approval.
Not affiliated with G.E.H.A; for official answers members should contact GEHA or BENEFEDS."""
WRITE_TOOLS = {"submit_enrollment_change"}
Approve = Callable[[str, dict], bool]


class AwsSigV4Auth(httpx.Auth):
    """httpx auth that signs each request with the caller's AWS credentials (SigV4, service
    "lambda"), as an IAM-authenticated Lambda Function URL requires. Credentials come from the
    usual AWS chain: environment, ~/.aws profile, or the agent's IAM role."""

    requires_request_body = True

    def __init__(self, region: str, credentials=None):
        import boto3
        self.region = region
        self.credentials = credentials or boto3.Session().get_credentials()
        if self.credentials is None:
            raise RuntimeError("No AWS credentials found for signing MCP requests")

    def auth_flow(self, request):
        from botocore.auth import SigV4Auth
        from botocore.awsrequest import AWSRequest
        signed = AWSRequest(method=request.method, url=str(request.url), data=request.content,
                            headers={k: v for k, v in request.headers.items() if k.lower() != "connection"})
        SigV4Auth(self.credentials.get_frozen_credentials(), "lambda", self.region).add_auth(signed)
        request.headers.update(dict(signed.headers))
        yield request


def lambda_url_region(url: str) -> str | None:
    match = re.search(r"\.lambda-url\.([a-z0-9-]+)\.on\.aws", url)
    return match.group(1) if match else None


def server_config(environment: str, server_url: str | None) -> dict[str, Any]:
    """Local stdio subprocess (the server runs in its own uv env with mcp 2.x), or a remote URL:
    a Lambda Function URL is called with SigV4-signed requests; other URLs may use MCP_TOKEN."""
    if server_url:
        connection: dict[str, Any] = {"transport": "streamable_http", "url": server_url}
        if region := lambda_url_region(server_url):
            connection["auth"] = AwsSigV4Auth(region)
        elif os.environ.get("MCP_TOKEN"):
            connection["headers"] = {"Authorization": f"Bearer {os.environ['MCP_TOKEN']}"}
        return {"benefits": connection}
    return {"benefits": {"transport": "stdio", "command": "uv",
                         "args": ["run", "-q", "--no-project", "--python", "3.12", "--with", "mcp>=2,<3",
                                  "python", str(SERVER)],
                         "env": {**os.environ, "MCP_ENV": environment}}}


def chat_model(name: str):
    if name.startswith("ollama:"):
        from langchain_ollama import ChatOllama
        return ChatOllama(model=name.split(":", 1)[1], temperature=0)
    if name == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-sonnet-5-5", max_tokens=2000)
    if name == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=0)
    raise ValueError("--model must be ollama:<model>, claude or openai")


def approval_gate(approve: Approve):
    """Client-side human-in-the-loop: a write call with confirm=true runs only if a human says yes.
    The server also refuses to act without confirm=true, so the two layers back each other up."""
    async def gate(state: MessagesState) -> dict:
        last = state["messages"][-1]
        denied = []
        for call in getattr(last, "tool_calls", []):
            if call["name"] in WRITE_TOOLS and call["args"].get("confirm") and not approve(call["name"], call["args"]):
                denied.append(ToolMessage("The member declined; nothing was submitted.", tool_call_id=call["id"]))
        if denied:
            kept = [c for c in last.tool_calls if c["id"] not in {m.tool_call_id for m in denied}]
            return {"messages": [last.model_copy(update={"tool_calls": kept}), *denied]} if kept else {"messages": denied}
        return {"messages": []}
    return gate


def build_agent(model, tools: list, approve: Approve):
    bound = model.bind_tools(tools)

    async def agent(state: MessagesState):
        return {"messages": [await bound.ainvoke([SystemMessage(SYSTEM), *state["messages"]])]}

    def after_gate(state: MessagesState) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else "agent"

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("approval", approval_gate(approve))
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "approval", "__end__": "__end__"})
    graph.add_conditional_edges("approval", after_gate, ["tools", "agent"])
    graph.add_edge("tools", "agent")
    return graph.compile()


async def ask(question: str, model, *, environment: str = "production", server_url: str | None = None,
              approve: Approve = lambda name, args: False, log: Callable[[str], None] = print) -> dict[str, Any]:
    client = MultiServerMCPClient(server_config(environment, server_url))
    tools = await client.get_tools()
    log(f"[{environment if not server_url else server_url}] tools offered: {', '.join(t.name for t in tools)}")
    state = await build_agent(model, tools, approve).ainvoke({"messages": [HumanMessage(question)]},
                                                              {"recursion_limit": 20})
    calls = []
    for message in state["messages"]:
        for call in getattr(message, "tool_calls", []) or []:
            calls.append(call)
            log(f"  -> {call['name']}({json.dumps(call['args'])})")
        if isinstance(message, ToolMessage):
            log(f"  <- {str(message.content)[:200]}")
    answer = next((m.content for m in reversed(state["messages"]) if isinstance(m, AIMessage) and not m.tool_calls), "")
    return {"answer": answer, "tool_calls": calls, "tools_offered": [t.name for t in tools]}


def ask_human(name: str, args: dict) -> bool:
    reply = input(f"\nApprove {name}({json.dumps(args)})? [y/N] ")
    return reply.strip().lower() in {"y", "yes"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question")
    parser.add_argument("--model", default="ollama:qwen2.5:7b")
    parser.add_argument("--env", default="production", choices=("production", "pilot", "sandbox"))
    parser.add_argument("--server-url", help="a deployed MCP endpoint instead of the local subprocess")
    args = parser.parse_args()
    result = asyncio.run(ask(args.question, chat_model(args.model), environment=args.env,
                             server_url=args.server_url, approve=ask_human))
    print(f"\n{result['answer']}")


if __name__ == "__main__":
    sys.exit(main())
