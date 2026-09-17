"""Offline tests for the review-only LangGraph routing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from chunking_benchmarks_RAG.policy_review_graph import (
    build_review_graph,
    inspect_staged_table,
    repair_numeric_header,
)


class PolicyReviewGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        (self.directory / "table.html").write_text("<table><tr><td>row</td></tr></table>")
        self.initial = {
            "pdf_filename": "example.pdf",
            "run_dir": str(self.directory),
            "extraction": {
                "outputs": [{"table_number": 1, "heading": "Billing", "page": 2, "rows": 1,
                             "html": "table.html"}]
            },
        }
        self.renderer = lambda _filename, **_kw: {
            "pages": [{"png": str(self.directory / "page.png")}]
        }

    def test_clean_structure_still_requires_visual_review(self) -> None:
        graph = build_review_graph(
            renderer=self.renderer,
            inspector=lambda _path, _table: {"issue": None, "detail": "structure OK"},
        )
        result = graph.invoke(self.initial)
        self.assertEqual(result["status"], "awaiting_visual_review")
        self.assertEqual(result["repair_attempts"], 0)
        self.assertTrue(Path(result["report_path"]).is_file())

    def test_header_issue_repairs_once_then_reinspects(self) -> None:
        calls = []

        def inspect(_path: Path, _table: dict) -> dict:
            calls.append("inspect")
            return ({"issue": "numeric_header_row", "detail": "header"}
                    if len(calls) == 1 else {"issue": None, "detail": "fixed"})

        def repair(_path: Path) -> bool:
            calls.append("repair")
            return True

        graph = build_review_graph(renderer=self.renderer, inspector=inspect, repairer=repair)
        result = graph.invoke(self.initial)
        self.assertEqual(calls, ["inspect", "repair", "inspect"])
        self.assertEqual(result["repaired_tables"], [1])
        self.assertEqual(result["status"], "awaiting_visual_review")

    def test_other_issue_goes_to_human_review(self) -> None:
        graph = build_review_graph(
            renderer=self.renderer,
            inspector=lambda _path, _table: {"issue": "cell_mismatch", "detail": "check"},
        )
        result = graph.invoke(self.initial)
        self.assertEqual(result["status"], "needs_human_review")
        self.assertEqual(result["repair_attempts"], 0)

    def test_missing_image_never_passes(self) -> None:
        def broken_renderer(_filename: str, **_kwargs: object) -> dict:
            raise RuntimeError("renderer unavailable")

        graph = build_review_graph(
            renderer=broken_renderer,
            inspector=lambda _path, _table: {"issue": None, "detail": "structure OK"},
        )
        result = graph.invoke(self.initial)
        self.assertEqual(result["status"], "needs_human_review")
        self.assertEqual(result["findings"][0]["issue"], "missing_page_image")

    def test_real_numeric_header_repair_is_local_and_idempotent(self) -> None:
        path = self.directory / "numeric.html"
        path.write_text(
            '<html><table class="policy-table"><thead><tr><th>0</th><th>1</th>'
            '<th>2</th></tr></thead><tbody><tr><td>Drug Name</td>'
            '<td>HCPCS Code</td><td>Description</td></tr>'
            '<tr><td>Ziihera</td><td>J9276</td><td>Injection</td></tr>'
            '</tbody></table></html>', encoding="utf-8"
        )
        table = {"page": 2}
        self.assertEqual(inspect_staged_table(path, table)["issue"], "numeric_header_row")
        self.assertTrue(repair_numeric_header(path))
        self.assertIsNone(inspect_staged_table(path, table)["issue"])
        self.assertFalse(repair_numeric_header(path))
        self.assertIn("<th>HCPCS Code</th>", path.read_text(encoding="utf-8"))

    def test_visual_iterations_count_header_repair_and_recheck(self) -> None:
        initial = {**self.initial, "vision_model": "test-vision", "chunks": [
            {"chunk_number": 1, "headings": ["Indication criteria"],
             "pages": [2], "text": "Example criteria"},
        ]}
        repaired = False

        def inspect(_path: Path, _table: dict) -> dict:
            return {"issue": None if repaired else "numeric_header_row", "detail": "header"}

        def repair(_path: Path) -> bool:
            nonlocal repaired
            repaired = True
            return True

        def compare(**kwargs: object) -> dict:
            if kwargs["kind"] == "table" and not repaired:
                return {"verdict": "mismatch", "issues": [{"type": "numeric_header_row"}]}
            return {"verdict": "match", "issues": []}

        graph = build_review_graph(
            renderer=self.renderer, inspector=inspect, repairer=repair,
            table_renderer=lambda _html, output, **_kwargs: output,
            comparator=compare,
        )
        result = graph.invoke(initial)
        self.assertEqual([item["total_error_count"] for item in result["iterations"]], [1, 0])
        self.assertEqual([item["chunk_unit_count"] for item in result["iterations"]], [1, 1])
        self.assertEqual(result["status"], "visual_qc_passed_pending_human_review")

    def test_chunk_heading_error_is_counted_without_auto_repair(self) -> None:
        initial = {**self.initial, "vision_model": "test-vision", "chunks": [
            {"chunk_number": 1, "headings": ["Wrong heading"],
             "pages": [2], "text": "Example criteria"},
        ]}

        def compare(**kwargs: object) -> dict:
            if kwargs["kind"] == "chunk":
                return {"verdict": "mismatch", "issues": [{"type": "heading_mismatch"}]}
            return {"verdict": "match", "issues": []}

        graph = build_review_graph(
            renderer=self.renderer,
            inspector=lambda _path, _table: {"issue": None, "detail": "structure OK"},
            table_renderer=lambda _html, output, **_kwargs: output,
            comparator=compare,
        )
        result = graph.invoke(initial)
        self.assertEqual(result["iterations"][0]["chunk_heading_error_count"], 1)
        self.assertEqual(result["iterations"][0]["total_error_count"], 1)
        self.assertEqual(result["status"], "needs_human_review")
        self.assertEqual(result["repair_attempts"], 0)

    def test_visual_api_failure_is_uncertain_not_zero_error_pass(self) -> None:
        initial = {**self.initial, "vision_model": "test-vision", "chunks": []}

        def fail(**_kwargs: object) -> dict:
            raise RuntimeError("network unavailable")

        graph = build_review_graph(
            renderer=self.renderer,
            inspector=lambda _path, _table: {"issue": None, "detail": "structure OK"},
            table_renderer=lambda _html, output, **_kwargs: output,
            comparator=fail,
        )
        result = graph.invoke(initial)
        self.assertEqual(result["iterations"][0]["total_error_count"], 0)
        self.assertEqual(result["iterations"][0]["uncertain_count"], 1)
        self.assertEqual(result["status"], "needs_human_review")


if __name__ == "__main__":
    unittest.main()
