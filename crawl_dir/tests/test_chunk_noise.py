from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from crawl_dir.src.pipeline.chunk_noise import (
    build_report,
    compute_run_stats,
    find_runs,
    is_form,
    is_tiny,
    is_toc,
    list_runs,
    load_run_stats,
    loglog_slope,
    resolve_run,
)

TOC = "Contents\nIntroduction ........ 3\nBenefits ........ 7\nExclusions ........ 12\n"
FORM = "Member name ________\nSignature:\nDate of birth:\n"
PROSE = " ".join(["Coverage applies to preventive dental care for members."] * 6)


def write_run(root: Path, family: str, document: str, batch: str, created: str, texts: list[str]) -> None:
    run_dir = root / family / document / batch
    (run_dir / "candidate").mkdir(parents=True)
    (run_dir / "run-manifest.json").write_text(json.dumps({"created_at": created}), encoding="utf-8")
    records = [
        {"chunk_id": f"{document}-{i}", "text": text, "pages": [i + 1]}
        for i, text in enumerate(texts)
    ]
    (run_dir / "candidate" / "chunks.jsonl").write_text(
        "\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8"
    )


class HeuristicTests(unittest.TestCase):
    def test_toc_needs_several_page_references(self):
        self.assertTrue(is_toc(TOC))
        self.assertFalse(is_toc("See page 3 ........ 3"))

    def test_form_needs_several_fields(self):
        self.assertTrue(is_form(FORM))
        self.assertFalse(is_form(PROSE))

    def test_tiny_counts_words(self):
        self.assertTrue(is_tiny("Page 4 of 12"))
        self.assertFalse(is_tiny(PROSE))

    def test_loglog_slope_of_power_law(self):
        self.assertEqual(loglog_slope([(1, 100), (10, 10), (100, 1)]), -1.0)


class ReportTests(unittest.TestCase):
    def test_newest_run_per_document_is_selected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_run(root, "dental", "guide", "batch-a", "2026-10-01", [PROSE])
            write_run(root, "dental", "guide", "batch-b", "2026-10-09", [PROSE])
            self.assertEqual(find_runs(root)["dental/guide"].name, "batch-b")
            self.assertEqual(find_runs(root, "batch-a")["dental/guide"].name, "batch-a")

    def test_shared_template_lines_count_as_boilerplate(self):
        template = "Policy type: medical\nFor internal use only\nDisclaimer applies here"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for i in range(5):
                write_run(root, "policies", f"policy-{i}", "batch", "2026-10-09", [template, PROSE + f" {i}"])
            write_run(root, "dental", "brochure", "batch", "2026-10-09", [TOC, FORM, PROSE])
            report = build_report(root)

        policies = next(group for group in report["families"] if group["group"] == "policies")
        self.assertEqual(policies["boilerplate_chunks"], 5)
        dental = next(row for row in report["documents"] if row["document_id"] == "brochure")
        self.assertEqual((dental["toc"], dental["form"], dental["boilerplate"]), (1, 1, 0))
        self.assertEqual(report["corpus"]["chunks"], 13)


class RunStatsTests(unittest.TestCase):
    def test_stats_are_saved_under_the_run_path_and_reloaded(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs_root, stats_root = Path(temporary) / "runs", Path(temporary) / "stats"
            write_run(runs_root, "research", "ey", "run-1", "2026-10-10", [TOC, PROSE])
            run_id = "research/ey/run-1"
            self.assertEqual([run["id"] for run in list_runs(runs_root)], [run_id])
            self.assertIsNone(load_run_stats(runs_root, stats_root, run_id))

            computed = compute_run_stats(runs_root, stats_root, run_id)
            self.assertTrue((stats_root / run_id / "chunk-noise.json").is_file())
            self.assertEqual(load_run_stats(runs_root, stats_root, run_id), computed)
            self.assertEqual([row["toc"] for row in computed["chunks"]], [True, False])

    def test_run_ids_outside_runs_root_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            runs_root = Path(temporary) / "runs"
            write_run(runs_root, "research", "ey", "run-1", "2026-10-10", [PROSE])
            write_run(Path(temporary) / "elsewhere", "research", "ey", "run-1", "2026-10-10", [PROSE])
            for run_id in ("../elsewhere/research/ey/run-1", "research/ey/run-1/x", "research/ey"):
                with self.assertRaises(ValueError):
                    resolve_run(runs_root, run_id)


if __name__ == "__main__":
    unittest.main()
