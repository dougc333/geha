"""Tool registry: every MCP tool declares how far it has been promoted and why.

The rules here implement docs/mcp-promotion-standard.md. A tool is exposed in an
environment only if its tier is allowed there; check_promotion.py verifies that
each tool meets the criteria for its declared tier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

TIERS = ("sandbox", "pilot", "production")
DATA_CLASSES = ("public", "internal", "phi")
ACCESS = ("read", "write")
# Patterns a tool must follow to be approved (standard section 3).
APPROVED_PATTERNS = {
    "deterministic-lookup": "Read-only lookup over an authoritative table; no model output.",
    "document-search-with-citations": "Search over an approved corpus; every result cites its source.",
    "minimum-necessary-phi-read": "Returns aggregates for one member; never names or free text.",
    "write-with-human-approval": "Proposes a change, executes only after explicit human confirmation.",
}
# Controls a PHI tool needs before it may leave the sandbox (standard section 2).
PHI_CONTROLS = ("audit_hashing", "minimum_necessary", "encryption_at_rest", "hipaa_review")
# Which tiers each environment serves.
EXPOSED_IN = {
    "sandbox": {"sandbox", "pilot", "production"},
    "pilot": {"pilot", "production"},
    "production": {"production"},
}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Callable[..., Any]
    tier: str
    data_class: str
    access: str
    pattern: str
    owner: str
    version: str
    tests: tuple[str, ...]
    eval_evidence: str = ""          # link or description of evaluation results
    phi_controls: tuple[str, ...] = ()
    human_approval: bool = False
    notes: str = ""

    @property
    def description(self) -> str:
        return (self.func.__doc__ or "").strip()

    def metadata(self) -> dict[str, Any]:
        """Published with the tool (MCP tool meta) so clients and gateways can see its standing."""
        return {"tier": self.tier, "data_class": self.data_class, "access": self.access,
                "pattern": self.pattern, "owner": self.owner, "version": self.version}


def exposed(specs: list[ToolSpec], environment: str) -> list[ToolSpec]:
    if environment not in EXPOSED_IN:
        raise ValueError(f"MCP_ENV must be one of {sorted(EXPOSED_IN)}, not {environment!r}")
    return [s for s in specs if s.tier in EXPOSED_IN[environment]]


def requirements(spec: ToolSpec, tier: str, existing_tests: set[str]) -> list[str]:
    """Unmet criteria for `spec` to sit at `tier`; an empty list means it qualifies."""
    missing: list[str] = []
    level = TIERS.index(tier)
    # Every tier, including sandbox.
    if spec.tier not in TIERS:
        missing.append(f"unknown tier {spec.tier!r}")
    if spec.data_class not in DATA_CLASSES:
        missing.append(f"unknown data class {spec.data_class!r}")
    if spec.access not in ACCESS:
        missing.append(f"unknown access {spec.access!r}")
    if spec.pattern not in APPROVED_PATTERNS:
        missing.append(f"pattern {spec.pattern!r} is not an approved pattern")
    if not spec.owner:
        missing.append("a named owner")
    if not re.fullmatch(r"\d+\.\d+\.\d+", spec.version):
        missing.append("a semantic version (MAJOR.MINOR.PATCH)")
    if len(spec.description) < 40:
        missing.append("a description of at least 40 characters (the model reads it)")
    if spec.access == "write" and not spec.human_approval:
        missing.append("human approval for a write tool")
    if spec.data_class == "phi" and "audit_hashing" not in spec.phi_controls:
        missing.append("PHI arguments hashed in the audit log")
    # Pilot and above.
    if level >= 1:
        absent = [t for t in spec.tests if t not in existing_tests]
        if not spec.tests or absent:
            missing.append("passing tests that exist" + (f" (missing: {', '.join(absent)})" if absent else ""))
        if spec.data_class == "phi":
            lacking = [c for c in PHI_CONTROLS if c not in spec.phi_controls]
            if lacking:
                missing.append("PHI controls: " + ", ".join(lacking))
    # Production only.
    if level >= 2:
        if not spec.eval_evidence:
            missing.append("evaluation evidence (results on a fixed question set)")
        if spec.access == "write":
            missing.append("read-only access (write tools are not promotable to production in v1)")
        if spec.data_class == "phi":
            missing.append("non-PHI data (PHI tools are not promotable to production in v1)")
    return missing
