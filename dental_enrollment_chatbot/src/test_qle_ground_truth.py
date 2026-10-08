"""QLE rules against the brochure, and local-parser trap cases.

QLE_BROCHURE is typed from the rendered 2026 GEHA dental plan brochure PDF
(downloads/dental/fedvip/2026-geha-dental-plan-brochure.pdf, PDF pages 10-11,
printed pages 8-9), not copied from QLE_MATRIX, so a wrong matrix cell fails here.

Parser traps exercise the local keyword parsers only (Jev disabled).
"""

import unittest

from enrollment_graph import (
    QLE_EVENTS, QLE_MATRIX, Ambiguous, DentalEnrollmentGraph, parse_member_type, parse_qle_event,
)

ACTIONS = ("new_enrollment", "increase_enrollment", "decrease_enrollment", "cancel_enrollment", "change_plan")
LWOP = "if_cancelled_during_lwop"

# Columns follow ACTIONS: Not Enrolled -> Enrolled, Increase, Decrease, Cancel, Change plan.
QLE_BROCHURE = {
    "marriage":                   (True,  True,  False, False, True),
    "acquire_family_member":      (False, True,  False, False, False),
    "lose_family_member":         (False, False, True,  False, False),
    "lose_other_coverage":        (True,  True,  False, False, False),
    "move_service_area":          (False, False, False, False, True),
    "active_military_nonpay":     (False, False, False, True,  False),
    "return_active_military":     (True,  False, False, False, False),
    "return_lwop":                (LWOP,  False, False, False, LWOP),
    "annuity_restored":           (True,  False, False, False, False),
    "transfer_eligible_position": (False, False, False, True,  False),
}


class QleMatrixMatchesBrochure(unittest.TestCase):
    def test_same_ten_events(self):
        self.assertEqual(set(QLE_MATRIX), set(QLE_BROCHURE))
        self.assertEqual({key for key, _ in QLE_EVENTS.values()}, set(QLE_BROCHURE))

    def test_all_fifty_cells(self):
        for event, expected in QLE_BROCHURE.items():
            for action, want in zip(ACTIONS, expected):
                with self.subTest(event=event, action=action):
                    self.assertEqual(QLE_MATRIX[event][action], want)

    def test_every_event_end_to_end_shows_brochure_values(self):
        shown = {True: "Yes", False: "No", LWOP: "Yes, if enrollment was cancelled during LWOP"}
        labels = ("From Not Enrolled to Enrolled", "Increase Enrollment Type", "Decrease Enrollment Type",
                  "Cancel", "Change from One Plan to Another")
        for number, (event, _) in QLE_EVENTS.items():
            with self.subTest(event=event):
                bot = DentalEnrollmentGraph(jev=lambda *_: None)
                thread = f"qle-{event}"
                bot.reply("", thread)
                for message in ("1", "2", "2"):
                    bot.reply(message, thread)
                reply, _ = bot.reply(number, thread)
                for label, want in zip(labels, QLE_BROCHURE[event]):
                    self.assertIn(f"| {label} | {shown[want]} |", reply)


class LocalParserCases(unittest.TestCase):
    """Natural phrasings the local parsers already handle."""

    def test_member_types(self):
        for text, want in [
            ("I am a federal employee", "active_employee"),
            ("I am retired military", "retired_uniformed"),
            ("I am an annuitant", "federal_retiree"),
            ("I am a dependent of a retiree", "eligible_family"),
            ("not sure", "unclear"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(parse_member_type(text), want)

    def test_qle_events(self):
        for text, want in [
            ("I got married", "marriage"),
            ("I got divorced", "lose_family_member"),
            ("I am moving out of the service area", "move_service_area"),
            ("I am returning from leave without pay", "return_lwop"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(parse_qle_event(text), want)


def qle_bot(thread: str) -> DentalEnrollmentGraph:
    """A bot paused at the QLE event question (active employee -> option 2 -> QLE)."""
    bot = DentalEnrollmentGraph(jev=lambda *_: None)
    bot.reply("", thread)
    for message in ("1", "2", "2"):
        bot.reply(message, thread)
    return bot


class ParserTraps(unittest.TestCase):
    """Answers the old longest-match parser misread silently or missed. A wrong
    non-empty result is worse than a miss: it is accepted without consulting Jev."""

    # Conflicting readings are reported, not resolved by alias length.
    def test_relative_of_employee_is_ambiguous(self):
        for text in ("my spouse is a federal employee", "I am the mother of a federal employee"):
            with self.subTest(text=text):
                self.assertEqual(parse_member_type(text), Ambiguous(("active_employee", "eligible_family")))

    def test_ambiguous_member_gets_targeted_question_then_proceeds(self):
        bot = DentalEnrollmentGraph(jev=lambda *_: None)
        bot.reply("", "who")
        reply, state = bot.reply("my spouse is a federal employee", "who")
        self.assertEqual(state["stage"], "member_type")
        self.assertIn("1. Active federal employee", reply)
        self.assertIn("4. Eligible family member of an eligible enrollee", reply)
        self.assertNotIn("2. Federal retiree", reply)
        reply, state = bot.reply("4", "who")
        self.assertEqual(state["stage"], "family_sponsor")

    def test_retired_sponsor_mentioning_active_is_asked(self):
        bot = DentalEnrollmentGraph(jev=lambda *_: None)
        bot.reply("", "sponsor")
        bot.reply("4", "sponsor")
        reply, state = bot.reply("retired, no longer active", "sponsor")
        self.assertEqual(state["stage"], "family_sponsor")
        self.assertIn("2. Retired", reply)
        _, state = bot.reply("2", "sponsor")
        self.assertEqual(state["status"], "Retired")

    def test_aliases_match_whole_words_only(self):
        self.assertEqual(parse_member_type("my brother works for the VA"), "")  # not "other"
        bot = DentalEnrollmentGraph(jev=lambda *_: None)
        bot.reply("", "inactive")
        bot.reply("4", "inactive")
        _, state = bot.reply("inactive, he retired", "inactive")
        self.assertEqual(state["status"], "Retired")  # "inactive" is not "active"

    def test_phrasings_the_old_parser_missed(self):
        for text, want in [
            ("we had a baby", "acquire_family_member"),
            ("we adopted a child", "acquire_family_member"),
            ("my spouse died", "lose_family_member"),
            ("I lost my dental coverage at my old job", "lose_other_coverage"),
            ("my annuity was restored", "annuity_restored"),
            ("I am being deployed on active duty without pay", "active_military_nonpay"),
            ("I am returning from active duty", "return_active_military"),
        ]:
            with self.subTest(text=text):
                self.assertEqual(parse_qle_event(text), want)

    def test_two_events_are_asked_about_then_resolved(self):
        bot = qle_bot("two-events")
        reply, state = bot.reply("we got married and had a baby", "two-events")
        self.assertEqual(state["stage"], "qle_event")
        self.assertIn("1. Marriage", reply)
        self.assertIn("2. Acquiring an eligible family member", reply)
        reply, state = bot.reply("1", "two-events")
        self.assertTrue(state["complete"])
        self.assertIn("QLE policy table for **Marriage**", reply)

    def test_unrecognised_event_is_reasked_not_a_crash(self):
        bot = qle_bot("unknown-event")
        reply, state = bot.reply("something happened at work", "unknown-event")
        self.assertEqual(state["stage"], "qle_event")
        self.assertIn("I couldn't identify one listed QLE", reply)


if __name__ == "__main__":
    unittest.main()
