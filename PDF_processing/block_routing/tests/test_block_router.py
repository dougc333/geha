import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jsonschema  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from block_router import (INVOICE_BLOCKS, Config, JevRouter, bol_blocks, candidate_cuts, decide, merge_invoice,  # noqa: E402
                          propose_blocks, quality, rule_decision)
from block_router import extract_document, n_schema_fields  # noqa: E402
from block_router.blocks import InvalidProposal, boxes_from_proposal  # noqa: E402

INV = {"family": "invoice"}


def llm(use, conf):
    return lambda f: {"use_blocks": use, "confidence": conf, "reason": "stub"}


class StubJevClient:
    def __init__(self, probs):
        self.probs = probs

    def system_one(self, state, questions):
        return SimpleNamespace(choices={"route": SimpleNamespace(probabilities=self.probs)})


class Rules(unittest.TestCase):
    def test_poor_first_pass_uses_blocks(self):
        d = decide({**INV, "first_pass_quality": 0.80})
        self.assertEqual((d.use_blocks, d.method), (True, "rules"))

    def test_good_first_pass_does_not(self):
        d = decide({**INV, "first_pass_quality": 0.99})
        self.assertEqual((d.use_blocks, d.method), (False, "rules"))

    def test_ambiguous_band_is_undecided_by_rules(self):
        self.assertIsNone(rule_decision({**INV, "first_pass_quality": 0.93})[0])

    def test_no_first_pass_uses_field_count(self):
        self.assertTrue(rule_decision({**INV, "n_expected_fields": 40})[0])
        self.assertFalse(rule_decision({**INV, "n_expected_fields": 8})[0])
        self.assertIsNone(rule_decision({**INV, "n_expected_fields": 20})[0])

    def test_family_without_schemas_never_blocks(self):
        self.assertFalse(decide({"family": "brochure", "first_pass_quality": 0.1}).use_blocks)

    def test_versioned_template_blocks(self):
        self.assertTrue(decide({"family": "bill_of_lading", "has_versioned_template": True}).use_blocks)


class Chain(unittest.TestCase):
    amb = {**INV, "first_pass_quality": 0.93}

    def test_llm_decides_when_confident(self):
        d = decide(self.amb, llm_decider=llm(True, 0.9))
        self.assertEqual((d.use_blocks, d.method), (True, "llm"))

    def test_low_confidence_llm_goes_to_jev(self):
        jev = JevRouter(StubJevClient({"blocks": 0.7, "single_pass": 0.2, "unsure": 0.1}))
        d = decide(self.amb, llm_decider=llm(False, 0.4), jev=jev)
        self.assertEqual((d.use_blocks, d.method), (True, "jev"))
        self.assertEqual([t["stage"] for t in d.trace], ["rules", "llm", "jev"])

    def test_llm_error_goes_to_jev(self):
        def boom(f):
            raise TimeoutError("slow")
        jev = JevRouter(StubJevClient({"blocks": 0.1, "single_pass": 0.8, "unsure": 0.1}))
        d = decide(self.amb, llm_decider=boom, jev=jev)
        self.assertEqual((d.use_blocks, d.method), (False, "jev"))
        self.assertIn("TimeoutError", d.trace[1]["error"])

    def test_jev_unsure_falls_back_deterministically(self):
        jev = JevRouter(StubJevClient({"blocks": 0.3, "single_pass": 0.3, "unsure": 0.4}))
        d = decide(self.amb, llm_decider=llm(None, 0.0), jev=jev)
        self.assertEqual(d.method, "fallback")
        self.assertTrue(d.use_blocks)  # 0.93 < 0.97

    def test_jev_failure_falls_back(self):
        class Broken:
            def system_one(self, **k):
                raise RuntimeError("down")
        d = decide(self.amb, jev=JevRouter(Broken()))
        self.assertEqual(d.method, "fallback")
        self.assertIn("RuntimeError", d.trace[-2]["error"])

    def test_nothing_known_defaults_to_blocks_and_says_so(self):
        d = decide(INV, jev=False, llm_decider=None)  # jev=False: never call the real service from a test
        self.assertEqual((d.use_blocks, d.method), (True, "fallback"))

    def test_same_inputs_same_decision(self):
        f = {**INV, "first_pass_quality": 0.93}
        jev = lambda: JevRouter(StubJevClient({"blocks": 0.6, "single_pass": 0.3, "unsure": 0.1}))
        a, b = decide(f, llm_decider=llm(None, 0), jev=jev()), decide(f, llm_decider=llm(None, 0), jev=jev())
        self.assertEqual(a, b)

    def test_no_test_reaches_the_real_jev_service(self):
        # every path that can reach stage 3 in this file passes an explicit stub or jev=False
        m = sys.modules["block_router.decide"]  # `block_router.decide` the attribute is the re-exported function
        called = []
        orig = m.JevRouter.route
        m.JevRouter.route = lambda self, f: called.append(1) or {"use_blocks": None, "probabilities": {}, "margin": 0, "top": "unsure"}
        try:
            decide({"family": "invoice", "first_pass_quality": 0.93}, jev=False)
        finally:
            m.JevRouter.route = orig
        self.assertEqual(called, [])

    def test_jev_ties_break_by_name(self):
        r = JevRouter(StubJevClient({}), min_margin=0.0).interpret({"single_pass": 0.5, "blocks": 0.5, "unsure": 0.0})
        self.assertEqual(r["top"], "blocks")


class Quality(unittest.TestCase):
    good = {"invoice_number": "INV-1", "invoice_date": "2026-04-01", "due_date": "2026-04-15", "pretax_amount": 100.0,
            "total_tax_amount": 20.0, "total_amount": 120.0, "total_number_of_items": 2,
            "sender": {"sender_name": "A Ltd"}, "receiver": {"receiver_name": "B Ltd"},
            "items": [{"item_name": "x", "quantity": 1, "unit_price": 40.0, "total_price": 40.0},
                      {"item_name": "y", "quantity": 2, "unit_price": 30.0, "total_price": 60.0}]}

    def test_consistent_invoice_scores_one(self):
        self.assertEqual(quality("invoice", self.good)["score"], 1.0)

    def test_broken_totals_lower_the_score(self):
        bad = {**self.good, "total_amount": 999.0, "invoice_date": "2026-13-45"}
        q = quality("invoice", bad)
        self.assertLess(q["score"], 0.8)
        self.assertEqual(q["checks"]["totals_reconcile"], 0.0)
        self.assertEqual(q["checks"]["dates_valid"], 0.5)

    def test_dates_kept_as_printed_are_valid(self):
        q = quality("invoice", {**self.good, "invoice_date": "12/03/2026", "due_date": "26/04/2026"})
        self.assertEqual(q["checks"]["dates_valid"], 1.0)
        self.assertIsNone(q["checks"]["due_after_invoice"])  # ambiguous order is not judged

    def test_balance_after_insurance_reconciles(self):
        rec = {**self.good, "pretax_amount": 2220.0, "total_tax_amount": 133.2, "total_amount": 355.2,
               "insurance_payment": 1776, "insurance_adjustments": 222}
        self.assertEqual(quality("invoice", rec)["checks"]["totals_reconcile"], 1.0)

    def test_discounted_line_uses_net_price(self):
        rec = {**self.good, "items": [{"item_name": "x", "quantity": 19, "unit_price": 315.98, "net_price": 300.18, "total_price": 5703.5}],
               "pretax_amount": 5703.5, "total_tax_amount": 0.0, "total_amount": 5703.5, "total_number_of_items": 1}
        self.assertEqual(quality("invoice", rec)["checks"]["line_math"], 1.0)

    def test_bol_patterns(self):
        ok = quality("bill_of_lading", {"bl_number": "BL123456789", "scac": "MRDN"})
        bad = quality("bill_of_lading", {"bl_number": "XX1", "scac": "MRDN"})
        self.assertGreater(ok["checks"]["patterns_valid"], bad["checks"]["patterns_valid"])


class Blocks(unittest.TestCase):
    def page(self):
        im = Image.new("RGB", (800, 1000), "white")
        d = ImageDraw.Draw(im)
        for y in (50, 70, 90):                       # header text rows
            d.rectangle([60, y, 700, y + 8], fill="black")
        d.rectangle([40, 300, 760, 303], fill="black")  # a ruling line
        for y in (400, 420, 440, 460):               # table rows
            d.rectangle([60, y, 740, y + 8], fill="black")
        return im

    def test_candidates_find_rule_and_gaps_deterministically(self):
        c1, c2 = candidate_cuts(self.page()), candidate_cuts(self.page())
        self.assertEqual(c1, c2)
        self.assertTrue(any(c["kind"] == "rule" and abs(c["y"] - 301) <= 3 for c in c1))
        self.assertTrue(any(c["kind"] == "gap" for c in c1))

    def test_valid_proposal_becomes_boxes(self):
        cuts = candidate_cuts(self.page())
        rule = next(c for c in cuts if c["kind"] == "rule")
        boxes = boxes_from_proposal({"blocks": [{"name": "header", "top": "page_top", "bottom": rule["id"]},
                                                {"name": "line_items", "top": rule["id"], "bottom": "page_bottom"}]},
                                    cuts, 800, 1000, list(INVOICE_BLOCKS))
        self.assertEqual([b["name"] for b in boxes], ["header", "line_items"])
        self.assertEqual(boxes[0]["box_px"][3], boxes[1]["box_px"][1])

    def test_invalid_proposals_rejected(self):
        cuts = candidate_cuts(self.page())
        names = list(INVOICE_BLOCKS)
        for bad in ({"blocks": [{"name": "header", "top": "h99", "bottom": "page_bottom"}]},
                    {"blocks": [{"name": "nonsense", "top": "page_top", "bottom": "page_bottom"}]},
                    {"blocks": [{"name": "header", "top": "page_top", "bottom": "page_bottom"},
                                {"name": "totals", "top": "page_top", "bottom": "page_bottom"}]},
                    {"blocks": []}):
            with self.assertRaises(InvalidProposal):
                boxes_from_proposal(bad, cuts, 800, 1000, names)

    def test_bad_model_reply_uses_fallback(self):
        r = propose_blocks(self.page(), "invoice", list(INVOICE_BLOCKS), model_call=lambda p, i: "not json")
        self.assertEqual(r["method"], "fallback")
        self.assertTrue(r["boxes"])

    def test_good_model_reply_is_used(self):
        im = self.page()
        rule = next(c for c in candidate_cuts(im) if c["kind"] == "rule")
        reply = '{"blocks":[{"name":"header","top":"page_top","bottom":"%s"},{"name":"line_items","top":"%s","bottom":"page_bottom"}]}' % (rule["id"], rule["id"])
        self.assertEqual(propose_blocks(im, "invoice", list(INVOICE_BLOCKS), lambda p, i: reply)["method"], "model")


class Schemas(unittest.TestCase):
    def test_invoice_block_schemas_are_valid_json_schema(self):
        for name, s in INVOICE_BLOCKS.items():
            jsonschema.Draft202012Validator.check_schema(s)
            self.assertFalse(s["additionalProperties"], name)

    def test_bol_blocks_come_from_the_spec(self):
        blocks = bol_blocks()
        self.assertEqual(len(blocks), 8)
        jsonschema.validate({"bl_number": "BL123456789", "scac": "MRDN"}, blocks["1_header"])
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({"bl_number": "nope", "scac": "MRDN"}, blocks["1_header"])

    def test_merge_has_benchmark_shape(self):
        m = merge_invoice({"header": {"invoice_number": "1", "currency": "EUR"},
                           "parties": {"sender_name": "A", "receiver_name": "B"},
                           "line_items": {"items": [{"item_name": "x"}]},
                           "totals": {"total_amount": 5}, "extras": {"extras": {"po_reference": "P1"}}})
        self.assertEqual(m["sender"], {"sender_name": "A"})
        self.assertEqual(m["receiver"], {"receiver_name": "B"})
        self.assertEqual((m["invoice_number"], m["po_reference"], len(m["items"])), ("1", "P1", 1))


class Pipeline(unittest.TestCase):
    GOOD = Quality.good
    BAD = {**Quality.good, "total_amount": 999.0}  # totals do not reconcile

    def image(self):
        return Blocks().page()

    def block_extract(self, calls):
        def f(crop, name, schema):
            calls.append(name)
            return {"header": {"invoice_number": "INV-1", "invoice_date": "2026-04-01", "due_date": "2026-04-15"},
                    "parties": {"sender_name": "A Ltd", "receiver_name": "B Ltd"},
                    "line_items": {"items": self.GOOD["items"]},
                    "totals": {"pretax_amount": 100.0, "total_tax_amount": 20.0, "total_amount": 120.0, "total_number_of_items": 2},
                    "extras": {"extras": {}}}[name]
        return f

    def test_good_single_pass_never_uses_blocks(self):
        calls = []
        r = extract_document(self.image(), "invoice", single_pass=lambda im: self.GOOD, block_extract=self.block_extract(calls), jev=False)
        self.assertEqual((r["chosen"], r["decision"].method, calls), ("single_pass", "rules", []))

    def test_poor_single_pass_triggers_blocks_and_blocks_win(self):
        calls = []
        r = extract_document(self.image(), "invoice", single_pass=lambda im: self.BAD, block_extract=self.block_extract(calls), jev=False)
        self.assertEqual(r["decision"].use_blocks, True)
        self.assertEqual(r["chosen"], "blocks")
        self.assertEqual(r["quality_final"]["score"], 1.0)
        self.assertLess(r["quality_first"]["score"], 0.9)
        self.assertTrue(calls)

    def test_worse_block_result_is_not_kept(self):
        worse = lambda crop, name, schema: {}
        r = extract_document(self.image(), "invoice", single_pass=lambda im: self.BAD, block_extract=worse, jev=False)
        self.assertEqual(r["record"], self.BAD) if r["chosen"] == "single_pass" else self.assertGreaterEqual(r["quality_final"]["score"], r["quality_first"]["score"])

    def test_schema_field_counts(self):
        self.assertGreater(n_schema_fields("invoice"), 30)


if __name__ == "__main__":
    unittest.main()
