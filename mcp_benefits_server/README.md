# GEHA benefits MCP server: a promotion standard enforced in code

An MCP server that exposes GEHA's 2026 dental plan data and coverage policies as tools,
with a **promotion standard** deciding which tools each deployment may offer. It shows
how an organisation can let teams build MCP tools quickly while keeping PHI, write
actions and unproven tools away from production agents.

Demo built on GEHA's public plan documents; not affiliated with G.E.H.A. No LLM is
called anywhere: the tools are deterministic or search-based, and the demo client is
scripted.

```
agent ──MCP──► deployment (MCP_ENV=production | pilot | sandbox)
                 ├─ registry: each tool's tier, data class, access, pattern, owner, version
                 ├─ only tools promoted to this tier are listed (others can't be called)
                 ├─ audit log: every call, PHI arguments hashed
                 └─ tools: guide tables, brochure CDT index, coverage-policy search, mocks
CI ──► check_promotion.py: fails when a tool claims a tier it doesn't meet
```

## Tools

| Tool | Tier | Data | What it does |
|---|---|---|---|
| `rate_code_lookup` | production | public | State + ZIP → premium rate code (benefits guide p. 10) |
| `premium_quote` | production | public | Plan, status, enrollment, location → 2026 premium (pp. 10–11) |
| `cdt_procedure_class` | production | public | CDT code → benefit class A–D and brochure page (378 codes) |
| `coverage_policy_search` | pilot | public | BM25 over 32 medical coverage policies, results cite file and section |
| `member_claims_summary` | sandbox | PHI (synthetic) | Minimum-necessary claim aggregates for one member |
| `submit_enrollment_change` | sandbox | internal, **write** | QLE change, validated against the 2026 matrix; needs human confirmation; mock only |

The rules are in [`docs/mcp-promotion-standard.md`](docs/mcp-promotion-standard.md).

## Run

The MCP SDK (`mcp` 2.0) is supplied by `uv`, so nothing is installed into the repo's environment.

```bash
cd /Users/dc/geha/mcp_benefits_server/src
uv run --no-project --python 3.12 --with mcp python demo_client.py           # agent vs each deployment
uv run --no-project --python 3.12 --with mcp python check_promotion.py --report
cd .. && uv run --no-project --python 3.12 --with mcp python -m unittest discover -s tests -v
```

To use it from an MCP client such as Claude Code, register the server command with the
deployment's environment, e.g. `MCP_ENV=production`, running
`uv run --no-project --python 3.12 --with mcp python /Users/dc/geha/mcp_benefits_server/src/server.py`.

## Agent

`agent/benefits_agent.py` is a LangGraph agent whose only tools are the ones the MCP
deployment offers. It asks a human before any write call with `confirm=true`.

```bash
cd /Users/dc/geha/mcp_benefits_server/agent
uv run --no-project --python 3.12 --with langchain-mcp-adapters --with langgraph \
  --with langchain-anthropic python benefits_agent.py --model claude \
  "What would High Option Self and Family cost me in 64063, MO, and what class is D2740?"
```

`--model` also takes `openai` or `ollama:<model>`; `--env` picks the local deployment;
`--server-url` points at a deployed one. Tests drive it with a scripted model (no LLM).

## Deploy to AWS

Lambda behind a Function URL with `AuthType: AWS_IAM`, one stack per tier
(`aws/template.yaml`). The server runs in stateless Streamable HTTP mode; audit records go
to CloudWatch Logs with configurable retention. The agent signs requests with SigV4 using
your AWS credentials, so the endpoint is never public.

```bash
cd /Users/dc/geha/mcp_benefits_server/aws
./build.sh                                   # code + only the plan pages the tools read
sam build --region us-west-2                 # Linux arm64 dependencies
sam deploy --stack-name geha-benefits-mcp-sandbox --parameter-overrides McpEnv=sandbox \
  --region us-west-2 --capabilities CAPABILITY_IAM --resolve-s3
```

Repeat with `McpEnv=pilot` / `production` for the other tiers. Then point the agent at
the `McpUrl` output (your IAM user or role needs the `AgentPolicyArn` output attached, or
equivalent `lambda:InvokeFunctionUrl` + `lambda:InvokeFunction` permissions):

```bash
python benefits_agent.py --model claude --server-url https://<id>.lambda-url.us-west-2.on.aws/mcp "..."
```

Cost at demo traffic is a few cents a month (Lambda and CloudWatch); the tools make no
model calls. `sam delete --stack-name geha-benefits-mcp-sandbox` removes everything.

## What the demo shows

- **Production deployment:** 3 read-only tools. The agent cannot call the policy search
  or the PHI tool: they are not in its tool list.
- **Pilot:** adds `coverage_policy_search`, which is blocked from production until it has
  a retrieval benchmark (evaluation evidence).
- **Sandbox:** adds the synthetic-PHI read and the write tool. The write tool returns
  `approval_required` and only submits (to a mock) when called again with `confirm=true`.
- **Audit trail:** every call, including errors; member ids appear only as hashes.
- **Promotion report:**

```
tool                       tier        data      access  status
rate_code_lookup           production  public    read    OK
premium_quote              production  public    read    OK
cdt_procedure_class        production  public    read    OK
coverage_policy_search     pilot       public    read    OK
                           -> production: needs evaluation evidence (results on a fixed question set)
member_claims_summary      sandbox     phi       read    OK
                           -> pilot: needs PHI controls: encryption_at_rest, hipaa_review
submit_enrollment_change   sandbox     internal  write   OK
                           -> pilot: eligible
```

## Layout

| Path | Purpose |
|---|---|
| `src/registry.py` | Tool specs, tiers, approved patterns, promotion criteria |
| `src/tools.py` | Tool implementations and their registry entries |
| `src/server.py` | MCP server; exposes tools by `MCP_ENV`, writes the audit log |
| `src/check_promotion.py` | The standard as a CI check |
| `src/demo_client.py` | Scripted agent connecting to each deployment over stdio |
| `tests/test_server.py` | Tools, gating, audit hashing, promotion rules, an end-to-end stdio test |

Rate codes and premiums reuse `dental_enrollment_chatbot/src/guide_tables.py` rather
than copying it.
