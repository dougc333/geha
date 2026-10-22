# Agent Permissions

`agent_permissions` is a fail-closed permission layer for this repository's
LangChain tool-calling agents. `PermissionMiddleware` intercepts every tool call
created by `langchain.agents.create_agent`, evaluates an ordered policy, and
either runs the tool, returns a denial to the model, or requests approval.

It provides:

- argument-aware `ALLOW`, `DENY`, and `ASK` rules;
- synchronous, asynchronous, or LangGraph-interrupt approval flows;
- static inspection of command and script arguments;
- JSONL audit records and streaming permission events;
- default policies for the FHIR, pharmacy, fraud, self-improving, and benefits
  agents in this repository.

This is an application-level authorization gate. It is **not** an operating
system sandbox, network firewall, container boundary, or substitute for
server-side authorization.

## Decision flow

```text
model proposes a tool call
          |
          v
evaluate ordered policy rules
          |
          +-- DENY --------------------------+
          |                                  |
          +-- ALLOW / ASK                    |
                  |                          |
                  v                          |
          inspect command-like arguments     |
                  |                          |
                  +-- finding -> DENY --------+
                  |
                  +-- ASK -> approver or interrupt
                  |             |
                  |             +-- declined/unavailable -> DENY
                  |             +-- approved -------------> ALLOW
                  |
                  v
             write audit record
                  |
                  +-- audit failure -> DENY
                  |
                  v
       run tool or return error ToolMessage
```

Script inspection happens before an `ASK` is resolved. A script finding is a
hard denial and is not overridable by the approver.

## Quick start

```python
from langchain.agents import create_agent

from agent_permissions import PermissionMiddleware
from agent_permissions.policies import fraud_policy

permissions = PermissionMiddleware(
    fraud_policy(),
    agent_name="fraud",
)

agent = create_agent(
    model,
    tools,
    system_prompt=SYSTEM,
    middleware=[permissions],
)
```

With no approver and `interactive=False`, `ASK` is treated as `DENY`. This is
the safe default for servers, scheduled jobs, tests, and other unattended runs.

## Decisions

| Policy decision | Behavior |
|---|---|
| `ALLOW` | The tool runs after script inspection and a successful audit write. |
| `DENY` | The tool never runs. The model receives an error `ToolMessage` containing the reason or the rule's custom message. |
| `ASK` | The middleware tries an approver callback, then an interactive LangGraph interrupt when enabled; without either, it denies the call. |

A denied call does not crash the agent loop. The model sees the error and can
choose another tool or explain that the requested operation was refused. Errors
raised by the tool after authorization are normal tool errors and are not
handled by this middleware.

## Define a policy

Policies are ordered lists of `Rule` objects. The **first matching rule wins**.
If nothing matches, the policy's default decision applies.

```python
from agent_permissions import ALLOW, ASK, DENY, Policy, Rule

policy = Policy(
    rules=[
        Rule(
            "*",
            DENY,
            "argument points at a secret",
            args={"path": "re:(^|/)(\\.env|\\.ssh)"},
        ),
        Rule("re:^fhir_(search|read)$", ALLOW, "FHIR read"),
        Rule(
            "submit_enrollment_change",
            ASK,
            "submits an enrollment change",
            args={"confirm": True},
            message="The member declined; nothing was submitted.",
        ),
    ],
    default=ASK,
    default_reason="tool is not covered by an explicit rule",
)
```

### Rule matching

`Rule` supports:

| Field | Meaning |
|---|---|
| `tool` | Tool-name glob, or a regular expression prefixed with `re:` |
| `decision` | `ALLOW`, `DENY`, or `ASK` |
| `reason` | Human-readable reason used in audits and denials |
| `args` | Required argument patterns |
| `agent` | Agent-name glob or `re:` regular expression; default `*` |
| `when` | Optional Python predicate `(tool_name, args, agent_name) -> bool` |
| `message` | Replacement text returned to the model when the call is denied |

Argument matching rules:

- strings are globs unless prefixed with `re:`;
- `True` and `False` compare the argument's truth value;
- `None` means the argument must be absent;
- a missing argument does not match any other pattern.

`re:` patterns use regular-expression search, not an implicit full match. Add
`^` and `$` when you need to constrain the whole value.

Put narrow denial rules before broad allow rules. For example, a secret-path
rule must appear before `Rule("*", ALLOW)`.

### YAML or JSON policies

```python
from agent_permissions import load_policy

policy = load_policy("agent_permissions/examples/example.yaml")
```

Example:

```yaml
default: ask
rules:
  - tool: "*"
    decision: deny
    reason: argument points at secrets
    args:
      path: "re:(^|/)(\\.env|\\.ssh)"

  - tool: "re:^fhir_(search|read)$"
    decision: allow
    reason: FHIR read

  - tool: "re:^fhir_(create|update|patch|delete)$"
    decision: ask
    reason: FHIR write
```

File policies accept `tool`, `decision`, `reason`, `args`, `agent`, and
`message`. The callable `when` predicate is available only to policies defined
in Python. Unknown rule keys and invalid decisions raise `ValueError`.

## Approval modes

### In-process approver callback

Pass an approver when the application already has a trusted confirmation UI or
CLI prompt:

```python
def approve(tool_name: str, args: dict, reason: str) -> bool:
    reply = input(f"Approve {tool_name}({args})? {reason} [y/N] ")
    return reply.strip().lower() in {"y", "yes"}

permissions = PermissionMiddleware(
    policy,
    agent_name="benefits",
    approver=approve,
)
```

The asynchronous agent API (`ainvoke` or `astream`) can await an async approver.
The synchronous API requires a synchronous approver; supplying an async callback
there fails closed.

Accepted approvals include `True`, common affirmative strings, and dictionaries
such as `{"approve": true}` or `{"type": "accept"}`. Everything else is a
decline.

### LangGraph interrupt

Set `interactive=True` to pause the graph with a structured
`permission_request`. The agent must have a checkpointer and a stable thread ID.

```python
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

permissions = PermissionMiddleware(
    policy,
    agent_name="interactive-agent",
    interactive=True,
)

agent = create_agent(
    model,
    tools,
    middleware=[permissions],
    checkpointer=InMemorySaver(),
)

config = {"configurable": {"thread_id": "permission-demo-1"}}
paused = agent.invoke({"messages": [("user", "update this record")]}, config)

request = paused["__interrupt__"][0].value
print(request["tool"], request["args"], request["reason"])

result = agent.invoke(Command(resume={"approve": True}), config)
```

The interrupt payload contains:

```json
{
  "type": "permission_request",
  "agent": "interactive-agent",
  "tool": "fhir_update",
  "args": {},
  "reason": "FHIR write: changes server data",
  "tool_call_id": "..."
}
```

The middleware uses its own interrupt instead of LangChain's generic
`HumanInTheLoopMiddleware` because the decision can depend on arguments, script
inspection, and the calling agent—not only on the tool name.

## Script inspection

`PermissionMiddleware` inspects values under these argument names by default:

```text
command, cmd, commands, script, shell_command, code_to_run
```

It recognizes:

- `python`, `bash`, `sh`, `zsh`, or `node` executing a file;
- Python/shell/Node inline code passed through `-c`, `-e`, or `--eval`;
- directly executed `.py`, `.sh`, `.bash`, `.zsh`, `.js`, `.mjs`, and `.cjs`
  files;
- commands joined with operators such as `&&`, `||`, `;`, and `|`.

Current findings include:

- file deletion and destructive shell commands;
- network egress and network-client imports;
- reads of `.env`, `.ssh`, private-key, AWS credential, and `.netrc` paths;
- Python `eval`, `exec`, `compile`, and unresolved dynamic imports;
- selected subprocess behavior.

Python files are parsed with the AST. Shell and JavaScript use conservative
patterns. Missing, unreadable, non-UTF-8, larger-than-1-MB, or unparseable
scripts are findings and are denied.

Configuration:

```python
permissions = PermissionMiddleware(
    policy,
    workdir="/workspace",       # resolves relative script paths
    command_keys=("command",), # inspect only these argument names
    inspect_scripts=True,
)
```

`python -m package.module` is not opened as a source file; the policy decision
still applies to the command. Disabling inspection removes this additional
tripwire and should be done only when another trusted execution boundary exists.

Static inspection is intentionally incomplete. It can miss obfuscated behavior,
runtime imports, actions hidden inside libraries, and effects performed directly
by a tool. Pair command tools with a real execution sandbox and restrict the
tool's filesystem, network, identity, and credentials.

## Audit log and streaming events

Every final decision is appended as one JSON object per line. The default path
is:

```text
~/.cache/agent_permissions/audit.jsonl
```

Override it with:

```bash
export AGENT_PERMISSIONS_AUDIT_LOG=/absolute/path/to/permissions.jsonl
```

or in code:

```python
from agent_permissions import AuditLog, PermissionMiddleware

permissions = PermissionMiddleware(
    policy,
    audit=AuditLog("/absolute/path/to/permissions.jsonl"),
)
```

Each record includes the timestamp, agent, tool, tool-call ID, arguments,
decision, reason, matching rule, script findings, and decision path:
`policy`, `approver`, `interrupt`, `non-interactive`, or `fail-closed`.

The audit currently records full tool arguments without redaction. Do not put
secrets, production PHI, or other sensitive values in tool arguments unless the
audit destination and retention policy are appropriate.

An audit-write failure prevents an otherwise allowed tool from running. For
tests, use `MemoryAuditLog`:

```python
from agent_permissions import MemoryAuditLog

audit = MemoryAuditLog()
permissions = PermissionMiddleware(policy, audit=audit)
```

The middleware also dispatches a custom LangChain event named
`permission_decision`. Streaming UIs use it to display refused calls, because a
denied tool never starts and therefore has no normal `on_tool_end` event. Event
dispatch is telemetry only; a callback failure does not change the permission
decision.

## Repository policies

Default policies live in `policies.py`:

| Policy | Explicitly allowed | Requires approval |
|---|---|---|
| `fhir_agent_policy()` | `fhir_search`, `fhir_read` | FHIR writes, command/code execution, unknown tools |
| `pharmacy_policy()` | FHIR reads plus bound RxNorm and openFDA lookups | FHIR writes, command/code execution, unknown tools |
| `fraud_policy()` | FHIR reads and six read-only claims-analysis tools | FHIR writes, command/code execution, unknown tools |
| `self_improving_policy(names)` | Fraud-policy reads plus the supplied learned-tool names | Everything else |
| `benefits_policy()` | Benefits reads and enrollment-change preview calls | Confirmed enrollment submission and unknown tools |

The built-in secret rule denies a tool when its `path` argument names `.env`,
`.ssh`, or `id_rsa`. It does not scan every arbitrary argument; command-like
arguments receive the separate script inspection described above.

Unknown tools default to `ASK`. In the unattended FHIR, pharmacy, fraud, and
self-improving runs, there is no approver, so an unexpected tool is denied.

## Current integrations

The middleware is used by:

- `hapi/langgraph_agent.py` — general FHIR agent;
- `hapi/pharmacy_agent.py` — pharmacy and public drug-data agent;
- `hapi/fraud/agent.py` and the fraud research workflow — payment-integrity
  investigation;
- `hapi/self-improving-agents/agent.py` — approved learned-tool execution;
- `mcp_benefits_server/agent/benefits_agent.py` — benefits reads and confirmed
  enrollment-change approval.

The benefits server also enforces `confirm=true` on the server side. The client
permission policy is defense in depth, not the sole authorization check.

## Fail-closed behavior

The call is denied if any of these fail:

- policy evaluation or a `when` predicate;
- script parsing or inspection;
- an approver callback;
- the audit write.

LangGraph's internal interrupt signal is re-raised so checkpoint/resume works.
All other permission-path exceptions become an error `ToolMessage` explaining
that the check failed closed.

## Tests

The tests use a scripted chat model and stand-in tools. They do not call an LLM,
MCP server, or FHIR server.

Run the policy, middleware, inspection, and agent-integration suites in an
isolated `uv` environment:

```bash
cd /Users/dc/geha

uv run --no-project --python 3.12 \
  --with 'langchain==1.4.2' \
  --with langchain-anthropic \
  --with langchain-openai \
  --with langchain-mcp-adapters \
  --with pyyaml \
  --with httpx \
  python -m unittest \
    agent_permissions.test_permissions \
    agent_permissions.test_agents_smoke \
    -v
```

For only the self-contained permission-layer tests:

```bash
cd /Users/dc/geha
uv run --no-project --python 3.12 \
  --with 'langchain==1.4.2' \
  --with pyyaml \
  python -m unittest agent_permissions.test_permissions -v
```

## File map

| File | Role |
|---|---|
| `policy.py` | Rule matching, verdicts, dictionary/YAML loading |
| `middleware.py` | LangChain sync/async tool-call interception and approval handling |
| `script_inspection.py` | Static inspection of command arguments and referenced scripts |
| `audit.py` | Thread-safe JSONL and in-memory audit logs |
| `policies.py` | Repository-specific default policies |
| `testing.py` | Scripted chat model and tool-call helpers |
| `examples/example.yaml` | File-based policy example |
| `test_permissions.py` | Unit tests for rules, inspection, middleware, audit, and interrupts |
| `test_agents_smoke.py` | Smoke tests proving each integrated agent enforces its policy |

## Security guidance

- Default to `ASK` or `DENY`, not `ALLOW`, for unknown tools.
- Keep server-side authorization and validation even when middleware approval is
  present.
- Treat tool descriptions and model output as untrusted; policy decisions must
  be based on the actual tool name and arguments.
- Use a sandbox for shell/code tools. Static inspection is only a tripwire.
- Protect audit logs as sensitive operational data.
- Review policy ordering whenever tools are added or renamed.
- Test both the allowed and denied paths for every high-impact tool.
