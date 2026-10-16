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
from crawl_dir.src.pipeline.contextual_retrieval import (
    PROMPT_VERSION,
    contextual_retrieval_prompt,
    contextualize_candidate,
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


class ContextualRetrievalTests(unittest.TestCase):
    def test_prompt_contains_the_whole_document_and_target_chunk(self):
        prompt = contextual_retrieval_prompt("Whole policy text", "Target row")
        self.assertIn("Whole policy text", prompt["system"][1]["text"])
        self.assertEqual(prompt["system"][1]["cache_control"], {"type": "ephemeral"})
        self.assertIn("Target row", prompt["message"])

    def test_contextual_output_is_separate_and_resumable(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            candidate = run / "candidate"
            candidate.mkdir(parents=True)
            (candidate / "document.md").write_text("Full policy about Datroway.")
            chunk = {
                "chunk_id": "datroway-chunk-0001",
                "document_id": "datroway",
                "document_version": "2026",
                "plan_year": 2026,
                "pages": [2],
                "section": "Coverage",
                "content_type": "text",
                "text": "Prior authorization is required.",
                "contextualized_text": "datroway | pages 2 | Coverage\n\nPrior authorization is required.",
                "table_ids": [],
                "source_sha256": "abc",
                "review_status": "pending",
            }
            (candidate / "chunks.jsonl").write_text(json.dumps(chunk) + "\n")
            calls: list[tuple[str, str]] = []

            def generate(document: str, text: str) -> str:
                calls.append((document, text))
                return "This is the Datroway coverage-policy authorization section."

            output = contextualize_candidate(
                run, model="test-claude", generate_context=generate
            )
            record = json.loads(output.read_text().strip())
            self.assertEqual(record["text"], chunk["text"])
            self.assertEqual(record["contextualized_text"], chunk["contextualized_text"])
            self.assertTrue(record["contextual_retrieval_text"].endswith(chunk["text"]))
            self.assertEqual(record["contextual_retrieval_prompt_version"], PROMPT_VERSION)
            contextualize_candidate(run, model="test-claude", generate_context=generate)
            self.assertEqual(len(calls), 1)

    def test_empty_canonical_markdown_blocks_claude(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "run"
            candidate = run / "candidate"
            candidate.mkdir(parents=True)
            (candidate / "document.md").write_text("   \n")
            (candidate / "chunks.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "document.md is empty"):
                contextualize_candidate(
                    run,
                    model="test-claude",
                    generate_context=lambda _document, _chunk: "must not run",
                )


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
