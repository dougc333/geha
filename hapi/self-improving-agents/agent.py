"""Fraud-investigation agent (LangGraph) that reports every step as a trace event.

Tools: the FHIR MCP server's read-only tools (raw records) plus the claims-analytics
tools in tools.py (aggregates). The agent chooses among them; nothing tells it which
providers or schemes to look for. Events (dicts) are passed to `emit` as they happen:

  run_start   question, model, the tools on offer
  thinking    Claude's summarized reasoning before a step
  text        text Claude writes between tool calls
  tool_call   tool chosen and its arguments
  tool_result preview of the result, size, duration, error flag
  final       the report, plus parsed findings JSON if present
  done / error
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
from pathlib import Path
from typing import Awaitable, Callable

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage
from langchain_core.tools import BaseTool, StructuredTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from tools import ANALYTIC_TOOLS

HAPI = Path(__file__).resolve().parent.parent
# Models the agent can run on (ladder.py --model, the app's dropdown). "nous" is Nous
# Research's Portal (OpenAI-compatible; Hermes models): set NOUS_API_KEY, and optionally
# NOUS_MODEL / NOUS_BASE_URL. result_chars is the cap on each tool result, smaller where the
# context window is smaller.
MODELS = {
    "claude": {"provider": "anthropic", "model": "claude-opus-5-5", "result_chars": 30_000,
               "kwargs": {"thinking": {"type": "adaptive", "display": "summarized"}}},
    "sonnet": {"provider": "anthropic", "model": "claude-sonnet-5-5", "result_chars": 30_000,
               "kwargs": {"thinking": {"type": "adaptive", "display": "summarized"}}},
    # Haiku 4.5 takes a thinking budget (not adaptive) and has a 200k context window.
    "haiku": {"provider": "anthropic", "model": "claude-haiku-4-5", "result_chars": 15_000,
              "kwargs": {"thinking": {"type": "enabled", "budget_tokens": 4000}}},
    "gpt-4o": {"provider": "openai-compatible", "model": "gpt-4o", "api_key_env": "OPENAI_API_KEY",
               "result_chars": 8_000, "kwargs": {"temperature": 0}},
    "gpt-5": {"provider": "openai-compatible", "model": "gpt-5", "api_key_env": "OPENAI_API_KEY",
              "result_chars": 15_000, "kwargs": {}},  # gpt-5 only accepts the default temperature
    # Nous Portal is a gateway (no Hermes models listed on 2026-09-30); default to DeepSeek V4 Pro.
    "nous": {"provider": "openai-compatible", "model": os.getenv("NOUS_MODEL", "deepseek/deepseek-v4-pro"),
             "base_url": os.getenv("NOUS_BASE_URL", "https://inference-api.nousresearch.com/v1"),
             "api_key_env": "NOUS_API_KEY", "api_key_alt": "NOUS_KEY", "result_chars": 30_000,
             "kwargs": {"temperature": 0}},
}
DEFAULT_MODEL = "claude"
QUESTION = ("Investigate our claims (ExplanationOfBenefit) for billing fraud, waste or abuse. "
            "Identify the providers most likely involved, the schemes, the evidence (claim ids, "
            "dates, amounts) and the dollars at risk. Check your suspicions against the raw "
            "records before you conclude.")
SYSTEM = """You are a payment-integrity investigator at a health plan. The claims data is a
FHIR R4 server of synthetic members (Synthea) plus whatever the plan has received since.

You have two kinds of tools:
- fhir_search / fhir_read: raw FHIR records (Patient, Practitioner, ExplanationOfBenefit, ...).
- analytics tools: aggregates over all claims (provider rankings, peer cost comparisons,
  duplicates, claims after death, a provider's daily workload).

Work like an investigator: start broad, form hypotheses, test them with the most direct
tool, and confirm the strongest findings in the raw records (read a few of the actual
claims and the patient or practitioner). Don't call the same tool with the same arguments
twice. Resource ids, meta.lastUpdated / versionId and other storage metadata only reflect
how records were loaded, not billing behavior: never use them to find or rank suspects.
Synthetic data has noise; separate isolated oddities from patterns, and say which is
which. Every number you report must come from a tool result.

There may be several schemes, a few small ones, or none at all. Only report a provider
when the evidence supports it; if you find no fraud, say so and return an empty list.

Finish with a short report (per provider: who, what they appear to be doing, evidence,
dollars at risk, confidence), then this block, filled in:
```json
{"findings": [{"provider": "Practitioner/<id>", "name": "...", "scheme": "<what the provider is doing, in your own words>",
  "claims": 0, "amount_at_risk": 0.0, "confidence": "high | medium | low", "evidence": "..."}]}
```"""

LESSONS_HEADER = """

Lessons from earlier investigations. Each was written after a past investigation was
graded against confirmed outcomes. Apply them where they fit; they are general guidance,
not facts about the current data:
"""

Emit = Callable[[dict], Awaitable[None]]
MAX_RESULT_CHARS = 30_000  # ~8k tokens; one unbounded fhir_search returned 3.8 MB and overflowed the context


def as_text(output) -> str:
    """Tool output (MCP tools may return content blocks) as text."""
    if isinstance(output, str):
        return output
    if isinstance(output, list):
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in output)
    return json.dumps(output, default=str)


def capped(tool: BaseTool, limit: int = MAX_RESULT_CHARS) -> BaseTool:
    """Same tool, but results longer than `limit` characters are cut, with a note telling
    the agent how to narrow the call, so a single huge result can't fill its context."""
    async def run(**kwargs):
        # Each MCP call starts the stdio server; the pipe occasionally breaks (seen with four
        # parallel fhir_read calls). Retry, then hand the error to the agent instead of ending the run.
        for attempt in range(3):
            try:
                text = as_text(await tool.ainvoke(kwargs))
                break
            except Exception as exc:
                if attempt == 2:
                    detail = "; ".join(f"{type(e).__name__}: {e}" for e in getattr(exc, "exceptions", [exc]))
                    return f"[TOOL ERROR after 3 attempts: {detail[:300]}. Try the call again or a different one.]"
                await asyncio.sleep(0.5 * (attempt + 1))
        if len(text) <= limit:
            return text
        return (text[:limit] + f"\n\n[TRUNCATED: the result was {len(text):,} characters; only the first "
                f"{limit:,} are shown. Narrow the call (smaller _count, _elements, more search filters) "
                "or use an analytics tool for aggregates.]")
    return StructuredTool(name=tool.name, description=tool.description, args_schema=tool.args_schema,
                          coroutine=run)


def fhir_client() -> MultiServerMCPClient:
    return MultiServerMCPClient({"fhir": {
        "transport": "stdio", "command": str(HAPI / "bin" / "langcare-mcp-fhir"),
        "args": ["-config", str(HAPI / "langcare-config.yaml")]}})


async def load_tools(limit: int = MAX_RESULT_CHARS, learned_statuses: tuple[str, ...] = ("approved",)) -> list:
    """FHIR MCP tools, the analytics tools, and the learned tools a person has approved
    (learned.py; improve.py --auto-approve also passes "trial" for its own test runs)."""
    import learned  # here, not at the top: learned.py imports tools, which agent.py also imports
    fhir = [t for t in await fhir_client().get_tools() if t.name in {"fhir_search", "fhir_read"}]
    return [capped(t, limit) for t in fhir + ANALYTIC_TOOLS + learned.langchain_tools(learned_statuses)]


def tool_source(name: str) -> str:
    return "fhir-mcp" if name.startswith("fhir_") else "analytics"  # learned tools show with the analytics tools


def chat_model(name: str):
    """The chat model for a MODELS entry."""
    spec = MODELS[name]
    if spec["provider"] == "anthropic":
        return ChatAnthropic(model=spec["model"], max_tokens=16000, **spec["kwargs"])
    from langchain_openai import ChatOpenAI  # only needed for OpenAI-compatible providers
    key = os.getenv(spec["api_key_env"]) or os.getenv(spec.get("api_key_alt", ""))
    if not key:
        raise RuntimeError(f"{spec['api_key_env']} is not set (needed for model '{name}')")
    return ChatOpenAI(model=spec["model"], base_url=spec.get("base_url"), api_key=key, max_tokens=8000,
                      **spec["kwargs"])


def build(tools: list, model_name: str = DEFAULT_MODEL, lessons: str = ""):
    model = chat_model(model_name).bind_tools(tools)
    system = SYSTEM + (LESSONS_HEADER + lessons.strip() if lessons.strip() else "")

    async def agent(state: MessagesState):
        return {"messages": [await model.ainvoke([SystemMessage(system), *state["messages"]])]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()


def parse_findings(text: str) -> list[dict] | None:
    """The findings list from the report: a ```json block, or a bare {"findings": ...} object
    (not every model fences its JSON)."""
    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    bare = text.rfind('{"findings"')
    if bare >= 0:
        candidates.append(text[bare:text.rfind("}") + 1])
    for candidate in candidates:
        try:
            findings = json.loads(candidate).get("findings")
        except (json.JSONDecodeError, AttributeError):
            continue
        if isinstance(findings, list):
            return findings
    return None


async def investigate(question: str, emit: Emit, model_name: str = DEFAULT_MODEL, lessons: str = "",
                      learned_statuses: tuple[str, ...] = ("approved",)) -> None:
    started = time.perf_counter()
    spec = MODELS[model_name]
    tools = await load_tools(spec["result_chars"], learned_statuses)
    await emit({"type": "run_start", "question": question, "model": spec["model"], "model_option": model_name,
                "lessons": lessons.strip(),
                "tools": [{"name": t.name, "source": tool_source(t.name),
                           "description": (t.description or "").split("\n")[0][:200]} for t in tools]})
    app = build(tools, model_name, lessons)
    step, calls, tool_started, final_text = 0, 0, {}, ""
    usage = {"input_tokens": 0, "output_tokens": 0}
    async for event in app.astream_events({"messages": [("user", question)]}, version="v2",
                                          config={"recursion_limit": 80}):
        kind = event["event"]
        if kind == "on_chat_model_end":
            message = event["data"]["output"]
            step += 1
            meta = getattr(message, "usage_metadata", None) or {}
            usage["input_tokens"] += meta.get("input_tokens", 0)
            usage["output_tokens"] += meta.get("output_tokens", 0)
            content = message.content if isinstance(message.content, list) else [{"type": "text", "text": message.content}]
            reasoning = (getattr(message, "additional_kwargs", None) or {}).get("reasoning_content")
            if isinstance(reasoning, str) and reasoning.strip():  # OpenAI-compatible reasoning models
                await emit({"type": "thinking", "step": step, "text": reasoning.strip()[:4000]})
            for block in content:
                if block.get("type") == "thinking" and block.get("thinking", "").strip():
                    await emit({"type": "thinking", "step": step, "text": block["thinking"].strip()})
                elif block.get("type") == "text" and block.get("text", "").strip():
                    if message.tool_calls:
                        await emit({"type": "text", "step": step, "text": block["text"].strip()})
                    else:
                        final_text = block["text"].strip()
            for call in message.tool_calls:
                calls += 1
                await emit({"type": "tool_call", "step": step, "call_id": call["id"], "name": call["name"],
                            "source": tool_source(call["name"]), "args": call["args"]})
        elif kind == "on_tool_start":
            tool_started[event["run_id"]] = time.perf_counter()
        elif kind == "on_tool_end":
            output = event["data"].get("output")
            if not getattr(output, "tool_call_id", None):
                continue  # the inner call inside a capped() wrapper; the outer one is reported
            text = getattr(output, "content", output)
            text = text if isinstance(text, str) else json.dumps(text, default=str)
            status = getattr(output, "status", "success")
            await emit({"type": "tool_result", "step": step, "call_id": getattr(output, "tool_call_id", ""),
                        "name": event["name"], "source": tool_source(event["name"]),
                        "ms": round((time.perf_counter() - tool_started.pop(event["run_id"], time.perf_counter())) * 1000),
                        "is_error": status == "error", "size": len(text), "preview": text[:1500],
                        "truncated": "[TRUNCATED: the result was" in text})
    await emit({"type": "final", "text": final_text, "findings": parse_findings(final_text)})
    await emit({"type": "done", "tool_calls": calls, "model_steps": step,
                "seconds": round(time.perf_counter() - started, 1), "usage": usage})
