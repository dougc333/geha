"""Adapted behavioral repro of https://github.com/langchain-ai/langgraph/issues/8834.
Reported with langgraph 1.2.11 / checkpoint-sqlite 3.1.1. No upstream code fetched/executed.
The demo uses conditional authorization routing; this tests recovery if a router raises.
"""

from importlib.metadata import version
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from support import Fixture, CFG


class RouteState(TypedDict):
    reached: bool


class UpstreamRegressionTests(Fixture):
    def exercise(self, failure_location):
        calls = {"node": 0, "route": 0}

        def node(s):
            calls["node"] += 1
            if failure_location == "node" and calls["node"] == 1:
                raise ValueError("transient")
            return {"reached": False}

        def route(s):
            calls["route"] += 1
            if failure_location == "route" and calls["route"] == 1:
                raise ValueError("transient")
            return "finish"

        builder = StateGraph(RouteState)

        builder.add_node("work", node)

        builder.add_node("finish", lambda s: {"reached": True})

        builder.add_edge(START, "work")
        builder.add_conditional_edges("work", route)

        builder.add_edge("finish", END)

        with SqliteSaver.from_conn_string(str(self.db)) as saver:
            g = builder.compile(checkpointer=saver)
            with self.assertRaisesRegex(ValueError, "transient"):
                g.invoke({"reached": False}, CFG)
            result = g.invoke(None, CFG)
            self.assertTrue(
                result["reached"],
                f"#8834: downstream skipped; langgraph={version('langgraph')}, sqlite={version('langgraph-checkpoint-sqlite')}",
            )

    def test_node_failure_control_recovers(self):
        self.exercise("node")

    def test_router_failure_recovers_without_silent_completion(self):
        self.exercise("route")
