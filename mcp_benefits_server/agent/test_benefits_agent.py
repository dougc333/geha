"""Agent tests against the real MCP server (stdio subprocess) with a scripted model: no LLM calls.

    cd /Users/dc/geha/mcp_benefits_server/agent
    uv run --no-project --python 3.12 --with langchain-mcp-adapters --with langgraph \
        python -m unittest test_benefits_agent -v
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest

from langchain_core.messages import AIMessage, ToolMessage

from benefits_agent import ask

os.environ["MCP_AUDIT_LOG"] = os.path.join(tempfile.mkdtemp(), "audit.jsonl")


class ScriptedModel:
    """Stands in for an LLM: plays back AIMessages and records what it was shown."""

    def __init__(self, *replies):
        self.replies, self.seen, self.bound_tools = list(replies), [], []

    def bind_tools(self, tools, **kwargs):
        self.bound_tools = [t.name for t in tools]
        return self

    async def ainvoke(self, messages):
        self.seen.append(list(messages))
        return self.replies.pop(0)


def call(name, args, call_id="c1"):
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


def run(question, model, **kwargs):
    return asyncio.run(ask(question, model, log=lambda _: None, **kwargs))


class AgentTests(unittest.TestCase):
    def test_answers_from_real_tool_results(self):
        model = ScriptedModel(call("cdt_procedure_class", {"code": "D2740"}), AIMessage("A crown is Class C [page 28]."))
        result = run("Is a crown covered?", model)
        tool_result = next(m for m in model.seen[-1] if isinstance(m, ToolMessage))
        self.assertIn("Class C (major)", str(tool_result.content))
        self.assertEqual(result["answer"], "A crown is Class C [page 28].")

    def test_production_deployment_hides_phi_and_write_tools(self):
        model = ScriptedModel(AIMessage("I can't see member records."))
        result = run("Show my claims", model)
        self.assertEqual(set(result["tools_offered"]), {"rate_code_lookup", "premium_quote", "cdt_procedure_class"})
        self.assertEqual(set(model.bound_tools), set(result["tools_offered"]))

    def test_write_tool_needs_human_approval(self):
        args = {"member_id": "M-100001", "event": "marriage", "action": "change_plan", "confirm": True}
        model = ScriptedModel(call("submit_enrollment_change", args), AIMessage("Not submitted."))
        result = run("Change my plan", model, environment="sandbox", approve=lambda name, a: False)
        declined = next(m for m in model.seen[-1] if isinstance(m, ToolMessage))
        self.assertIn("declined", declined.content)
        self.assertEqual(result["answer"], "Not submitted.")

        model = ScriptedModel(call("submit_enrollment_change", args), AIMessage("Submitted."))
        run("Change my plan", model, environment="sandbox", approve=lambda name, a: True)
        submitted = next(m for m in model.seen[-1] if isinstance(m, ToolMessage))
        self.assertIn("submitted_to_mock", str(submitted.content))

    def test_tool_errors_reach_the_model(self):
        model = ScriptedModel(call("cdt_procedure_class", {"code": "D0000"}), AIMessage("That code isn't listed."))
        run("What is D0000?", model)
        error = next(m for m in model.seen[-1] if isinstance(m, ToolMessage))
        self.assertIn("not listed", str(error.content))


if __name__ == "__main__":
    unittest.main()
