"""Compare JEV and DSPy on identical scripted end-to-end personas."""

from __future__ import annotations

import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

from enrollment_graph import DentalEnrollmentGraph  # noqa: E402
from dspy_router import DspyExtractor  # noqa: E402
from jev_router import JevExtractor  # noqa: E402


PERSONAS = {
    "routine-retiree": {
        "answers": {
            "member_type": ["After 22 years in the Army, I am now retired."],
            "opportunity": ["I am enrolling during the current Open Season."],
            "enrollment": ["Coverage is only for me: Self Only."],
            "state": ["Austin, Texas is home."],
            "zip": ["My ZIP code is 78701."],
            "need": ["Only cleanings and checkups; I want the cheapest premium."],
            "plan": ["I accept the recommended Standard plan."],
        },
        "expected": "Enrollment estimate complete: Standard, Self Only, rate code 3",
    },
    "widow": {
        "answers": {
            "member_type": ["I was covered as the spouse of an eligible federal enrollee."],
            "family_sponsor": ["My husband was a retired federal employee."],
            "opportunity": ["My covered husband died last month, so I need to change coverage."],
            "opportunity_detail": ["This is a qualifying life event because my husband died."],
            "qle_event": ["I lost my covered family member when my husband passed away."],
        },
        "expected": "Losing a covered family member",
    },
    "new-baby": {
        "answers": {
            "member_type": ["I am an active federal employee at the VA."],
            "opportunity": ["My wife and I had a baby two weeks ago and need to add the baby."],
            "opportunity_detail": ["The birth is a qualifying life event."],
            "qle_event": ["We acquired an eligible family member when our baby was born."],
        },
        "expected": "Acquiring an eligible family member",
    },
    "braces-new-hire": {
        "answers": {
            "member_type": [
                "I am an active federal employee and started my new federal job last week; "
                "my child also needs braces."
            ],
            "opportunity": [
                "I keep calling it a QLE, but the actual reason is that I was newly hired last week."
            ],
            "opportunity_detail": [
                "Both sound relevant, but I am explicitly a new hire and also said QLE.",
                "New hire or newly eligible.",
            ],
            "enrollment": ["Please cover me and one child: Self Plus One."],
            "state": ["I live near Modesto in California and love the farmers market."],
            "zip": ["Our ZIP is 95350."],
            "need": ["My child needs braces, so our need is orthodontia."],
            "plan": ["I accept the recommended High plan."],
        },
        "expected": "Enrollment estimate complete: High, Self Plus One, rate code 4",
    },
}


class MeteredExtractor:
    def __init__(self, inner):
        self.inner = inner
        self.name = inner.name
        self.calls = 0
        self.seconds = []

    def __call__(self, *args, **kwargs):
        self.calls += 1
        started = time.perf_counter()
        try:
            return self.inner(*args, **kwargs)
        finally:
            self.seconds.append(time.perf_counter() - started)


def run_persona(extractor, name: str, persona: dict) -> dict:
    metered = MeteredExtractor(extractor)
    graph = DentalEnrollmentGraph(jev=lambda *_: None, extractor=metered)
    thread = f"comparison-{extractor.name}-{name}-{time.time_ns()}"
    response, state = graph.reply("", thread)
    transcript = [{"stage": "start", "answer": "", "response": response}]
    used: dict[str, int] = {}
    clarifications = reprompts = 0
    started = time.perf_counter()

    for _ in range(16):
        if state.get("complete"):
            break
        stage = state.get("stage", "")
        choices = persona["answers"].get(stage)
        index = used.get(stage, 0)
        if not choices or index >= len(choices):
            transcript.append({"stage": stage, "error": "No scripted answer available"})
            break
        answer = choices[index]
        used[stage] = index + 1
        previous_stage = stage
        response, state = graph.reply(answer, thread)
        clarifications += "could mean more than one" in response
        reprompts += state.get("stage") == previous_stage and not state.get("complete")
        transcript.append({"stage": stage, "answer": answer, "response": response,
                           "stage_after": state.get("stage")})

    elapsed = time.perf_counter() - started
    final_response = transcript[-1].get("response", "")
    passed = bool(state.get("complete")) and persona["expected"] in final_response
    return {
        "persona": name,
        "passed": passed,
        "complete": bool(state.get("complete")),
        "expected": persona["expected"],
        "final_response": final_response,
        "turns": sum(bool(row.get("answer")) for row in transcript),
        "clarifications": clarifications,
        "reprompts": reprompts,
        "model_calls": metered.calls,
        "model_seconds": round(sum(metered.seconds), 4),
        "elapsed_seconds": round(elapsed, 4),
        "transcript": transcript,
    }


def run_model(extractor) -> dict:
    rows = [run_persona(extractor, name, persona) for name, persona in PERSONAS.items()]
    lm = getattr(extractor, "lm", None)
    history = getattr(lm, "history", []) or []
    token_values = []
    costs = []
    for item in history:
        usage = item.get("usage") or {}
        if (tokens := usage.get("total_tokens") or usage.get("totalTokens")) is not None:
            token_values.append(int(tokens))
        if item.get("cost") is not None:
            costs.append(float(item["cost"]))
    return {
        "name": extractor.name,
        "passed": sum(row["passed"] for row in rows),
        "personas": len(rows),
        "turns": sum(row["turns"] for row in rows),
        "clarifications": sum(row["clarifications"] for row in rows),
        "reprompts": sum(row["reprompts"] for row in rows),
        "model_calls": sum(row["model_calls"] for row in rows),
        "median_persona_seconds": round(statistics.median(row["elapsed_seconds"] for row in rows), 4),
        "total_tokens": sum(token_values) if token_values else None,
        "total_cost_usd": round(sum(costs), 6) if costs else None,
        "rows": rows,
    }


def main() -> None:
    results = [run_model(JevExtractor()), run_model(DspyExtractor())]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = Path(__file__).parents[1] / "runs" / f"trajectory-jev-vs-dspy-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    output = run_dir / "results.json"
    output.write_text(json.dumps(results, indent=2))

    print("\nEnd-to-end guarded trajectories")
    print(f"{'model':<8} {'passed':>8} {'turns':>7} {'ask':>5} {'reprompt':>9} "
          f"{'calls':>7} {'median':>9} {'tokens':>9} {'cost':>10}")
    for result in results:
        tokens = str(result["total_tokens"]) if result["total_tokens"] is not None else "n/a"
        cost = (f"${result['total_cost_usd']:.4f}"
                if result["total_cost_usd"] is not None else "n/a")
        print(f"{result['name']:<8} {result['passed']:>2}/{result['personas']:<5} "
              f"{result['turns']:>7} {result['clarifications']:>5} {result['reprompts']:>9} "
              f"{result['model_calls']:>7} {result['median_persona_seconds']:>8.2f}s "
              f"{tokens:>9} {cost:>10}")
    for result in results:
        for row in result["rows"]:
            print(f"{result['name']:<8} {row['persona']:<20} "
                  f"{'PASS' if row['passed'] else 'FAIL'} turns={row['turns']} "
                  f"ask={row['clarifications']} calls={row['model_calls']}")
    print(f"\nSaved raw trajectories: {output}")


if __name__ == "__main__":
    main()
