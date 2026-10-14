"""PermissionMiddleware: checks every tool call against a Policy before it runs.

    agent = create_agent(model, tools, middleware=[PermissionMiddleware(policy, agent_name="fraud")])

Per call: the policy decides ALLOW / DENY / ASK; an ALLOW that runs a script
(`python x.py`, `bash -c ...`) is downgraded to DENY if script_inspection finds anything.

- ALLOW: the tool runs.
- DENY: the tool does not run; the model gets an error ToolMessage with the reason, so it
  can recover (try something else, or tell the user) instead of the run crashing.
- ASK: resolved by, in order,
    1. `approver(tool_name, args, reason) -> bool` (sync or async): an in-process callback,
       e.g. a CLI prompt or a test stub;
    2. `interactive=True`: LangGraph `interrupt()` with a permission_request payload. The
       graph needs a checkpointer; resume with Command(resume=True / False /
       {"approve": bool}). create_agent sends each tool call to its own task, so each
       pending call gets its own interrupt;
    3. otherwise (scripts, servers, tests) ASK is treated as DENY.

Why interrupt() here rather than HumanInTheLoopMiddleware: HITL's `interrupt_on` is keyed by
tool name only, so it can't express "ask only when confirm=true" or ask because a script
looked risky, and it would have to sit beside this middleware as a second gate with its
own config. Calling interrupt() from the same wrap_tool_call keeps one decision, one
reason and one audit record per call.

Fail closed: any exception while evaluating the policy, inspecting a script, asking, or
writing the audit record denies the call. LangGraph's own interrupt signal (GraphBubbleUp)
is re-raised, not swallowed. Exceptions from the tool itself are not ours; they propagate
as they would without the middleware.
"""

from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.errors import GraphBubbleUp

from .audit import AuditLog
from .policy import ALLOW, ASK, DENY, Policy, Verdict
from .script_inspection import COMMAND_KEYS, inspect_call

log = logging.getLogger("agent_permissions")
Approver = Callable[[str, dict, str], "bool | Awaitable[bool]"]
EVENT = "permission_decision"


def _approved(answer: Any) -> bool:
    if isinstance(answer, dict):
        answer = answer.get("approve", answer.get("approved", answer.get("type") in {"approve", "accept"}))
    if isinstance(answer, str):
        return answer.strip().lower() in {"y", "yes", "approve", "approved", "allow", "true"}
    return answer is True


class PermissionMiddleware(AgentMiddleware):
    def __init__(self, policy: Policy, *, agent_name: str = "", approver: Approver | None = None,
                 interactive: bool = False, audit: AuditLog | None = None, inspect_scripts: bool = True,
                 workdir: str | Path = ".", command_keys=COMMAND_KEYS):
        super().__init__()
        self.policy = policy
        self.agent_name = agent_name
        self.approver = approver
        self.interactive = interactive
        self.audit = audit if audit is not None else AuditLog()
        self.inspect_scripts = inspect_scripts
        self.workdir = Path(workdir)
        self.command_keys = command_keys

    @property
    def name(self) -> str:
        return f"PermissionMiddleware[{self.agent_name}]" if self.agent_name else "PermissionMiddleware"

    # -- decision ---------------------------------------------------------------------------

    def _verdict(self, tool: str, args: dict) -> tuple[Verdict, list[str]]:
        verdict = self.policy.evaluate(tool, args, self.agent_name)
        findings: list[str] = []
        if verdict.decision != DENY and self.inspect_scripts:
            findings = inspect_call(args, self.workdir, self.command_keys)
            if findings:
                verdict = Verdict(DENY, "script inspection: " + "; ".join(findings))
        return verdict, findings

    def _interrupt(self, call: dict, verdict: Verdict) -> bool:
        from langgraph.types import interrupt
        answer = interrupt({"type": "permission_request", "agent": self.agent_name, "tool": call["name"],
                            "args": call.get("args", {}), "reason": verdict.reason, "tool_call_id": call.get("id")})
        return _approved(answer)

    def _no_approver(self) -> str:
        return "needs approval, but no approver is available (non-interactive run): treated as deny"

    def _finish(self, call: dict, verdict: Verdict, findings: list[str], via: str) -> tuple[str, str, str]:
        """Audit the final decision. Returns (decision, reason, denial message)."""
        decision, reason = verdict.decision, verdict.reason
        self.audit.record(agent=self.agent_name, tool=call["name"], args=call.get("args", {}),
                          tool_call_id=call.get("id"), decision=decision, reason=reason, via=via,
                          rule=verdict.rule.tool if verdict.rule else None, findings=findings)
        return decision, reason, verdict.message

    def _decide(self, call: dict) -> tuple[Verdict, list[str]]:
        args = call.get("args")
        return self._verdict(call["name"], args if isinstance(args, dict) else {})

    def _fail_closed(self, call: dict, exc: BaseException) -> tuple[str, str, str]:
        reason = f"permission check failed ({type(exc).__name__}: {str(exc)[:200]}); failing closed"
        log.exception("permission check failed for %s", call.get("name"))
        try:
            self.audit.record(agent=self.agent_name, tool=call.get("name"), args=call.get("args", {}),
                              tool_call_id=call.get("id"), decision=DENY, reason=reason, via="fail-closed")
        except Exception:  # noqa: BLE001 - the call is denied either way
            log.exception("audit write failed")
        return DENY, reason, ""

    @staticmethod
    def _denied(call: dict, reason: str, message: str) -> ToolMessage:
        return ToolMessage(message or f"Permission denied for {call['name']}: {reason}",
                           tool_call_id=call.get("id") or "", name=call.get("name"), status="error")

    @staticmethod
    def _event(decision: str, call: dict, reason: str) -> dict:
        return {"decision": decision, "tool": call.get("name"), "tool_call_id": call.get("id"),
                "args": call.get("args", {}), "reason": reason}

    # -- hooks ------------------------------------------------------------------------------

    def wrap_tool_call(self, request, handler):
        call = request.tool_call
        try:
            verdict, findings = self._decide(call)
            via = "policy"
            if verdict.decision == ASK:
                if self.approver is not None:
                    answer = self.approver(call["name"], call.get("args", {}), verdict.reason)
                    if inspect.isawaitable(answer):
                        raise TypeError("an async approver needs the async agent API (ainvoke/astream)")
                    via = "approver"
                elif self.interactive:
                    answer, via = self._interrupt(call, verdict), "interrupt"
                else:
                    answer, via = False, "non-interactive"
                verdict = self._resolve(verdict, answer, via)
            decision, reason, message = self._finish(call, verdict, findings, via)
        except GraphBubbleUp:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed
            decision, reason, message = self._fail_closed(call, exc)
        self._dispatch_sync(decision, call, reason)
        if decision == ALLOW:
            return handler(request)
        return self._denied(call, reason, message)

    async def awrap_tool_call(self, request, handler):
        call = request.tool_call
        try:
            verdict, findings = self._decide(call)
            via = "policy"
            if verdict.decision == ASK:
                if self.approver is not None:
                    answer = self.approver(call["name"], call.get("args", {}), verdict.reason)
                    if inspect.isawaitable(answer):
                        answer = await answer
                    via = "approver"
                elif self.interactive:
                    answer, via = self._interrupt(call, verdict), "interrupt"
                else:
                    answer, via = False, "non-interactive"
                verdict = self._resolve(verdict, answer, via)
            decision, reason, message = self._finish(call, verdict, findings, via)
        except GraphBubbleUp:
            raise
        except Exception as exc:  # noqa: BLE001 - fail closed
            decision, reason, message = self._fail_closed(call, exc)
        await self._dispatch_async(decision, call, reason)
        if decision == ALLOW:
            return await handler(request)
        return self._denied(call, reason, message)

    def _resolve(self, verdict: Verdict, answer: Any, via: str) -> Verdict:
        if via == "non-interactive":
            return Verdict(DENY, f"{verdict.reason}; {self._no_approver()}", verdict.rule)
        if _approved(answer):
            return Verdict(ALLOW, f"{verdict.reason}; approved ({via})", verdict.rule)
        return Verdict(DENY, f"{verdict.reason}; declined ({via})", verdict.rule)

    # Custom events let streaming UIs show denied calls (a denied call never starts the tool,
    # so there is no on_tool_end for it). Telemetry only: a failure here changes nothing.
    def _dispatch_sync(self, decision, call, reason):
        try:
            from langchain_core.callbacks import dispatch_custom_event
            dispatch_custom_event(EVENT, self._event(decision, call, reason))
        except Exception:  # noqa: BLE001
            pass

    async def _dispatch_async(self, decision, call, reason):
        try:
            from langchain_core.callbacks import adispatch_custom_event
            await adispatch_custom_event(EVENT, self._event(decision, call, reason))
        except Exception:  # noqa: BLE001
            pass
