from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from crawl_dir.src.pipeline.artifact_io import resolve_raw_document
from crawl_dir.src.pipeline.chunks import (
    build_chunk_records,
    validate_chunks,
    validate_embedding_token_lengths,
)
from crawl_dir.src.pipeline.promotion import promote_run
from crawl_dir.src.pipeline.tables import merge_table_fragments


class TableConsolidationTests(unittest.TestCase):
    def test_continuation_fragments_become_one_logical_table(self):
        outputs = [
            {"table_number": 1, "heading": "Billing", "page": 2,
             "header_promoted": False, "header_inherited_from_table": None},
            {"table_number": 2, "heading": "Billing", "page": 3,
             "header_promoted": False, "header_inherited_from_table": 1},
        ]
        frames = {
            1: pd.DataFrame([["Treanda", "J9033"]], columns=["Drug", "HCPCS"]),
            2: pd.DataFrame([["Bendeka", "J9034"]], columns=["Drug", "HCPCS"]),
        }
        merged = merge_table_fragments(outputs, frames)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["source_pages"], [2, 3])
        self.assertEqual(merged[0]["frame"]["HCPCS"].tolist(), ["J9033", "J9034"])


class ChunkContractTests(unittest.TestCase):
    def test_context_and_provenance_are_explicit(self):
        records = build_chunk_records(
            [{"pages": [5], "headings": ["Billing"], "text": "Treanda uses HCPCS code J9033 for one milligram."}],
            document_id="bendamustine", document_version="2026-01",
            plan_year=2026, source_sha256="abc",
        )
        errors, warnings = validate_chunks(records)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertIn("Billing", records[0]["contextualized_text"])
        self.assertEqual(records[0]["pages"], [5])

    def test_contextless_chunk_is_not_silently_accepted(self):
        records = build_chunk_records(
            [{"pages": [], "headings": [], "text": "OncoHealth"}],
            document_id="bendamustine", document_version="2026-01",
            plan_year=2026, source_sha256="abc",
        )
        errors, warnings = validate_chunks(records)
        self.assertIn("missing_page_provenance", {item["issue"] for item in errors})
        self.assertIn("context_too_short", {item["issue"] for item in warnings})

    def test_embedding_overflow_is_a_structural_error(self):
        records = build_chunk_records(
            [{"pages": [1], "headings": ["Benefits"], "text": "one two three four"}],
            document_id="plan", document_version="2026", plan_year=2026,
            source_sha256="abc",
        )
        errors = validate_embedding_token_lengths(
            records,
            encode=lambda value: value.split(),
            max_tokens=3,
        )
        self.assertEqual(errors[0]["issue"], "embedding_token_limit_exceeded")


class SafetyTests(unittest.TestCase):
    def test_raw_path_cannot_escape_family(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "raw" / "medical").mkdir(parents=True)
            with self.assertRaises(ValueError):
                resolve_raw_document(root, "medical", "../../secret.pdf")

    def test_promotion_rejects_unreviewed_run(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            run.mkdir()
            (run / "run-manifest.json").write_text(json.dumps({
                "family": "medical", "document_id": "doc", "document_version": "2026"
            }))
            (run / "qc-report.json").write_text(json.dumps({
                "status": "needs_visual_review", "visual_verification": {"status": "pending"}
            }))
            with self.assertRaises(ValueError):
                promote_run(run, Path(directory) / "reviewed")


if __name__ == "__main__":
    unittest.main()
