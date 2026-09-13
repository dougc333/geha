"""Opt-in integration test against the running local Langfuse stack."""

import os
import time
import unittest

from dotenv import load_dotenv

load_dotenv()

from failure_demos.demo_failure_distributed_trace import run_distributed_trace_demo
from langfuse import get_client


@unittest.skipUnless(
    os.environ.get("RUN_LANGFUSE_INTEGRATION_TESTS") == "1",
    "set RUN_LANGFUSE_INTEGRATION_TESTS=1 to write a live local Langfuse trace",
)
class DistributedTraceIntegrationTests(unittest.TestCase):
    def test_spawned_processes_form_one_complete_trace_tree(self):
        result = run_distributed_trace_demo(workers=3)
        self.assertTrue(result["all_workers_joined_one_trace"], result)

        client = get_client()
        observations = []
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            observations = client.api.observations.get_many(
                trace_id=result["trace_id"], limit=100
            ).data
            if len(observations) >= 10:
                break
            time.sleep(0.1)

        by_name = {}
        for observation in observations:
            by_name.setdefault(observation.name, []).append(observation)
        root = by_name["distributed-langgraph-parent"][0]
        self.assertIsNone(root.parent_observation_id)
        self.assertEqual(len([o for o in observations if o.name.startswith("worker-process-")]), 3)
        self.assertEqual(
            len([o for o in observations if o.name.startswith("distributed-worker-graph-")]),
            3,
        )
        self.assertEqual(len(by_name.get("calculate", [])), 3)
        for worker in [o for o in observations if o.name.startswith("worker-process-")]:
            self.assertEqual(worker.parent_observation_id, root.id)
