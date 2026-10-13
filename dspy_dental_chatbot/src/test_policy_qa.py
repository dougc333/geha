"""Tests for local dental-policy retrieval and grounded DSPy synthesis."""

from __future__ import annotations

import unittest
import json
from pathlib import Path
from types import SimpleNamespace

from evaluate_policy_qa import evaluate_retrieval
from policy_qa import DentalPolicyIndex, DentalPolicyQA, PolicyChunk


class FakeProgram:
    def __init__(self, answer: str):
        self.answer = answer
        self.calls: list[dict[str, str]] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(answer=self.answer)


class DentalPolicyQATests(unittest.TestCase):
    def setUp(self):
        self.index = DentalPolicyIndex(
            [
                PolicyChunk(2, "Routine cleanings are covered twice per calendar year."),
                PolicyChunk(7, "Orthodontic services have a separate lifetime maximum."),
            ]
        )

    def test_retrieves_relevant_page_and_passes_it_to_dspy(self):
        program = FakeProgram("Cleanings are covered twice each calendar year [p. 2].")
        qa = DentalPolicyQA(self.index, program=program)

        answer, chunks = qa.ask("How often are routine cleanings covered?")

        self.assertIn("[p. 2]", answer)
        self.assertEqual(chunks[0].page, 2)
        self.assertIn("[p. 2]", program.calls[0]["evidence"])

    def test_does_not_call_dspy_when_retrieval_has_no_match(self):
        program = FakeProgram("This should not be used.")
        qa = DentalPolicyQA(self.index, program=program)

        answer, chunks = qa.ask("volcanic geology")

        self.assertIn("couldn't find", answer)
        self.assertEqual(chunks, [])
        self.assertEqual(program.calls, [])

    def test_rejects_citations_to_pages_not_retrieved(self):
        qa = DentalPolicyQA(self.index, program=FakeProgram("It is covered [p. 99]."))

        answer, _ = qa.ask("Are cleanings covered?")

        self.assertIn("couldn't verify", answer)

    def test_adds_retrieved_page_markers_when_model_omits_citations(self):
        qa = DentalPolicyQA(
            self.index,
            program=FakeProgram("Routine cleanings are covered twice per calendar year."),
        )

        answer, chunks = qa.ask("How often are routine cleanings covered?")

        self.assertEqual(chunks[0].page, 2)
        self.assertIn("Additional retrieved source pages: [p. 2]", answer)

    def test_adds_only_missing_retrieved_page_markers(self):
        program = FakeProgram("D7140 is an extraction with plan cost sharing [p. 5].")
        qa = DentalPolicyQA(self.index, program=program)

        def retrieve(query, top_k):
            return [
                PolicyChunk(26, "D7140 simple extraction", 1.0),
                PolicyChunk(5, "Class B cost sharing", 0.5),
            ]

        answer, _ = qa.ask("What is D7140?", retrieve=retrieve)

        self.assertIn("[p. 5]", answer)
        self.assertIn("Additional retrieved source pages: [p. 26]", answer)

    def test_search_query_isolated_while_full_conversation_reaches_model(self):
        program = FakeProgram("The hearing aid discount is described on page 9 [p. 9].")
        qa = DentalPolicyQA(self.index, program=program)
        search_queries = []

        def retrieve(query, top_k):
            search_queries.append(query)
            return [PolicyChunk(9, "Hearing aid discount", 1.0)]

        qa.ask(
            "What is the hearing aid discount?",
            conversation="Earlier we discussed Walmart glasses and frames.",
            retrieval_query="What is the hearing aid discount?",
            retrieve=retrieve,
        )

        self.assertEqual(search_queries, ["What is the hearing aid discount?"])
        self.assertIn("Walmart glasses", program.calls[0]["conversation"])

    def test_accepts_an_injected_retriever_for_answer_generation(self):
        program = FakeProgram("Frames cost 60% of retail price [p. 7].")
        qa = DentalPolicyQA(self.index, program=program)
        calls = []

        def retrieve(query, top_k):
            calls.append((query, top_k))
            return [PolicyChunk(7, "| Frames | 60% of retail price |", 1.0)]

        answer, chunks = qa.ask("Are Walmart glasses covered?", retrieve=retrieve)

        self.assertEqual(calls, [("Are Walmart glasses covered?", 4)])
        self.assertEqual(chunks[0].page, 7)
        self.assertIn("[p. 7]", answer)

    def test_explicit_retrieval_query_avoids_conversation_contamination(self):
        program = FakeProgram("D7140 is covered [p. 26].")
        qa = DentalPolicyQA(self.index, program=program)
        calls = []

        def retrieve(query, top_k):
            calls.append((query, top_k))
            return [PolicyChunk(26, "D7140 simple extraction", 1.0)]

        answer, _ = qa.ask(
            "Is D7140 covered?",
            conversation="Earlier discussion about hearing aids and fitness discounts.",
            retrieve=retrieve,
            retrieval_query="Is D7140 covered?",
        )

        self.assertEqual(calls, [("Is D7140 covered?", 4)])
        self.assertIn("hearing aids", program.calls[0]["conversation"])
        self.assertIn("[p. 26]", answer)

    def test_member_vocabulary_retrieves_vision_table(self):
        index = DentalPolicyIndex(
            [
                PolicyChunk(2, "Learn about your plan and member account."),
                PolicyChunk(
                    7,
                    "Focused on vision. Vision services in-network: frames, "
                    "60% of retail price; lenses from $50 to $135.",
                ),
                PolicyChunk(8, "Oral health resources for members."),
            ]
        )

        hits = index.search("Is my Costco glasses covered?", top_k=2)

        self.assertEqual(hits[0].page, 7)

    def test_member_discount_eval_cases_retrieve_expected_facts(self):
        project = Path(__file__).resolve().parents[1]
        repo = project.parent
        cases = json.loads((project / "data/policy_qa_eval_cases.json").read_text())
        index = DentalPolicyIndex.from_pdf(
            repo / "crawl_dir/raw/dental/fedvip/2026-geha-dental-benefits-guide.pdf"
        )

        failures = []
        for case in cases:
            result = evaluate_retrieval(case, index.search(case["question"], top_k=4))
            if not result["passed"]:
                failures.append({"id": case["id"], **result})

        self.assertEqual(failures, [])


if __name__ == "__main__":
    unittest.main()
