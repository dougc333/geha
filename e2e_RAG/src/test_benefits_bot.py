"""Tests for the medical tables, the dental + medical state machine and the Streamlit chat app.

Reads GEHA's 2026 PDFs (DENTAL_GUIDE and FEHB_DIR override the paths); no API key.
"""

import re
import unittest

import pymupdf

from benefits_bot import BenefitsBot, rule_extract
from dental_tables import DentalTables
from medical_tables import FEHB_DIR, PLANS, SBC_FILES, MedicalTables

DENTAL, MEDICAL = DentalTables(), MedicalTables()


def flat(text: str) -> str:
    return " ".join(text.replace("–", "-").replace("’", "'").split())


class MedicalTableTests(unittest.TestCase):
    def test_premiums_for_every_plan_and_enrollment(self):
        self.assertEqual(len(MEDICAL.premiums), 15)
        p = MEDICAL.premium("Elevate Plus", "EMPLOYED", "Self Only")
        self.assertEqual((p["enrollment_code"], p["value"], p["period"]), ("251", 205.13, "biweekly"))
        self.assertEqual(MEDICAL.premium("High", "RETIRED", "Self and Family")["value"], 1137.89)

    def test_every_sbc_has_the_federal_form_rows(self):
        for plan in PLANS:
            with self.subTest(plan=plan):
                rows = MEDICAL.grid[plan]
                self.assertEqual(len(rows), 30)
                self.assertTrue(rows[0].service.startswith("Primary care visit"))
                self.assertEqual(rows[-1].service, "Children’s dental check-up")

    def test_every_parsed_cell_is_printed_in_its_sbc(self):
        for plan, name in SBC_FILES.items():
            with pymupdf.open(FEHB_DIR / name) as doc:
                text = flat(" ".join(page.get_text() for page in doc))
            for row in MEDICAL.grid[plan]:
                for cell in (row.network, row.out_of_network):
                    for chunk in re.split(r"\s{2,}", cell):   # every word must be there, in order
                        with self.subTest(plan=plan, service=row.service):
                            self.assertTrue(all(w in text for w in flat(chunk).split()))

    def test_spot_values(self):
        cell = lambda plan, service: next(r for r in MEDICAL.grid[plan] if r.service.startswith(service))
        self.assertEqual(cell("Elevate Plus", "Specialist").network, "$50* / visit")
        self.assertEqual(cell("Elevate Plus", "Diagnostic").network, "No charge* for Lab; $50* for all other tests")
        self.assertEqual(cell("HDHP", "Emergency room").network, "5% coinsurance")
        self.assertEqual(cell("Elevate Plus", "Urgent care").out_of_network, "Not covered")
        self.assertIn("$200 / Self Only", MEDICAL.questions["Elevate Plus"]["deductible"])
        self.assertIn("$7,000 / Self Only", MEDICAL.questions["Elevate Plus"]["out_of_pocket_limit"])


class ExtractTests(unittest.TestCase):
    def test_high_and_standard_go_to_the_line_being_asked(self):
        self.assertEqual(rule_extract("high", "ask_dental_plan", [], {"line": "both"})["dental_plan"], "HIGH")
        self.assertEqual(rule_extract("high", "ask_medical_plan", [], {"line": "both"})["medical_plan"], "High")
        self.assertNotIn("dental_plan", rule_extract("high", "", [], {"line": "both"}))

    def test_medical_only_plan_names(self):
        got = rule_extract("elevate plus please", "", [], {})
        self.assertEqual((got["medical_plan"], got["line"]), ("Elevate Plus", "medical"))
        self.assertEqual(rule_extract("hdhp", "", [], {})["medical_plan"], "HDHP")

    def test_shared_topics_are_marked_either(self):
        self.assertIn("either:deductible", rule_extract("what's the deductible?", "", [], {})["topics"])
        self.assertIn("medical:imaging", rule_extract("is an MRI covered", "", [], {})["topics"])
        self.assertIn("dental:orthodontics", rule_extract("braces?", "", [], {})["topics"])


class RuleFixTests(unittest.TestCase):
    """Rules added for the conversation test set's misses, and words they must not misread."""

    def x(self, message, stage="", slots=None):
        return rule_extract(message, stage, [], slots or {})

    def test_family_size(self):
        self.assertEqual(self.x("me and my daughter")["enrollment"], "Self Plus One")
        self.assertEqual(self.x("my husband and son")["enrollment"], "Self and Family")
        self.assertEqual(self.x("me and my 3 kids")["enrollment"], "Self and Family")
        self.assertEqual(self.x("individual coverage")["enrollment"], "Self Only")

    def test_status_wording_and_typos(self):
        for text, want in [("I'm a postal worker", "EMPLOYED"), ("still working", "EMPLOYED"),
                           ("USPS letter carrier", "EMPLOYED"), ("retierd", "RETIRED"), ("retird", "RETIRED")]:
            with self.subTest(text=text):
                self.assertEqual(self.x(text)["status"], want)

    def test_line_wording(self):
        self.assertEqual(self.x("both")["line"], "both")                       # before the bot asks
        self.assertEqual(self.x("FEHB and FEDVIP")["line"], "both")
        self.assertEqual(self.x("dentl and medcal")["line"], "both")
        self.assertNotIn("line", self.x("compare both", "ask_dental_plan", {"line": "dental"}))

    def test_plan_wording(self):
        got = self.x("high dental and standard medical", "ask_dental_plan", {"line": "both"})
        self.assertEqual((got["dental_plan"], got["medical_plan"]), ("HIGH", "Standard"))
        self.assertEqual(self.x("the cheaper one", "ask_dental_plan", {"line": "dental"})["dental_plan"], "STANDARD")
        self.assertEqual(self.x("elevat plus")["medical_plan"], "Elevate Plus")
        self.assertEqual(self.x("standrad", "ask_dental_plan", {"line": "dental"})["dental_plan"], "STANDARD")

    def test_words_that_must_not_be_misread(self):
        self.assertNotIn("enrollment", self.x("I'm familiar with HDHP"))
        self.assertNotIn("line", self.x("I have Medicare"))
        self.assertNotIn("line", self.x("good oral health matters"))
        self.assertNotIn("state", self.x("ok, I'm employed", "ask_status"))
        self.assertNotIn("medical_plan", self.x("cheapest please", "ask_medical_plan", {"line": "medical"}))


class StateMachineTests(unittest.TestCase):
    def chat(self, *messages):
        bot = BenefitsBot(DENTAL, MEDICAL)
        return bot, [bot.reply(m, "t") for m in messages]

    def test_both_lines_ask_shared_slots_once_and_total(self):
        bot, r = self.chat("hi", "both", "20500", "retired", "me and my wife", "high", "elevate plus")
        self.assertIn("dental, medical, or both", r[0])
        self.assertIn("ZIP", r[1])
        self.assertIn("rate code 4", r[2])
        self.assertIn("Which dental plan", r[4])
        self.assertIn("Which medical plan", r[5])
        self.assertIn("Dental High (rate code 4): $112.84 monthly", r[6])
        self.assertIn("Medical Elevate Plus (enrollment code 253): $974.09 monthly", r[6])
        self.assertIn("Total: $1,086.93 monthly", r[6])
        self.assertEqual(sum("employee" in x and "retiree" in x for x in r), 1)   # status asked once

    def test_medical_only_needs_no_zip(self):
        _, r = self.chat("medical, active employee, self only, compare")
        self.assertNotIn("ZIP", r[0])
        self.assertIn("Medical HDHP (enrollment code 341): $81.62 biweekly", r[0])
        self.assertNotIn("Total", r[0])   # comparing five plans: no single total

    def test_dental_only_matches_the_dental_bot(self):
        _, r = self.chat("dental 94105 employed self only standard")
        self.assertIn("Dental Standard (rate code 5): $16.00 biweekly", r[0])

    def test_ambiguous_deductible_waits_for_the_line(self):
        _, r = self.chat("what's the deductible?", "dental")
        self.assertIn("which one did you mean", r[0])
        self.assertIn("$75 out-of-network deductible", r[1])
        self.assertNotIn("Medical deductible", r[1])

    def test_medical_benefit_question_uses_the_chosen_plan(self):
        _, r = self.chat("medical, elevate plus", "does it cover an mri?")
        self.assertIn("$175 total per test", r[1])
        self.assertNotIn("HDHP", r[1])

    def test_adding_a_line_later_asks_only_what_is_new(self):
        _, r = self.chat("medical, retired, self only, standard", "add dental too, zip 64101", "high")
        self.assertIn("Which dental plan", r[1])
        self.assertIn("Dental High (rate code 2)", r[2])
        self.assertIn("Medical Standard", r[2])

    def test_every_dollar_in_a_quote_is_a_table_value(self):
        _, r = self.chat("both", "20500", "employed", "self and family", "both", "compare")
        values = {f"${v:,.2f}" for v in DENTAL.premiums.values()}
        values |= {f"${p.employed_biweekly:,.2f}" for p in MEDICAL.premiums.values()}
        for amount in re.findall(r"\$[\d,]+\.\d\d", r[-1]):
            self.assertIn(amount, values)


class ChatAppTests(unittest.TestCase):
    def test_app_runs_a_conversation(self):
        from streamlit.testing.v1 import AppTest
        at = AppTest.from_file("benefits_chat_app.py", default_timeout=120).run()
        self.assertFalse(at.exception)
        self.assertIn("dental, medical, or both", at.chat_message[0].markdown[0].value)
        at.chat_input[0].set_value("medical, active employee, self only, elevate").run()
        self.assertIn("77.92 biweekly", at.chat_message[-1].markdown[0].value)
        self.assertIn("Elevate", " ".join(m.value for m in at.sidebar.markdown))


if __name__ == "__main__":
    unittest.main()
