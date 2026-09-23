"""Kill a worker after an interrupt checkpoint, then recover in a new process."""

from __future__ import annotations

import json
import multiprocessing as mp
import tempfile
from pathlib import Path

from demo import resume, workflow
from failure_demos.common import CONFIG, receive, stop_process, write_synthetic_inputs


def _start_worker(pipe, base: str, db: str) -> None:
    try:
        with workflow(Path(db), Path(base)) as graph:
            graph.invoke({"claim_id": "CLM-FAILURE-DEMO", "actor": "member"}, CONFIG)
            snapshot = graph.get_state(CONFIG)
            pipe.send(("committed", {"next": snapshot.next, "state": snapshot.values}))
            pipe.recv()
    except BaseException as exc:
        pipe.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        pipe.close()


def _recover_worker(pipe, base: str, db: str) -> None:
    try:
        with workflow(Path(db), Path(base)) as graph:
            before = graph.get_state(CONFIG)
            result = resume(graph, "failure-demo", "approve", "Recovered after restart")
            after = graph.get_state(CONFIG)
            pipe.send(
                (
                    "result",
                    {
                        "before_next": before.next,
                        "after_next": after.next,
                        "review_action": result["review"]["action"],
                        "answer_released": bool(result["answer"]),
                    },
                )
            )
    except BaseException as exc:
        pipe.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        pipe.close()


def run_restart_demo() -> dict:
    ctx = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="geha-restart-demo-") as folder:
        base = Path(folder)
        db = base / "checkpoints.sqlite"
        write_synthetic_inputs(base)

        parent, child = ctx.Pipe()
        first = ctx.Process(target=_start_worker, args=(child, str(base), str(db)))
        first.start()
        child.close()
        committed = receive(parent, "committed")
        first.kill()
        first.join(5)
        first_exit = first.exitcode
        parent.close()
        stop_process(first)

        parent, child = ctx.Pipe()
        second = ctx.Process(target=_recover_worker, args=(child, str(base), str(db)))
        second.start()
        child.close()
        recovered = receive(parent, "result")
        second.join(5)
        second_exit = second.exitcode
        parent.close()
        stop_process(second)

        return {
            "scenario": "process_restart_after_interrupt_checkpoint",
            "first_process_exit": first_exit,
            "recovery_process_exit": second_exit,
            "checkpoint_before_kill": committed,
            "recovery": recovered,
            "passed": (
                committed["next"] == ("review",)
                and recovered["before_next"] == ("review",)
                and not recovered["after_next"]
                and recovered["review_action"] == "approve"
            ),
        }


if __name__ == "__main__":
    print(json.dumps(run_restart_demo(), indent=2))
