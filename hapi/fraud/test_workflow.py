"""Tests for the learn -> compile -> workflow path: spec loader, code steps, question
classifiers, runner, research sub-agent, router, replay, compiler and learning notes.
Synthetic claims, scripted models and stand-in tools: no HAPI, MCP server or LLM.

    cd hapi/fraud
    uv run --no-project --python 3.12 --with 'langchain==1.4.2' --with langchain-anthropic \\
        --with langchain-openai --with langchain-mcp-adapters --with httpx \\
        python -m unittest test_workflow -v
"""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

import compile_workflow
import runs
import workflow
import workflow_ops
from agent import parse_findings, write_note
from agent_permissions.testing import ScriptedChatModel, call
from questions import JevClassifier, LLMClassifier, RulesClassifier, make_classifier
from scoring import score

logging.getLogger("agent_permissions").setLevel(logging.CRITICAL)
QUESTION = "Investigate the claims for fraud."
# Letters only: scoring.py matches names with digits stripped.
NAMES = {i: f"Dr. {n}" for i, n in enumerate(["Ames", "Bell", "Cruz", "Dunn", "Eads", "Fox", "Gale", "Hart", "Ives"], 1)}


def claim(eob, provider, patient, date, code="A", service="Office visit", paid=100.0, minutes=30, hour=9, lines=1):
    return {"eob": f"ExplanationOfBenefit/{eob}", "provider": provider, "patient": patient, "facility": "",
            "date": date, "start": f"{date}T{hour:02d}:00:00+00:00", "minutes": minutes, "code": code,
            "service": service, "lines": lines, "paid": paid}


def make_claims():
    """Upcoder P1, duplicate biller P4, after-death biller P5 (P6 only certifies deaths),
    impossible day P7, and honest peers P2/P3."""
    rows, n = [], 0

    def add(*args, **kw):
        nonlocal n
        n += 1
        rows.append(claim(n, *args, **kw))
    for i in range(4):
        add("Practitioner/1", f"Patient/{10 + i}", f"2026-02-0{i + 1}", paid=300.0)
    for prov in ("Practitioner/2", "Practitioner/3"):
        for i in range(3):
            add(prov, f"Patient/{20 + i}", f"2026-03-0{i + 1}", paid=100.0)
    add("Practitioner/4", "Patient/30", "2026-04-01", code="B", service="Lab", paid=50.0)
    add("Practitioner/4", "Patient/30", "2026-04-01", code="B", service="Lab", paid=50.0)
    for d in ("2026-02-10", "2026-03-10", "2026-04-10"):
        add("Practitioner/5", "Patient/99", d, code="H", service="Home visit", paid=80.0)
    add("Practitioner/6", "Patient/99", "2026-01-03", code="D", service="Death Certification", paid=140.0)
    for i in range(12):
        add("Practitioner/7", f"Patient/{40 + i}", "2026-05-05", code="C", service="Consult", paid=90.0,
            minutes=60, hour=7 + i // 2)
    names = {f"Practitioner/{i}": n for i, n in NAMES.items()}
    return rows, names, {"Patient/99": "2026-01-01"}


def guilty_score(providers: dict[str, list[str]]) -> dict:
    return {"type": "score", "level": 1, "guilty": len(providers), "found": len(providers), "false_positives": [],
            "false_positive_providers": 0, "providers": [
                {"provider": p, "name": NAMES[int(p.split('/')[1])], "found": True, "schemes": {s: True for s in schemes}}
                for p, schemes in providers.items()]}


def fixture_trace(run_id="r1", missed_unbundling=True) -> dict:
    """A graded agent trace in which each analytics tool's result names a guilty provider."""
    calls = [("find_duplicate_claims", "Practitioner/4"), ("claims_after_patient_death", "Practitioner/5"),
             ("service_cost_by_provider", "Practitioner/1"), ("provider_daily_load", "Practitioner/7"),
             ("top_services", "")]
    events = [{"type": "run_start", "tools": []}]
    for i, (name, ref) in enumerate(calls):
        events += [{"type": "tool_call", "step": i + 1, "call_id": f"c{i}", "name": name, "args": {}},
                   {"type": "tool_result", "step": i + 1, "call_id": f"c{i}", "name": name, "preview": f'{{"provider":"{ref}"}}'}]
    events.append({"type": "final", "text": "Death certification claims after death are routine paperwork.", "findings": []})
    providers = {"Practitioner/4": ["duplicates"], "Practitioner/5": ["after_death"], "Practitioner/1": ["upcoding"],
                 "Practitioner/7": ["impossible_day"]}
    sc = guilty_score(providers)
    if missed_unbundling:
        sc["providers"].append({"provider": "Practitioner/8", "name": "Dr. Hart", "found": False, "schemes": {"unbundling": False}})
    events.append(sc)
    return {"run_id": run_id, "level": 2, "mode": "agent", "events": events}


def fixture_spec(**changes) -> dict:
    trace = fixture_trace()
    notes = [runs.derive_note(trace, "duplicates re-billed one day later"),
             {"run_id": "r1", "source": "agent", "wish_known_first": "Check next-day re-billing first."}]
    spec = compile_workflow.compile_spec([trace], notes)
    spec.update(changes)
    return spec


class Events:
    def __init__(self):
        self.events: list[dict] = []

    async def __call__(self, event: dict) -> None:
        self.events.append(event)

    def of(self, kind: str) -> list[dict]:
        return [e for e in self.events if e["type"] == kind]


def run(coro):
    return asyncio.run(coro)


class FixedClassifier:
    """Answers every question with one probability (or per provider)."""
    name = "fixed"

    def __init__(self, p=0.9, per_provider: dict | None = None):
        self.p, self.per_provider, self.asked = p, per_provider or {}, []

    async def ask(self, node, evidence):
        self.asked.append((node["id"], evidence["name"]))
        p = self.per_provider.get(evidence["name"], self.p)
        return {"probabilities": {"yes": p, "no": 1 - p}, "backend": "fixed", "model": "fixed",
                "usage": {"input_tokens": 10, "output_tokens": 2}}


# ---------------------------------------------------------------- spec

class SpecLoaderTests(unittest.TestCase):
    def test_compiled_spec_validates_and_round_trips(self):
        spec = fixture_spec()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "spec.json"
            path.write_text(json.dumps(spec, default=str))
            loaded = workflow.load_spec(path)
        self.assertEqual([n["type"] for n in loaded["nodes"]].count("question"), 4)
        self.assertEqual(workflow.spec_hash(loaded), workflow.spec_hash(json.loads(json.dumps(spec, default=str))))

    def test_missing_file(self):
        with self.assertRaisesRegex(workflow.SpecError, "compile_workflow"):
            workflow.load_spec("/nonexistent/spec.json")

    def test_rejects_malformed_specs(self):
        def broken(mutate):
            spec = copy.deepcopy(fixture_spec())
            mutate(spec)
            return spec
        q = lambda s: next(n for n in s["nodes"] if n["type"] == "question")  # noqa: E731
        cases = {
            "unknown op": lambda s: s["nodes"][0].update(op="rm_rf"),
            "unknown type": lambda s: s["nodes"][0].update(type="shell"),
            "unique": lambda s: s["nodes"][1].update(id=s["nodes"][0]["id"]),
            "earlier code node": lambda s: q(s).update(input="research"),
            "positive scale": lambda s: q(s)["prior"].update(scale=0),
            "yes and no": lambda s: q(s).update(choices={"maybe": "?"}),
            "band": lambda s: next(n for n in s["nodes"] if n["type"] == "research").update(band=[0.8, 0.2]),
            "min_confidence": lambda s: next(n for n in s["nodes"] if n["type"] == "escalate").update(min_confidence=2),
            "report_threshold": lambda s: s.update(report_threshold=1.5),
            "non-empty": lambda s: s.update(nodes=[]),
        }
        for message, mutate in cases.items():
            with self.subTest(message), self.assertRaisesRegex(workflow.SpecError, message):
                workflow.validate_spec(broken(mutate))


# ---------------------------------------------------------------- code steps and classifiers

class OpsTests(unittest.TestCase):
    def setUp(self):
        self.rows, self.names, self.deaths = make_claims()

    def test_peer_cost_flags_the_upcoder_only(self):
        out = workflow_ops.peer_cost(self.rows, self.names, self.deaths, min_claims=3)["providers"]
        self.assertEqual(out["Practitioner/1"]["ratio_to_peer_median"], 3.0)
        self.assertEqual(out["Practitioner/1"]["amount"], 800.0)  # 4 claims x $200 over the peer median
        self.assertNotIn("Practitioner/2", out)

    def test_duplicates_exact_rebilled_and_routine(self):
        rows = self.rows + [claim(900, "Practitioner/9", "Patient/1", "2026-06-01", code="X", paid=70),
                            claim(901, "Practitioner/9", "Patient/1", "2026-06-02", code="X", paid=70)]
        rows += [claim(910 + i, "Practitioner/10", "Patient/2", f"2026-06-{i + 1:02d}", code="Y", paid=60) for i in range(5)]
        exact_only = workflow_ops.duplicates(rows, self.names, self.deaths, window_days=0)["providers"]
        self.assertEqual(set(exact_only), {"Practitioner/4"})
        out = workflow_ops.duplicates(rows, self.names, self.deaths, window_days=1)["providers"]
        self.assertEqual(out["Practitioner/4"]["score"], 1)
        self.assertEqual(out["Practitioner/9"]["rebilled_within_window"], 1)
        self.assertEqual(out["Practitioner/9"]["score"], 0.5)
        self.assertEqual(out["Practitioner/10"]["score"], 0)  # a daily series is routine
        self.assertEqual(out["Practitioner/10"]["routine_repeats"], 4)

    def test_after_death_excludes_routine_services(self):
        out = workflow_ops.after_death(self.rows, self.names, self.deaths, exclude_services=["Death Certification"])
        self.assertEqual(set(out["providers"]), {"Practitioner/5"})
        self.assertEqual(out["providers"]["Practitioner/5"]["score"], 3)
        self.assertEqual(out["summary"]["excluded_routine_claims"], 1)

    def test_daily_load_counts_short_visits(self):
        out = workflow_ops.daily_load(self.rows, self.names, self.deaths)["providers"]
        self.assertEqual(out["Practitioner/7"]["visits"], 12)
        self.assertGreater(out["Practitioner/7"]["overlapping_minutes"], 0)

    def test_profile_limits(self):
        out = workflow_ops.profile(self.rows, self.names, self.deaths, min_claims=3,
                                   limits={"exclusive_patient_share": 0.5})["providers"]
        self.assertIn("Practitioner/7", out)  # 12 patients no one else sees
        self.assertNotIn("Practitioner/1", workflow_ops.profile(self.rows, self.names, self.deaths, limits={})["providers"])


class ClassifierTests(unittest.TestCase):
    node = {"id": "q", "question": "Upcoding?", "choices": {"yes": "y", "no": "n"},
            "prior": {"feature": "score", "center": 1.25, "scale": 0.05}}

    def test_rules_is_a_logistic_on_the_score(self):
        rules = RulesClassifier()
        self.assertAlmostEqual(run(rules.ask(self.node, {"score": 1.25}))["probabilities"]["yes"], 0.5)
        self.assertGreater(run(rules.ask(self.node, {"score": 2.0}))["probabilities"]["yes"], 0.99)
        self.assertLess(run(rules.ask(self.node, {"score": 1.0}))["probabilities"]["yes"], 0.01)

    def test_llm_classifier_uses_structured_output(self):
        from questions import Answer
        seen = []

        class Fake:
            def with_structured_output(self, schema, include_raw):
                assert schema is Answer and include_raw
                return self

            async def ainvoke(self, messages):
                seen.append(messages)
                return {"parsed": Answer(answer="no", p_yes=0.2), "parsing_error": None,
                        "raw": AIMessage("", usage_metadata={"input_tokens": 50, "output_tokens": 5, "total_tokens": 55})}
        result = run(LLMClassifier(model=Fake()).ask(self.node, {"score": 3.0, "ratio": 3.0}))
        self.assertEqual(result["probabilities"], {"yes": 0.2, "no": 0.8})
        self.assertEqual(result["usage"]["input_tokens"], 50)
        self.assertNotIn('"score"', seen[0][1][1])  # the model sees the facts, not the rules score

    def test_jev_classifier_renormalizes_yes_no(self):
        captured = {}

        class Choice:
            def __init__(self, instructions, criteria):
                captured["criteria"] = criteria

        class Client:
            def system_one(self, state, questions):
                captured["state"] = state
                probs = {"yes": 0.6, "no": 0.2, "unsure": 0.2}
                return types.SimpleNamespace(model="jev-test", choices={"q": types.SimpleNamespace(probabilities=probs)})
        with mock.patch.dict(sys.modules, {"typesafe_sdk": types.SimpleNamespace(Choice=Choice)}):
            result = run(JevClassifier(client=Client()).ask(self.node, {"score": 1.5, "ratio": 1.5}))
        self.assertAlmostEqual(result["probabilities"]["yes"], 0.75)
        self.assertIn("unsure", captured["criteria"])
        self.assertIn("provider_evidence", captured["state"])

    def test_auto_falls_back_to_rules_without_keys(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertEqual(make_classifier("auto").name, "rules")


# ---------------------------------------------------------------- runner, research, router, replay

class RunnerTests(unittest.TestCase):
    def test_workflow_emits_agent_events_and_scorable_findings(self):
        events = Events()
        out = run(workflow.run_workflow(QUESTION, events, fixture_spec(), RulesClassifier(), research_model=None,
                                        claims=make_claims))
        kinds = [e["type"] for e in events.events]
        self.assertEqual(kinds[0], "run_start")
        self.assertEqual(kinds[-2:], ["final", "done"])
        self.assertEqual(len(events.of("tool_call")), 5)  # 4 code steps + profile
        self.assertEqual(len(events.of("tool_result")), 5)
        final = events.of("final")[0]
        self.assertEqual(parse_findings(final["text"]), [{k: v for k, v in f.items() if k != "probability"}
                                                         for f in final["findings"]])
        reported = {(f["provider"], f["scheme"].split(":")[0]) for f in out["findings"]}
        self.assertEqual(reported, {("Practitioner/1", "upcoding"), ("Practitioner/4", "duplicate billing"),
                                    ("Practitioner/5", "billing after death"), ("Practitioner/7", "impossible day")})
        key = {"guilty": {"Practitioner/1": {"name": "Dr. Ames", "schemes": {"upcoding": {"keywords": ["upcod"]}}}}}
        self.assertEqual(score(final["findings"], key)["found"], 1)
        records = [e for e in events.events if e["type"] == "workflow_node"]
        self.assertEqual({r["kind"] for r in records}, {"spec", "code", "question", "route"})
        self.assertEqual(events.of("done")[0]["usage"], {"input_tokens": 0, "output_tokens": 0})

    def test_uncertain_question_goes_to_research_with_fhir_reads_only(self):
        ran = []

        def stand_in(name):
            async def go(**kwargs):
                ran.append((name, kwargs))
                return f"{name}: ExplanationOfBenefit/5 is a home visit 40 days after death"
            return StructuredTool.from_function(coroutine=go, name=name, description=name)
        spec = fixture_spec()
        research = next(n for n in spec["nodes"] if n["type"] == "research")
        research["tools"] = ["fhir_search", "fhir_read", "fhir_update"]  # a misconfigured spec: the policy still refuses writes
        model = ScriptedChatModel(replies=[
            call("fhir_update", {"resourceType": "ExplanationOfBenefit", "id": "5"}, "u1"),
            call("fhir_search", {"resourceType": "ExplanationOfBenefit", "queryParams": "provider=Practitioner/5"}, "s1"),
            AIMessage('{"answer": "yes", "p_yes": 0.92, "evidence": "ExplanationOfBenefit/5 after death"}')])
        classifier = FixedClassifier(0.95, per_provider={"Dr. Eads": 0.5})
        events = Events()
        out = run(workflow.run_workflow(QUESTION, events, spec, classifier, research_model=model,
                                        research_tools=[stand_in(n) for n in ("fhir_search", "fhir_read", "fhir_update")],
                                        claims=make_claims))
        self.assertEqual([name for name, _ in ran], ["fhir_search"])
        denied = [e for e in events.of("tool_result") if e.get("denied")]
        self.assertEqual([e["name"] for e in denied], ["fhir_update"])
        rec = next(e for e in events.events if e["type"] == "workflow_node" and e["kind"] == "research")
        self.assertEqual((rec["provider"], rec["p_question"], rec["p_yes"]), ("Practitioner/5", 0.5, 0.92))
        p5 = next(f for f in out["findings"] if f["provider"] == "Practitioner/5")
        self.assertEqual(p5["confidence"], "high")
        self.assertIn("after death", p5["evidence"])
        self.assertFalse(out["route"]["escalate"])
        self.assertEqual(out["tool_calls"], 5 + 2)  # code steps + the two research calls (one refused)

    def test_router_escalates_when_unsure(self):
        handed = []

        async def fake_agent(question, emit, step0):
            handed.append((question, step0))
            await emit({"type": "run_start", "tools": []})
            await emit({"type": "tool_call", "step": step0, "call_id": "a1", "name": "fhir_search", "source": "fhir-mcp", "args": {}})
            await emit({"type": "final", "text": "agent report", "findings": [{"provider": "Practitioner/5"}]})
            await emit({"type": "done", "tool_calls": 1, "model_steps": 2, "usage": {"input_tokens": 1000, "output_tokens": 100}})
        events = Events()
        out = run(workflow.run_routed(QUESTION, events, fixture_spec(), FixedClassifier(0.95, {"Dr. Eads": 0.5}),
                                      research_model=None, escalate_fn=fake_agent, claims=make_claims))
        self.assertTrue(out["escalated"])
        self.assertIn("Uncertain: Practitioner/5 after_death p=0.5", handed[0][0])
        self.assertEqual(len(events.of("run_start")), 1)
        self.assertEqual(events.of("final")[0]["text"], "agent report")
        done = events.of("done")
        self.assertEqual(len(done), 1)
        self.assertTrue(done[0]["escalated"])
        self.assertEqual(done[0]["usage"]["input_tokens"], 1000 + 4 * 10)  # agent + four classifier calls
        self.assertEqual(done[0]["tool_calls"], 5 + 1)

    def test_router_keeps_confident_workflow_answers(self):
        async def never(*args):
            raise AssertionError("the full agent should not run")
        events = Events()
        out = run(workflow.run_routed(QUESTION, events, fixture_spec(), RulesClassifier(), research_model=None,
                                      escalate_fn=never, claims=make_claims))
        self.assertFalse(out["escalated"])
        self.assertEqual(len(events.of("final")[0]["findings"]), 4)

    def test_router_escalates_unexplained_profiles(self):
        spec = fixture_spec()
        prof = next(n for n in spec["nodes"] if n.get("op") == "profile")
        prof["params"] = {"min_claims": 2, "limits": {"claims_per_patient_day": 1.5}}  # P4 bills 2 claims per patient-day
        spec["nodes"] = [n for n in spec["nodes"] if n.get("id") != "q_duplicates"]
        events = Events()
        out = run(workflow.run_routed(QUESTION, events, spec, RulesClassifier(), research_model=None,
                                      escalate=False, claims=make_claims))
        self.assertEqual(out["route"]["unexplained"], ["Practitioner/4"])
        self.assertTrue(out["route"]["escalate"])
        self.assertTrue(events.of("done")[0]["would_escalate"])


class ReplayTests(unittest.TestCase):
    def setUp(self):
        events = Events()
        self.out = run(workflow.run_workflow(QUESTION, events, fixture_spec(), FixedClassifier(0.95, {"Dr. Eads": 0.6}),
                                             research_model=None, claims=make_claims))
        self.trace = {"run_id": "w1", "events": events.events + [guilty_score({"Practitioner/1": ["upcoding"]})]}

    def test_replay_reproduces_decisions_without_models_or_data(self):
        with mock.patch("tools.claims", side_effect=AssertionError("no data access")), \
             mock.patch("questions.LLMClassifier.ask", side_effect=AssertionError("no model calls")):
            again = workflow.replay(json.loads(json.dumps(self.trace, default=str)))
        self.assertEqual(again["findings"], self.out["findings"])
        self.assertEqual(again["route"], self.out["route"])
        self.assertEqual(again["spec"], again["original_spec"])
        self.assertEqual(again["score"]["found"], 1)
        self.assertEqual(again["score"]["false_positive_providers"], 3)

    def test_replay_with_another_spec(self):
        stricter = fixture_spec(report_threshold=0.9)
        again = workflow.replay(self.trace, stricter)
        self.assertNotIn("Practitioner/5", {f["provider"] for f in again["findings"]})
        self.assertNotEqual(again["spec"], again["original_spec"])
        rules = workflow.replay(self.trace, None, reclassify=True)
        self.assertEqual(rules["findings"][0]["probability"], 1.0)

    def test_replay_rejects_agent_traces(self):
        with self.assertRaises(workflow.SpecError):
            workflow.replay(fixture_trace())


# ---------------------------------------------------------------- learning and compiling

class LearningTests(unittest.TestCase):
    def test_derived_note(self):
        trace = fixture_trace()
        trace["events"].insert(3, {"type": "tool_call", "step": 1, "call_id": "dup", "name": "find_duplicate_claims", "args": {}})
        note = runs.derive_note(trace, "level text")
        self.assertEqual(note["first_hit"]["Practitioner/4"]["tool"], "find_duplicate_claims")
        self.assertEqual(note["evidence_tools"]["find_duplicate_claims"], 1)
        self.assertIn("repeated an earlier call", note["wasted"][0])
        self.assertEqual(note["missed"], ["Dr. Hart: unbundling"])

    def test_agent_writes_a_note(self):
        model = ScriptedChatModel(replies=[AIMessage('Note: {"evidence_tools": ["find_duplicate_claims"], "wasted": [], '
                                                     '"wish_known_first": "check re-billing", "least_sure": "P5"}')])
        log = [{"step": 1, "name": "find_duplicate_claims", "args": {}, "size": 10, "head": "{}"}]
        note = run(write_note("claude", QUESTION, {"log": log, "final_text": "report"}, model=model))
        self.assertEqual(note["evidence_tools"], ["find_duplicate_claims"])
        self.assertIn("find_duplicate_claims", model.seen[0][1].content)

    def test_record_run_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as d, \
             mock.patch.multiple(runs, TRACES_JSONL=Path(d) / "t.jsonl", NOTES_JSONL=Path(d) / "n.jsonl"):
            runs.record_run(fixture_trace(), "agent", {"type": "note", "wish_known_first": "x"}, "desc")
            runs.record_run({**fixture_trace("w"), "mode": "workflow"}, "workflow")
            self.assertEqual([t["mode"] for t in runs.read(runs.TRACES_JSONL)], ["agent", "workflow"])
            self.assertEqual([n["source"] for n in runs.read(runs.NOTES_JSONL)], ["derived", "agent"])


class CompilerTests(unittest.TestCase):
    def test_steps_params_and_coverage_come_from_the_runs(self):
        spec = fixture_spec()
        code = [n["op"] for n in spec["nodes"] if n["type"] == "code"]
        self.assertEqual(code, ["duplicates", "after_death", "peer_cost", "daily_load", "profile"])  # agent's call order
        params = {n["op"]: n["params"] for n in spec["nodes"] if n["type"] == "code"}
        self.assertEqual(params["duplicates"]["window_days"], 1)  # the note mentions re-billing a day later
        self.assertEqual(params["after_death"]["exclude_services"], ["Death Certification"])  # the report called them routine
        self.assertEqual(list(spec["uncovered_schemes"]), ["unbundling"])
        self.assertEqual(spec["hints"], ["Check next-day re-billing first."])
        self.assertNotIn("top_services", [n.get("op") for n in spec["nodes"]])

    def test_tools_without_evidence_are_left_out(self):
        trace = fixture_trace()
        trace["events"] = [e for e in trace["events"] if e.get("name") != "provider_daily_load"]
        spec = compile_workflow.compile_spec([trace], [runs.derive_note(trace)])
        self.assertNotIn("daily_load", [n.get("op") for n in spec["nodes"]])
        self.assertIn("impossible_day", spec["uncovered_schemes"])

    def test_calibration_fits_between_guilty_and_innocent(self):
        spec = fixture_spec()

        def q(provider, s):
            return {"type": "workflow_node", "kind": "question", "node": "q_upcoding", "scheme": "upcoding",
                    "provider": provider, "evidence": {"score": s}}
        traces = [{"mode": "workflow", "events": [q("Practitioner/1", 3.0), q("Practitioner/2", 1.2), q("Practitioner/3", 1.18),
                                                   guilty_score({"Practitioner/1": ["upcoding"]})]},
                  {"mode": "workflow", "events": [q("Practitioner/9", 1.6), q("Practitioner/2", 1.2),
                                                   guilty_score({"Practitioner/9": ["upcoding"]})]}]
        fitted = compile_workflow.calibrate(spec, traces)
        node = next(n for n in fitted["nodes"] if n["id"] == "q_upcoding")
        self.assertEqual(node["prior"]["source"], "calibrated")
        self.assertTrue(1.2 < node["prior"]["center"] < 1.6)
        self.assertLessEqual(node["calibration"]["log_loss_after"], node["calibration"]["log_loss_before"])
        skipped = next(n for n in fitted["nodes"] if n["id"] == "q_duplicates")
        self.assertNotIn("calibration", skipped)

    def test_no_graded_runs(self):
        with self.assertRaises(SystemExit):
            compile_workflow.compile_spec([], [])


if __name__ == "__main__":
    unittest.main()
