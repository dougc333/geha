"""Smoke tests: each migrated agent builds with PermissionMiddleware attached and enforces
its default policy. Scripted model and stand-in tools: no LLM, MCP server or FHIR server.

    cd /Users/dc/geha
    uv run --no-project --python 3.12 --with 'langchain==1.4.2' --with langchain-anthropic \
        --with langchain-openai --with langchain-mcp-adapters --with pyyaml --with httpx \
        python -m unittest agent_permissions.test_agents_smoke -v
"""

from __future__ import annotations

import asyncio
import importlib
import logging
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool

from agent_permissions import EVENT
from agent_permissions.testing import ScriptedChatModel, call

ROOT = Path(__file__).resolve().parents[1]
logging.getLogger("agent_permissions").setLevel(logging.CRITICAL)


@contextmanager
def agent_module(directory: str, module: str):
    """Import `module` from `directory` the way its scripts do (cwd on sys.path), keeping
    the two hapi agents' same-named modules (agent, tools, learned) apart."""
    shared = ("agent", "tools", "learned", "langgraph_agent", "pharmacy_agent", "benefits_agent")
    saved = {name: sys.modules.pop(name) for name in shared if name in sys.modules}
    sys.path.insert(0, str(ROOT / directory))
    try:
        yield importlib.import_module(module)
    finally:
        sys.path.remove(str(ROOT / directory))
        for name in shared:
            sys.modules.pop(name, None)
        sys.modules.update(saved)


def stand_in(name: str, ran: list) -> StructuredTool:
    async def run(**kwargs):
        ran.append(name)
        return f"{name} ok"
    return StructuredTool.from_function(coroutine=run, name=name, description=f"stand-in for {name}")


def tool_messages(state) -> list[ToolMessage]:
    return [m for m in state["messages"] if isinstance(m, ToolMessage)]


class MigratedAgentTests(unittest.TestCase):
    def check(self, app, model, ran, allowed: str, refused: str, run=None):
        """One call the agent's policy allows (it runs) and one it doesn't (refused, and the
        model is told): proof that PermissionMiddleware is wired into this agent."""
        model.replies = [call(allowed, {}, "a"), call(refused, {}, "b"), AIMessage("done")]
        state = asyncio.run((run or app.ainvoke)({"messages": [("user", "q")]}))
        first, second = tool_messages(state)
        self.assertEqual(first.content, f"{allowed} ok")
        self.assertEqual(second.status, "error")
        self.assertIn("Permission denied", second.content)
        self.assertEqual(ran, [allowed])
        return state

    def test_fhir_langgraph_agent(self):
        with agent_module("hapi", "langgraph_agent") as mod:
            ran, model = [], ScriptedChatModel()
            app = mod.build_graph([stand_in("fhir_read", ran), stand_in("fhir_delete", ran)], model=model)
            self.check(app, model, ran, "fhir_read", "fhir_delete")
            self.assertIn("synthetic (Synthea)", model.seen[0][0].content)  # system prompt kept

    def test_pharmacy_agent_reuses_the_graph_with_its_policy(self):
        with agent_module("hapi", "pharmacy_agent") as mod:
            ran, model = [], ScriptedChatModel()
            app = mod.build_graph([stand_in("openfda_search_recalls", ran), stand_in("fhir_update", ran)],
                                  system=mod.SYSTEM, policy=mod.pharmacy_policy(), model=model)
            self.check(app, model, ran, "openfda_search_recalls", "fhir_update")

    def test_fraud_agent_and_its_trace_events(self):
        with agent_module("hapi/fraud", "agent") as mod:
            ran, model = [], ScriptedChatModel()
            tools = [mod.capped(stand_in("provider_billing_summary", ran)), mod.capped(stand_in("shell", ran))]
            app = mod.build(tools, model=model)
            self.check(app, model, ran, "provider_billing_summary", "shell")
            self.assertIn("payment-integrity investigator", model.seen[0][0].content)

            # investigate() reports a refused call as a tool_result (it has no on_tool_end).
            ran.clear()
            events = []

            async def emit(event):
                events.append(event)

            async def fake_tools(limit):
                return tools
            model = ScriptedChatModel(replies=[call("shell", {"command": "ls"}, "s1"),
                                               AIMessage('Report.\n```json\n{"findings": []}\n```')])
            mod.load_tools, mod.chat_model = fake_tools, lambda name: model
            asyncio.run(mod.investigate("q", emit))
            kinds = [e["type"] for e in events]
            self.assertEqual(kinds, ["run_start", "tool_call", "tool_result", "final", "done"])
            result = events[2]
            self.assertTrue(result["is_error"] and result["denied"])
            self.assertEqual(result["call_id"], "s1")
            self.assertEqual(events[3]["findings"], [])
            self.assertEqual(ran, [])

    def test_self_improving_agent_retries_unusable_replies(self):
        with agent_module("hapi/self-improving-agents", "agent") as mod:
            ran, model = [], ScriptedChatModel()
            tools = [mod.capped(stand_in("top_services", ran)), mod.capped(stand_in("fhir_delete", ran))]
            mod.learned_names = lambda statuses: []
            app = mod.build(tools, lessons="Check duplicates first.", model=model)
            self.check(app, model, ran, "top_services", "fhir_delete")
            self.assertIn("Check duplicates first.", model.seen[0][0].content)

            # An empty reply is retried (RetryModelReplies), as the hand-built node did.
            model = ScriptedChatModel(replies=[AIMessage(""), AIMessage("the report")])
            app = mod.build([], model=model)
            state = asyncio.run(app.ainvoke({"messages": [("user", "q")]}))
            self.assertEqual(state["messages"][-1].content, "the report")
            self.assertEqual(len(model.seen), 2)

    def test_self_improving_agent_allows_only_the_learned_tools_requested(self):
        with agent_module("hapi/self-improving-agents", "agent") as mod:
            ran, model = [], ScriptedChatModel()
            mod.learned_names = lambda statuses: ["learned_ok"] if statuses == ("approved",) else []
            app = mod.build([stand_in("learned_ok", ran), stand_in("learned_other", ran)], model=model)
            self.check(app, model, ran, "learned_ok", "learned_other")

    def test_benefits_agent(self):
        with agent_module("mcp_benefits_server/agent", "benefits_agent") as mod:
            ran, model = [], ScriptedChatModel()
            # Unknown tools default to ASK, so the member is asked; here they say no.
            app = mod.build_agent(model, [stand_in("premium_quote", ran), stand_in("member_delete", ran)],
                                  approve=lambda name, args: False)
            self.check(app, model, ran, "premium_quote", "member_delete")

            ran.clear()
            asked = []
            model = ScriptedChatModel(replies=[call("submit_enrollment_change", {"confirm": True}), AIMessage("no")])
            app = mod.build_agent(model, [stand_in("submit_enrollment_change", ran)],
                                  approve=lambda name, args: asked.append(name) or False)
            state = asyncio.run(app.ainvoke({"messages": [("user", "q")]}))
            self.assertEqual(tool_messages(state)[0].content, "The member declined; nothing was submitted.")
            self.assertEqual((asked, ran), (["submit_enrollment_change"], []))


class EventNameTests(unittest.TestCase):
    def test_event_name_is_stable(self):
        # hapi/*/agent.py match on this name to report refused calls to the UI.
        self.assertEqual(EVENT, "permission_decision")


if __name__ == "__main__":
    unittest.main()
