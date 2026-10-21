import unittest

from finetuning import eval_generator
from finetuning import prepare_generator_sft as sft


GOLD = "doc | pages 3 | Waiting periods\n\nWaiting periods\nThere is no waiting period for basic services. Orthodontia has a 12-month waiting period."


class PrepareGeneratorSftTests(unittest.TestCase):
    def test_evidence_picks_answer_sentence_from_gold(self):
        evidence = sft.evidence_sentences(
            [(2, GOLD)], "Orthodontia has a 12-month waiting period.", limit=1
        )
        self.assertEqual(evidence, [(2, "Orthodontia has a 12-month waiting period.")])

    def test_examples_mix_gold_with_distractors_and_record_gold_numbers(self):
        row = {
            "id": "q1",
            "question": "Is there a waiting period for orthodontia?",
            "answer": "Orthodontia has a 12-month waiting period.",
            "reference_contexts": [GOLD],
            "source_chunk_ids": ["gold"],
        }
        chunks = [
            {"chunk_id": "gold", "text": "x" * 200},
            {"chunk_id": "short", "text": "too short"},
            {"chunk_id": "d1", "text": "Implants are covered at 50 percent. " * 5},
            {"chunk_id": "d2", "text": "Vision discounts are available. " * 5},
        ]
        examples = sft.build_examples([row], chunks, distractors=2, seed=1)
        self.assertEqual([e["task"] for e in examples], ["direct", "cot"])
        prompt = examples[0]["messages"][1]["content"]
        self.assertNotIn("too short", prompt)
        self.assertNotIn("x" * 200, prompt)
        gold = examples[0]["gold_passages"]
        self.assertEqual(len(gold), 1)
        self.assertIn(f"[{gold[0]}] doc | pages 3", prompt)
        self.assertTrue(
            examples[1]["messages"][2]["content"].startswith(f"Evidence:\n- [{gold[0]}]")
        )

    def test_cot_scoring_checks_citations_and_quotes(self):
        example = {
            "task": "cot",
            "reference_answer": "Orthodontia has a 12-month waiting period.",
            "gold_passages": [1],
            "messages": [{}, {"content": f"[1] {GOLD}"}],
        }
        output = (
            'Evidence:\n- [1] "Orthodontia has a 12-month waiting period."\n'
            '- [2] "made up quote here"\n'
            "Answer: Orthodontia has a 12-month waiting period."
        )
        result = eval_generator.score(example, output)
        self.assertEqual(result["answer_f1"], 1.0)
        self.assertEqual(result["format_ok"], 1.0)
        self.assertEqual(result["citation_precision"], 0.5)
        self.assertEqual(result["quote_grounded"], 0.5)


if __name__ == "__main__":
    unittest.main()
