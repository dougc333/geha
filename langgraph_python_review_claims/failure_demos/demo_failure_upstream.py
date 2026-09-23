"""Exercise retries, permanent errors, timeouts, and malformed node output."""

from __future__ import annotations

import argparse
import asyncio
import json
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy


class WorkState(TypedDict, total=False):
    input: int
    output: int


def run_upstream_demo(scenario: str) -> dict:
    attempts = {"count": 0}

    def dependency(state: WorkState):
        attempts["count"] += 1
        if scenario == "transient" and attempts["count"] == 1:
            raise ConnectionError("simulated transient dependency failure")
        if scenario == "permanent":
            raise ConnectionError("simulated permanent dependency failure")
        if scenario == "invalid-output":
            return ["node output must be a state update mapping"]
        return {"output": state["input"] * 2}

    async def slow_dependency(state: WorkState):
        attempts["count"] += 1
        await asyncio.sleep(0.2)
        return {"output": state["input"] * 2}

    builder = StateGraph(WorkState)
    builder.add_node(
        "dependency",
        slow_dependency if scenario == "timeout" else dependency,
        retry_policy=RetryPolicy(
            initial_interval=0.01,
            backoff_factor=1.0,
            max_interval=0.01,
            max_attempts=2,
            jitter=False,
            retry_on=ConnectionError,
        ),
        timeout=0.05 if scenario == "timeout" else None,
    )
    builder.add_edge(START, "dependency")
    builder.add_edge("dependency", END)
    graph = builder.compile()
    try:
        result = (
            asyncio.run(graph.ainvoke({"input": 21}))
            if scenario == "timeout"
            else graph.invoke({"input": 21})
        )
        return {
            "scenario": scenario,
            "attempts": attempts["count"],
            "result": result,
            "failed": False,
        }
    except BaseException as exc:
        return {
            "scenario": scenario,
            "attempts": attempts["count"],
            "failed": True,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario", choices=["transient", "permanent", "timeout", "invalid-output"]
    )
    print(json.dumps(run_upstream_demo(parser.parse_args().scenario), indent=2))
