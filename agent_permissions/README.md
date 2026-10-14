# agent_permissions

A permission layer for the repo's tool-calling agents. `PermissionMiddleware` is a LangChain 1.x
`create_agent` middleware (`wrap_tool_call` / `awrap_tool_call`). It checks every tool call
before the tool runs.

```python
from langchain.agents import create_agent
from agent_permissions import PermissionMiddleware
from agent_permissions.policies import fraud_policy

agent = create_agent(model, tools, system_prompt=SYSTEM,
                     middleware=[PermissionMiddleware(fraud_policy(), agent_name="fraud")])
```

## Decisions

| Policy says | What happens |
|---|---|
| ALLOW | The tool runs. If a command-like argument runs a script, the script is inspected first; any finding turns the call into DENY. |
| DENY | The tool doesn't run. The model gets an error `ToolMessage` with the reason, so it can recover. |
| ASK | Resolved in this order: an `approver(tool, args, reason)` callback (sync or async); with `interactive=True`, LangGraph `interrupt()` (needs a checkpointer; resume with `Command(resume=True/False)`); otherwise DENY, for servers, scripts and tests. |

ASK uses `interrupt()` from the same middleware rather than `HumanInTheLoopMiddleware`, because
HITL's `interrupt_on` is keyed by tool name only. It can't express "ask only when `confirm=true`"
or "ask because the script looked risky". Running two gates would also split one decision across
two configs. `create_agent` sends each tool call to its own task, so each pending call gets its
own interrupt.

**Fail closed.** Any exception in the policy path denies the call: in a rule, script inspection,
the approver, or the audit write. LangGraph's interrupt signal is re-raised. Errors from the tool
itself propagate as they would without the middleware.

**Audit.** Every decision is written as one JSON line to `$AGENT_PERMISSIONS_AUDIT_LOG`, or by
default `~/.cache/agent_permissions/audit.jsonl`. Each line records the agent, tool, args,
decision, reason, rule, and how the decision was made (`policy`, `approver`, `interrupt`,
`non-interactive`, `fail-closed`). The decision is also sent as a `permission_decision` custom
event, so streaming UIs can show refused calls (a refused tool never fires `on_tool_end`).

## Policies

[policy.py](policy.py) holds an ordered list of `Rule(tool, decision, reason, args={}, agent="*",
when=None, message="")`. The first rule that matches wins; otherwise `default` applies.

- **Tool and agent patterns:** globs, or regexes prefixed with `re:`.
- **Arg patterns** match the string form of the argument. `True`/`False` match its truth value;
  `None` means the argument is absent.
- **`when`** is an optional Python predicate.
- **`message`** replaces the text the model sees when this rule denies a call.
- **YAML:** `load_policy("policy.yaml")`; see [examples/example.yaml](examples/example.yaml).

The default policies in [policies.py](policies.py) are built from the tools each agent actually
binds. Reads are ALLOW, writes and shell/code execution are ASK, and any argument pointing at
`.env` / `.ssh` is DENY. Unknown tools default to ASK, which is DENY when nobody is there to
answer.

| Agent | Policy | Allowed | Asks |
|---|---|---|---|
| [hapi/langgraph_agent.py](../hapi/langgraph_agent.py) | `fhir_agent_policy` | `fhir_search`, `fhir_read` | FHIR writes, shell, unknown |
| [hapi/pharmacy_agent.py](../hapi/pharmacy_agent.py) | `pharmacy_policy` | + the `rxnorm_*` / `openfda_*` look-ups it binds | same |
| [hapi/fraud/agent.py](../hapi/fraud/agent.py) | `fraud_policy` | FHIR reads + the 6 analytics tools | same |
| [hapi/self-improving-agents/agent.py](../hapi/self-improving-agents/agent.py) | `self_improving_policy` | + learned tools with the requested status (normally `approved`) | same |
| [mcp_benefits_server/agent/benefits_agent.py](../mcp_benefits_server/agent/benefits_agent.py) | `benefits_policy` | the benefits read tools; `submit_enrollment_change` without `confirm` (a preview) | `submit_enrollment_change` with `confirm=true` (asks the member through `approve`), unknown |

## Script inspection

[script_inspection.py](script_inspection.py) looks at arguments named `command`, `cmd`,
`commands`, `script`, and similar. It applies when the argument runs one of:

- `python|bash|sh|zsh|node <file>`
- `-c` / `-e` inline code
- `./script.py`
- several commands joined by `&&` `;` `|`

It reads the file and flags:

- file deletion (`os.remove`, `shutil.rmtree`, `Path.unlink`, `rm`, `fs.unlinkSync`, …)
- `rm` through `subprocess` / `os.system`
- network egress (requests, socket, httpx, urllib, curl, wget, nc, `fetch`, …)
- reads of `.env`, `~/.ssh`, and key files
- `eval` / `exec` / dynamic imports

Python is checked on its AST; shell and JavaScript are checked with patterns. A script that is
missing, unreadable, too large, not UTF-8, or doesn't parse is itself a finding, so it is denied.

It is a static tripwire, not a sandbox. Obfuscated code can get past it, so pair it with an
execution sandbox (for example `ShellToolMiddleware` with a Docker execution policy) wherever
real shell access is offered.

## Migration notes

All four agents previously hand-built a `StateGraph` + `ToolNode` loop. They now use
`create_agent`, with the same models, MCP tools, system prompts and recursion limits.

- **Fraud and self-improving tool calls:** the retry and result cap stay in `capped()`, inside
  each tool. Unlike `ToolRetryMiddleware`, it hands the agent the same
  `[TOOL ERROR after 3 attempts …]` text, and the truncation needs a tool wrapper anyway.
- **Self-improving model calls:** the agent node's retries for dropped connections and
  empty/cut-off replies are now a small `RetryModelReplies` middleware. It isn't
  `ModelRetryMiddleware`, because that one only retries exceptions.
- **Benefits approval:** the hand-written `approval` node is replaced by `benefits_policy` plus
  `approver=`, and the declined message is unchanged.
- **Trace events:** `hapi/*/agent.py` `investigate()` also emits a `tool_result` (with
  `denied: true`) for refused calls.
- **Dependencies:** run commands and READMEs now include `--with langchain`.

## Tests

```bash
cd /Users/dc/geha
uv run --no-project --python 3.12 --with 'langchain==1.4.2' --with langchain-anthropic --with langchain-openai \
    --with langchain-mcp-adapters --with pyyaml --with httpx \
    python -m unittest agent_permissions.test_permissions agent_permissions.test_agents_smoke -v
```
