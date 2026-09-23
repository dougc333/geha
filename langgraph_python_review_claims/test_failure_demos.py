import unittest

from failure_demos.demo_failure_concurrency import run_concurrency_demo
from failure_demos.demo_failure_restart import run_restart_demo
from failure_demos.demo_failure_upstream import run_upstream_demo


class FailureDemoTests(unittest.TestCase):
    def test_restart_recovers_committed_interrupt(self):
        result = run_restart_demo()
        self.assertTrue(result["passed"], result)

    def test_concurrent_review_race_is_blocked(self):
        result = run_concurrency_demo()
        self.assertEqual(result["both_workers_observed"], [("review",), ("review",)])
        self.assertEqual(len(result["results"]), 2)
        self.assertEqual(result["accepted_count"], 1)
        self.assertFalse(result["race_detected"], result)

    def test_transient_dependency_is_retried(self):
        result = run_upstream_demo("transient")
        self.assertFalse(result["failed"], result)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["result"]["output"], 42)

    def test_permanent_dependency_exhausts_retry_budget(self):
        result = run_upstream_demo("permanent")
        self.assertTrue(result["failed"], result)
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["error_type"], "ConnectionError")

    def test_timeout_is_reported(self):
        result = run_upstream_demo("timeout")
        self.assertTrue(result["failed"], result)
        self.assertIn("Timeout", result["error_type"])

    def test_invalid_node_output_is_reported(self):
        result = run_upstream_demo("invalid-output")
        self.assertTrue(result["failed"], result)
        self.assertEqual(result["error_type"], "InvalidUpdateError")


if __name__ == "__main__":
    unittest.main()
