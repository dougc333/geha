#!/usr/bin/env python3
"""GEHA 2026 dental (FEDVIP) + medical (FEHB) enrollment chatbot: one state machine, structured RAG.

Shared slots (employed or retired, enrollment type, which line of coverage) are asked once.
Dental adds ZIP -> rate code -> dental plan; medical adds the plan option (no ZIP: FEHB
premiums are national). Every premium, rate code and benefit in a reply is a table row
parsed from GEHA's PDFs (dental_tables.py, medical_tables.py); the message parser only
fills slots.

    understand ─▶ answer_benefits? ─▶ ask_line | ask_zip | find_rate_code ─▶ ask_state
                                    | ask_status | ask_enrollment | ask_dental_plan
                                    | ask_medical_plan | quote

    python benefits_bot.py          # terminal chat; streamlit run benefits_chat_app.py for the web UI
"""

from __future__ import annotations

import re
from typing import Any, Callable, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from dental_enrollment import TOPICS as DENTAL_TOPICS
from dental_tables import BENEFITS as DENTAL_BENEFITS
from dental_tables import DentalTables
from medical_tables import PLANS as MEDICAL_PLANS
from medical_tables import MedicalTables

ENROLLMENT = ("Self Only", "Self Plus One", "Self and Family")
# medical benefit topic -> (message pattern, SBC service labels it covers)
MEDICAL_TOPICS = {
    "primary care": (r"primary care|\bpcp\b|sick visit|doctor visit", ["primary care"]),
    "specialist": (r"specialist", ["specialist"]),
    "preventive care": (r"preventive|annual physical|screening|immuniz|vaccin|flu shot", ["preventive"]),
    "lab and x-ray": (r"\blab\b|blood work|x-?ray|diagnostic", ["diagnostic"]),
    "imaging": (r"\bmri\b|ct scan|pet scan|imaging", ["imaging"]),
    "prescription drugs": (r"prescription|\bdrugs?\b|\brx\b|generic|brand|pharmacy", ["drugs"]),
    "outpatient surgery": (r"outpatient surgery|ambulatory|surgery center", ["ambulatory surgery"]),
    "emergency room": (r"emergency room|\ber\b|emergency care", ["emergency room"]),
    "ambulance": (r"ambulance", ["transportation"]),
    "urgent care": (r"urgent care", ["urgent"]),
    "hospital stay": (r"hospital|inpatient stay|admission", ["hospital room"]),
    "mental health": (r"mental|behavioral|therapy|therapist|counsel|substance", ["outpatient services", "inpatient services"]),
    "pregnancy": (r"pregnan|maternity|prenatal|childbirth|delivery|having a baby", ["office visits", "childbirth"]),
    "home health care": (r"home health", ["home health"]),
    "rehabilitation": (r"rehab|physical therapy|habilitation", ["rehabilitation", "habilitation"]),
    "skilled nursing": (r"skilled nursing|nursing facility", ["skilled nursing"]),
    "medical equipment": (r"durable|wheelchair|cpap|glucose meter|medical equipment", ["durable"]),
    "hospice": (r"hospice", ["hospice"]),
    "children's eye care": (r"eye exam|glasses|vision", ["eye exam", "glasses"]),
}
MEDICAL_QUESTIONS = {"deductible": r"deductible", "out_of_pocket_limit": r"out[- ]of[- ]pocket|oop"}
SHARED_TOPICS = {"deductible", "lab and x-ray"}   # dental and medical both have one; ask which if unclear
STATE_KEYS = ("slots", "candidates", "topics", "quoted", "stage")   # what a client carries between turns
CLOSING = {
    "dental": "Dental: enroll at BENEFEDS.gov (G.E.H.A Connection Dental Federal) or call BENEFEDS at 1-877-888-3337.",
    "medical": "Medical: enroll through your agency's HR or benefits system, or your retirement system if retired, using the enrollment code above.",
    "dates": "The guides list Open Season for 2026 benefits as November 10 to December 8, 2025; check current dates.",
}


class Chat(TypedDict, total=False):
    message: str
    slots: dict[str, Any]   # line, status, enrollment, zip, state, rate_code, dental_plan, medical_plan
    candidates: list[str]
    topics: list[str]       # benefit topics waiting to be answered ("dental:..." / "medical:..." / "either:...")
    parts: list[str]
    quoted: str
    stage: str


def rule_extract(message: str, stage: str, candidates: list[str], slots: dict) -> dict[str, Any]:
    text, out = message.lower(), {}
    if m := re.search(r"\b(\d{5})(?:-\d{4})?\b", message):
        out["zip"] = m.group(1)
    if stage == "ask_state" and (hits := [s for s in candidates if s.lower() in set(re.findall(r"[a-z]{2}", text))]):
        out["state"] = hits[0]
    if re.search(r"retire|annuitant", text):
        out["status"] = "RETIRED"
    elif re.search(r"employ|active|work for|federal worker|\bfed\b", text):
        out["status"] = "EMPLOYED"
    if re.search(r"family|kids|children|son|daughter", text):
        out["enrollment"] = "Self and Family"
    elif re.search(r"plus one|\+ ?1|spouse|partner|wife|husband", text):
        out["enrollment"] = "Self Plus One"
    elif re.search(r"self only|just me|only me|myself|single", text):
        out["enrollment"] = "Self Only"

    dental = bool(re.search(r"dental|dentist|teeth|tooth", text))
    medical = bool(re.search(r"medical|health plan|health insurance|fehb|elevate|hdhp", text))
    if stage == "ask_line" and re.search(r"\bboth\b|\beach\b|all of", text) or (dental and medical):
        out["line"] = "both"
    elif dental:
        out["line"] = "dental"
    elif medical:
        out["line"] = "medical"

    # Plan names: Elevate / Elevate Plus / HDHP are medical only; High and Standard exist in both lines,
    # so they go to the line being asked about, the line named in the message, or the only line chosen.
    compare = bool(re.search(r"\bboth\b|compare|either|not sure|don't know|all\b", text))
    if m := re.search(r"elevate plus|elevate\+|elevate|hdhp|high deductible", text):
        out["medical_plan"] = {"elevate plus": "Elevate Plus", "elevate+": "Elevate Plus", "elevate": "Elevate",
                               "hdhp": "HDHP", "high deductible": "HDHP"}[m.group(0)]
    shared = "HIGH" if re.search(r"\bhigh\b(?! deductible)", text) else "STANDARD" if re.search(r"\bstandard\b", text) else None
    line = slots.get("line")
    target = ("dental" if stage == "ask_dental_plan" else "medical" if stage == "ask_medical_plan"
              else "dental" if dental and not medical else "medical" if medical and not dental
              else line if line in ("dental", "medical") else None)
    if shared and target == "dental":
        out["dental_plan"] = shared
    elif shared and target == "medical" and "medical_plan" not in out:
        out["medical_plan"] = shared.title()
    elif compare and target == "dental" and stage != "ask_line":
        out["dental_plan"] = "BOTH"
    elif compare and target == "medical" and stage != "ask_line" and "medical_plan" not in out:
        out["medical_plan"] = "ALL"

    topics = [f"dental:{t}" for t, p in DENTAL_TOPICS.items() if re.search(p, text) and t != "deductible"]
    topics += [f"medical:{t}" for t, (p, _) in MEDICAL_TOPICS.items() if re.search(p, text) and t not in SHARED_TOPICS]
    topics += [f"medical:{q}" for q, p in MEDICAL_QUESTIONS.items() if q != "deductible" and re.search(p, text)]
    for shared_topic, pattern in (("deductible", r"deductible"), ("lab and x-ray", MEDICAL_TOPICS["lab and x-ray"][0])):
        if re.search(pattern, text):
            topics.append(f"either:{shared_topic}")
    out["topics"] = topics
    out["reset"] = bool(re.search(r"start over|restart|reset", text))
    return out


class BenefitsBot:
    def __init__(self, dental: DentalTables | None = None, medical: MedicalTables | None = None,
                 extract: Callable | None = None):
        self.dental = dental or DentalTables()
        self.medical = medical or MedicalTables()
        self.extract = extract or rule_extract
        self.graph = self._build(checkpointer=MemorySaver())   # keeps each thread's state in memory
        self.stateless = self._build(checkpointer=None)        # the caller passes the state back in (serverless)

    # helpers
    @staticmethod
    def needs(slots: dict, line: str) -> bool:
        return slots.get("line") in (line, "both")

    @staticmethod
    def _signature(sl: dict) -> str:
        return "|".join(str(sl.get(k)) for k in ("line", "status", "enrollment", "rate_code", "dental_plan", "medical_plan"))

    # nodes
    def understand(self, s: Chat) -> Chat:
        got = self.extract(s["message"], s.get("stage", ""), s.get("candidates", []), s.get("slots", {}))
        reset = got.get("reset")
        slots = {} if reset else dict(s.get("slots", {}))
        candidates = [] if reset else s.get("candidates", [])
        if got.get("zip") and got["zip"] != slots.get("zip"):
            slots = {k: v for k, v in slots.items() if k not in ("zip", "state", "rate_code")}
            slots["zip"], candidates = got["zip"], []
        if got.get("line"):
            old = slots.get("line")
            slots["line"] = "both" if old and old != got["line"] else got["line"]
        for key in ("state", "status", "enrollment", "dental_plan", "medical_plan"):
            if got.get(key):
                slots[key] = got[key]
        pending = [] if reset else s.get("topics", [])
        return {"slots": slots, "candidates": candidates, "topics": pending + got.get("topics", []), "parts": [],
                "quoted": "" if reset else s.get("quoted", "")}

    def answer_benefits(self, s: Chat) -> Chat:
        sl, lines, waiting = s["slots"], [], []
        for topic in s["topics"]:
            line, name = topic.split(":", 1)
            if line == "either":
                if sl.get("line") in ("dental", "medical", "both"):
                    lines += self._dental(name, sl) if self.needs(sl, "dental") else []
                    lines += self._medical(name, sl) if self.needs(sl, "medical") else []
                else:
                    waiting.append(topic)
            else:
                lines += self._dental(name, sl) if line == "dental" else self._medical(name, sl)
        return {"parts": s["parts"] + lines, "topics": waiting}

    def _dental(self, topic: str, sl: dict) -> list[str]:
        topic = "deductible" if topic == "deductible" else "preventive" if topic == "lab and x-ray" else topic
        row = DENTAL_BENEFITS.get(topic)
        if not row:
            return []
        cols = {"HIGH": ["High"], "STANDARD": ["Standard in-network", "Standard out-of-network"]}.get(
            sl.get("dental_plan"), ["High", "Standard in-network", "Standard out-of-network"])
        return [f"Dental, {row['label']} (dental guide page {row['page']}): " + "; ".join(f"{c}: {row[c]}" for c in cols) + "."]

    def _medical(self, topic: str, sl: dict) -> list[str]:
        plan = sl.get("medical_plan")
        plans = [plan] if plan in MEDICAL_PLANS else list(MEDICAL_PLANS)
        if topic in ("deductible", "out_of_pocket_limit"):
            label = "deductible" if topic == "deductible" else "out-of-pocket limit"
            return [f"Medical {label}, {p} (SBC page 1): {self.medical.questions[p].get(topic, 'see the SBC')}" for p in plans]
        _, labels = MEDICAL_TOPICS[topic]
        out = []
        for p in plans:
            for row in self.medical.find(p, labels):
                limits = "" if row.limits in ("", "None") else f" Note: {row.limits}"
                out.append(f"Medical, {p}, {row.service} (SBC page {row.page}): in-network {row.network}; "
                           f"out-of-network {row.out_of_network}.{limits}")
        if any("*" in line for line in out):
            out.append("* = the deductible does not apply.")
        return out

    def find_rate_code(self, s: Chat) -> Chat:
        slots = dict(s["slots"])
        found = self.dental.rate_code(slots["zip"], slots.get("state"))
        if "error" in found:
            slots.pop("zip"), slots.pop("state", None)
            return {"slots": slots, "parts": s["parts"] + [found["error"]]}
        if "ask_state" in found:
            return {"candidates": found["ask_state"]}
        slots.update(rate_code=found["rate_code"], state=found["state"])
        return {"slots": slots, "candidates": [], "parts": s["parts"] + [
            f"ZIP {slots['zip']} ({found['state']}) is dental rate code {found['rate_code']} (dental guide page 10)."]}

    def quote(self, s: Chat) -> Chat:
        sl, lines, total, period = s["slots"], [], 0.0, ""
        who = "an active federal employee" if sl["status"] == "EMPLOYED" else "a retiree"
        lines.append(f"2026 premiums for {who}, {sl['enrollment']}:")
        single = True
        if self.needs(sl, "dental"):
            plan = None if sl["dental_plan"] == "BOTH" else sl["dental_plan"]
            q = self.dental.premium(sl["rate_code"], sl["status"], sl["enrollment"], plan)
            for p, v in q["premiums"].items():
                lines.append(f"  Dental {p} (rate code {sl['rate_code']}): {v}")
            if plan:
                total += self.dental.premiums[(plan, q["status"], q["enrollment"], sl["rate_code"])]
            single &= bool(plan)
        if self.needs(sl, "medical"):
            plans = [sl["medical_plan"]] if sl["medical_plan"] in MEDICAL_PLANS else list(MEDICAL_PLANS)
            for p in plans:
                q = self.medical.premium(p, sl["status"], sl["enrollment"])
                period = q["period"]
                lines.append(f"  Medical {p} (enrollment code {q['enrollment_code']}): ${q['value']:,.2f} {period}")
            if len(plans) == 1:
                total += self.medical.premium(plans[0], sl["status"], sl["enrollment"])["value"]
            single &= len(plans) == 1
        if sl.get("line") == "both" and single:
            period = "biweekly" if sl["status"] == "EMPLOYED" else "monthly"
            lines.append(f"  Total: ${total:,.2f} {period}")
        lines += [CLOSING[k] for k in ("dental", "medical") if self.needs(sl, k)] + [CLOSING["dates"]]
        return {"parts": s["parts"] + lines, "quoted": self._signature(sl), "stage": "quote"}

    # routing
    def route(self, s: Chat) -> str:
        sl = s["slots"]
        ready = [t for t in s.get("topics", []) if not t.startswith("either:") or sl.get("line")]
        if ready:
            return "answer_benefits"
        if not sl.get("line"):
            return "ask_line"
        if self.needs(sl, "dental"):
            if not sl.get("zip"):
                return "ask_zip"
            if not sl.get("rate_code"):
                return "ask_state" if s.get("candidates") and not sl.get("state") else "find_rate_code"
        for slot, node in (("status", "ask_status"), ("enrollment", "ask_enrollment")):
            if not sl.get(slot):
                return node
        if self.needs(sl, "dental") and not sl.get("dental_plan"):
            return "ask_dental_plan"
        if self.needs(sl, "medical") and not sl.get("medical_plan"):
            return "ask_medical_plan"
        return END if s.get("quoted") == self._signature(sl) else "quote"

    def _build(self, checkpointer):
        hi, std = DENTAL_BENEFITS["annual_maximum"]["High"], DENTAL_BENEFITS["annual_maximum"]["Standard in-network"]
        asks = {
            "ask_line": lambda s: ("Do you want a quote for dental, medical, or both?" +
                                   (" (Dental and medical both have a deductible; which one did you mean?)"
                                    if any(t.startswith("either:") for t in s.get("topics", [])) else "")),
            "ask_zip": lambda s: "What's your ZIP code? Your dental premium depends on your rate code, which comes from your ZIP.",
            "ask_state": lambda s: (f"ZIP prefix {s['slots']['zip'][:3]} is used in {', '.join(s['candidates'])}, "
                                    "which have different dental rate codes. Which state are you in?"),
            "ask_status": lambda s: "Are you an active federal employee (biweekly premiums) or a retiree (monthly premiums)?",
            "ask_enrollment": lambda s: "Who will be covered: Self Only, Self Plus One or Self and Family?",
            "ask_dental_plan": lambda s: (f"Which dental plan: High (annual maximum {hi.lower()}) or Standard (lowest premium, "
                                          f"{std} in-network maximum)? Say 'both' to compare."),
            "ask_medical_plan": lambda s: (f"Which medical plan option: {', '.join(MEDICAL_PLANS)}? "
                                           "Say 'compare' to see all five."),
        }
        g = StateGraph(Chat)
        g.add_node("understand", self.understand)
        g.add_node("answer_benefits", self.answer_benefits)
        g.add_node("find_rate_code", self.find_rate_code)
        g.add_node("quote", self.quote)
        for stage, text in asks.items():
            g.add_node(stage, (lambda st, fn: lambda s: {"stage": st, "parts": s["parts"] + [fn(s)]})(stage, text))
            g.add_edge(stage, END)
        nexts = ["answer_benefits", "find_rate_code", "quote", END, *asks]
        g.add_edge(START, "understand")
        for node in ("understand", "answer_benefits", "find_rate_code"):
            g.add_conditional_edges(node, self.route, [n for n in nexts if n != node])
        g.add_edge("quote", END)
        return g.compile(checkpointer=checkpointer)

    def reply(self, message: str, thread: str = "default") -> str:
        out = self.graph.invoke({"message": message}, {"configurable": {"thread_id": thread}})
        return "\n".join(out["parts"]) or "Anything else? Ask about a benefit, or change your coverage or plan."

    def step(self, message: str, state: dict | None = None) -> tuple[str, dict]:
        """One turn without server-side memory: returns the reply and the state to send next time."""
        out = self.stateless.invoke({**(state or {}), "message": message})
        reply = "\n".join(out["parts"]) or "Anything else? Ask about a benefit, or change your coverage or plan."
        return reply, {k: out[k] for k in STATE_KEYS if k in out}

    def state(self, thread: str = "default") -> dict:
        snap = self.graph.get_state({"configurable": {"thread_id": thread}})
        return dict(snap.values.get("slots", {})) if snap and snap.values else {}


def main() -> None:
    bot = BenefitsBot()
    print("GEHA 2026 dental + medical quote. 'start over' resets, Ctrl-D quits.")
    print(bot.reply("hi"))
    while True:
        try:
            message = input("\nyou> ").strip()
        except EOFError:
            break
        if message:
            print(bot.reply(message))


if __name__ == "__main__":
    main()
