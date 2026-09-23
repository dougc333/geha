"""Disposable fixtures and bounded, spawn-based worker management."""

import json
import multiprocessing as mp
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo import workflow, resume, make_graph
from langgraph.checkpoint.sqlite import SqliteSaver

CFG = {"configurable": {"thread_id": "case"}}


def worker(pipe, base, db, mode, action="approve"):
    try:
        if mode == "inspect":
            with workflow(db, base) as g:
                s = g.get_state(CFG)
                pipe.send(("result", {"state": s.values, "next": s.next}))
            return
        with workflow(db, base) as g:
            if mode == "start_crash":
                g.invoke({"claim_id": "CLM-1", "actor": "member"}, CFG)
                pipe.send(("ready", "interrupt committed"))
                pipe.recv()
            elif mode == "before_commit":
                # Test-only hook: halt before the first checkpoint put on resume.
                original = g.checkpointer.put

                def gate(*args, **kwargs):
                    pipe.send(("ready", "before checkpoint put"))
                    pipe.recv()
                    return original(*args, **kwargs)

                g.checkpointer.put = gate
                resume(g, "case", action, "Crash test")
            elif mode == "complete_crash":
                resume(g, "case", action, "Crash test")
                pipe.send(("ready", "completion committed"))
                pipe.recv()
            elif mode == "race":
                original = g.get_state
                first_read = True

                def gate(*args, **kwargs):
                    nonlocal first_read
                    s = original(*args, **kwargs)
                    if first_read:
                        first_read = False
                        pipe.send(("ready", s.next))
                        pipe.recv()
                    return s

                g.get_state = gate
                try:
                    result = resume(g, "case", action, "Concurrent test")
                    pipe.send(
                        (
                            "result",
                            {"accepted": True, "action": result["review"]["action"]},
                        )
                    )
                except ValueError as exc:
                    pipe.send(("result", {"accepted": False, "error": str(exc)}))
            elif mode == "recover":
                snap = g.get_state(CFG)
                if snap.next:
                    # Resume durable pending work; don't inject a second decision
                    # if the original resume value was already persisted.
                    result = g.invoke(None, CFG)
                    if g.get_state(CFG).next == ("review",):
                        result = resume(g, "case", "approve", "Recovery test")
                else:
                    result = snap.values
                pipe.send(("result", {"state": result, "next": g.get_state(CFG).next}))
    except BaseException as exc:
        pipe.send(("error", f"{type(exc).__name__}: {exc}"))
    finally:
        pipe.close()


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="geha-reliability-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.db = self.base / "checkpoints.sqlite"
        folder = self.base / "demo_data"
        folder.mkdir(parents=True)
        self.sources = {
            folder / "claims.json": [
                {"claim_id": "CLM-1", "member_id": "M1", "plan": "Synthetic"}
            ],
            folder / "audit_trails.json": [
                {
                    "claim_id": "CLM-1",
                    "final_status": "PENDING_REVIEW",
                    "stages": [{"status": "PENDING", "note": "Prior auth review"}],
                }
            ],
            folder / "public_reference.json": [],
        }
        for p, value in self.sources.items():
            p.write_text(json.dumps(value))
        self.originals = {p: p.read_bytes() for p in self.sources}
        self.addCleanup(self.check_sources)

    def check_sources(self):
        for p, value in self.originals.items():
            self.assertEqual(p.read_bytes(), value)

    def start(self):
        with workflow(self.db, self.base) as g:
            g.invoke({"claim_id": "CLM-1", "actor": "member"}, CFG)

    def launch(self, mode, action="approve"):
        ctx = mp.get_context("spawn")
        parent, child = ctx.Pipe()
        proc = ctx.Process(
            target=worker, args=(child, self.base, self.db, mode, action)
        )
        proc.start()
        child.close()

        def cleanup():
            if proc.is_alive():
                proc.kill()
            proc.join(5)
            parent.close()
            self.assertFalse(proc.is_alive(), "Worker did not exit")
            proc.close()

        self.addCleanup(cleanup)
        return proc, parent

    def receive(self, pipe, kind):
        self.assertTrue(pipe.poll(20), "Worker timed out")
        actual, value = pipe.recv()
        self.assertEqual(actual, kind, value)
        return value

    def kill_at_gate(self, mode):
        proc, pipe = self.launch(mode)
        self.receive(pipe, "ready")
        proc.kill()
        proc.join(5)
        self.assertIsNotNone(proc.exitcode)
        self.assertNotEqual(proc.exitcode, 0)
        with closing(sqlite3.connect(self.db)) as c:
            self.assertEqual(c.execute("PRAGMA integrity_check").fetchone()[0], "ok")

    def inspect(self):
        proc, pipe = self.launch("inspect")
        result = self.receive(pipe, "result")
        proc.join(5)
        self.assertEqual(proc.exitcode, 0)
        return result
