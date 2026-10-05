import unittest

from enrollment_graph import DentalEnrollmentGraph, QLE_EVENTS, format_qle_action_table
from guide_tables import GuideTables


class GuideTableTests(unittest.TestCase):
    def setUp(self):
        self.tables = GuideTables()

    def test_rate_codes(self):
        self.assertEqual(self.tables.rate_code("CA", "90210"), "5")
        self.assertEqual(self.tables.rate_code("CA", "95350"), "4")
        self.assertEqual(self.tables.rate_code("TX", "78701"), "3")

    def test_premiums(self):
        self.assertEqual(self.tables.premium("High", "Retired", "Self Plus One", "4"), "$112.84")
        self.assertEqual(self.tables.premium("Standard", "Employed", "Self Only", "1"), "$10.82")


class EnrollmentFlowTests(unittest.TestCase):
    def test_standard_flow(self):
        bot = DentalEnrollmentGraph(jev=lambda *_: None)
        thread = "standard"
        bot.reply("", thread)
        messages = ["1", "1", "1", "CA", "95350", "routine cleanings and lowest premium", "2"]
        replies = [bot.reply(message, thread)[0] for message in messages]
        self.assertIn("Recommended plan: Standard", replies[-2])
        self.assertIn("$14.81 biweekly", replies[-1])
        self.assertIn("BENEFEDS.gov", replies[-1])

    def test_high_flow_after_newly_eligible_verification(self):
        bot = DentalEnrollmentGraph(jev=lambda *_: None)
        thread = "high"
        bot.reply("", thread)
        messages = ["2", "2", "1", "3", "TX", "78701", "I need a crown", "High"]
        replies = [bot.reply(message, thread)[0] for message in messages]
        self.assertIn("Which applies to you", replies[1])
        self.assertIn("New-hire/newly-eligible route selected", replies[2])
        self.assertIn("Recommended plan: High", replies[-2])
        self.assertIn("$151.21 monthly", replies[-1])
        self.assertIn("requires BENEFEDS verification", replies[-1])

    def test_option_two_pauses_at_newly_eligible_or_qle_node(self):
        bot = DentalEnrollmentGraph(jev=lambda *_: None)
        thread = "opportunity-detail"
        bot.reply("", thread)
        bot.reply("1", thread)
        prompt, state = bot.reply("2", thread)
        self.assertEqual(state["stage"], "opportunity_detail")
        self.assertIn("1. New hire or newly eligible", prompt)
        self.assertIn("2. Qualifying life event", prompt)
        response, state = bot.reply("1", thread)
        self.assertEqual(state["enrollment_reason"], "newly_eligible")
        self.assertIn("within 60 days", response)

    def test_qle_option_three_is_terminal_and_shows_its_page_10_row(self):
        bot = DentalEnrollmentGraph(jev=lambda *_: None)
        thread = "qle-option-three"
        bot.reply("", thread)
        for message in ["1", "2", "2"]:
            bot.reply(message, thread)
        reply, state = bot.reply("3", thread)
        self.assertEqual(state["stage"], "complete")
        self.assertTrue(state["complete"])
        self.assertIn("QLE policy lookup complete", reply)
        self.assertIn("QLE policy table for **Losing a covered family member**", reply)
        self.assertIn("| From Not Enrolled to Enrolled | No |", reply)
        self.assertIn("| Increase Enrollment Type | No |", reply)
        self.assertIn("| Decrease Enrollment Type | Yes |", reply)
        self.assertIn("| Cancel | No |", reply)
        self.assertIn("| Change from One Plan to Another | No |", reply)
        self.assertNotIn("What enrollment action", reply)
        self.assertNotIn("First, which describes", reply)
        self.assertIn("This QLE session is complete", reply)

    def test_all_ten_qle_options_are_terminal_without_returning_to_start(self):
        for number, (event, label) in QLE_EVENTS.items():
            with self.subTest(number=number, event=event):
                bot = DentalEnrollmentGraph(jev=lambda *_: None)
                thread = f"qle-terminal-{number}"
                bot.reply("", thread)
                for message in ["1", "2", "2"]:
                    bot.reply(message, thread)
                reply, state = bot.reply(number, thread)
                self.assertEqual(state["stage"], "complete")
                self.assertTrue(state["complete"])
                self.assertIn(f"QLE policy table for **{label}**", reply)
                self.assertNotIn("First, which describes", reply)
                self.assertNotIn("What enrollment action", reply)

    def test_every_qle_terminal_table_has_all_five_actions(self):
        for event, label in QLE_EVENTS.values():
            with self.subTest(event=event):
                table = format_qle_action_table(event)
                self.assertIn(label, table)
                self.assertEqual(table.count("\n|"), 7)  # blank/header/separator plus five data rows
                for action in (
                    "From Not Enrolled to Enrolled", "Increase Enrollment Type",
                    "Decrease Enrollment Type", "Cancel", "Change from One Plan to Another",
                ):
                    self.assertIn(f"| {action} |", table)

        lwop = format_qle_action_table("return_lwop")
        self.assertIn("Yes, if enrollment was cancelled during LWOP", lwop)

    def test_qle_event_uses_jev_when_local_parser_is_ambiguous(self):
        calls = []

        def fake_jev(message, field):
            calls.append((message, field))
            if field == "qle_event":
                return {"value": "marriage", "confidence": 0.94, "model": "test-jev"}
            return None

        bot = DentalEnrollmentGraph(jev=fake_jev)
        thread = "qle-jev"
        bot.reply("", thread)
        for message in ["1", "2", "2"]:
            bot.reply(message, thread)
        reply, state = bot.reply("my situation changed recently", thread)
        self.assertEqual(calls[-1], ("my situation changed recently", "qle_event"))
        self.assertEqual(state["stage"], "complete")
        self.assertTrue(state["complete"])
        self.assertIn("QLE policy table for **Marriage**", reply)

    def test_uncertain_member_does_not_get_plan_assignment(self):
        bot = DentalEnrollmentGraph(jev=lambda *_: None)
        bot.reply("", "unclear")
        reply, state = bot.reply("5", "unclear")
        self.assertTrue(state["complete"])
        self.assertIn("cannot confirm eligibility", reply)

    def test_jev_is_only_fallback_normalization(self):
        calls = []

        def fake_jev(message, field):
            calls.append((message, field))
            return {"value": "active_employee", "confidence": 0.9, "model": "test"}

        bot = DentalEnrollmentGraph(jev=fake_jev)
        bot.reply("", "jev")
        reply, state = bot.reply("I work for an agency", "jev")
        self.assertEqual(calls, [("I work for an agency", "member_type")])
        self.assertEqual(state["status"], "Employed")
        self.assertIn("enrollment opportunity", reply.lower())


if __name__ == "__main__":
    unittest.main()
