from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from aws_data_workflow.docling_preextract import (
    _cached_decision,
    _write_report,
    assess_page,
)


class DoclingPreextractTests(unittest.TestCase):
    def test_accepts_text_with_high_token_recall(self) -> None:
        source = "Coverage requires prior authorization before specialty medication treatment begins."
        result = assess_page(source, source, has_visual_content=False)
        self.assertTrue(result["accepted"])
        self.assertFalse(result["fallback_required"])

    def test_routes_missing_text_to_fallback(self) -> None:
        source = "Coverage requires prior authorization before specialty medication treatment begins."
        result = assess_page("Coverage", source, has_visual_content=False)
        self.assertFalse(result["accepted"])
        self.assertIn("low_embedded_text_recall", result["reasons"])

    def test_routes_unreadable_visual_page_to_fallback(self) -> None:
        result = assess_page("", "", has_visual_content=True)
        self.assertTrue(result["fallback_required"])

    def test_cached_decision_requires_markdown_and_valid_quality_record(self) -> None:
        with TemporaryDirectory() as temp_dir:
            page_dir = Path(temp_dir)
            decision = {"accepted": True, "fallback_required": False}
            (page_dir / "docling.md").write_text("Extracted text\n", encoding="utf-8")
            (page_dir / "docling-quality.json").write_text(
                '{"accepted": true, "fallback_required": false}\n',
                encoding="utf-8",
            )
            self.assertEqual(_cached_decision(page_dir), decision)

    def test_partial_report_is_resumable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            pages_dir = Path(temp_dir)
            decisions = {
                "1": {"accepted": True, "fallback_required": False},
                "2": {"accepted": False, "fallback_required": True},
            }
            report = _write_report(Path("source.pdf"), pages_dir, decisions, 3)
            self.assertEqual(report["status"], "running")
            self.assertEqual(report["completed_pages"], 2)
            self.assertEqual(report["remaining_pages"], 1)
            self.assertEqual(report["fallback_pages"], [2])


if __name__ == "__main__":
    unittest.main()
