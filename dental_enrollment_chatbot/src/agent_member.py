"""Run the enrollment chatbot against simulated members (an LLM plays the member).

Each persona has a fact card the simulated member answers from, a speaking style,
and the outcome the chatbot should reach. The chatbot runs locally with Jev
disabled, so this exercises the keyword parsers and clarifying questions.
The member is Amazon Nova Lite on Bedrock (your AWS credentials, us-west-2).

    cd dental_enrollment_chatbot
    python src/agent_member.py                 # all personas
    python src/agent_member.py --persona widow --quiet
"""

from __future__ import annotations

import argparse
import sys

import boto3

from enrollment_graph import DentalEnrollmentGraph

MODEL = "amazon.nova-lite-v1:0"
MAX_TURNS = 14

PERSONAS = {
    "routine-retiree": {
        "facts": "You are a retired Army officer (retired uniformed services). You are enrolling during "
                 "2026 Open Season. Coverage just for yourself. You live in Austin, Texas, ZIP 78701. "
                 "You only need cleanings and checkups and want the cheapest premium. "
                 "You accept whatever plan is recommended.",
        "style": "Brief and plain. Never use menu numbers; answer in words.",
        "expect": {"member_type": "retired_uniformed", "enrollment_opportunity": "open_season",
                   "recommended_plan": "Standard", "complete": True},
    },
    "widow": {
        "facts": "Your husband died last month. He was a retired federal employee, and you were covered "
                 "as his spouse. You want to know what you can change about your dental coverage now.",
        "style": "Conversational, a little upset, explains in full sentences, never says 'QLE'.",
        "expect": {"member_type": "eligible_family", "status": "Retired",
                   "qle_event": "lose_family_member", "complete": True},
    },
    "new-baby": {
        "facts": "You are an active federal employee at the VA. You and your wife just had a baby two "
                 "weeks ago and you want to add the baby to your dental plan.",
        "style": "Casual, mentions the baby and your wife, does not know insurance terms.",
        "expect": {"member_type": "active_employee", "qle_event": "acquire_family_member", "complete": True},
    },
    "braces-new-hire": {
        "facts": "You started a federal job last week (new hire, active employee). Coverage for you and "
                 "one child. You live in Modesto, California, ZIP 95350. Your child needs braces. "
                 "You accept whatever plan is recommended.",
        "style": "Rambling: often adds unrelated detail, sometimes answers two questions at once.",
        "expect": {"member_type": "active_employee", "enrollment_reason": "newly_eligible",
                   "enrollment": "Self Plus One", "recommended_plan": "High", "complete": True},
    },
}

TRACKED = ("member_type", "status", "enrollment_opportunity", "enrollment_reason", "qle_event",
           "enrollment", "rate_code", "recommended_plan", "selected_plan", "premium")


def member_reply(client, persona: dict, transcript: list[tuple[str, str]]) -> str:
    """The simulated member's next message, answering only from the fact card."""
    system = (
        "You are role-playing a member of a federal dental plan talking to an enrollment chatbot.\n"
        f"FACTS (answer only from these; if asked something not covered, say you don't know):\n{persona['facts']}\n"
        f"STYLE: {persona['style']}\n"
        "Reply with only your next message to the chatbot, one or two sentences. "
        "If the chatbot offers numbered options and your facts clearly match one, you may answer with words or the number."
    )
    # The chatbot is the "user" side of this conversation; the member is the assistant.
    messages = [{"role": "user" if who == "bot" else "assistant", "content": [{"text": text}]}
                for who, text in transcript]
    out = client.converse(modelId=MODEL, system=[{"text": system}], messages=messages,
                          inferenceConfig={"maxTokens": 120, "temperature": 0.7})
    return out["output"]["message"]["content"][0]["text"].strip()


def run(name: str, persona: dict, client, quiet: bool) -> dict:
    bot = DentalEnrollmentGraph(jev=lambda *_: None)
    thread = f"agent-{name}"
    reply, state = bot.reply("", thread)
    transcript = [("bot", reply)]
    seen: dict = {}
    clarifications = reprompts = 0
    if not quiet:
        print(f"\n=== {name} ===\nBOT: {reply}")
    for _ in range(MAX_TURNS):
        said = member_reply(client, persona, transcript)
        transcript.append(("member", said))
        previous = transcript[-2][1]
        reply, state = bot.reply(said, thread)
        transcript.append(("bot", reply))
        seen.update({k: state[k] for k in TRACKED if state.get(k)})  # QLE completion clears state
        clarifications += "could mean more than one" in reply
        reprompts += reply.strip() == previous.strip() or "couldn't" in reply
        if not quiet:
            print(f"MEMBER: {said}\nBOT: {reply}")
        if state.get("complete"):
            break
    outcome = {**seen, "complete": bool(state.get("complete"))}
    wrong = {k: (outcome.get(k), v) for k, v in persona["expect"].items() if outcome.get(k) != v}
    return {"persona": name, "passed": not wrong, "turns": len(transcript) // 2,
            "clarifications": clarifications, "reprompts": reprompts, "wrong": wrong}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--persona", default="all", choices=["all", *PERSONAS])
    parser.add_argument("--quiet", action="store_true", help="summary only, no transcripts")
    args = parser.parse_args()
    client = boto3.client("bedrock-runtime", region_name="us-west-2")
    names = list(PERSONAS) if args.persona == "all" else [args.persona]
    results = [run(n, PERSONAS[n], client, args.quiet) for n in names]
    print("\npersona            result  turns  clarify  reprompt  mismatches (got, expected)")
    for r in results:
        print(f"{r['persona']:<18} {'PASS' if r['passed'] else 'FAIL':<7} {r['turns']:>5}  {r['clarifications']:>7}"
              f"  {r['reprompts']:>8}  {r['wrong'] or ''}")
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
