"""LangGraph state machine for a 2026 GEHA dental enrollment proof of concept."""

from __future__ import annotations

import re
from typing import Any, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from guide_tables import GuideTables
from jev_router import classify as jev_classify


class EnrollmentState(TypedDict, total=False):
    message: str
    stage: str
    member_type: str
    status: str
    enrollment_opportunity: str
    enrollment_reason: str
    eligibility_status: str
    enrollment: str
    state_code: str
    zip_code: str
    rate_code: str
    dental_need: str
    recommended_plan: str
    selected_plan: str
    premium: str
    qle_event: str
    qle_decision: dict[str, Any]
    response: str
    complete: bool
    jev_diagnostic: dict[str, Any]


MEMBER_TYPES = {
    "1": "active_employee",
    "2": "federal_retiree",
    "3": "retired_uniformed",
    "4": "eligible_family",
    "5": "unclear",
}
OPPORTUNITIES = {"1": "open_season", "2": "newly_eligible_or_qle", "3": "unsure"}
OPPORTUNITY_DETAILS = {"1": "newly_eligible", "2": "qle"}
ENROLLMENTS = {"1": "Self Only", "2": "Self Plus One", "3": "Self and Family"}
NEEDS = {"1": "routine", "2": "major", "3": "orthodontia", "4": "maximum", "5": "unsure"}
PLANS = {"1": "High", "2": "Standard"}
SPONSOR_STATUSES = {"1": "Employed", "2": "Retired"}
MEMBER_LABELS = {
    "active_employee": "Active federal employee",
    "federal_retiree": "Federal retiree or annuitant",
    "retired_uniformed": "Retired uniformed service member",
    "eligible_family": "Eligible family member of an eligible enrollee",
    "unclear": "Other or not sure",
}
OPPORTUNITY_LABELS = {
    "open_season": "2026 Open Season (November 10–December 8, 2025)",
    "newly_eligible_or_qle": "Newly eligible or a qualifying life event",
    "unsure": "Not sure",
}
OPPORTUNITY_DETAIL_LABELS = {"newly_eligible": "New hire or newly eligible", "qle": "Qualifying life event"}
NEED_LABELS = {
    "routine": "Preventive/routine care and the lowest premium",
    "major": "Upcoming major dental work",
    "orthodontia": "Orthodontia",
    "maximum": "Maximum coverage, unlimited annual maximum, or three adult cleanings",
    "unsure": "Not sure",
}
SPONSOR_LABELS = {"Employed": "Active federal employee (still working)", "Retired": "Retired"}
QLE_EVENTS = {
    "1": ("marriage", "Marriage"),
    "2": ("acquire_family_member", "Acquiring an eligible family member (non-spouse)"),
    "3": ("lose_family_member", "Losing a covered family member"),
    "4": ("lose_other_coverage", "Losing other dental/vision coverage"),
    "5": ("move_service_area", "Moving out of a regional plan's service area"),
    "6": ("active_military_nonpay", "Going on active military duty in non-pay status"),
    "7": ("return_active_military", "Returning to pay status from active military duty"),
    "8": ("return_lwop", "Returning to pay status from Leave Without Pay"),
    "9": ("annuity_restored", "Annuity or compensation restored"),
    "10": ("transfer_eligible_position", "Transferring to an eligible position"),
}
QLE_MATRIX: dict[str, dict[str, bool | str]] = {
    "marriage": {"new_enrollment": True, "increase_enrollment": True, "decrease_enrollment": False,
                 "cancel_enrollment": False, "change_plan": True},
    "acquire_family_member": {"new_enrollment": False, "increase_enrollment": True,
                              "decrease_enrollment": False, "cancel_enrollment": False,
                              "change_plan": False},
    "lose_family_member": {"new_enrollment": False, "increase_enrollment": False,
                           "decrease_enrollment": True, "cancel_enrollment": False,
                           "change_plan": False},
    "lose_other_coverage": {"new_enrollment": True, "increase_enrollment": True,
                            "decrease_enrollment": False, "cancel_enrollment": False,
                            "change_plan": False},
    "move_service_area": {"new_enrollment": False, "increase_enrollment": False,
                          "decrease_enrollment": False, "cancel_enrollment": False,
                          "change_plan": True},
    "active_military_nonpay": {"new_enrollment": False, "increase_enrollment": False,
                               "decrease_enrollment": False, "cancel_enrollment": True,
                               "change_plan": False},
    "return_active_military": {"new_enrollment": True, "increase_enrollment": False,
                               "decrease_enrollment": False, "cancel_enrollment": False,
                               "change_plan": False},
    "return_lwop": {"new_enrollment": "if_cancelled_during_lwop", "increase_enrollment": False,
                    "decrease_enrollment": False, "cancel_enrollment": False,
                    "change_plan": "if_cancelled_during_lwop"},
    "annuity_restored": {"new_enrollment": True, "increase_enrollment": False,
                         "decrease_enrollment": False, "cancel_enrollment": False,
                         "change_plan": False},
    "transfer_eligible_position": {"new_enrollment": False, "increase_enrollment": False,
                                   "decrease_enrollment": False, "cancel_enrollment": True,
                                   "change_plan": False},
}


class Ambiguous(tuple):
    """Several categories matched one answer, so the member is asked which one applies."""


# Relationship words: "my spouse is a federal employee" names a category but may describe
# someone other than the person seeking coverage.
RELATIONS = ("spouse", "husband", "wife", "partner", "mother", "father", "parent", "son",
             "daughter", "child", "dependent", "brother", "sister")


def _words(message: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", message.lower()).strip()


def _alias_spans(text: str, alias: str) -> list[tuple[int, int]]:
    # Aliases match at the start of a word: "other" is not in "mother", "active" not in "inactive".
    return [match.span() for match in re.finditer(rf"(?<![a-z0-9]){re.escape(alias)}", text)]


def _number_or_alias(message: str, options: dict[str, str],
                     aliases: dict[str, tuple[str, ...]]) -> str | Ambiguous:
    """One label, "" for no match, or Ambiguous when aliases of different labels match."""
    text = _words(message)
    if text in options:
        return options[text]
    spans = [(start, end, value) for value, phrases in aliases.items()
             for alias in phrases for start, end in _alias_spans(text, alias)]
    # A match inside a longer match is part of that phrase, not a competing reading.
    found = {value for start, end, value in spans
             if not any(s <= start and end <= e and e - s > end - start for s, e, _ in spans)}
    if len(found) > 1:
        return Ambiguous(sorted(found))
    return found.pop() if found else ""


def parse_member_type(message: str) -> str | Ambiguous:
    value = _number_or_alias(message, MEMBER_TYPES, {
        "active_employee": ("active federal employee", "federal employee", "active employee"),
        "federal_retiree": ("federal retiree", "annuitant", "retired federal"),
        "retired_uniformed": ("retired uniformed", "military retiree", "retired military"),
        "eligible_family": ("eligible family", "family member", "spouse", "dependent"),
        "unclear": ("not sure", "other", "none"),
    })
    text = _words(message)
    if value in {"active_employee", "federal_retiree", "retired_uniformed"} and any(
            _alias_spans(text, word) for word in RELATIONS):
        return Ambiguous((value, "eligible_family"))
    return value


def parse_opportunity(message: str) -> str | Ambiguous:
    return _number_or_alias(message, OPPORTUNITIES, {
        "open_season": ("open season",),
        "newly_eligible_or_qle": ("newly eligible", "new hire", "qualifying life event", "qle"),
        "unsure": ("not sure", "unsure", "do not know"),
    })


def parse_opportunity_detail(message: str) -> str | Ambiguous:
    return _number_or_alias(message, OPPORTUNITY_DETAILS, {
        "newly_eligible": ("newly eligible", "new hire", "became eligible"),
        "qle": ("qualifying life event", "qle", "life event"),
    })


def parse_need(message: str) -> str | Ambiguous:
    return _number_or_alias(message, NEEDS, {
        "routine": ("routine", "preventive", "cleaning", "lowest premium"),
        "major": ("major", "root canal", "crown", "bridge", "dentures", "surgery", "extraction"),
        "orthodontia": ("orthodont", "braces"),
        "maximum": ("maximum", "unlimited", "third cleaning", "most coverage"),
        "unsure": ("not sure", "unsure", "compare"),
    })


MENUS: dict[str, tuple[dict[str, str], dict[str, str]]] = {
    "member_type": (MEMBER_TYPES, MEMBER_LABELS),
    "family_sponsor": (SPONSOR_STATUSES, SPONSOR_LABELS),
    "opportunity": (OPPORTUNITIES, OPPORTUNITY_LABELS),
    "opportunity_detail": (OPPORTUNITY_DETAILS, OPPORTUNITY_DETAIL_LABELS),
    "enrollment": (ENROLLMENTS, {value: value for value in ENROLLMENTS.values()}),
    "need": (NEEDS, NEED_LABELS),
    "plan": (PLANS, {value: value for value in PLANS.values()}),
    "qle_event": ({number: event for number, (event, _) in QLE_EVENTS.items()}, dict(QLE_EVENTS.values())),
}


def _menu(stage: str, only: tuple[str, ...] | None = None) -> str:
    numbering, labels = MENUS[stage]
    return "\n".join(f"{number}. {labels[value]}" for number, value in numbering.items()
                     if only is None or value in only)


def _numbered_prompt(title: str, rows: dict[str, tuple[str, str]]) -> str:
    return title + "\n" + "\n".join(f"{number}. {label}" for number, (_, label) in rows.items())


def parse_qle_event(message: str) -> str | Ambiguous:
    return _number_or_alias(message, {number: event for number, (event, _) in QLE_EVENTS.items()}, {
        "marriage": ("marriage", "married", "wedding"),
        "acquire_family_member": ("acquiring", "new family member", "birth", "adopt", "baby", "newborn"),
        "lose_family_member": ("losing a covered family member", "divorce", "death", "died",
                               "passed away", "deceased"),
        "lose_other_coverage": ("losing other coverage", "lost other coverage", "loss of coverage",
                                "lost my dental", "lost my vision", "lost my coverage", "lost coverage"),
        "move_service_area": ("moving out", "service area"),
        "active_military_nonpay": ("going on active military", "non pay status", "deployed",
                                   "active duty without pay"),
        "return_active_military": ("returning from active military", "return to pay from active",
                                   "returning from active duty"),
        "return_lwop": ("returning from lwop", "leave without pay", "lwop"),
        "annuity_restored": ("annuity", "compensation restored"),
        "transfer_eligible_position": ("eligible position", "transferring"),
    })


def format_qle_action_table(event: str) -> str:
    """Render the selected brochure QLE row from the same matrix used for decisions."""
    label = next(label for key, label in QLE_EVENTS.values() if key == event)
    page = 11 if event in {"annuity_restored", "transfer_eligible_position"} else 10
    row = QLE_MATRIX[event]
    labels = (
        ("new_enrollment", "From Not Enrolled to Enrolled"),
        ("increase_enrollment", "Increase Enrollment Type"),
        ("decrease_enrollment", "Decrease Enrollment Type"),
        ("cancel_enrollment", "Cancel"),
        ("change_plan", "Change from One Plan to Another"),
    )

    def display(rule: bool | str) -> str:
        if rule == "if_cancelled_during_lwop":
            return "Yes, if enrollment was cancelled during LWOP"
        return "Yes" if rule else "No"

    lines = [
        f"QLE policy table for **{label}** (dental brochure page {page}):",
        "",
        "| Enrollment action | Allowed |",
        "|---|---|",
    ]
    lines.extend(f"| {action_label} | {display(row[key])} |" for key, action_label in labels)
    return "\n".join(lines)


class DentalEnrollmentGraph:
    """Conversation wrapper around the auditable enrollment state machine."""

    def __init__(self, tables: GuideTables | None = None, jev=jev_classify):
        self.tables = tables or GuideTables()
        self.jev = jev
        self.graph = self._build()

    @staticmethod
    def _prompt(stage: str) -> str:
        prompts = {
            "member_type": "First, which describes the person seeking coverage?\n" + _menu("member_type"),
            "family_sponsor": "Is the sponsoring enrollee an active federal employee or retired?",
            "opportunity": "What enrollment opportunity applies?\n" + _menu("opportunity"),
            "opportunity_detail": "Which applies to you?\n" + _menu("opportunity_detail"),
            "enrollment": "Who will be covered?\n" + _menu("enrollment"),
            "state": "Enter your two-letter state or territory abbreviation.",
            "zip": "Enter your five-digit ZIP code so I can determine the dental rate code.",
            "need": "What best describes your dental needs?\n" + _menu("need"),
            "plan": "Choose a plan: 1. High or 2. Standard.",
        }
        return prompts[stage]

    @staticmethod
    def _clarify(stage: str, candidates: Ambiguous) -> str:
        """Ask only between the readings that matched, numbered as in the full menu."""
        return "Your answer could mean more than one of these. Which one applies?\n" + _menu(stage, candidates)

    def start(self, _: EnrollmentState) -> EnrollmentState:
        return {"stage": "member_type", "response": self._prompt("member_type"), "complete": False}

    def process(self, state: EnrollmentState) -> EnrollmentState:
        stage, message = state.get("stage", "member_type"), state.get("message", "")
        if message.strip().lower() in {"restart", "start over", "reset"}:
            return self.start({})
        update: EnrollmentState = {"jev_diagnostic": {}}

        if stage == "member_type":
            value = parse_member_type(message)
            if isinstance(value, Ambiguous):
                return {**update, "response": self._clarify(stage, value)}
            if not value and (result := self.jev(message, "member_type")):
                value, update["jev_diagnostic"] = result["value"], result
            if not value:
                return {**update, "response": "I couldn't determine the member category.\n" + self._prompt(stage)}
            if value == "unclear":
                return {
                    **update, "eligibility_status": "needs_benefeds_verification", "complete": True,
                    "stage": "complete",
                    "response": "I cannot confirm eligibility from the benefits guide. Verify eligibility at BENEFEDS.gov or call 1-877-888-3337.",
                }
            update["member_type"] = value
            if value == "active_employee":
                update["status"], update["stage"] = "Employed", "opportunity"
            elif value in {"federal_retiree", "retired_uniformed"}:
                update["status"], update["stage"] = "Retired", "opportunity"
            else:
                update["stage"] = "family_sponsor"
            update["response"] = self._prompt(update["stage"])
            return update

        if stage == "family_sponsor":
            value = _number_or_alias(message, SPONSOR_STATUSES, {
                "Employed": ("active", "employ", "working"), "Retired": ("retir", "annuit"),
            })
            if isinstance(value, Ambiguous):
                return {**update, "response": self._clarify(stage, value)}
            if not value:
                return {**update, "response": "Please answer active employee or retired. " + self._prompt(stage)}
            return {**update, "status": value, "stage": "opportunity", "response": self._prompt("opportunity")}

        if stage == "opportunity":
            value = parse_opportunity(message)
            if isinstance(value, Ambiguous):
                return {**update, "response": self._clarify(stage, value)}
            if not value and (result := self.jev(message, "opportunity")):
                value, update["jev_diagnostic"] = result["value"], result
            if not value:
                return {**update, "response": "I couldn't determine the enrollment opportunity.\n" + self._prompt(stage)}
            update["enrollment_opportunity"] = value
            if value == "newly_eligible_or_qle":
                return {
                    **update, "eligibility_status": "needs_benefeds_verification",
                    "stage": "opportunity_detail", "response": self._prompt("opportunity_detail"),
                }
            update["eligibility_status"] = "self_attested" if value == "open_season" else "needs_benefeds_verification"
            note = ""
            if value == "unsure":
                note = "BENEFEDS must verify your enrollment opportunity; I can still estimate a plan and premium.\n\n"
            return {**update, "stage": "enrollment", "response": note + self._prompt("enrollment")}

        if stage == "opportunity_detail":
            value = parse_opportunity_detail(message)
            if isinstance(value, Ambiguous):
                return {**update, "response": self._clarify(stage, value)}
            if not value and (result := self.jev(message, "opportunity_detail")):
                value, update["jev_diagnostic"] = result["value"], result
            if not value:
                return {**update, "response": self._prompt(stage)}
            if value == "qle":
                return {
                    **update, "enrollment_reason": value, "eligibility_status": "needs_benefeds_verification",
                    "stage": "qle_event",
                    "response": _numbered_prompt("Which qualifying life event applies?", QLE_EVENTS),
                }
            note = (
                "New-hire/newly-eligible route selected. The brochure says enrollment is available within "
                "60 days after becoming eligible; BENEFEDS must verify that condition (brochure page 9)."
            )
            return {
                **update, "enrollment_reason": value, "eligibility_status": "needs_benefeds_verification",
                "stage": "enrollment", "response": note + "\n\n" + self._prompt("enrollment"),
            }

        if stage == "enrollment":
            value = _number_or_alias(message, ENROLLMENTS, {
                "Self Only": ("self only",), "Self Plus One": ("self plus one", "self 1"),
                "Self and Family": ("self and family", "family"),
            })
            if isinstance(value, Ambiguous):
                return {**update, "response": self._clarify(stage, value)}
            if not value:
                return {**update, "response": self._prompt(stage)}
            return {**update, "enrollment": value, "stage": "state", "response": self._prompt("state")}

        if stage == "state":
            value = message.strip().upper()
            if not re.fullmatch(r"[A-Z]{2}", value):
                return {**update, "response": self._prompt(stage)}
            return {**update, "state_code": value, "stage": "zip", "response": self._prompt("zip")}

        if stage == "zip":
            zip_code = message.strip()
            try:
                rate_code = self.tables.rate_code(state["state_code"], zip_code)
            except ValueError as error:
                return {**update, "response": f"{error} {self._prompt(stage)}"}
            return {
                **update, "zip_code": zip_code[:5], "rate_code": rate_code, "stage": "need",
                "response": f"That is 2026 dental rate code {rate_code} (guide page 10).\n\n{self._prompt('need')}",
            }

        if stage == "need":
            value = parse_need(message)
            if isinstance(value, Ambiguous):
                return {**update, "response": self._clarify(stage, value)}
            if not value and (result := self.jev(message, "need")):
                value, update["jev_diagnostic"] = result["value"], result
            if not value:
                return {**update, "response": self._prompt(stage)}
            plan = "Standard" if value == "routine" else "High" if value in {"major", "orthodontia", "maximum"} else ""
            if not plan:
                return {
                    **update, "dental_need": value, "recommended_plan": "Compare",
                    "stage": "plan",
                    "response": (
                        "No single plan can be assigned from that preference. High emphasizes maximum coverage; "
                        "Standard emphasizes preventive/routine care and the lowest premium (guide pages 4, 6–7).\n\n"
                        + self._prompt("plan")
                    ),
                }
            reason = (
                "Standard is the guide's lowest-premium plan for preventive and routine care."
                if plan == "Standard" else
                "High provides the guide's maximum coverage, unlimited annual maximum, and lower member shares for Classes B–D."
            )
            return {
                **update, "dental_need": value, "recommended_plan": plan, "stage": "plan",
                "response": f"Recommended plan: {plan}. {reason}\n\n{self._prompt('plan')}",
            }

        if stage == "plan":
            value = _number_or_alias(message, PLANS, {"High": ("high",), "Standard": ("standard", "std")})
            if isinstance(value, Ambiguous):
                return {**update, "response": self._clarify(stage, value)}
            if not value:
                return {**update, "response": self._prompt(stage)}
            premium = self.tables.premium(value, state["status"], state["enrollment"], state["rate_code"])
            verification = (
                "Your enrollment opportunity still requires BENEFEDS verification. "
                if state.get("eligibility_status") == "needs_benefeds_verification" else ""
            )
            return {
                **update, "selected_plan": value, "premium": premium, "stage": "complete", "complete": True,
                "response": (
                    f"Enrollment estimate complete: {value}, {state['enrollment']}, rate code {state['rate_code']}, "
                    f"{premium} {self.tables.period(state['status'])}. {verification}"
                    "To enroll, visit BENEFEDS.gov or call 1-877-888-3337 (guide pages 11–12). "
                    "This prototype recommends and estimates; it does not enroll you."
                ),
            }

        return {"response": "Enrollment flow complete. Type 'start over' to begin again."}

    # QLE node 1: normalize the event. Jev is a fail-closed fallback only.
    def qle_route_event(self, state: EnrollmentState) -> EnrollmentState:
        event = parse_qle_event(state.get("message", ""))
        if isinstance(event, Ambiguous):
            return {"stage": "qle_event", "jev_diagnostic": {}, "response": self._clarify("qle_event", event)}
        diagnostic: dict[str, Any] = {}
        if not event and (result := self.jev(state.get("message", ""), "qle_event")):
            event, diagnostic = result["value"], result
        if event not in QLE_MATRIX:
            return {
                "stage": "qle_event", "jev_diagnostic": diagnostic,
                "response": "I couldn't identify one listed QLE.\n\n" +
                            _numbered_prompt("Which qualifying life event applies?", QLE_EVENTS),
            }
        allowed_labels = {
            "new_enrollment": "starting a new enrollment",
            "increase_enrollment": "increasing the enrollment type",
            "decrease_enrollment": "decreasing the enrollment type",
            "cancel_enrollment": "cancelling enrollment",
            "change_plan": "changing from one plan to another",
        }
        allowed = [allowed_labels[action] for action, rule in QLE_MATRIX[event].items() if rule]
        return {
            "qle_event": event,
            "qle_decision": {
                "terminal_lookup": True,
                "reason": "The 2026 QLE table permits " + ", ".join(allowed) + ".",
            },
            "stage": "qle_information_complete", "jev_diagnostic": diagnostic,
            "response": "",
        }

    # Every QLE selection terminates here after showing its complete brochure row.
    def qle_complete(self, state: EnrollmentState) -> EnrollmentState:
        decision = state.get("qle_decision", {})
        policy_table = format_qle_action_table(state["qle_event"])
        result = (
            "QLE policy lookup complete. " + decision.get("reason", "") +
            " Select an allowed action through BENEFEDS.gov or call 1-877-888-3337."
            f"\n\n{policy_table}\n\nThis QLE session is complete. Click **Start over** to begin a new enrollment session."
        )
        cleared: EnrollmentState = {
            "stage": "complete", "response": result,
            "complete": True, "member_type": "", "status": "", "enrollment_opportunity": "",
            "enrollment_reason": "", "eligibility_status": "", "enrollment": "",
            "state_code": "", "zip_code": "", "rate_code": "", "dental_need": "",
            "recommended_plan": "", "selected_plan": "", "premium": "", "qle_event": "",
            "qle_decision": {},
        }
        return cleared

    @staticmethod
    def route_after_start(_: EnrollmentState) -> str:
        return END

    def _build(self):
        graph = StateGraph(EnrollmentState)
        graph.add_node("start", self.start)
        graph.add_node("process_answer", self.process)
        graph.add_node("qle_route_event", self.qle_route_event)
        graph.add_node("qle_complete", self.qle_complete)

        def entry(state: EnrollmentState) -> str:
            stage = state.get("stage", "")
            if not stage:
                return "start"
            if stage == "qle_event":
                return "qle_route_event"
            return "process_answer"

        graph.add_conditional_edges(
            START,
            entry,
            {
                "start": "start", "process_answer": "process_answer",
                "qle_route_event": "qle_route_event",
            },
        )
        graph.add_edge("start", END)
        graph.add_edge("process_answer", END)
        # Re-asking for the event (unrecognised or ambiguous) ends the turn; only a known event completes.
        graph.add_conditional_edges(
            "qle_route_event",
            lambda state: "qle_complete" if state.get("stage") == "qle_information_complete" else END,
            {"qle_complete": "qle_complete", END: END},
        )
        graph.add_edge("qle_complete", END)
        return graph.compile(checkpointer=MemorySaver())

    def reply(self, message: str, thread_id: str = "default") -> tuple[str, dict[str, Any]]:
        result = self.graph.invoke(
            {"message": message}, {"configurable": {"thread_id": thread_id}}
        )
        return result["response"], dict(result)

    def mermaid(self) -> str:
        return self.graph.get_graph().draw_mermaid()
