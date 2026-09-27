"""Tests for the optional Ragas evaluation path; no network calls are made."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from evaluate_ragas import load_jsonl
from ragas_evaluator import (
    RagasEvaluator,
    RagasSample,
    _install_vertexai_import_compatibility,
)


class RagasEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample = RagasSample(
            user_input="What is instruction tuning?",
            response="It fine-tunes a model on instruction and answer pairs.",
            retrieved_contexts=["Instruction tuning uses instruction-response examples."],
            reference="Instruction tuning trains a model with instruction-response pairs.",
        )

    def test_sample_requires_retrieved_context(self):
        with self.assertRaisesRegex(ValueError, "retrieved_contexts"):
            RagasSample(
                user_input="question",
                response="answer",
                retrieved_contexts=[],
                reference="reference",
            )

    def test_evaluate_aggregates_injected_metric_results(self):
        evaluator = RagasEvaluator(
            metric_runner=lambda sample: {
                "faithfulness": {"value": 0.75, "reason": "supported"},
                "answer_relevancy": {"value": 0.5, "reason": None},
            }
        )
        result = evaluator.evaluate([self.sample, self.sample])

        self.assertEqual(result["sample_count"], 2)
        self.assertEqual(result["aggregate"]["faithfulness"], 0.75)
        self.assertEqual(result["aggregate"]["answer_relevancy"], 0.5)
        self.assertEqual(result["samples"][0]["user_input"], self.sample.user_input)

    def test_write_json_creates_machine_readable_report(self):
        evaluator = RagasEvaluator(
            metric_runner=lambda sample: {"faithfulness": {"value": 1.0}}
        )
        result = evaluator.evaluate([self.sample])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "nested" / "result.json"
            evaluator.write_json(output, result)
            saved = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(saved["sample_count"], 1)
        self.assertEqual(saved["aggregate"]["faithfulness"], 1.0)

    def test_load_jsonl_validates_required_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory) / "questions.jsonl"
            dataset.write_text('{"user_input": "question"}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "reference"):
                load_jsonl(dataset)

    def test_ragas_can_import_with_modern_langchain(self):
        _install_vertexai_import_compatibility()
        from ragas.metrics.collections import Faithfulness

        self.assertEqual(Faithfulness.__name__, "Faithfulness")


if __name__ == "__main__":
    unittest.main()
