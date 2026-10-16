# Learn-then-compile: a simple example

This shows the pattern behind the fraud investigator's workflow mode
([dougc333/geha#69](https://github.com/dougc333/geha/pull/69)), reduced to one offline
file, [`demo.py`](demo.py):

**Run an expensive agent on training cases, compile what worked into a fixed workflow
of plain code, send the clear cases through the workflow, and route only the uncertain
ones back to the agent.**

It's the lecture's "plan then execute" idea (ReWOO, LLMCompiler), applied *after*
the fact: the plan is learned from graded agent runs instead of written up front.

```
            training cases
                  │
   1. LEARN       ▼
        agent runs (tool calls + verdict) ──► graded against the answer key
                  │
   2. COMPILE     ▼  keep the checks that decided correct verdicts
        workflow spec: ordered checks + thresholds + normal "profile" ranges
                  │
   3. RUN         ▼  new case
        workflow (plain code, no model)
          ├─ clearly guilty / clearly clean ──► answer
          └─ value between thresholds, or profile unlike training ──► escalate to agent
```

## The steps

1. **Learn.** The agent investigates 80 training providers, calling tools
   (`check_duplicates`, `check_peer_cost`, `check_after_death`, and an expensive
   `research`) and giving a verdict. Each run is recorded and graded against the answer key.
2. **Compile.** From the *correct* runs only, keep each check that decided a verdict, and
   learn two limits per check: the highest value seen on clean providers and the lowest
   value seen on guilty ones. Also record the normal range of a cheap **profile**
   (claims per day, weekend share) that code can compute for any provider.
3. **Run.** The workflow runs the checks as plain code:
   - a value at or above the guilty limit → **guilty**
   - a value between the two limits → **escalate** (the training runs never settled this range)
   - all checks clean and profile normal → **innocent**
   - all checks clean but profile unusual → **escalate** (something the checks don't cover)
4. **Compare** agent-only, workflow-only and routed on **held-out** providers, generated
   with different seeds and never seen by the compiler. The second held-out set adds a fraud
   scheme (`phantom_weekend_visits`) that never appeared in training and that no check covers.

## Results (`python learn_then_compile/demo.py`)

```
COMPILE  from 77 correct runs:
           check_peer_cost    guilty >= 1.70, clean <= 1.28  (decided 10 runs)
           check_after_death  guilty >= 4.00, clean <= 1.00  (decided 10 runs)
           check_duplicates   guilty >= 0.12, clean <= 0.04  (decided 8 runs)
           profile claims_per_day  normal 11.38 .. 33.04
           profile weekend_share   normal 0.04 .. 0.21

HELD-OUT, known schemes          guilty found  false acc.  agent runs  cost $
  agent only                          15/16           3          60    7.63
  workflow only                       16/16           0           0    0.00
  routed                              16/16           0           3    0.36

HELD-OUT, plus a NEW scheme
  agent only                          14/19           0          60    8.82
  workflow only                       12/19           0           0    0.00
  routed                              17/19           0           8    1.03
```

What this shows:

- **On known schemes the workflow is enough.** It costs nothing and makes no false
  accusations. Routing sends 3 borderline cases to the agent for **$0.36 instead of
  $7.63**. (It beats the agent here only because the simulated agent is noisy, so don't
  read much into that.)
- **On a new scheme the workflow alone fails quietly.** It misses all 7 phantom-weekend
  providers. Its checks look clean, so it would call them innocent.
- **The profile check is what saves it.** Those providers' weekend share is far outside
  anything seen in training, so the router escalates them. Routed mode finds **17/19**,
  more than the agent alone (14/19), for **12% of the agent's cost** (8 agent runs instead
  of 60).

## What makes this pattern meaningful (and what #69 lacked)

- **Test on held-out data.** Thresholds and profile ranges are learned only from the
  training runs. If you tune them by looking at the test cases, as #69 did with its
  priors and profile limits, the results are true by construction.
- **The router is the safety net, not the workflow.** A compiled workflow only knows the
  schemes it was compiled from. Escalation on "between limits" and "unusual profile" is
  what catches the rest, so the profile features matter as much as the checks.
- **Compile only from correct runs**, so the agent's mistakes don't become rules.

## Limits of this demo

- **The agent is simulated:** it tries checks in random order, misreads 5% of the time,
  makes false accusations 3% of the time, and is charged tokens per call. Real gains
  depend on a real agent's accuracy and cost.
- **The data is a toy**, with one number per check and clean separation between guilty and
  innocent values. Real signals overlap, so the "between limits" band would be wider and
  more cases would be escalated.
- **The compiler only selects and sets thresholds for existing checks.** It doesn't write
  new checks. The new scheme is caught by the profile, but never turned into a check.
- **Costs are Sonnet list prices without prompt caching.**

## Other seeds

The pattern holds, but the numbers move:

| Seed | Set | Agent only | Workflow only | Routed | Routed cost vs agent |
|---|---|---|---|---|---|
| 1 | known | 15/16, 3 false | 16/16 | 16/16 | 5% |
| 1 | + new scheme | 14/19 | 12/19 | 17/19 | 12% |
| 2 | known | 25/26 | 19/26 | 26/26 | 6% |
| 2 | + new scheme | 17/26, 2 false | 13/26 | 18/26 | 27% |
| 3 | known | 22/26, 1 false | 23/26 | 24/26 | 15% |
| 3 | + new scheme | 20/22 | 11/22 | 20/22 | 33% |

Routed mode matched or beat the agent in every row, with no false accusations, for 5–33%
of its cost. Workflow-only is the unreliable one. Cases it would escalate count as innocent
when there's no agent to escalate to, which costs it guilty providers when many cases fall
between its limits (seed 2). It also always misses the new scheme.

Change `--seed` to try others.
