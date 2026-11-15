from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from .run_store import DurableRun, RunStore


class RunStoreTests(unittest.TestCase):
    def test_events_and_terminal_status_survive_reopening_database(self):
        with TemporaryDirectory() as temporary:
            database = Path(temporary) / "state.sqlite3"
            store = RunStore(database)
            store.create("run-1", "forms/bill-of-lading.pdf")
            run = DurableRun(store, "run-1")

            run.emit({"type": "agent_started"})
            run.emit({"type": "page_ready", "page": 1})

            reopened = RunStore(database)
            events, complete = reopened.snapshot("run-1", 0)
            self.assertEqual([event["seq"] for event in events], [1, 2])
            self.assertFalse(complete)

            run.finish()
            events, complete = reopened.snapshot("run-1", 1)
            self.assertEqual([event["seq"] for event in events], [2])
            self.assertTrue(complete)
            self.assertEqual(reopened.get("run-1")["status"], "succeeded")

    def test_agent_error_persists_failed_status(self):
        with TemporaryDirectory() as temporary:
            store = RunStore(Path(temporary) / "state.sqlite3")
            store.create("run-2", "forms/bill-of-lading.pdf")
            run = DurableRun(store, "run-2")

            run.emit({"type": "agent_error", "message": "failed"})
            run.finish()

            record = store.get("run-2")
            self.assertEqual(record["status"], "failed")
            self.assertIn("failed", record["error"])


if __name__ == "__main__":
    unittest.main()
