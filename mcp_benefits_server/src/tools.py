"""GEHA benefit tools exposed over MCP, each registered with its promotion standing.

All data is public GEHA plan material (the 2026 dental benefits guide and plan
brochure, and the published coverage policies), except member_claims_summary,
which reads a small synthetic member file. Nothing here calls a model.
"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from registry import ToolSpec

REPO = Path(__file__).resolve().parents[2]
DENTAL = REPO / "downloads" / "dental" / "fedvip"
BROCHURE_PAGES = DENTAL / "2026-geha-dental-plan-brochure_pages"
POLICY_DIR = REPO / "downloads" / "coverage-policies"

# Reuse the enrollment chatbot's parser for guide pages 10-11 rather than copying it.
sys.path.insert(0, str(REPO / "dental_enrollment_chatbot" / "src"))
from guide_tables import GuideTables  # noqa: E402


@lru_cache(maxsize=1)
def _guide() -> GuideTables:
    return GuideTables(DENTAL / "2026-geha-dental-benefits-guide_pages")


# --- production: deterministic lookups ------------------------------------------------

def rate_code_lookup(state: str, zip_code: str) -> dict[str, Any]:
    """Return the 2026 GEHA dental (FEDVIP) premium rate code (1-5) for a US state or
    territory abbreviation and five-digit ZIP code, from the benefits guide's page-10 table."""
    code = _guide().rate_code(state, zip_code)
    return {"state": state.upper(), "zip_code": zip_code, "rate_code": int(code),
            "source": "2026 GEHA dental benefits guide, page 10"}


def premium_quote(plan: str, status: str, enrollment: str, state: str, zip_code: str) -> dict[str, Any]:
    """Return the 2026 GEHA dental premium for plan High or Standard, status Employed
    (biweekly) or Retired (monthly), enrollment 'Self Only', 'Self Plus One' or
    'Self and Family', and the member's state and ZIP code (guide pages 10-11)."""
    if plan.title() not in {"High", "Standard"}:
        raise ValueError("plan must be High or Standard")
    if status.title() not in {"Employed", "Retired"}:
        raise ValueError("status must be Employed or Retired")
    if enrollment not in {"Self Only", "Self Plus One", "Self and Family"}:
        raise ValueError("enrollment must be 'Self Only', 'Self Plus One' or 'Self and Family'")
    code = _guide().rate_code(state, zip_code)
    return {"plan": plan.title(), "status": status.title(), "enrollment": enrollment,
            "rate_code": int(code), "premium": _guide().premium(plan, status, enrollment, code),
            "period": _guide().period(status),
            "source": "2026 GEHA dental benefits guide, pages 10-11"}


CDT_CLASSES = {**{p: "Class A (basic: diagnostic and preventive)" for p in range(20, 23)},
               **{p: "Class B (intermediate)" for p in range(23, 27)},
               **{p: "Class C (major)" for p in range(27, 36)},
               **{p: "Class D (orthodontic)" for p in range(36, 38)}}
CDT_RE = re.compile(r"\*?\b(D\d{4})\s+(.+?)(?=(?:\s+\*?D\d{4}\b)|$)")


@lru_cache(maxsize=1)
def _cdt_index() -> dict[str, dict[str, Any]]:
    """Each CDT code at its first listing on brochure pages 20-37 (later mentions are limits)."""
    index: dict[str, dict[str, Any]] = {}
    for page, benefit_class in CDT_CLASSES.items():
        for raw in (BROCHURE_PAGES / f"page-{page:03d}.md").read_text(encoding="utf-8").splitlines():
            line = re.sub(r"\s+", " ", re.sub(r"\s*\|\s*", " ", raw.strip().strip("|"))).strip()
            for match in CDT_RE.finditer(line):
                description = re.split(r"\s+-\s+(?:Limited|Coverage determined|When covered|Not covered)",
                                       match.group(2), maxsplit=1)[0].rstrip(" ,.;")
                index.setdefault(match.group(1), {"code": match.group(1), "description": description,
                                                  "benefit_class": benefit_class, "page": page})
    return index


def cdt_procedure_class(code: str) -> dict[str, Any]:
    """Return the GEHA dental benefit class (A basic, B intermediate, C major, D orthodontic)
    and brochure page for a CDT procedure code such as D2740, from the 2026 plan brochure."""
    record = _cdt_index().get(code.strip().upper())
    if not record:
        raise ValueError(f"{code!r} is not listed in the 2026 GEHA dental plan brochure (pages 20-37)")
    return {**record, "source": f"2026 GEHA dental plan brochure, page {record['page']}"}


# --- pilot: document search with citations -------------------------------------------

TOKEN = re.compile(r"[a-z0-9]+")


@lru_cache(maxsize=1)
def _policy_sections() -> list[dict[str, Any]]:
    sections = []
    for path in sorted(POLICY_DIR.glob("geha-coverage-policy-*.docling.md")):
        policy = path.name.removeprefix("geha-coverage-policy-").removesuffix(".docling.md")
        heading, body = "Overview", []
        for line in path.read_text(encoding="utf-8").splitlines() + ["## END"]:
            if line.startswith("## "):
                text = re.sub(r"<!--.*?-->", "", " ".join(body)).strip()
                if text:
                    sections.append({"policy": policy, "section": heading, "text": text,
                                     "tokens": TOKEN.findall(f"{heading} {text}".lower()), "file": path.name})
                heading, body = line[3:].strip(), []
            else:
                body.append(line.strip())
    return sections


def coverage_policy_search(query: str, limit: int = 3) -> dict[str, Any]:
    """Search GEHA's published medical coverage policies (oncology drugs, IVIG, GnRH
    analogues and others) with BM25 and return the best sections, each citing its policy
    file and section heading. Use for prior-authorization and medical-necessity criteria."""
    sections, terms = _policy_sections(), TOKEN.findall(query.lower())
    if not terms:
        raise ValueError("query must contain words")
    n, avg = len(sections), sum(len(s["tokens"]) for s in sections) / len(sections)
    df = Counter(t for s in sections for t in set(s["tokens"]))
    scored = []
    for s in sections:
        tf = Counter(s["tokens"])
        score = sum(math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5)) * tf[t] * 2.2
                    / (tf[t] + 1.2 * (0.25 + 0.75 * len(s["tokens"]) / avg)) for t in terms if tf[t])
        if score:
            scored.append((score, s))
    scored.sort(key=lambda pair: -pair[0])
    return {"query": query, "results": [
        {"policy": s["policy"], "section": s["section"], "score": round(score, 2),
         "snippet": s["text"][:400], "source": f"downloads/coverage-policies/{s['file']}"}
        for score, s in scored[:max(1, min(limit, 10))]]}


# --- sandbox: PHI read (synthetic) and a write action --------------------------------

SYNTHETIC_MEMBERS = {  # made-up members; no real person or record
    "M-100001": [("preventive", 0.0), ("preventive", 0.0), ("major", 612.40)],
    "M-100002": [("intermediate", 88.15), ("orthodontic", 1450.00)],
}


def member_claims_summary(member_id: str) -> dict[str, Any]:
    """Return a minimum-necessary dental claims summary for one member id: claim counts and
    member cost by benefit category. Never returns names, dates of birth or claim text."""
    claims = SYNTHETIC_MEMBERS.get(member_id)
    if claims is None:
        raise ValueError("unknown member id")
    by_category: dict[str, dict[str, float]] = {}
    for category, cost in claims:
        row = by_category.setdefault(category, {"claims": 0, "member_cost": 0.0})
        row["claims"] += 1
        row["member_cost"] = round(row["member_cost"] + cost, 2)
    return {"member_id": member_id, "by_category": by_category, "data": "synthetic"}


# 2026 FEDVIP qualifying-life-event matrix, dental brochure pages 10-11 (subset).
QLE_ACTIONS = {
    "marriage": {"new_enrollment", "increase_enrollment", "change_plan"},
    "acquire_family_member": {"increase_enrollment"},
    "lose_family_member": {"decrease_enrollment"},
    "lose_other_coverage": {"new_enrollment", "increase_enrollment"},
    "move_service_area": {"change_plan"},
}
_submitted: list[dict[str, Any]] = []


def submit_enrollment_change(member_id: str, event: str, action: str, confirm: bool = False) -> dict[str, Any]:
    """Propose a dental enrollment change for a qualifying life event. Without confirm=true it
    only validates the request against the 2026 QLE matrix and returns what would be sent;
    a human must review that and call again with confirm=true. Submits to a mock only."""
    allowed = QLE_ACTIONS.get(event)
    if allowed is None:
        raise ValueError(f"event must be one of {sorted(QLE_ACTIONS)}")
    if action not in allowed:
        return {"status": "not_permitted", "event": event, "action": action,
                "allowed_actions": sorted(allowed), "source": "2026 GEHA dental plan brochure, pages 10-11"}
    request = {"member_id": member_id, "event": event, "action": action}
    if not confirm:
        return {"status": "approval_required", "proposed_request": request,
                "next_step": "A human must confirm; call again with confirm=true."}
    _submitted.append(request)
    return {"status": "submitted_to_mock", "reference": f"MOCK-{len(_submitted):04d}", "request": request,
            "note": "Mock only: no enrollment was changed. Real changes go through BENEFEDS."}


# --- registry ---------------------------------------------------------------------------

SPECS = [
    ToolSpec("rate_code_lookup", rate_code_lookup, tier="production", data_class="public", access="read",
             pattern="deterministic-lookup", owner="benefits-ai@example (demo)", version="1.0.0",
             tests=("test_rate_code_lookup",), eval_evidence="tests: every guide-page-10 row resolves"),
    ToolSpec("premium_quote", premium_quote, tier="production", data_class="public", access="read",
             pattern="deterministic-lookup", owner="benefits-ai@example (demo)", version="1.0.0",
             tests=("test_premium_quote",), eval_evidence="tests: quotes match guide page 11"),
    ToolSpec("cdt_procedure_class", cdt_procedure_class, tier="production", data_class="public",
             access="read", pattern="deterministic-lookup", owner="benefits-ai@example (demo)",
             version="1.0.0", tests=("test_cdt_procedure_class",),
             eval_evidence="tests: codes on each class's pages map to that class"),
    ToolSpec("coverage_policy_search", coverage_policy_search, tier="pilot", data_class="public",
             access="read", pattern="document-search-with-citations", owner="benefits-ai@example (demo)",
             version="0.3.0", tests=("test_coverage_policy_search",),
             notes="Needs a gold-question retrieval benchmark before production."),
    ToolSpec("member_claims_summary", member_claims_summary, tier="sandbox", data_class="phi", access="read",
             pattern="minimum-necessary-phi-read", owner="benefits-ai@example (demo)", version="0.1.0",
             tests=("test_member_claims_summary",), phi_controls=("audit_hashing", "minimum_necessary"),
             notes="Synthetic members only until encryption at rest and HIPAA review are done."),
    ToolSpec("submit_enrollment_change", submit_enrollment_change, tier="sandbox", data_class="internal",
             access="write", pattern="write-with-human-approval", owner="benefits-ai@example (demo)",
             version="0.1.0", tests=("test_submit_requires_confirmation",), human_approval=True,
             notes="Mock submission; a real integration needs BENEFEDS approval."),
]
