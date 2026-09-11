from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from geha_reference.selfimprove import (
    OverfitClassifier,
    ProbeAgent,
    category_names,
    evaluate,
    run_loop,
)
from geha_reference.selfimprove.data import Example, ExampleGenerator


class SelfImproveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.train = ExampleGenerator(seed=1).dataset(60)
        cls.heldout = ExampleGenerator(seed=2).dataset(20)

    def test_35_categories(self):
        names = category_names()
        self.assertEqual(len(names), 35)
        self.assertEqual(len(set(names)), 35)
        self.assertIn("appeal", names)
        self.assertIn("fraud", names)

    def test_idf_classifier_generalises_better_than_random(self):
        model = OverfitClassifier(memorization=0.0, idf=True)
        model.fit(self.train)
        m = evaluate(model.predict, self.heldout)
        # Generalising baseline: well above chance (1/35 ~ 2.9%).
        self.assertGreater(m["accuracy"], 0.6)
        self.assertLess(m["false_positive_rate"], 0.15)

    def test_memorization_overfits_train_but_not_heldout(self):
        # A memorising model hits zero on the train set...
        mem_model = OverfitClassifier(memorization=1.0, idf=True)
        mem_model.fit(self.train)
        mem_train = evaluate(mem_model.predict, self.train)
        self.assertEqual(mem_train["category_error_rate"], 0.0)
        # ...but does not beat the generalising model on held-out data.
        plain_model = OverfitClassifier(memorization=0.0, idf=True)
        plain_model.fit(self.train)
        mem_hold = evaluate(mem_model.predict, self.heldout)
        plain_hold = evaluate(plain_model.predict, self.heldout)
        self.assertGreaterEqual(
            mem_hold["category_error_rate"],
            plain_hold["category_error_rate"] - 0.05,
        )

    def test_probe_agent_writes_three_per_category(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            agent = ProbeAgent(seed=3)
            examples = agent.write(out, per_category=3, iteration=1)
            self.assertEqual(len(examples), 35 * 3)
            self.assertTrue((out / "probes_iter1.jsonl").exists())
            # Exactly 3 per category.
            counts = {name: 0 for name in category_names()}
            for ex in examples:
                counts[ex.label] += 1
            self.assertTrue(all(v == 3 for v in counts.values()))
            # Probes are disjoint from the seed train set (novel inputs).
            train_texts = {e.text for e in self.train}
            self.assertEqual(train_texts & {e.text for e in examples}, set())

    def test_run_loop_reaches_zero_train_error_and_writes_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            results = run_loop(
                iterations=5,
                per_category_probe=3,
                train_per_category=40,
                heldout_per_category=10,
                output_dir=out,
            )
            self.assertEqual(len(results), 5)
            # Overfit signature: training error collapses to zero.
            self.assertEqual(results[-1].train["category_error_rate"], 0.0)
            # Probe sets were written each iteration.
            for i in range(1, 6):
                self.assertTrue((out / f"probes_iter{i}.jsonl").exists())
            self.assertTrue((out / "loop_summary.json").exists())


if __name__ == "__main__":
    unittest.main()
