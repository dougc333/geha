#!/usr/bin/env python3
"""GEHA 2026 FEDVIP dental enrollment chatbot: a LangGraph state machine over structured tables.

Structured RAG: every rate code, premium and benefit in a reply is a row looked up from
tables parsed out of the 2026 dental benefits guide (dental_tables.py). Nothing is
embedded or searched by similarity, and no model writes a number.

Each user message runs one pass through the graph:

    understand ─▶ answer_benefits? ─▶ ask_zip | find_rate_code ─▶ ask_state
                                    | ask_status | ask_enrollment | ask_plan | quote

`understand` fills slots (ZIP, state, employed/retired, enrollment type, plan, benefit
topics) from the message, by rules or, with --llm, by an OpenAI structured-output call.
The router then moves to the first missing slot, so the conversation always follows the
guide's own steps: ZIP -> rate code (page 10) -> premium (page 11).

    python dental_enrollment.py            # rules only, no API key
    python dental_enrollment.py --llm      # OpenAI parses free-form replies (needs OPENAI_API_KEY)
"""

from __future__ import annotations

import argparse
import re
from typing import Any, Callable, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from dental_tables import BENEFIT_NOTES, BENEFITS, ENROLLMENT, PHONE, DentalTables

TOPICS = {
    "plan_comparison": (r"(?:high.*standard|standard.*high).*(?:benefit|coverage|feature)|"
                        r"(?:benefit|coverage|feature).*(?:high.*standard|standard.*high)"),
    "vision": r"vision|eye exam|frames|lenses|contact lenses?|lasik",
    "procedure_costs": r"(?:cost|price|pay).*(?:root canal|crown)|(?:root canal|crown).*(?:cost|price)",
    "whitening": r"whitening|smile brilliant",
    "toothbrush": r"electric toothbrush|caripro",
    "hearing": r"hearing aid|truhearing",
    "medical_alert": r"medical alert|life alert",
    "fitness": r"fitness|active\s*&\s*fit",
    "cleanings": r"cleaning",
    "preventive": r"exam|x-?ray|bitewing|preventive|check-?up",
    "teledentistry": r"teledent|virtual|video visit",
    "intermediate": r"filling|restoration|extraction|pulled|periodontal maintenance",
    "major": r"root canal|crown|bridge|denture|periodontal surgery|gum surgery",
    "orthodontics": r"ortho|braces|aligner|invisalign",
    "annual_maximum": r"annual max|yearly max|calendar year max|maximum benefit|\bmax(imum)?\b",
    "deductible": r"deductible",
    "implants": r"implant",
}
CLOSING = ("To enroll, visit BENEFEDS.gov and choose G.E.H.A Connection Dental Federal, or call BENEFEDS at "
           "1-877-888-3337. The guide lists Open Season for 2026 benefits as November 10 to December 8, 2025. "
           f"Questions: G.E.H.A FedVisers at {PHONE}.")


class Chat(TypedDict, total=False):
    message: str            # the latest user message
    slots: dict[str, Any]   # zip, state, rate_code, status, enrollment, plan
    candidates: list[str]   # states to choose from when a ZIP prefix is ambiguous
    topics: list[str]       # benefit topics asked about in this message
    parts: list[str]        # reply lines for this turn
    quoted: str             # slots of the last quote, to avoid repeating it
    stage: str              # the node that asked the last question


def rule_extract(message: str, stage: str, candidates: list[str]) -> dict[str, Any]:
    """Pull slot values out of a message with regular expressions."""
    text, out = message.lower(), {}
    if m := re.search(r"\b(\d{5})(?:-\d{4})?\b", message):
        out["zip"] = m.group(1)
    if stage == "ask_state":
        words = set(re.findall(r"[a-z]{2}", text))
        if hits := [s for s in candidates if s.lower() in words]:
            out["state"] = hits[0]
    if re.search(r"retire|annuitant", text):
        out["status"] = "RETIRED"
    elif re.search(r"employ|active|work for|federal worker", text):
        out["status"] = "EMPLOYED"
    if re.search(r"family|kids|children", text):
        out["enrollment"] = "Self and Family"
    elif re.search(r"plus one|\+ ?1|spouse|partner|wife|husband", text):
        out["enrollment"] = "Self Plus One"
    elif re.search(r"self only|just me|only me|myself|single", text):
        out["enrollment"] = "Self Only"
    if re.search(r"\bboth\b|compare|either|not sure|don't know", text):
        out["plan"] = "BOTH"
    elif re.search(r"\bhigh\b", text):
        out["plan"] = "HIGH"
    elif re.search(r"\bstandard\b", text):
        out["plan"] = "STANDARD"
    out["topics"] = [t for t, pattern in TOPICS.items() if re.search(pattern, text)]
    out["reset"] = bool(re.search(r"start over|restart|reset", text))
    return out


def llm_extract(llm: Any) -> Callable[[str, str, list[str]], dict[str, Any]]:
    """Structured-output extraction for free-form replies; rules fill anything the model leaves out."""
    from typing import Literal, Optional

    from pydantic import BaseModel, Field

    class Slots(BaseModel):
        zip: Optional[str] = Field(None, description="5-digit US ZIP code, if the user gave one")
        state: Optional[str] = Field(None, description="2-letter state code, only if the user named a state")
        status: Optional[Literal["EMPLOYED", "RETIRED"]] = None
        enrollment: Optional[Literal["Self Only", "Self Plus One", "Self and Family"]] = None
        plan: Optional[Literal["HIGH", "STANDARD", "BOTH"]] = None
        topics: list[Literal[tuple(TOPICS)]] = Field(default_factory=list, description="benefit topics asked about")
        reset: bool = False

    parser = llm.with_structured_output(Slots)

    def extract(message: str, stage: str, candidates: list[str]) -> dict[str, Any]:
        prompt = (f"A member is getting a 2026 GEHA dental premium quote. The bot last asked: {stage}. "
                  f"States offered: {candidates or 'n/a'}. Extract only what the member said.\n\nMember: {message}")
        got = {k: v for k, v in parser.invoke(prompt).model_dump().items() if v not in (None, [], False)}
        return {**rule_extract(message, stage, candidates), **got}

    return extract


class DentalEnrollmentBot:
    def __init__(self, tables: DentalTables | None = None, extract: Callable | None = None):
        self.tables = tables or DentalTables()
        self.extract = extract or rule_extract
        self.graph = self._build()

    # nodes
    def understand(self, s: Chat) -> Chat:
        got = self.extract(s["message"], s.get("stage", ""), s.get("candidates", []))
        slots = {} if got.get("reset") else dict(s.get("slots", {}))
        candidates = [] if got.get("reset") else s.get("candidates", [])
        if got.get("zip") and got["zip"] != slots.get("zip"):
            slots = {k: v for k, v in slots.items() if k not in ("zip", "state", "rate_code")}
            slots["zip"], candidates = got["zip"], []
        for key in ("state", "status", "enrollment", "plan"):
            if got.get(key):
                slots[key] = got[key]
        return {"slots": slots, "candidates": candidates, "topics": got.get("topics", []), "parts": [],
                "quoted": "" if got.get("reset") else s.get("quoted", "")}

    def answer_benefits(self, s: Chat) -> Chat:
        plan = s["slots"].get("plan")
        columns = {"HIGH": ["High"], "STANDARD": ["Standard in-network", "Standard out-of-network"]}.get(
            plan, ["High", "Standard in-network", "Standard out-of-network"])
        lines = []
        for topic in s["topics"]:
            row = BENEFITS[topic]
            values = "; ".join(f"{c}: {row[c]}" for c in columns)
            lines.append(f"{row['label']} (page {row['page']}). You pay, {values}.")
        if "preventive" in s["topics"]:
            lines.append(BENEFIT_NOTES[1])
        return {"parts": s["parts"] + lines, "topics": []}

    def find_rate_code(self, s: Chat) -> Chat:
        slots = dict(s["slots"])
        found = self.tables.rate_code(slots["zip"], slots.get("state"))
        if "error" in found:
            slots.pop("zip"), slots.pop("state", None)
            return {"slots": slots, "parts": s["parts"] + [found["error"]]}
        if "ask_state" in found:
            return {"candidates": found["ask_state"]}
        slots.update(rate_code=found["rate_code"], state=found["state"])
        line = f"ZIP {slots['zip']} ({found['state']}) is rate code {found['rate_code']} (guide page 10: {found['table_row']})."
        return {"slots": slots, "candidates": [], "parts": s["parts"] + [line]}

    def ask(self, stage: str, text: Callable[[Chat], str]) -> Callable[[Chat], Chat]:
        return lambda s: {"stage": stage, "parts": s["parts"] + [text(s)]}

    def quote(self, s: Chat) -> Chat:
        sl = s["slots"]
        plan = None if sl["plan"] == "BOTH" else sl["plan"]
        q = self.tables.premium(sl["rate_code"], sl["status"], sl["enrollment"], plan)
        who = "an active federal employee" if q["status"] == "EMPLOYED" else "a retiree"
        lines = [f"2026 premiums for {who}, {q['enrollment']}, rate code {q['rate_code']} (guide page 11):"]
        lines += [f"  {p}: {v}" for p, v in q["premiums"].items()]
        lines.append(CLOSING)
        return {"parts": s["parts"] + lines, "quoted": self._signature(sl), "stage": "quote"}

    # routing
    @staticmethod
    def _signature(slots: dict) -> str:
        return "|".join(str(slots.get(k)) for k in ("rate_code", "status", "enrollment", "plan"))

    def route(self, s: Chat) -> str:
        sl = s["slots"]
        if s.get("topics"):
            return "answer_benefits"
        if not sl.get("zip"):
            return "ask_zip"
        if not sl.get("rate_code"):
            return "ask_state" if s.get("candidates") and not sl.get("state") else "find_rate_code"
        for slot, node in (("status", "ask_status"), ("enrollment", "ask_enrollment"), ("plan", "ask_plan")):
            if not sl.get(slot):
                return node
        return END if s.get("quoted") == self._signature(sl) else "quote"

    def _build(self):
        g = StateGraph(Chat)
        high, std = BENEFITS["annual_maximum"]["High"], BENEFITS["annual_maximum"]["Standard in-network"]
        asks = {
            "ask_zip": lambda s: "What's your ZIP code? Your premium depends on your rate code, which comes from your ZIP.",
            "ask_state": lambda s: (f"ZIP prefix {s['slots']['zip'][:3]} is used in {', '.join(s['candidates'])}, "
                                    "which have different rate codes. Which state are you in?"),
            "ask_status": lambda s: "Are you an active federal employee (biweekly premiums) or a retiree (monthly premiums)?",
            "ask_enrollment": lambda s: f"Who will be covered: {', '.join(ENROLLMENT[:-1])} or {ENROLLMENT[-1]}?",
            "ask_plan": lambda s: (f"Which plan: High (annual maximum: {high.lower()}) or Standard (lowest premium, "
                                   f"{std} in-network annual maximum)? Say 'both' to compare."),
        }
        g.add_node("understand", self.understand)
        g.add_node("answer_benefits", self.answer_benefits)
        g.add_node("find_rate_code", self.find_rate_code)
        g.add_node("quote", self.quote)
        for stage, text in asks.items():
            g.add_node(stage, self.ask(stage, text))
            g.add_edge(stage, END)
        nexts = ["answer_benefits", "find_rate_code", "quote", END, *asks]
        g.add_edge(START, "understand")
        for node in ("understand", "answer_benefits", "find_rate_code"):
            g.add_conditional_edges(node, self.route, [n for n in nexts if n != node])
        g.add_edge("quote", END)
        return g.compile(checkpointer=MemorySaver())

    def reply(self, message: str, thread: str = "default") -> str:
        out = self.graph.invoke({"message": message}, {"configurable": {"thread_id": thread}})
        return "\n".join(out["parts"]) or "Anything else? Ask about a benefit, or change your ZIP, coverage or plan."


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--llm", action="store_true", help="parse replies with OpenAI structured output")
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()
    extract = None
    if args.llm:
        from dotenv import load_dotenv
        from langchain_openai import ChatOpenAI
        load_dotenv()
        extract = llm_extract(ChatOpenAI(model_name=args.model, temperature=0))
    bot = DentalEnrollmentBot(extract=extract)
    print("GEHA 2026 dental premium quote. Type 'start over' to reset, Ctrl-D to quit.")
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
