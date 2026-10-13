from __future__ import annotations

import json
import unittest
from types import SimpleNamespace

from dspy_router import DspyExtractor
from shared_graph import DentalEnrollmentGraph


class FakeProgram:
    def __init__(self, label: str, second_label: str = "none", ambiguous: bool = False):
        self.label = label
        self.second_label = second_label
        self.ambiguous = ambiguous
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            label=self.label,
            second_label=self.second_label,
            ambiguous=self.ambiguous,
        )


class DspyExtractorTests(unittest.TestCase):
    def test_returns_supported_label(self):
        program = FakeProgram("orthodontia")
        extractor = DspyExtractor(program=program)
        result = extractor(
            "What care is needed?",
            {"routine": "Routine", "orthodontia": "Braces"},
            "My child needs braces and I also love the local farmers market.",
        )
        self.assertEqual(result["decision"], "one")
        self.assertEqual(result["label"], "orthodontia")
        self.assertEqual(json.loads(program.calls[0]["options_json"])["orthodontia"], "Braces")

    def test_unsupported_label_fails_closed(self):
        result = DspyExtractor(program=FakeProgram("invented"))(
            "Question", {"allowed": "Allowed"}, "Answer"
        )
        self.assertEqual(result["decision"], "none")
        self.assertIsNone(result["label"])

    def test_new_hire_guard_overrides_dspy_qle_classification(self):
        bot = DentalEnrollmentGraph(
            jev=lambda *_: None,
            extractor=DspyExtractor(program=FakeProgram("qle")),
        )
        thread = "dspy-new-hire-priority"
        bot.reply("", thread)
        bot.reply("1", thread)
        bot.reply("2", thread)
        reply, state = bot.reply("QLE, but I am a new hire and started last week.", thread)
        self.assertEqual(state["enrollment_reason"], "newly_eligible")
        self.assertEqual(state["stage"], "enrollment")
        self.assertIn("takes priority", reply)

    def test_rambling_state_routes_to_zip(self):
        bot = DentalEnrollmentGraph(
            jev=lambda *_: None,
            extractor=DspyExtractor(program=FakeProgram("CA")),
        )
        thread = "dspy-state"
        bot.reply("", thread)
        for answer in ("1", "1", "1"):
            bot.reply(answer, thread)
        _, state = bot.reply("I live near Modesto in California and love the farmers market.", thread)
        self.assertEqual(state["state_code"], "CA")
        self.assertEqual(state["stage"], "zip")


if __name__ == "__main__":
    unittest.main()

