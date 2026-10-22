from __future__ import annotations

import unittest

from aws_data_workflow.policy_rag import (
    answer_policy_question,
    build_answer_prompt,
    retrieve,
)


RECORDS = [
    {
        "chunk_id": "preventive",
        "source_name": "dental-policy.pdf",
        "pages": [12],
        "text": "In-network preventive dental care is covered at 100%.",
        "contextual_retrieval_text": (
            "2026 dental plan preventive services\n\n"
            "In-network preventive dental care is covered at 100%."
        ),
        "embedding": [1.0, 0.0],
        "review_status": "approved",
    },
    {
        "chunk_id": "orthodontia",
        "source_name": "dental-policy.pdf",
        "pages": [28],
        "text": "Orthodontic services are subject to a lifetime maximum.",
        "contextual_retrieval_text": (
            "2026 dental plan orthodontic limitation\n\n"
            "Orthodontic services are subject to a lifetime maximum."
        ),
        "embedding": [0.0, 1.0],
        "review_status": "approved",
    },
]


class PolicyRagTests(unittest.TestCase):
    def test_hybrid_retrieval_returns_relevant_reviewed_chunk(self) -> None:
        results = retrieve(
            "Is preventive dental care covered?",
            RECORDS,
            embed_query=lambda _query: [1.0, 0.0],
            top_k=1,
        )
        self.assertEqual(results[0]["chunk_id"], "preventive")

    def test_unreviewed_chunks_are_excluded_by_default(self) -> None:
        pending = [{**RECORDS[0], "review_status": "pending"}]
        self.assertEqual(
            retrieve("preventive", pending, embed_query=lambda _query: [1.0, 0.0]),
            [],
        )

    def test_answer_uses_original_evidence_and_numbered_sources(self) -> None:
        seen_prompt: list[str] = []

        def answer(query, sources):
            seen_prompt.append(build_answer_prompt(query, sources))
            return "It is covered in network [1]."

        result = answer_policy_question(
            "Is preventive care covered?",
            RECORDS,
            embed_query=lambda _query: [1.0, 0.0],
            generate_answer=answer,
            top_k=1,
        )
        self.assertEqual(result["sources"][0]["pages"], [12])
        self.assertIn("[1] dental-policy.pdf page 12", seen_prompt[0])
        self.assertIn(RECORDS[0]["text"], seen_prompt[0])
        self.assertNotIn("2026 dental plan preventive services", seen_prompt[0])


if __name__ == "__main__":
    unittest.main()

