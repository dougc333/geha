"""Race two review decisions against one durable LangGraph thread."""

from __future__ import annotations

import json
import multiprocessing as mp
import tempfile
from pathlib import Path

from demo import resume, workflow
from failure_demos.common import CONFIG, receive, stop_process, write_synthetic_inputs


def _review_worker(pipe, base: str, db: str, action: str) -> None:
    try:
        with workflow(Path(db), Path(base)) as graph:
            original_get_state = graph.get_state

            def synchronized_get_state(*args, **kwargs):
                snapshot = original_get_state(*args, **kwargs)
                pipe.send(("ready", snapshot.next))
                pipe.recv()
                return snapshot

            graph.get_state = synchronized_get_state
            try:
                result = resume(graph, "failure-demo", action, f"Concurrent {action}")
                outcome = {"accepted": True, "action": result["review"]["action"]}
            except BaseException as exc:
                outcome = {
                    "accepted": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            pipe.send(("result", outcome))
    except BaseException as exc:
        pipe.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        pipe.close()


def run_concurrency_demo() -> dict:
    ctx = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="geha-concurrency-demo-") as folder:
        base = Path(folder)
        db = base / "checkpoints.sqlite"
        write_synthetic_inputs(base)
        with workflow(db, base) as graph:
            graph.invoke(
                {"claim_id": "CLM-FAILURE-DEMO", "actor": "member"}, CONFIG
            )

        workers = []
        pipes = []
        for action in ("approve", "reject"):
            parent, child = ctx.Pipe()
            process = ctx.Process(
                target=_review_worker, args=(child, str(base), str(db), action)
            )
            process.start()
            child.close()
            workers.append(process)
            pipes.append(parent)

        observed = [receive(pipe, "ready") for pipe in pipes]
        for pipe in pipes:
            pipe.send("go")
        results = [receive(pipe, "result") for pipe in pipes]
        for process, pipe in zip(workers, pipes):
            process.join(5)
            pipe.close()
            stop_process(process)

        with workflow(db, base) as graph:
            final = graph.get_state(CONFIG)

        accepted = sum(bool(result["accepted"]) for result in results)
        return {
            "scenario": "concurrent_human_review_race",
            "both_workers_observed": observed,
            "results": results,
            "accepted_count": accepted,
            "final_review": final.values.get("review"),
            "race_detected": accepted > 1,
            "required_production_control": (
                "cross-process lock or transactional compare-and-set plus idempotency key"
            ),
        }


if __name__ == "__main__":
    print(json.dumps(run_concurrency_demo(), indent=2))
