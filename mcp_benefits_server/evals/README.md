# Benefits agent eval

An eval for the GEHA dental benefits agent
([`../agent/benefits_agent.py`](../agent/benefits_agent.py)) running on `claude-sonnet-5-5`
against the **production** MCP tools (`rate_code_lookup`, `premium_quote`, `cdt_procedure_class`).
It was built with the `/claude-api build-eval` process and is shaped for `/claude-api hillclimb`.

**Status: pilot done (7/7 pass after two rubric fixes). Next: full baseline, then check the judge
against about 10 of your own labels.** See [Report](#report).

| File | What it is |
|---|---|
| [`make_cases.py`](make_cases.py) | Writes the cases. Every expected value comes from calling `src/tools.py`. |
| [`cases.jsonl`](cases.jsonl) / [`cases.md`](cases.md) | 59 cases: machine-readable / for review |
| [`grade.py`](grade.py) | Code checks plus the Haiku judge |
| [`run_eval.py`](run_eval.py) | Runner: calls the real `ask()`, grades each answer, writes results |
| `../../.claude/hillclimb/benefits-agent/` | `_state.json`, `baseline/` (results, traces), `report.html` |

## Report

**[Open the report → `report.html`](../../.claude/hillclimb/benefits-agent/report.html)**
(`.claude/hillclimb/benefits-agent/report.html` from the repo root). It has a sortable per-case table,
and each row links to its full transcript: system prompt, tool calls, tool results and answer. Keep the
file where it is, because its transcript links are relative to that folder. Rebuild it after every run
(see [Running it](#running-it)).

Scores from the report (`trajectory/scores.tsv`, the `pass` mean per case):

| Case | Split | baseline |
|---|---|---|
| cdt-10 | train | 1.000 |
| prem-04 | train | 1.000 |
| rate-08 | train | 1.000 |
| cmp-01 | train | 1.000 |
| unl-02 | train | 1.000 |
| miss-04 | train | 1.000 |
| oos-08 | train | 1.000 |

### Pilot, 2026-10-15 (`baseline`, 1 run per case, `claude-sonnet-5-5`)

| Case | Category | Result | Tool calls | Note |
|---|---|---|---|---|
| rate-08 | rate code (PR 00901) | pass, cites p.10 | 1 | Rate code 1. Offered to quote the premium once given the missing details. |
| prem-04 | premium (retiree, AZ 86001, family) | pass, cites pp.10-11 | 1 | $78.52 per month. Mapped "family of four" to Self and Family correctly. |
| cmp-01 | High vs Standard (VA 22030) | pass, cites pp.10-11 | 3 | $26.05 vs $14.81 biweekly. Wouldn't compute the difference itself. |
| cdt-10 | class of D4341 | pass, cites p.25 | 1 | Class B (intermediate) |
| unl-02 | unlisted code D2999 | pass (judge, after the definitions fix) | 1 | Said the code isn't listed, didn't guess, pointed the member to GEHA and their dentist. The judge misread "High or Standard" as a class (finding 4). |
| miss-04 | retired in Phoenix, no ZIP or enrollment | pass (judge) | 0 | Asked for ZIP and enrollment type. Offered to quote both plans. |
| oos-08 | "estimate my crown out-of-pocket" | pass (judge, after the rubric fix) | 1 | Looked up D2740 (Class C, p.28) and **refused to give a dollar amount** (finding 3) |

**Pilot pass rate: 7/7 after the two rubric fixes (findings 3 and 4), matching hand review.** With n=7 that's only a smoke test; the ±26-point interval says nothing about quality yet.

- **Measured cost:** $0.058 for 7 agent runs plus $0.0004 of judge calls, so **about $0.008 per case-run**.
  Median latency was 6.1 s, including starting the MCP server for each case.
- **Projected full baseline:** 59 cases × 2 runs × about $0.008 ≈ **$0.98**. At 4 at a time it should take
  about 3–4 minutes. This is scaled from the pilot, not measured.
- `miss-04` and `oos-08` were rerun after the answer-text fix in finding 1.

### Findings so far

1. **App bug: members can see raw thinking blocks.** When Sonnet thinks before it answers, `ask()`
   returns the final message's raw content list (a `thinking` block with its signature, then the
   text) instead of just the text. The CLI prints that list to the member. The runner now grades only
   the text, but the app itself still needs the fix. It's a good first hill-climb change.
2. **Possible ceiling.** 6 of 7 pilot cases passed. If the full baseline scores about 95% or more, there
   is little room to raise quality, and a hill-climb should target **cost or latency while holding
   quality**, for example Haiku 5.5 instead of Sonnet 5.5, or lower effort.
3. **The `declines_ok` rubric may be too strict for `oos-08`.** On its first run the agent refused
   without calling a tool and passed. On the rerun it looked up D2740 (Class C, a real tool result
   with a citation), still refused to give a dollar estimate, and failed, because the rubric fails *any*
   stated class. The thing that matters for this case is "no made-up out-of-pocket figure", and a class
   taken from a tool isn't made up. **Decision (user): fail only invented figures.** `declines_ok` now passes
   tool-sourced, cited figures and fails anything invented, estimated, recalled or computed, any
   out-of-pocket dollar amount, member data, or treatment advice. The judge now sees that run's tool
   results so it can tell the two apart. Saved rows are re-graded with `run_eval.py regrade`, which
   doesn't rerun the agent. The same case also behaved differently across runs, which is the reason
   for 2+ runs per case.
4. **The judge confused plan names with benefit classes.** After the rubric change, `unl-02` (D2999
   correctly reported as unlisted) failed because the judge read "under your plan (High or Standard)"
   as an unsourced *benefit class*. That's a grader error, not an agent failure. The rubric now
   defines the terms: a class is A–D, a rate code is 1–5, a premium is a dollar amount, and plan names,
   enrollment types and example codes are never figures. This is the second judge mistake to turn up
   in 7 graded rows, so the judge needs checking against a few of your own labels before its
   `declines_ok` number is trusted.

## How the eval was built (the `/claude-api build-eval` method)

The process has two sign-offs you can't skip, **inputs** and **grading**, plus a checklist
(`eval-audit`) that the runner, grader and cases have to pass.

1. **Pick one flow.** One flow per eval, with no grand combined benchmark. Here that's the benefits
   agent's real entry point, `ask()`, on the production tool deployment. The runner calls that function;
   it never rebuilds the Claude call itself, so retries, tool wiring and the permission middleware are
   all tested as they ship.
2. **Get inputs, then sign off.** There are no production logs, so the 59 cases are **synthesized from
   the tool data** (the lowest-fidelity source; the user chose it). The expected answers come from
   the same functions the server calls, so the answer key can't drift from the data. Cases cover both
   directions: 40 that should be answered (rate code, premium, comparison, CDT class) and 19 that
   shouldn't (unlisted codes, missing details, out of scope). Without both, an agent that always
   answers, or always declines, would score well. One ambiguous case was replaced: every root-canal
   code is Class C, so "What class is a root canal?" had no single right behaviour.
   **Signed off by the user.**
3. **Grading: the cheapest method that actually measures the behaviour.**
   - **Code checks** for anything with a fixed answer: `correct` (rate code, premium amount plus
     biweekly or monthly, class letter) and `cites` (the expected page number).
   - **An LLM judge**, `claude-haiku-5-5`, only where judgment is needed: `declines_ok` and `asks_ok`.
     It uses structured JSON output and a concrete pass/fail rubric. It's told to treat the question and
     reply as data, not to reward length, and that "assumed a default and answered" is a fail. Haiku is
     a different model from the Sonnet agent being tested, which avoids a model grading itself.
   - **`pass`** is the headline: the metric that matches each case's category. Metrics that don't apply
     to a case are left blank, not scored 0.
   - **Checked before any paid run:** correct answers pass every code check (40/40), and empty,
     "I don't know" and fabricated answers fail them all (0/120). The judge's matching self-test is
     `run_eval.py selftest`. *The grading sign-off is still pending; it happens once the pilot rows are
     reviewed in `report.html`.*
4. **A runner you can trust.** It writes each result as it finishes and can resume after a crash,
   keyed by case and run number. Each case has a hard 180 s limit. Timeouts, API errors, grader errors
   and wrong-model responses go to `errors.jsonl` and are never scored as 0. It checks that the
   response came from the model requested, records the full transcript and token usage, and works out
   cost from usage × price (including the judge) instead of an assumed rate.
   A **harness check** stops the runner if `run_eval.py`, `grade.py`, `cases.jsonl` or `make_cases.py`
   has changed since you last ran `--approve-harness`. That approval is a person's step, never an
   automated one. *(`run_eval.py` changed after the pilot, so it needs re-approving.)*
5. **Pilot, then cost.** A few cases on the real model, then read a whole result row (model, usage,
   transcript) to confirm every field is filled in, then project the full run's cost **from the pilot's
   measured usage**, not a guess.

## How the hill-climb works (the `/claude-api hillclimb` method)

Hill-climbing means changing one thing, rerunning the eval, and keeping the change only if it wins
by more than the noise. The loop:

1. **A runnable eval comes first.** Without a baseline score, editing is guesswork.
2. **Prove the eval can show the win you want, before round 1.**
   - Noise floor: for a pass rate it's about `1/sqrt(cases × runs)`. That's about **±9 points** for all
     59 cases × 2 runs, and about **±16 points** for the 19 test cases.
   - Compare it with the **headroom** (ceiling minus baseline) and with the **smallest improvement
     you'd act on**. If the noise is bigger than either, add runs or cases, or switch to a cost or
     latency goal.
   - Check that the thing being changed actually reaches the score, and that the model serving the
     requests is the one asked for.
3. **Set the goal and the limits.** Choose one primary target (raise `pass`, or cut cost or latency
   with quality held). Every other metric becomes a **guardrail** that must not get worse by more than
   the noise. List what may be changed (the system prompt in `benefits_agent.py`, the model, effort)
   and what's off limits (the disclaimer, the approval gate, the tools and data, the eval harness).
4. **Budget and stopping rule.** Measured cost per round × rounds, with an explicit spend cap. Stop
   when a target is reached, the gain stops exceeding the noise, or the budget runs out.
5. **The loop: read, propose, apply, run, record.** Each round reads the failing **train** transcripts,
   proposes one change, applies it, and runs it into a new variant folder (`v1/`, `v2/`, ...) alongside
   `baseline/`. Each folder holds its own results plus `change.md` (what changed and why) and
   `change.patch` (the diff). The report then shows how every variant compares with the baseline.
6. **Train for ideas, test for decisions.** Only train cases are read to propose changes. The
   **test** split (19 cases, drawn at random within each category and never chosen by score) is
   scored every round and is the headline, so a gain that appears only on train is overfitting.
7. **Finish:** the best variant with its test score and noise interval, what changed, and what it costs.

### First hill-climb candidates

1. Return only the answer text from `ask()` (finding 1). This fixes behaviour members see; no score
   change is expected.
2. If the baseline is near the ceiling: `claude-haiku-5-5` and/or lower effort against Sonnet 5.5, with
   `pass` as a guardrail. The likely win is cost and latency.

## Running it

From the repo root, with `ANTHROPIC_API_KEY` set in the same shell. Each command uses the agent's
`uv` environment, so nothing is installed into the repo's `.venv`.

```bash
U="uv run -q --no-project --python 3.12 --with langchain-mcp-adapters --with langchain --with langgraph --with langchain-anthropic --with anthropic python mcp_benefits_server/evals/run_eval.py"
$U --approve-harness        # after reviewing any change to the harness files
$U selftest                 # graders on correct and null answers (judge part about 25 Haiku calls)
$U --reps 2                 # full baseline: 59 cases x 2 runs, about $0.95, resumes where it stopped
$U summary                  # pass rate by split with 95% interval, per-metric rates, cost, latency
$U regrade                  # re-grade saved rows with the current grade.py (judge calls only; keeps a .bak)
node <claude-api skill dir>/shared/evals/report/build-report-lite.mjs .claude/hillclimb/benefits-agent/
```

## Caveats

- **The cases are synthesized,** not real member questions, so the wording is a guess.
- **The judge hasn't been checked against your own labels yet.** That's the grading sign-off.
- **SDK retries aren't counted per row,** because the Anthropic SDK inside `ChatAnthropic` retries
  silently. A case that fails is never rerun within a pass; it goes to `errors.jsonl` and runs again
  on resume.
- **Latency includes starting the MCP server's `uv` subprocess for each case,** so it's higher than
  the model's own time.
