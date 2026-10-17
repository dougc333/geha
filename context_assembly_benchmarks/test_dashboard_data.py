"""Keep the checked-in answer results and React dashboard export in sync."""

import json
import unittest

from context_assembly_benchmarks.build_dashboard_data import DIRECTORY, answer_section


class DashboardAnswerDataTest(unittest.TestCase):
    def test_answer_export_contains_completed_evaluation(self):
        report = json.loads((DIRECTORY / "chunking_judge_results.json").read_text())
        answers = answer_section()

        self.assertIsNotNone(answers)
        self.assertEqual(report["configuration"]["evaluation_version"], 3)
        self.assertEqual(answers["summary"]["queries_completed"], report["summary"]["queries_completed"])
        self.assertEqual(answers["summary"]["queries_requested"], report["summary"]["queries_requested"])
        self.assertEqual(len(answers["cases"]), len(report["results"]))
        self.assertEqual(
            {case["id"] for case in answers["cases"]},
            {case["id"] for case in report["results"]},
        )
        for case in answers["cases"]:
            if case.get("error"):
                continue
            self.assertEqual(set(case["strategies"]), {"flat", "table", "notes"})
            for strategy in case["strategies"].values():
                for fact in strategy["facts"]:
                    expected = (
                        "correct" if fact["in_answer"] else "generation_drop"
                    ) if fact["in_context"] else (
                        "unsupported" if fact["in_answer"] else "assembly_error"
                    )
                    self.assertEqual(fact["cell"], expected)

    def test_checked_in_dashboard_includes_answers(self):
        dashboard = json.loads((DIRECTORY / "dashboard/public/data/dashboard.json").read_text())
        answers = answer_section()

        self.assertEqual(dashboard["answers"], answers)
        self.assertEqual(len(dashboard["context"]["cases"]), answers["summary"]["queries_requested"])


if __name__ == "__main__":
    unittest.main()
