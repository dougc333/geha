from __future__ import annotations

import unittest

from app.models import RetrievedContext
from app.service import NO_EVIDENCE, RagService


class FakeRetriever:
    def __init__(self, contexts):
        self.contexts = contexts

    def retrieve(self, question):
        self.question = question
        return self.contexts


class FakeGenerator:
    def generate(self, prompt):
        self.prompt = prompt
        return "Coverage criteria require documented evidence [1]."


class RagServiceTests(unittest.TestCase):
    def test_grounded_answer_returns_source(self):
        retriever = FakeRetriever(
            [RetrievedContext("Documented evidence is required.", "gs://policies/example.pdf", 0.91)]
        )
        generator = FakeGenerator()
        result = RagService(retriever, generator).answer("  What   evidence is required?  ")

        self.assertTrue(result.grounded)
        self.assertEqual(result.citations[0].source_uri, "gs://policies/example.pdf")
        self.assertEqual(retriever.question, "What evidence is required?")
        self.assertIn("[1] Source: gs://policies/example.pdf", generator.prompt)

    def test_no_evidence_abstains_without_generation(self):
        class MustNotRun:
            def generate(self, prompt):
                raise AssertionError("generator must not run without evidence")

        result = RagService(FakeRetriever([]), MustNotRun()).answer("unknown policy question")
        self.assertFalse(result.grounded)
        self.assertEqual(result.answer, NO_EVIDENCE)
        self.assertEqual(result.citations, [])

    def test_rejects_effectively_empty_question(self):
        with self.assertRaisesRegex(ValueError, "at least 3"):
            RagService(FakeRetriever([]), FakeGenerator()).answer(" \x00 ")


if __name__ == "__main__":
    unittest.main()

