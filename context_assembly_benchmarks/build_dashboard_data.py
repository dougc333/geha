"""Collect both evaluations into one JSON file for the React dashboard.

    .venv/bin/python context_assembly_benchmarks/build_dashboard_data.py
reads hybrid_context_results.json (context completeness) and, when present,
chunking_judge_results.json (answer completeness), and writes dashboard/public/data/dashboard.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent
OUT = DIRECTORY / "dashboard" / "public" / "data" / "dashboard.json"
CONTEXT_MODES = {"flat_semantic_chunks": "flat", "table_aware_rag": "table", "table_aware_notes": "notes"}
ANSWER_PATHS = {"flat": "flat", "hierarchical": "table", "hierarchical_notes": "notes"}
SLICES = {"overall": "overall", "preference": "preference", "relation": "relation", "qualifier": "qualifier",
          "Preference lookup": "preference", "Row-to-column relationship": "relation", "Qualifier": "qualifier"}


def context_section() -> dict:
    report = json.loads((DIRECTORY / "hybrid_context_results.json").read_text())
    summary = {CONTEXT_MODES[mode]: {SLICES[s]: v for s, v in slices.items()}
               for mode, slices in report["summary"].items()}
    cases = []
    for result in report["results"]:
        cases.append({
            "id": result["id"], "kind": result["kind"], "query": result["query"],
            "source": result["expected_source"],
            "strategies": {
                CONTEXT_MODES[mode]: {
                    "coverage": result[mode]["expected_evidence_coverage"],
                    "complete": result[mode]["complete_evidence"],
                    "tokens": result[mode]["estimated_tokens"],
                    "rows_sent": result[mode]["rows_sent"],
                    "sibling_rows": result[mode]["sibling_rows"],
                    "facts": result[mode]["facts"],
                }
                for mode in CONTEXT_MODES if mode in result
            },
        })
    return {"configuration": report.get("configuration", {}), "summary": summary, "cases": cases}


def answer_section() -> dict | None:
    path = DIRECTORY / "chunking_judge_results.json"
    if not path.exists():
        return None
    report = json.loads(path.read_text())
    if report.get("configuration", {}).get("evaluation_version") != 3:
        return None
    summary = {"queries_completed": report["summary"]["queries_completed"],
               "queries_requested": report["summary"]["queries_requested"],
               "total_llm_tokens": report["summary"]["total_llm_tokens"]}
    for path_name, key in ANSWER_PATHS.items():
        summary[key] = {SLICES[s]: v for s, v in report["summary"][path_name].items()}
    cases = []
    for result in report["results"]:
        if result.get("error"):
            cases.append({"id": result["id"], "kind": result["kind"], "query": result["query"],
                          "error": result["error"]})
            continue
        cases.append({
            "id": result["id"], "kind": result["kind"], "query": result["query"],
            "reference": result.get("reference"),
            "strategies": {
                key: {
                    "answer": result[path_name]["answer"],
                    "judge": result[path_name]["verdict"],
                    "facts": result[path_name]["facts"],
                    "context_tokens": result["context_metrics"][path_name]["estimated_tokens"],
                    "llm_tokens": result[path_name]["total_tokens"],
                }
                for path_name, key in ANSWER_PATHS.items()
            },
        })
    return {"configuration": report["configuration"], "summary": summary, "cases": cases}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "strategies": [
            {"id": "flat", "label": "Flat row chunks"},
            {"id": "table", "label": "Table-aware RAG"},
            {"id": "notes", "label": "Table-aware + attached notes"},
        ],
        "context": context_section(),
        "answers": answer_section(),
    }
    OUT.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {OUT} (answers: {'yes' if data['answers'] else 'not yet'})")


if __name__ == "__main__":
    main()
