# YouTube Demo Script: Governing Agent Tools with an MCP Promotion Standard

**Target length:** 11–13 minutes  
**Application:** `mcp_benefits_server`  
**Related projects:** `dspy_dental_chatbot`, `crawl_dir`, and `agent_permissions`  
**Audience:** AI solution architects, platform engineers, security teams, and agent developers  
**Central message:** An MCP server should expose only the tools that a deployment is approved to use. This demo encodes tool ownership, data classification, tests, evaluation evidence, audit controls, and human approval into a promotion standard enforced at registration, runtime, and CI.

## Recommended video title

**From Sandbox to Production: Governing AI Agent Tools with MCP**

## Thumbnail text

**Which Tools Can the Agent Call?**

## What this video should demonstrate

1. MCP separates the agent from the implementation and data behind each benefits tool.
2. Tools have promotion tiers; deployments have environments. The environment determines which promoted tools exist in the agent's tool list.
3. Production exposes three deterministic, read-only public-data tools.
4. Pilot adds cited BM25 coverage-policy search, which still lacks the retrieval benchmark required for production.
5. Sandbox adds a synthetic-PHI aggregate and a mock write action protected by human approval.
6. Every call is audited; PHI arguments are hashed and tool results are not written to the audit record.
7. CI checks declared tier, owner, version, description, approved pattern, tests, evaluation evidence, PHI controls, and write restrictions.
8. The agent model is replaceable. The MCP server itself performs deterministic lookup or search and makes no LLM calls.

## Related projects included in this story

| Project | Why it belongs in this demo |
|---|---|
| `dspy_dental_chatbot` | Supplies the consolidated parser for the authoritative premium and rate-code tables. |
| `crawl_dir` | Supplies canonical dental pages and the 34 public coverage-policy PDFs used by the tools. |
| `agent_permissions` | Adds a client-side permission gate that requires explicit approval before a confirmed write. |

These projects are data and control dependencies, not separate demos. Keep the recording centered on the MCP server and show each dependency only where it explains a tool's source or safety boundary.

## Before recording

### Check the MCP SDK version

The server imports the MCP 2.x `MCPServer` API. Do not let an active repository virtual environment silently supply MCP 1.x.

```bash
cd /Users/dc/geha/mcp_benefits_server

UV_CACHE_DIR=/tmp/geha-mcp-uv-cache \
uv run --isolated --python 3.12 --with 'mcp>=2,<3' \
  python -c 'import importlib.metadata as m; print(m.version("mcp"))'
```

Stop if the printed major version is not `2`. The active `/Users/dc/geha/.venv` currently contains MCP 1.30, which does not provide `mcp.server.mcpserver` and cannot run this server.

### Run the promotion report

This check does not need the MCP runtime:

```bash
cd /Users/dc/geha/mcp_benefits_server
/Users/dc/geha/.venv/bin/python src/check_promotion.py --report
```

Expected result: `6/6 tools meet the standard for their declared tier.`

### Run the MCP tests in an isolated environment

```bash
cd /Users/dc/geha/mcp_benefits_server

UV_CACHE_DIR=/tmp/geha-mcp-uv-cache \
uv run --isolated --python 3.12 --with 'mcp>=2,<3' \
  python -m unittest discover -s tests -v
```

The test suite covers tool behavior, tier gating, audit hashing, promotion rules, and a complete MCP stdio connection. Do not record the demo until this command passes.

### Prepare the recording tabs

1. Open `/Users/dc/geha/mcp_benefits_server/README.md`.
2. Open `/Users/dc/geha/mcp_benefits_server/docs/mcp-promotion-standard.md`.
3. Open `/Users/dc/geha/mcp_benefits_server/src/registry.py`.
4. Open `/Users/dc/geha/mcp_benefits_server/src/tools.py`.
5. Open `/Users/dc/geha/mcp_benefits_server/evals/README.md` at the pilot report.
6. Keep a terminal in `/Users/dc/geha/mcp_benefits_server/src`.
7. If demonstrating the real LangGraph agent, keep a second terminal in `mcp_benefits_server/agent`.

### Reliable demo calls

| Environment | Tool or question | Expected result |
|---|---|---|
| Production | `rate_code_lookup(MO, 64063)` | Rate code 2, guide page 10. |
| Production | High, employed, Self Only, MO 64063 | `$21.32` biweekly, guide pages 10–11. |
| Production | `cdt_procedure_class(D2740)` | Class C, brochure page 28. |
| Production | Coverage-policy search | Not listed; the agent cannot call it. |
| Pilot | `romiplostim authorization` | Nplate policy sections with file and section citations. |
| Sandbox | Claims summary for `M-100001` | Synthetic minimum-necessary category aggregates. |
| Sandbox | Marriage plan change without confirmation | `approval_required`. |
| Sandbox | Same change with explicit confirmation | Submitted to a mock only. |

## Main recording script

### 0:00–0:45 — Hook: remove unsafe tools from the model's world

**On screen**

- Show the production, pilot, and sandbox tool lists side by side.
- Highlight that production has three tools and sandbox has six.

**Narration**

> Agent safety is stronger when a prohibited tool does not exist in the model's tool list.
>
> This MCP server has six benefits tools, but a production agent sees only three deterministic, read-only tools over public plan data. Pilot adds document search. Sandbox adds a synthetic member-data aggregate and a mock enrollment write.
>
> The model does not decide which tools are safe. The deployment tier, registry, promotion checks, and permission middleware decide that before the model can act.

### 0:45–1:45 — Architecture and trust boundaries

**On screen**

- Show the README architecture block.
- Move from agent to deployment, registry, tools, and audit log.

**Narration**

> The agent connects through MCP and asks the deployment for its available tools. `MCP_ENV` selects production, pilot, or sandbox. The server reads the registry and registers only the tools promoted for that environment.
>
> Every tool publishes its tier, data class, access mode, approved pattern, owner, and semantic version. MCP annotations identify read-only, destructive, and idempotent behavior. Every call is wrapped by the audit layer.
>
> The MCP server makes no model calls. Deterministic tools read approved tables, the search tool runs BM25 over an approved corpus, and the two sandbox tools operate only on synthetic data or a mock destination. A LangGraph agent can use Claude, OpenAI, or Ollama without changing the server-side governance.

**On-screen callout**

```text
Agent
  ↓ MCP list_tools / call_tool
Tiered deployment
  ↓
Registry filter → approved tools only
  ↓
Audited deterministic lookup, cited search, PHI aggregate, or approved write
```

### 1:45–2:45 — Tool tiers and approved patterns

**On screen**

- Show the tool table in the README.
- Point to the four approved patterns in the promotion standard.

**Narration**

> Production contains rate-code lookup, premium quote, and CDT procedure classification. These are deterministic lookups over authoritative public tables and include source pages in their responses.
>
> Pilot adds coverage-policy search. It follows the document-search-with-citations pattern, but it is intentionally not production because it lacks evaluation evidence on a fixed retrieval question set.
>
> Sandbox adds two higher-risk patterns. The claims tool returns minimum-necessary aggregates for synthetic members. The enrollment tool previews a qualifying-life-event change and acts only after explicit confirmation. Its destination is a mock; no real enrollment changes occur.

### 2:45–4:05 — Run the scripted three-tier demo

**On screen**

- Run `demo_client.py`.
- Pause after each environment's tool list.
- Highlight failed access caused by absence from the list.

```bash
cd /Users/dc/geha/mcp_benefits_server/src

UV_CACHE_DIR=/tmp/geha-mcp-uv-cache \
uv run --isolated --python 3.12 --with 'mcp>=2,<3' \
  python demo_client.py
```

**Narration**

> This client uses the real MCP stdio transport but no LLM, so the policy behavior is repeatable.
>
> In production, the client can call the three approved lookup tools. Coverage-policy search and member claims are not merely rejected after a model selects them. They are absent from `list_tools`, so the model cannot select them.
>
> Pilot adds only the cited policy-search tool. Sandbox inherits the lower-risk tools and adds the synthetic-PHI read and mock write.
>
> This separates tool promotion from deployment. A tool has one declared tier. An environment exposes that tier and every lower-risk tier allowed by policy.

### 4:05–5:05 — Show authoritative structured lookups

**On screen**

- Show the production outputs for Missouri ZIP 64063 and D2740.
- Open the relevant functions in `src/tools.py`.

**Narration**

> Rate codes and premiums reuse the guide-table parser from `dspy_dental_chatbot` rather than asking a language model to read a table on every turn. Missouri ZIP 64063 maps to rate code 2, and the High Option employed Self Only premium is $21.32 biweekly.
>
> The CDT lookup builds an index from canonical brochure pages 20 through 37. The current index contains 378 procedure codes. D2740 maps to Class C and cites brochure page 28.
>
> These facts are deterministic. The agent may decide which tool to call, but it does not calculate the premium or invent the procedure class.

### 5:05–6:00 — Pilot search over the coverage-policy corpus

**On screen**

- Show `coverage_policy_search("romiplostim authorization", limit=2)`.
- Expand the Nplate result and its citation.
- Briefly show `crawl_dir/raw/coverage-policies`.

**Narration**

> The pilot tool searches 520 extracted sections from 34 public coverage-policy PDFs in `crawl_dir`. BM25 preserves exact drug names, authorization terms, and billing codes.
>
> The romiplostim query returns the Nplate section and billing section, with the source file and section heading attached to each result.
>
> Unit tests prove that the function runs. They do not prove that its rankings are good across real questions. Production promotion therefore requires a fixed gold-question retrieval benchmark with metrics such as hit at k and reciprocal rank.

### 6:00–7:05 — Sandbox PHI handling and audit evidence

**On screen**

- Show the synthetic claims-summary result.
- Show the resulting audit JSONL record.
- Point to the hashed `member_id` argument and absence of the tool result.

**Narration**

> The claims tool returns only counts and member cost grouped by benefit category. It omits names, dates of birth, service dates, and free text, and the demo data is synthetic.
>
> The audit record stores the environment, tool, version, tier, data class, hashed arguments, outcome, and latency. For PHI-classified tools, the member identifier appears as a short SHA-256 hash. Results are not logged.
>
> This is still sandbox-only. Hashing and minimum-necessary output are present, but encryption at rest and HIPAA review are missing. The promotion check names those missing controls explicitly.

### 7:05–8:20 — Human approval for write actions

**On screen**

- Show the enrollment-change preview returning `approval_required`.
- Show the client-side approval prompt for `confirm=true`.
- Approve once and display `submitted_to_mock`.

**Narration**

> The write path has two gates.
>
> First, the server validates the qualifying life event and returns a preview. Without `confirm=true`, nothing is written. Second, when the agent proposes the confirmed call, `agent_permissions` classifies it as ASK and requires the member's approval.
>
> The server and client reinforce each other. The middleware prevents an unapproved confirmed call, while the server refuses to act on an unconfirmed call. Even after approval, this demonstration writes only to an in-memory mock and tells the user that real changes go through BENEFEDS.

**On-screen callout**

```text
Agent proposes change
      ↓
Server validates QLE → approval_required
      ↓
Agent requests confirm=true
      ↓
PermissionMiddleware asks the human
      ↓ approved
Server submits to mock only
```

### 8:20–9:20 — Promotion is a code and review process

**On screen**

- Run `check_promotion.py --report`.
- Open `registry.py` and highlight `requirements()`.

```bash
cd /Users/dc/geha/mcp_benefits_server
/Users/dc/geha/.venv/bin/python src/check_promotion.py --report
```

**Narration**

> Promotion is a registry change in a pull request, not a runtime button.
>
> Every tool needs an owner, semantic version, useful description, and an approved pattern. Pilot requires passing tests and all required PHI controls. Production additionally requires evaluation evidence, read-only access, and non-PHI data under this version of the standard.
>
> The report passes all six tools at their declared tiers. It also explains what blocks the next tier: retrieval evaluation for policy search, encryption and HIPAA review for the claims tool, and a permanent production restriction for write tools in version one.

### 9:20–10:25 — Run the actual agent and inspect tool calls

**On screen**

- Run the production agent with a combined premium and procedure question.
- Show the offered tool list, calls, results, citations, and final answer.

```bash
cd /Users/dc/geha/mcp_benefits_server/agent

UV_CACHE_DIR=/tmp/geha-agent-uv-cache \
uv run --isolated --python 3.12 \
  --with langchain-mcp-adapters --with langchain --with langgraph \
  --with langchain-anthropic \
  python benefits_agent.py --model claude \
  "What would High Option Self and Family cost me in 64063, MO, and what class is D2740?"
```

**Narration**

> The agent sees only the production MCP deployment's three tools. The model chooses the rate or premium lookup and the CDT lookup, but the returned facts and citations come from the tools.
>
> The same server can support Claude, OpenAI, or a local Ollama model. Governance does not depend on trusting one model provider to remember the policy.
>
> If the agent asks for an unknown tool, permission middleware defaults to ASK, which a non-interactive run turns into denial. New capabilities therefore fail closed until the policy names them.

### 10:25–11:30 — Evaluation and hill-climbing

**On screen**

- Show `evals/README.md` and the seven-case pilot table.
- Open the HTML report if available.

**Narration**

> Tool correctness and agent behavior need different evaluations. The server tests deterministic outputs and policy gates. The agent evaluation runs the real `ask()` entry point with the production tools.
>
> The full fixture contains 59 cases: forty answerable lookup questions and nineteen cases that require clarification or refusal. Fixed answers use code checks. Questions about appropriate decline or clarification use a separate Haiku judge.
>
> The seven-case pilot passed seven of seven after two rubric fixes, at about eight-tenths of a cent per case-run and 6.1 seconds median latency. Seven cases are only a smoke test. The report also found judge mistakes and an application bug that can expose raw thinking blocks.
>
> Hill-climbing changes one thing at a time, evaluates on held-out cases, and keeps the change only when the improvement exceeds measurement noise. If quality is already near the ceiling, the next target should be lower cost or latency while preserving pass rate.

### 11:30–12:20 — AWS deployment boundary

**On screen**

- Show `aws/template.yaml`.
- Highlight one stack per tier, IAM authentication, and CloudWatch audit logs.

**Narration**

> The AWS template deploys one Lambda stack per environment. Each stack receives its own `MCP_ENV` and exposes a stateless Streamable HTTP endpoint through a Lambda Function URL.
>
> The endpoint uses AWS IAM authentication. The agent signs each request with SigV4, and the stack outputs a least-privilege invocation policy for the agent's IAM identity. Audit records go to a dedicated CloudWatch log group with configurable retention.
>
> This repository contains the deployment design and commands. Do not claim a tier is currently deployed unless the CloudFormation stack and Function URL are verified immediately before recording.

### 12:20–12:55 — Close: govern capabilities, not prompts

**On screen**

- Return to the three tier tool lists.
- Display the repository path `mcp_benefits_server/`.

**Narration**

> Prompts are not an authorization system. A safer agent receives only the tools approved for its deployment, deterministic tools return authoritative values, searches return citations, PHI access is minimized and audited, and write actions require human approval.
>
> MCP provides the interface. The promotion registry, evaluation evidence, permissions, audit controls, and deployment isolation make that interface governable.

## Optional AWS deployment segment

Use this only after verifying AWS credentials, stack names, and expected charges.

```bash
cd /Users/dc/geha/mcp_benefits_server/aws

./build.sh
sam build --region us-west-2
sam deploy \
  --stack-name geha-benefits-mcp-sandbox \
  --parameter-overrides McpEnv=sandbox \
  --region us-west-2 \
  --capabilities CAPABILITY_IAM \
  --resolve-s3
```

Then attach the output `AgentPolicyArn` to the agent's IAM user or role and pass the `McpUrl` output to `benefits_agent.py --server-url`. The client signs Lambda Function URL requests with SigV4.

Delete the demo stack when finished:

```bash
sam delete \
  --stack-name geha-benefits-mcp-sandbox \
  --region us-west-2
```

## Optional 90-second version

> This MCP server demonstrates how agent tools move from sandbox to pilot to production.
>
> Production agents see three deterministic public-data tools: rate-code lookup, premium quote, and CDT procedure classification. Pilot adds cited BM25 search over 34 coverage-policy PDFs. Sandbox adds a minimum-necessary aggregate over synthetic member claims and a mock enrollment write protected by human approval.
>
> The model cannot call a tool that the deployment does not list. Each registered tool declares its tier, data class, access mode, approved pattern, owner, version, tests, and evaluation evidence. CI rejects a tool that claims a tier without meeting the criteria.
>
> Every call is audited. PHI arguments are hashed, tool results are not logged, and the write path requires both an explicit `confirm=true` request and approval through client-side permission middleware.
>
> The MCP server makes no model calls. It can sit behind Claude, OpenAI, or a local model. The safety boundary comes from tool exposure, deterministic data access, permissions, audit controls, and deployment isolation rather than from asking the model to remember a policy.

## Suggested YouTube chapters

```text
00:00 Remove unsafe tools from the model's world
00:45 MCP architecture and trust boundaries
01:45 Tool tiers and approved patterns
02:45 Production, pilot, and sandbox demo
04:05 Deterministic benefits lookups
05:05 Pilot coverage-policy search
06:00 PHI minimization and audit hashing
07:05 Human approval for writes
08:20 Promotion checks in CI
09:20 LangGraph benefits agent
10:25 Agent evaluation and hill-climbing
11:30 IAM-authenticated AWS deployment
12:20 Production boundary and summary
```

## Accuracy and recording notes

- This is a demonstration built from public GEHA plan documents and synthetic member data; it is not affiliated with G.E.H.A.
- The current local corpus contains 34 coverage-policy PDFs and 520 indexed policy sections. Update the script if the corpus changes.
- The CDT index currently contains 378 codes from canonical brochure pages 20–37.
- The active repository virtual environment currently contains MCP 1.30. Run the server and tests in an isolated MCP 2.x environment.
- The MCP server itself makes no LLM calls. The optional LangGraph agent does.
- `coverage_policy_search` is pilot, not production, because its fixed retrieval benchmark is missing.
- `member_claims_summary` uses synthetic data only. It is not proof of HIPAA readiness.
- `submit_enrollment_change` writes only to an in-memory mock. Real enrollment changes go through BENEFEDS.
- A production deployment exposes only the three declared production tools. Sandbox and pilot examples must use their matching environments.
- The seven-case agent pilot is a smoke test, not a quality guarantee. Its judge required two rubric corrections.
- Do not display API keys, AWS account IDs, IAM credentials, raw audit identifiers, or unrelated browser tabs.
- Do not claim AWS stacks are running unless you verify them immediately before recording.
- The code promotion report passed all six tools at their declared tiers on October 25, 2026.

## Suggested links for the video description

```text
MCP benefits server:
mcp_benefits_server/

Promotion standard:
mcp_benefits_server/docs/mcp-promotion-standard.md

Tool registry and promotion checks:
mcp_benefits_server/src/registry.py
mcp_benefits_server/src/check_promotion.py

Benefits agent:
mcp_benefits_server/agent/benefits_agent.py

Agent evaluation:
mcp_benefits_server/evals/

Client-side permission middleware:
agent_permissions/

Canonical document corpus:
crawl_dir/
```
