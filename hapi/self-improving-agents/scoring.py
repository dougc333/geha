"""Score an agent's findings against the planted answer key, by provider.

A guilty provider counts as found if any finding names it (by reference, or by name).
The scheme counts as described if that finding's text contains one of the scheme's
keywords (the agent describes schemes in its own words). Every other provider the
agent accuses is a false positive; on level 5 (no fraud) every accusation is one.
"""

from __future__ import annotations

import re


def _ref(value: str) -> str:
    match = re.search(r"Practitioner/(\d+)", value or "")
    return f"Practitioner/{match.group(1)}" if match else ""


def _norm(value: str) -> str:
    return re.sub(r"[^a-z]", "", (value or "").lower())


def score(findings: list[dict] | None, key: dict) -> dict:
    findings = findings or []
    guilty = key.get("guilty", {})
    matched: set[int] = set()
    providers = []
    for ref, g in guilty.items():
        hits = [i for i, f in enumerate(findings)
                if _ref(f.get("provider", "")) == ref or (g["name"] and _norm(g["name"]) in _norm(f.get("name", "")))]
        matched.update(hits)
        text = " ".join(f"{findings[i].get('scheme', '')} {findings[i].get('evidence', '')}" for i in hits).lower()
        schemes = {name: any(k in text for k in s["keywords"]) for name, s in g["schemes"].items()}
        providers.append({"provider": ref, "name": g["name"], "found": bool(hits), "schemes": schemes})
    false_pos = [{"provider": f.get("provider", ""), "name": f.get("name", ""), "scheme": f.get("scheme", ""),
                  "confidence": f.get("confidence", "")}
                 for i, f in enumerate(findings) if i not in matched]
    # Several findings can name the same innocent provider; count providers.
    fp_providers = {(_ref(f["provider"]) or _norm(f["name"])) for f in false_pos}
    found = sum(p["found"] for p in providers)
    schemes_total = sum(len(p["schemes"]) for p in providers)
    schemes_found = sum(v for p in providers for v in p["schemes"].values())
    return {"level": key.get("level"), "guilty": len(providers), "found": found,
            "recall": round(found / len(providers), 2) if providers else None,
            "schemes_total": schemes_total, "schemes_described": schemes_found,
            "false_positive_providers": len(fp_providers), "false_positives": false_pos,
            "providers": providers}
