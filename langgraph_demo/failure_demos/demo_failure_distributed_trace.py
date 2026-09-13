"""Attach concurrent LangGraph worker processes to one Langfuse trace."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import uuid
from typing import TypedDict

from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler
from langgraph.graph import END, START, StateGraph

from failure_demos.common import receive, stop_process
from langfuse_app import checked_client, settings_from_env


class WorkerState(TypedDict):
    worker: int
    result: int


def _worker(pipe, trace_id: str, parent_span_id: str, worker_id: int) -> None:
    try:
        settings = settings_from_env()
        client = checked_client(settings)

        def calculate(state: WorkerState):
            return {"result": state["worker"] * state["worker"]}

        builder = StateGraph(WorkerState)
        builder.add_node("calculate", calculate)
        builder.add_edge(START, "calculate")
        builder.add_edge("calculate", END)
        graph = builder.compile()

        with client.start_as_current_observation(
            trace_context={"trace_id": trace_id, "parent_span_id": parent_span_id},
            name=f"worker-process-{worker_id}",
            as_type="agent",
            input={"worker": worker_id},
            metadata={"pid_worker": worker_id, "transport": "multiprocessing"},
        ) as span:
            with propagate_attributes(
                session_id=trace_id,
                tags=["distributed", "multiprocessing", "langgraph"],
                metadata={"worker": worker_id},
            ):
                result = graph.invoke(
                    {"worker": worker_id, "result": 0},
                    config={
                        "callbacks": [CallbackHandler()],
                        "run_name": f"distributed-worker-graph-{worker_id}",
                    },
                )
            span.update(output=result)
            worker_result = {
                "worker": worker_id,
                "result": result["result"],
                "trace_id": span.trace_id,
                "span_id": span.id,
            }
        client.flush()
        pipe.send(("result", worker_result))
    except BaseException as exc:
        pipe.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        pipe.close()


def run_distributed_trace_demo(workers: int = 4) -> dict:
    if workers < 2:
        raise ValueError("Use at least two workers to demonstrate distributed tracing")
    settings = settings_from_env()
    client = checked_client(settings)
    run_id = str(uuid.uuid4())
    ctx = mp.get_context("spawn")

    with client.start_as_current_observation(
        name="distributed-langgraph-parent",
        as_type="agent",
        input={"workers": workers, "run_id": run_id},
    ) as parent_span:
        trace_id = parent_span.trace_id
        processes = []
        pipes = []
        for worker_id in range(workers):
            parent, child = ctx.Pipe()
            process = ctx.Process(
                target=_worker,
                args=(child, trace_id, parent_span.id, worker_id),
            )
            process.start()
            child.close()
            processes.append(process)
            pipes.append(parent)
        results = [receive(pipe, "result", timeout=30) for pipe in pipes]
        for process, pipe in zip(processes, pipes):
            process.join(10)
            pipe.close()
            stop_process(process)
        parent_span.update(output={"worker_results": results})

    client.flush()
    valid = (
        all(result["trace_id"] == trace_id for result in results)
        and len({result["span_id"] for result in results}) == workers
    )
    return {
        "scenario": "multiprocess_distributed_langgraph_trace",
        "langfuse_base_url": settings.base_url,
        "trace_id": trace_id,
        "parent_span_id": parent_span.id,
        "workers": results,
        "all_workers_joined_one_trace": valid,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    print(json.dumps(run_distributed_trace_demo(parser.parse_args().workers), indent=2))
