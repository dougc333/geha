"""Tests for the spec-driven bill-of-lading parser (no OCR engine or network needed).

    cd PDF_processing/bill_lading && python -m unittest test_bol_parser -v
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from bol_parser import DEFAULT_GOLD, DEFAULT_SPEC, evaluate, iso6346_ok, parse

SPEC = json.loads(Path(DEFAULT_SPEC).read_text())
GOLD = json.loads(Path(DEFAULT_GOLD).read_text())


class LabelSplittingTests(unittest.TestCase):
    def test_paddle_style_run_together_labels_and_values_are_split(self):
        # PaddleOCR-VL's Table Recognition mode joins a cell's label and value with no space
        # (README: "OCEAN VESSEL / VOYAGEMERIDIAN LABREA / 124N", "SHIPPERFRUTAS DEL SOL S.A.Av. ...").
        # Its saved outputs aren't on disk, so this fixture reproduces that format.
        blocks = {
            3: "OCEAN VESSEL / VOYAGEMERIDIAN LABREA / 124NPORT OF LOADINGBUENOS AIRES, ARGENTINA"
               "PORT OF DISCHARGEROTTERDAM, NETHERLANDS",
            2: "SHIPPERFRUTAS DEL SOL S.A.\nAv. de los Incas 456, Buenos Aires, Argentina\n"
               "TEL: +54 11 4789 1234 | EMAIL: logistica@frutasdelsol.com.ar\nBOOKING REF.BKG5917532",
        }
        fields = parse(blocks, SPEC)["fields"]
        self.assertEqual(fields["vessel_voyage"], "MERIDIAN LABREA / 124N")
        self.assertEqual(fields["port_of_loading"], "BUENOS AIRES, ARGENTINA")
        self.assertEqual(fields["port_of_discharge"], "ROTTERDAM, NETHERLANDS")
        self.assertEqual(fields["shipper"]["name"], "FRUTAS DEL SOL S.A.")
        self.assertEqual(fields["shipper"]["email"], "logistica@frutasdelsol.com.ar")
        self.assertEqual(fields["booking_ref"], "BKG5917532")


class ValidationTests(unittest.TestCase):
    def test_misread_bl_number_is_flagged_not_passed_through(self):
        # Tesseract read "BL232472785" as "31232472785"; the spec's pattern must reject it.
        result = parse({1: "MERIDIAN SHIPPING BILL OF LADING\nB/LNO. 31232472785\nSCAC MRDN"}, SPEC)
        self.assertIsNone(result["fields"]["bl_number"])
        self.assertIn("bl_number: missing", result["errors"])
        self.assertFalse(result["valid"])

    def test_package_totals_rule(self):
        blocks = {6: "MRDN4455667\nSEAL: MSK112233\n20 PALLETS STC:\n18,500 KGS 28.00 CBM",
                  7: "TOTAL NUMBER OF PACKAGES\n25"}
        rules = {r["rule"]: r for r in parse(blocks, SPEC)["rules"]}
        self.assertIs(rules["packages_add_up"]["passed"], False)

    def test_original_bls_words_must_match_digit(self):
        rules = {r["rule"]: r for r in parse({8: "NUMBER OF ORIGINAL B/L'S: THREE (2)"}, SPEC)["rules"]}
        self.assertIs(rules["original_bls_words_match_digit"]["passed"], False)

    def test_iso6346(self):
        self.assertEqual(iso6346_ok("CSQU3054383"), (True, ""))       # textbook valid number
        self.assertFalse(iso6346_ok("CSQU3054384")[0])               # wrong check digit
        self.assertFalse(iso6346_ok("MRDN4455667")[0])               # category N: not registered


class SavedRunTests(unittest.TestCase):
    def test_claude_run_parses_every_field_and_tesseract_is_rejected(self):
        report = evaluate(SPEC, GOLD)
        if "Claude Opus 5.5" not in report:
            self.skipTest("saved Claude run not present")
        claude = report["Claude Opus 5.5"]
        self.assertEqual(claude["score"]["correct"], claude["score"]["total"])
        self.assertTrue(claude["result"]["valid"])
        if "Tesseract 5.5.1" in report:
            self.assertFalse(report["Tesseract 5.5.1"]["result"]["valid"])


if __name__ == "__main__":
    unittest.main()
