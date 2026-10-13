"""Tests for policy Q&A persona fixtures and deterministic scoring."""

from __future__ import annotations

import unittest
from pathlib import Path

from policy_personas import evaluate_persona_result, load_personas, typing_frames
from policy_qa import PolicyChunk


class PolicyPersonaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        project = Path(__file__).resolve().parents[1]
        cls.personas = load_personas(project / "data/policy_qa_personas.json")

    def test_thirteen_personas_have_unique_ids(self):
        self.assertEqual(len(self.personas), 13)
        self.assertEqual(len({persona["id"] for persona in self.personas}), 13)

    def test_retired_persona_checks_standard_orthodontic_facts(self):
        persona = next(
            item for item in self.personas
            if item["id"] == "retired-federal-employee-orthodontics"
        )
        answer = (
            "Adults are covered for orthodontics. Standard in-network members pay 50%, "
            "with a $2,500 lifetime maximum [p. 5]."
        )

        result = evaluate_persona_result(persona, answer, [PolicyChunk(5, "orthodontics")])

        self.assertTrue(result["passed"])

    def test_middle_aged_persona_checks_crown_cost_examples(self):
        persona = next(
            item for item in self.personas
            if item["id"] == "middle-aged-member-crown-cost"
        )
        answer = (
            "The example member cost for one porcelain crown is $422 with High "
            "and $548 with Standard, compared with an average $1,363 without "
            "insurance [p. 8]."
        )

        result = evaluate_persona_result(persona, answer, [PolicyChunk(8, "crown")])

        self.assertTrue(result["passed"])

    def test_parent_child_persona_compares_orthodontic_plans(self):
        persona = next(
            item for item in self.personas
            if item["id"] == "parent-child-braces"
        )
        answer = (
            "For orthodontics, High in-network members pay 30% with a $3,500 "
            "lifetime maximum. Standard in-network members pay 50% with a "
            "$2,500 lifetime maximum [p. 5]."
        )

        result = evaluate_persona_result(persona, answer, [PolicyChunk(5, "orthodontics")])

        self.assertTrue(result["passed"])

    def test_modesto_single_mom_persona_extracts_cleaning_question(self):
        persona = next(
            item for item in self.personas
            if item["id"] == "single-mom-modesto-rambling-cleanings"
        )
        answer = (
            "High covers three cleanings per calendar year, while Standard covers "
            "two. In-network preventive care has no member cost ($0) [p. 5]."
        )

        result = evaluate_persona_result(persona, answer, [PolicyChunk(5, "cleanings")])

        self.assertTrue(result["passed"])

        paraphrased = (
            "High covers three cleanings per calendar year and Standard covers two, "
            "with no out-of-pocket payment required in-network [p. 5]."
        )
        paraphrase_result = evaluate_persona_result(
            persona,
            paraphrased,
            [PolicyChunk(5, "cleanings")],
        )
        self.assertTrue(paraphrase_result["passed"])

        live_wording = (
            "High covers three cleanings per year and Standard covers two, "
            "with no cost in-network [p. 5]."
        )
        self.assertTrue(
            evaluate_persona_result(
                persona,
                live_wording,
                [PolicyChunk(5, "cleanings")],
            )["passed"]
        )

    def test_typing_frames_end_with_complete_query(self):
        frames = list(typing_frames("hello", stride=2))
        self.assertEqual(frames, ["he▌", "hell▌", "hello"])

    def test_evaluation_requires_fact_page_and_citation(self):
        persona = self.personas[0]
        answer = "Frames cost 60% of the retail price [p. 7]."

        passed = evaluate_persona_result(persona, answer, [PolicyChunk(7, "evidence")])
        wrong_page = evaluate_persona_result(persona, answer, [PolicyChunk(6, "evidence")])

        self.assertTrue(passed["passed"])
        self.assertFalse(wrong_page["passed"])

    def test_code_persona_requires_both_source_pages_and_citations(self):
        persona = next(item for item in self.personas if item["id"] == "code-root-canal-d3310")
        answer = (
            "D3310 is limited to once per tooth per lifetime [p. 29]. "
            "High pays 50% and Standard in-network pays 65% [p. 5]."
        )
        result = evaluate_persona_result(
            persona,
            answer,
            [PolicyChunk(29, "code"), PolicyChunk(5, "benefits")],
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["expected_page_groups"], [[29], [5, 28]])

    def test_d1110_accepts_no_cost_wording(self):
        persona = next(item for item in self.personas if item["id"] == "code-adult-cleaning-d1110")
        answer = (
            "High covers three adult cleanings per year and Standard covers "
            "two, with no cost to the member in-network [p. 21][p. 5]."
        )
        result = evaluate_persona_result(
            persona,
            answer,
            [PolicyChunk(21, "D1110"), PolicyChunk(5, "Class A")],
        )
        self.assertTrue(result["passed"])

    def test_hearing_persona_normalizes_percentage_range_wording(self):
        persona = next(item for item in self.personas if item["id"] == "retiree-hearing-aids")
        answer = (
            "Members receive 30% to 60% off TruHearing hearing aids, with average "
            "savings above $2,600 per pair [p. 9]."
        )
        result = evaluate_persona_result(persona, answer, [PolicyChunk(9, "hearing aids")])
        self.assertTrue(result["passed"])

    def test_hearing_persona_accepts_common_range_formats(self):
        persona = next(item for item in self.personas if item["id"] == "retiree-hearing-aids")
        variants = ["30%-60%", "30%–60%", "30% to 60%", "30 to 60 percent"]

        for percentage_range in variants:
            with self.subTest(percentage_range=percentage_range):
                answer = (
                    f"Members receive {percentage_range} off TruHearing hearing aids, "
                    "with average savings above $2,600 per pair [p. 9]."
                )
                result = evaluate_persona_result(
                    persona,
                    answer,
                    [PolicyChunk(9, "hearing aids")],
                )
                self.assertTrue(result["passed"])

    def test_d1110_rejects_class_b_cost_sharing(self):
        persona = next(item for item in self.personas if item["id"] == "code-adult-cleaning-d1110")
        wrong_answer = (
            "High covers three cleanings and Standard covers two per calendar year. "
            "Members pay 20% under High and 45% under Standard [p. 21][p. 5]."
        )

        result = evaluate_persona_result(
            persona,
            wrong_answer,
            [PolicyChunk(21, "D1110"), PolicyChunk(5, "benefits")],
        )

        self.assertFalse(result["passed"])
        self.assertEqual(result["missing_facts"], [["$0", "no member cost", "no cost"]])

    def test_modesto_persona_accepts_equivalent_zero_cost_wording(self):
        persona = next(
            item for item in self.personas
            if item["id"] == "single-mom-modesto-rambling-cleanings"
        )
        variants = ["$0", "no member cost", "pay nothing", "no out-of-pocket payment", "no cost"]

        for cost_wording in variants:
            with self.subTest(cost_wording=cost_wording):
                answer = (
                    "High covers three cleanings per year and Standard covers two, "
                    f"with {cost_wording} in-network [p. 5]."
                )
                result = evaluate_persona_result(
                    persona,
                    answer,
                    [PolicyChunk(5, "cleanings")],
                )
                self.assertTrue(result["passed"])

    def test_alternate_detail_page_and_citation_satisfy_source_group(self):
        persona = next(item for item in self.personas if item["id"] == "code-extraction-d7140")
        answer = (
            "D7140 is a simple extraction [p. 26]. High members pay 20% and "
            "Standard members pay 45% in-network [p. 23]."
        )

        result = evaluate_persona_result(
            persona,
            answer,
            [PolicyChunk(26, "code"), PolicyChunk(23, "cost sharing")],
        )

        self.assertTrue(result["passed"])
        self.assertEqual(result["missing_page_groups"], [])
        self.assertEqual(result["missing_citation_groups"], [])


if __name__ == "__main__":
    unittest.main()
