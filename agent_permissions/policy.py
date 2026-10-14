"""Policy engine: ordered rules over (tool_name, args, agent_name) -> ALLOW / DENY / ASK.

The first rule that matches decides; if none matches, the policy's default does. Patterns
are globs ("fhir_*") unless prefixed with "re:" ("re:^fhir_(read|search)$"). An `args`
pattern matches the string form of that argument; True/False match the argument's truth
value, and None matches an absent argument.

    policy = Policy([
        Rule("fhir_read", ALLOW),
        Rule("submit_*", ASK, args={"confirm": True}, reason="writes need a human"),
    ], default=ASK)
    policy.evaluate("fhir_read", {"id": "1"}, agent="fraud").decision  # "allow"
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ALLOW, DENY, ASK = "allow", "deny", "ask"
DECISIONS = (ALLOW, DENY, ASK)


def matches(pattern: str, value: str) -> bool:
    """Glob match, or a regex search when the pattern starts with "re:"."""
    if pattern.startswith("re:"):
        return re.search(pattern[3:], value) is not None
    return fnmatch.fnmatchcase(value, pattern)


def _arg_matches(expected: Any, args: dict, key: str) -> bool:
    if expected is None:
        return key not in args
    if key not in args:
        return False
    value = args[key]
    if isinstance(expected, bool):
        return bool(value) is expected
    return matches(str(expected), str(value))


@dataclass(frozen=True)
class Rule:
    """One rule. `when` is an optional extra test, (tool_name, args, agent) -> bool.
    `message` replaces the default tool error text when this rule leads to a denial
    (a DENY, or an ASK the approver declined)."""

    tool: str
    decision: str
    reason: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    agent: str = "*"
    when: Callable[[str, dict, str], bool] | None = None
    message: str = ""

    def __post_init__(self):
        if self.decision not in DECISIONS:
            raise ValueError(f"decision must be one of {DECISIONS}, not {self.decision!r}")

    def applies(self, tool_name: str, args: dict, agent: str) -> bool:
        return (matches(self.tool, tool_name) and matches(self.agent, agent)
                and all(_arg_matches(v, args, k) for k, v in self.args.items())
                and (self.when is None or bool(self.when(tool_name, args, agent))))


@dataclass(frozen=True)
class Verdict:
    decision: str
    reason: str
    rule: Rule | None = None

    @property
    def message(self) -> str:
        return self.rule.message if self.rule else ""


@dataclass
class Policy:
    rules: list[Rule] = field(default_factory=list)
    default: str = ASK
    default_reason: str = "no rule covers this tool"

    def __post_init__(self):
        if self.default not in DECISIONS:
            raise ValueError(f"default must be one of {DECISIONS}, not {self.default!r}")

    def evaluate(self, tool_name: str, args: dict | None, agent: str = "") -> Verdict:
        args = args if isinstance(args, dict) else {}
        for rule in self.rules:
            if rule.applies(tool_name, args, agent):
                return Verdict(rule.decision, rule.reason or f"rule {rule.tool!r} -> {rule.decision}", rule)
        return Verdict(self.default, self.default_reason)

    def ask_tools(self, tool_names: list[str], agent: str = "") -> list[str]:
        """Tools whose argument-free evaluation is ASK (for display and for HITL-style configs)."""
        return [n for n in tool_names if self.evaluate(n, {}, agent).decision == ASK]


def policy_from_dict(data: dict) -> Policy:
    """{"default": "ask", "rules": [{"tool": ..., "decision": ..., "args": {...}, ...}]}"""
    allowed = {"tool", "decision", "reason", "args", "agent", "message"}
    rules = []
    for raw in data.get("rules") or []:
        unknown = set(raw) - allowed
        if unknown:
            raise ValueError(f"unknown rule keys {sorted(unknown)} in {raw}")
        rules.append(Rule(**{k: v for k, v in raw.items()}))
    return Policy(rules, default=data.get("default", ASK))


def load_policy(path: str | Path) -> Policy:
    """A policy from a YAML (or JSON) file."""
    import yaml  # only needed for file-based policies
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping with 'rules' and 'default'")
    return policy_from_dict(data)
