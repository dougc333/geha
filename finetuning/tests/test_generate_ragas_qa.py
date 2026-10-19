import json
import tempfile
import unittest
from pathlib import Path

from finetuning.generate_ragas_qa import (
    SourceChunk,
    compact_qa_record,
    enrich_record,
    load_chunks,
    match_context_to_chunk,
    table_of_contents_reason,
)


class GenerateRagasQaTests(unittest.TestCase):
    def test_table_of_contents_filter_handles_heading_and_layout(self):
        self.assertEqual(
            table_of_contents_reason(
                {
                    "section": "Table of Contents",
                    "text": "Table of Contents\nEligibility .... 5",
                }
            ),
            "toc_heading",
        )
        self.assertEqual(
            table_of_contents_reason(
                {
                    "section": "Unsectioned",
                    "text": "Eligibility .... 5\nEnrollment .... 7\nClaims .... 9\nRates .... 12",
                }
            ),
            "toc_layout",
        )
        self.assertIsNone(
            table_of_contents_reason(
                {
                    "section": "Eligibility",
                    "text": "Eligible members may enroll during Open Season.",
                }
            )
        )

    def test_load_chunks_filters_short_text_and_preserves_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "chunks.jsonl"
            rows = [
                {
                    "chunk_id": "short",
                    "text": "x",
                    "contextualized_text": "tiny",
                    "pages": [1],
                },
                {
                    "chunk_id": "useful",
                    "text": "raw benefit text",
                    "contextualized_text": "Dental benefits and plan details " * 5,
                    "pages": [7, 8],
                    "section": "Benefits",
                    "content_type": "text",
                },
            ]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows))

            chunks = load_chunks(path, min_characters=50)

        self.assertEqual([chunk.chunk_id for chunk in chunks], ["useful"])
        self.assertEqual(chunks[0].pages, (7, 8))
        self.assertEqual(chunks[0].section, "Benefits")

    def test_match_context_to_chunk_handles_excerpt(self):
        chunk = SourceChunk(
            chunk_id="chunk-1",
            text="Annual deductible information is fifty dollars per person.",
            pages=(10,),
            section="Deductible",
            content_type="text",
        )

        self.assertEqual(
            match_context_to_chunk("fifty dollars per person", [chunk]), chunk
        )

    def test_enrich_and_compact_record_add_provenance(self):
        chunk = SourceChunk(
            chunk_id="chunk-1",
            text="The annual deductible is $50 per person.",
            pages=(10,),
            section="Deductible",
            content_type="text",
        )
        record = {
            "user_input": "What is the annual deductible?",
            "reference": "$50 per person.",
            "reference_contexts": [chunk.text],
            "synthesizer_name": "single_hop_specific_query_synthesizer",
        }

        enriched = enrich_record(record, [chunk], 3)
        compact = compact_qa_record(enriched)

        self.assertEqual(compact["id"], "ragas-0003")
        self.assertEqual(compact["source_chunk_ids"], ["chunk-1"])
        self.assertEqual(compact["source_pages"], [10])
        self.assertEqual(compact["question"], record["user_input"])
        self.assertEqual(compact["answer"], record["reference"])


if __name__ == "__main__":
    unittest.main()
