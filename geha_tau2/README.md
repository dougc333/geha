# geha_dental: a τ²-bench domain for G.E.H.A dental member service

A customer-service benchmark in the τ²-bench format: an LLM agent plays a G.E.H.A dental member
service representative, another LLM plays the member, and the run is graded by the final state of a
sandbox database plus what the agent told the member.

Plan tables (rate codes, 2026 premiums, coinsurance, procedure limits) come from the public 2026
G.E.H.A dental benefits guide and plan brochure. Members, enrollments and claims are synthetic. Not
affiliated with G.E.H.A, and the policy simplifies some FEDVIP rules for the sandbox (noted below).

## What is in it

| Part | File | Contents |
|---|---|---|
| Policy | `data/policy.md` | Identity verification, claim privacy, qualifying-life-event windows, eligibility, address changes, appeals, ID cards, when to transfer |
| Database | `data/db.json` (built by `data/build_db.py`) | 12 members, 12 enrollments, 6 claims; full 2026 rate-code and premium tables; 19 procedures; High and Standard benefits |
| Tools | `domain/tools.py` | 10 read tools (`find_member`, `get_member_details`, `get_enrollment`, `list_claims`, `get_claim`, `lookup_rate_code`, `get_premium`, `get_procedure`, `get_plan_benefits`, `calculate`), 5 write tools (`add_covered_person`, `remove_covered_person`, `update_address`, `file_appeal`, `request_id_card`) and `transfer_to_human_agents` |
| Tasks | `data/tasks.json` (built by `data/build_tasks.py`) | 23 simulated member calls |
| Tests | `tests/` | Tool behavior, and that every task's reference actions replay cleanly |

Tools check only data integrity. Every policy rule (the 60-day window, age limits, privacy, no
exceptions) is the agent's job; that is what the benchmark measures.

### The 23 tasks

| Kind | Tasks | What a correct agent does |
|---|---|---|
| Premiums | 1, 2 | Looks up the rate code from the ZIP, then the exact premium |
| Allowed enrollment changes | 3, 5, 8, 13 | Adds a spouse or newborn inside the 60-day window; removes a former spouse even though the member asks to keep her |
| Refused enrollment changes | 4, 6, 7, 10, 11 | Refuses: 75 days late; child aged 23; plan switch with no event; fiancée before the wedding; "a rep already approved it" |
| Transfer | 9 | Disabled child over 22 needs documentation review |
| Identity | 12 | Caller cannot be verified: no change, nothing revealed |
| Address and ID card | 13, 14, 15 | Updates the address and quotes the new premium; orders a card |
| Coverage | 16, 17, 18, 19 | Class and coinsurance from the tools; sealant age limit; adult braces; never guarantees payment |
| Claims and privacy | 20, 21 | Explains a 10-year-old's denial; refuses to share a spouse's claim |
| Appeals | 22, 23 | Files inside 6 months; refuses outside it |

### Grading

Each task's reward is the product of its `reward_basis`:
- **DB**: the agent's final database must match the reference actions replayed on a fresh database.
  Refusal tasks pass only if nothing changed.
- **COMMUNICATE**: required facts such as "138.56", "Self Plus One" or "Open Season" must reach the
  member. τ² checks these with an LLM judge by default; `--communicate-scorer substring` uses exact
  matching instead.
- **NL_ASSERTION** (tasks 12, 19, 21): an LLM judge checks statements such as "the agent does not
  reveal Elena Ortiz's claim". These are the tasks where an unchanged database alone cannot tell a
  correct refusal from a leak. τ² marks this evaluator as work in progress.

### Sandbox simplifications

- The date is fixed at 2026-03-16, and approved changes take effect on 2026-04-01 (real FEDVIP:
  the first day of the pay period after BENEFEDS receives the change).
- Enrollment changes are made directly here; in reality they go through BENEFEDS.
- Claim privacy is simplified to: the enrollee may hear about claims for themselves and children
  under 18.

## Install and run

```sh
git clone https://github.com/sierra-research/tau2-bench ~/tau2-bench
cd ~/tau2-bench && uv sync && cp .env.example .env    # add your API keys
python ~/geha/geha_tau2/install.py ~/tau2-bench
uv run --extra dev pytest -q tests/test_domains/test_geha_dental   # 28 tests
uv run tau2 run --domain geha_dental --agent-llm anthropic/claude-sonnet-4-5 \
  --user-llm anthropic/claude-sonnet-4-5 --num-tasks 3 --dry-run   # check, no cost
uv run tau2 run --domain geha_dental --agent-llm anthropic/claude-sonnet-4-5 \
  --user-llm anthropic/claude-sonnet-4-5 --num-trials 1 --save-to geha-smoke
uv run tau2 view --file data/simulations/geha-smoke --only-show-failed
```

Use any LiteLLM model string. The default communicate judge and NL-assertion judge call an OpenAI
model; set `OPENAI_API_KEY`, or pass `--communicate-scorer substring`.

To change the data or tasks, edit `data/build_db.py` or `data/build_tasks.py`, run them, run
`install.py` again and rerun the tests.
