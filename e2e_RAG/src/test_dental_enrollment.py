"""Tests for the dental enrollment state machine and the tables it reads.

Reads the 2026 GEHA dental benefits guide (DENTAL_GUIDE overrides the path); no API key.
"""

import csv
import unittest
from pathlib import Path

from dental_enrollment import DentalEnrollmentBot, rule_extract
from dental_tables import BENEFITS, GUIDE, DentalTables, pdf_text

CSV_DIR = GUIDE.parent
TABLES = DentalTables()


class TableTests(unittest.TestCase):
    def test_rate_codes_match_earlier_extraction(self):
        path = CSV_DIR / "2026_geha_dental_zip_to_rate_code.csv"
        if not path.exists():
            self.skipTest(f"{path} not found")
        rows = [(r["State"], r["First 3 digits of ZIP code"], int(r["Rate code"])) for r in csv.DictReader(path.read_text().splitlines())]
        self.assertEqual(rows, [(r.state, r.zips, r.code) for r in TABLES.rows])

    def test_premiums_match_earlier_extraction(self):
        path = CSV_DIR / "2026_geha_dental_premiums_all_classes.csv"
        if not path.exists():
            self.skipTest(f"{path} not found")
        want = {(r["Plan Option"], r["Employment Status"], r["Enrollment Type"], int(r["Rate Code"])): float(r["Premium"])
                for r in csv.DictReader(path.read_text().splitlines())}
        self.assertEqual(want, TABLES.premiums)

    def test_every_benefit_value_is_printed_in_the_guide(self):
        text = pdf_text().replace("’", "'")
        for topic, row in BENEFITS.items():
            for column in ("High", "Standard in-network", "Standard out-of-network"):
                with self.subTest(topic=topic, column=column):
                    self.assertIn(row[column].replace(" (in or out of network)", ""), text)

    def test_rate_code_lookups(self):
        cases = {"94105": 5, "96001": 4, "10001": 5, "64101": 2, "01201": 2, "02108": 4, "00901": 1, "83414": 2}
        for zip_code, code in cases.items():
            with self.subTest(zip=zip_code):
                self.assertEqual(TABLES.rate_code(zip_code)["rate_code"], code)

    def test_shared_prefix_with_one_code_needs_no_state(self):
        self.assertEqual(TABLES.rate_code("20500")["rate_code"], 4)   # DC, MD and VA all list 205 at code 4
        self.assertEqual(TABLES.rate_code("72601")["rate_code"], 1)   # AR, and MO lists 726

    def test_shared_prefix_with_different_codes_asks_for_state(self):
        tables = DentalTables()
        tables.rows = [r for r in tables.rows if not (r.state == "CT" and "060" in r.zips)]
        tables.rows.append(type(tables.rows[0])("CT", "060-063", 3))   # make CT 063 differ from NY 063 (code 4)
        self.assertEqual(tables.rate_code("06320")["ask_state"], ["CT", "NY"])
        self.assertEqual(tables.rate_code("06320", "NY")["rate_code"], 4)

    def test_unknown_prefix_is_an_error(self):
        self.assertIn("error", TABLES.rate_code("09012"))
        self.assertIn("error", TABLES.rate_code("12"))

    def test_premium(self):
        q = TABLES.premium(5, "retired", "self and family")
        self.assertEqual(q["premiums"], {"High": "$183.37 monthly", "Standard": "$104.00 monthly"})
        self.assertEqual(TABLES.premium(1, "employed", "Self Only", "STANDARD")["premiums"], {"Standard": "$10.82 biweekly"})


class ExtractTests(unittest.TestCase):
    def test_rules(self):
        got = rule_extract("Retired, me and my wife, zip 64101, does it cover braces?", "", [])
        self.assertEqual((got["zip"], got["status"], got["enrollment"]), ("64101", "RETIRED", "Self Plus One"))
        self.assertEqual(got["topics"], ["orthodontics"])

    def test_state_only_read_when_asked(self):
        self.assertNotIn("state", rule_extract("ok", "ask_status", ["OK", "TX"]))
        self.assertEqual(rule_extract("ok", "ask_state", ["OK", "TX"])["state"], "OK")


class StateMachineTests(unittest.TestCase):
    def chat(self, *messages):
        bot = DentalEnrollmentBot(tables=TABLES)
        return [bot.reply(m, "t") for m in messages]

    def test_asks_for_each_slot_in_order(self):
        replies = self.chat("hi", "94105", "active employee", "self only", "high")
        self.assertIn("ZIP code", replies[0])
        self.assertIn("rate code 5", replies[1])
        self.assertIn("employee", replies[1])
        self.assertIn("covered", replies[2])
        self.assertIn("Which plan", replies[3])
        self.assertIn("High: $28.23 biweekly", replies[4])

    def test_one_message_with_everything_quotes_immediately(self):
        reply = self.chat("retired, self and family, compare both plans, 96001")[0]
        self.assertIn("High: $169.28 monthly", reply)
        self.assertIn("Standard: $96.18 monthly", reply)

    def test_benefit_question_answers_then_keeps_going(self):
        reply = self.chat("94105", "do you cover implants?")[1]
        self.assertIn("$2,500 per person per year", reply)
        self.assertIn("active federal employee", reply)   # still asks the next missing slot

    def test_bad_zip_asks_again(self):
        reply = self.chat("09012")[0]
        self.assertIn("not in the rate-code table", reply)
        self.assertIn("ZIP code", reply)

    def test_changing_a_slot_requotes_and_unchanged_does_not(self):
        replies = self.chat("94105 employed self only standard", "what about high", "thanks")
        self.assertIn("Standard: $16.00 biweekly", replies[0])
        self.assertIn("High: $28.23 biweekly", replies[1])
        self.assertNotIn("$", replies[2])

    def test_new_zip_recomputes_rate_code(self):
        replies = self.chat("94105 employed self only standard", "I moved, zip is 64101")
        self.assertIn("rate code 2", replies[1])
        self.assertIn("Standard: $12.11 biweekly", replies[1])

    def test_start_over(self):
        replies = self.chat("94105 employed self only standard", "start over")
        self.assertIn("ZIP code", replies[1])


if __name__ == "__main__":
    unittest.main()
