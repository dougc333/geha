import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from finetuning import prepare_retriever_splits as split_module


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


class PrepareRetrieverSplitsTests(unittest.TestCase):
    def test_section_groups_and_toc_are_kept_out_of_training_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            guide = root / "guide.jsonl"
            brochure = root / "brochure.jsonl"
            brochure_qa = root / "brochure-qa.jsonl"
            output = root / "output"
            guide_rows = [
                {"chunk_id": "g-toc", "section": "What's inside", "text": "What's inside\n1 Plans"},
                {"chunk_id": "g-a1", "section": "A", "text": "Useful A1"},
                {"chunk_id": "g-a2", "section": "A", "text": "Useful A2"},
                {"chunk_id": "g-b1", "section": "B", "text": "Useful B1"},
                {"chunk_id": "g-c1", "section": "C", "text": "Useful C1"},
            ]
            brochure_rows = [
                {"chunk_id": "b-toc", "section": "Table of Contents", "text": "Table of Contents\nPlans .... 3"},
                {"chunk_id": "b-1", "section": "Plans", "text": "Useful test content"},
            ]
            write_jsonl(guide, guide_rows)
            write_jsonl(brochure, brochure_rows)
            write_jsonl(
                brochure_qa,
                [
                    {"id": "bad", "source_chunk_ids": ["b-toc"]},
                    {"id": "good", "source_chunk_ids": ["b-1"]},
                ],
            )

            with (
                patch.object(split_module, "GUIDE_CHUNKS", guide),
                patch.object(split_module, "BROCHURE_CHUNKS", brochure),
                patch.object(split_module, "BROCHURE_QA", brochure_qa),
            ):
                summary = split_module.prepare(
                    output, validation_fraction=0.25, seed=7
                )

            train = split_module.read_jsonl(output / "train/chunks.jsonl")
            validation = split_module.read_jsonl(output / "validation/chunks.jsonl")
            filtered = split_module.read_jsonl(
                output / "test/qa_pairs.filtered-existing.jsonl"
            )
            self.assertNotIn("g-toc", {row["chunk_id"] for row in train + validation})
            self.assertTrue(
                {row["section"] for row in train}.isdisjoint(
                    row["section"] for row in validation
                )
            )
            self.assertEqual([row["id"] for row in filtered], ["good"])
            self.assertEqual(summary["existing_test_questions_after_toc_filter"], 1)


if __name__ == "__main__":
    unittest.main()
