"""Route JSONL queries to the document cluster that should be searched.

TypeSafe Jev is optional.  When its SDK and API key are unavailable the module
uses a deterministic, inspectable scorer and reports that fallback explicitly.
"""

from __future__ import annotations

import json
import math
import os
import re
import uuid
from collections import Counter
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised only when the optional service is installed
    from typesafe_sdk import Choice, TypeSafeClient
except ImportError:  # pragma: no cover - normal local-development path
    Choice = TypeSafeClient = None


CLUSTER_DESCRIPTIONS = {
    "policy": (
        "Coverage rules, prior authorization, formularies, reimbursement, plan policy, "
        "and how insurers allocate premium dollars across medical care, administration, "
        "taxes, fees, cost containment, quality improvement, and profit."
    ),
    "clinical_guidance": "Clinical care, vaccines, treatment guidance, eye health, and patient education.",
    "population_health": (
        "General-population or geographic public-health statistics, state rankings, "
        "aging, prevalence, demographics, and national or state health trends. Exclude "
        "analyses of employer-sponsored plans, employees, plan sponsors, or plan members."
    ),
    "benefits_research": (
        "Employer-sponsored benefits and plan-member research, including employee health, "
        "plan-sponsor claims, employer premium trends or contributions, workforce surveys, "
        "SDOH risks in employer populations, and caregiving research. Exclude questions about "
        "how an insurer divides each premium dollar among spending categories."
    ),
    "forms_directory": "Applications, fillable forms, provider directories, and submission instructions.",
    "research": (
        "Empirical studies and analytical reports asking about observed findings, subgroup "
        "comparisons, intervention outcomes, associations, affordability, cost, utilization, "
        "or workforce analysis. Includes questions explicitly framed as findings from a study "
        "or analysis; excludes requests for clinical recommendations."
    ),
}

CLUSTER_SIGNALS = {
    "policy": (
        "coverage", "covered", "policy", "prior authorization", "formulary",
        "medical necessity", "criteria", "medicare", "reimbursement", "benefit limit",
        "premium allocated", "premium allocation", "health care dollar",
        "health plan premium", "spending categories", "medical spending",
    ),
    "clinical_guidance": (
        "vaccine", "vaccination", "immunization", "clinical", "treatment", "exam",
        "retinopathy", "dry eye", "patient", "care recommendation", "schedule",
    ),
    "population_health": (
        "population", "public health", "state ranking", "rankings", "older adults",
        "prevalence", "mortality", "demographic", "state summary", "health outcome",
    ),
    "benefits_research": (
        "employer", "employee", "workforce", "benefits survey", "health benefits",
        "premium", "caregiving", "open enrollment", "firms offer", "workplace",
        "plan sponsor", "employer plan", "employee health", "member population",
    ),
    "forms_directory": (
        "form", "application", "apply", "fillable", "provider directory", "provider list",
        "submit", "submission", "instructions", "eligibility application", "enroll",
    ),
    "research": (
        "study", "report", "analysis", "findings", "research", "cost", "utilization",
        "survey", "evidence", "statistics", "comparison",
    ),
}

QUERY_FIELDS = ("user_input", "query", "question")


def save_router_run(root: Path, payload: str, result: dict[str, Any]) -> dict[str, Any]:
    """Persist a complete router response so the UI can restore prior runs."""
    created_at = datetime.now(UTC)
    run_id = f"route-{created_at.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}"
    record = {
        **result,
        "run_id": run_id,
        "created_at": created_at.isoformat(),
        "input_jsonl": payload,
    }
    directory = root / "query-router-runs"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{run_id}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    return record


def list_router_runs(root: Path, limit: int = 20) -> list[dict[str, Any]]:
    """Return newest persisted router runs, skipping malformed artifacts."""
    directory = root / "query-router-runs"
    records = []
    for path in sorted(directory.glob("route-*.json"), reverse=True)[:max(0, limit)]:
        try:
            records.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return records


@lru_cache(maxsize=1)
def _jev_client():
    if TypeSafeClient is None:
        raise RuntimeError("typesafe-sdk is not installed")
    return TypeSafeClient(api_key=os.environ["TYPESAFE_API_KEY"])


def load_clusters(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    counts = Counter(item["cluster"] for item in manifest["documents"])
    return [
        {
            "id": cluster,
            "label": cluster.replace("_", " ").title(),
            "document_count": counts.get(cluster, 0),
            "description": description,
            "destination": f"cluster/{cluster}",
        }
        for cluster, description in CLUSTER_DESCRIPTIONS.items()
    ]


def router_capability() -> dict[str, Any]:
    sdk_installed = Choice is not None and TypeSafeClient is not None
    key_configured = bool(os.environ.get("TYPESAFE_API_KEY"))
    return {
        "name": "jev-cluster-router-v1",
        "provider": "TypeSafe Jev",
        "jev_available": sdk_installed and key_configured,
        "sdk_installed": sdk_installed,
        "key_configured": key_configured,
        "mode": "jev" if sdk_installed and key_configured else "deterministic_fallback",
    }


def parse_jsonl(payload: str) -> list[tuple[int, str]]:
    records: list[tuple[int, str]] = []
    for line_number, raw_line in enumerate(payload.splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            record = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Line {line_number} is not valid JSON: {error.msg}") from error
        if not isinstance(record, dict):
            raise ValueError(f"Line {line_number} must contain a JSON object")
        query = next(
            (record.get(field) for field in QUERY_FIELDS if isinstance(record.get(field), str)),
            None,
        )
        if not query or not query.strip():
            raise ValueError(
                f"Line {line_number} needs a non-empty user_input, query, or question field"
            )
        records.append((line_number, query.strip()))
    if not records:
        raise ValueError("Submit at least one non-empty JSONL record")
    return records


def _fallback_route(query: str) -> dict[str, Any]:
    normalized = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    raw_scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for cluster, signals in CLUSTER_SIGNALS.items():
        hits = [signal for signal in signals if signal in normalized]
        matched[cluster] = hits
        # Longer phrases are more discriminating than one-word matches.
        raw_scores[cluster] = sum(1.0 + 0.35 * signal.count(" ") for signal in hits)

    if not any(raw_scores.values()):
        raw_scores["research"] = 0.5
        matched["research"] = ["general research fallback"]

    ranked = sorted(raw_scores.items(), key=lambda item: (-item[1], item[0]))
    selected, best_score = ranked[0]
    exponents = {cluster: math.exp(min(score, 8.0)) for cluster, score in raw_scores.items()}
    denominator = sum(exponents.values())
    probabilities = {
        cluster: round(value / denominator, 4)
        for cluster, value in sorted(exponents.items())
    }
    return {
        "cluster": selected,
        "confidence": probabilities[selected],
        "method": "deterministic_fallback",
        "signals": matched[selected],
        "score": round(best_score, 3),
        "probabilities": probabilities,
    }


def _jev_route(query: str) -> dict[str, Any]:  # pragma: no cover - external API
    question = Choice(
        instructions=(
            "Route the user's search query to exactly one document cluster. "
            "Classify the requested evidence, not the answer. Treat statistics about "
            "employees, employer-sponsored plans, plan sponsors, or their members as "
            "benefits_research even when the topic is prevalence, health outcomes, or SDOH. "
            "Use population_health only for general, geographic, state, or national populations. "
            "Route insurer premium-dollar allocation, medical-versus-administrative spending, "
            "taxes, fees, cost containment, or insurer profit to policy. Route employer premium "
            "trends, employee contributions, and benefit surveys to benefits_research. Route "
            "questions about observed results from an empirical study or named analysis to research, "
            "including intervention outcomes and subgroup affordability findings. Route requests "
            "for treatment, screening, vaccination, or patient-care recommendations to "
            "clinical_guidance. Use population_health for descriptive population prevalence, "
            "demographics, geographic comparisons, and state or national rankings."
        ),
        criteria=CLUSTER_DESCRIPTIONS,
    )
    response = _jev_client().system_one(
        state={"user_query": query},
        questions={"cluster": question},
    )
    answer = response.choices["cluster"]
    probabilities = {key: round(float(value), 4) for key, value in answer.probabilities.items()}
    return {
        "cluster": answer.choice,
        "confidence": round(float(answer.confidence), 4),
        "method": "jev",
        "signals": [f"Jev model: {response.model}"],
        "score": round(float(answer.confidence), 4),
        "probabilities": probabilities,
    }


def _apply_routing_guardrails(query: str, result: dict[str, Any]) -> dict[str, Any]:
    """Apply narrow, explainable overrides where cluster semantics overlap."""
    normalized = re.sub(r"[^a-z0-9]+", " ", query.lower()).strip()
    source_markers = ("study", "analysis", "research report", "data point")
    finding_markers = (
        "according to", "observed", "findings", "most likely", "associated",
        "compared", "change", "changes", "outcome", "outcomes",
    )
    guidance_markers = (
        "recommend", "recommended", "recommendation", "should", "treatment",
        "treat", "screening", "vaccination", "vaccine schedule", "care plan",
    )
    source_marker = next((marker for marker in source_markers if marker in normalized), None)
    finding_marker = next((marker for marker in finding_markers if marker in normalized), None)
    is_study_finding = (
        source_marker is not None
        and finding_marker is not None
        and not any(marker in normalized for marker in guidance_markers)
    )
    if not is_study_finding or result["cluster"] == "research":
        return result

    target_confidence = 0.9
    probabilities = dict(result.get("probabilities") or {})
    other_total = sum(
        value for cluster, value in probabilities.items() if cluster != "research"
    )
    adjusted = {
        cluster: round(
            target_confidence if cluster == "research"
            else (value / other_total) * (1 - target_confidence) if other_total
            else 0.0,
            4,
        )
        for cluster, value in probabilities.items()
    }
    adjusted.setdefault("research", target_confidence)
    return {
        **result,
        "cluster": "research",
        "confidence": target_confidence,
        "score": target_confidence,
        "method": "research_finding_guardrail",
        "signals": [
            *result.get("signals", []),
            source_marker,
            finding_marker,
            "Explicit study/analysis finding; no clinical recommendation requested",
        ],
        "probabilities": adjusted,
    }


def route_jsonl(payload: str, manifest_path: Path) -> dict[str, Any]:
    capability = router_capability()
    events = [
        {"stage": "received", "status": "complete"},
        {"stage": "validating_jsonl", "status": "running"},
    ]
    try:
        records = parse_jsonl(payload)
    except ValueError as error:
        events[-1] = {"stage": "validating_jsonl", "status": "failed", "detail": str(error)}
        return {"status": "failed", "router": capability, "events": events, "routes": [], "error": str(error)}

    events[-1] = {
        "stage": "validating_jsonl",
        "status": "complete",
        "detail": f"{len(records)} record(s)",
    }
    events.append({"stage": "classifying", "status": "running"})
    routes = []
    fallback_reason = None
    for line_number, query in records:
        if capability["jev_available"]:
            try:
                result = _jev_route(query)
            except Exception as error:  # keep routing available and expose the degradation
                fallback_reason = f"Jev request failed: {type(error).__name__}: {error}"
                result = _fallback_route(query)
        else:
            result = _fallback_route(query)
        result = _apply_routing_guardrails(query, result)
        routes.append({
            "line": line_number,
            "query": query,
            **result,
            "destination": f"cluster/{result['cluster']}",
        })

    events[-1] = {"stage": "classifying", "status": "complete"}
    events.append({
        "stage": "routed",
        "status": "complete",
        "detail": f"{len(routes)} route(s) selected",
    })
    if fallback_reason:
        capability = {**capability, "mode": "deterministic_fallback", "fallback_reason": fallback_reason}
    return {
        "status": "routed",
        "router": capability,
        "events": events,
        "clusters": load_clusters(manifest_path),
        "routes": routes,
    }
