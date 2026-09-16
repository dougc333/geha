"""Evaluate Streamlit's semantic table fallback with name-free, code-free questions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

try:
    from .billing_code_data import requested_billing_codes
    from .medical_claims_advisor import retrieve_tables_for_named_condition
    from .table_rag import DEFAULT_DATABASE_URL
except ImportError:  # pragma: no cover - direct CLI execution
    from billing_code_data import requested_billing_codes
    from medical_claims_advisor import retrieve_tables_for_named_condition
    from table_rag import DEFAULT_DATABASE_URL


HERE = Path(__file__).resolve().parent
POLICY_DIR = HERE.parent / "downloads" / "coverage-policies"
DEFAULT_EVAL_FILE = HERE / "semantic_fallback_evals.json"


def run_evaluation(eval_file: Path, database_url: str) -> dict:
    cases = json.loads(eval_file.read_text(encoding="utf-8"))["cases"]
    app = AppTest.from_file(HERE / "medical_claims_advisor_ui.py", default_timeout=30).run()
    if app.exception:
        raise RuntimeError(f"Streamlit failed to start: {[e.message for e in app.exception]}")
    app.text_input[0].set_value(database_url).run()
    results = []
    for case in cases:
        markdown = POLICY_DIR / case["expected_source"].replace(".pdf", ".docling.md")
        source_lines = markdown.read_text(encoding="utf-8").splitlines()
        source_verified = case["source_anchor"].casefold() in source_lines[
            case["docling_line"] - 1
        ].casefold()

        code_free = not requested_billing_codes(case["query"])
        direct_lookup_empty = not retrieve_tables_for_named_condition(
            case["query"], database_url
        )
        app.session_state["claims_messages"] = []
        app.chat_input[0].set_value(case["query"]).run()
        response = app.session_state["claims_messages"][-1]
        summary = response.get("policy_summary")
        actual_source = summary["source"] if summary else None
        tables = summary.get("tables", []) if summary else []
        expected_table = next(
            (table for table in tables if table["title"] == case["expected_table"]),
            None,
        )
        full_parent_displayed = bool(
            actual_source == case["expected_source"]
            and expected_table
            and len(app.dataframe) > 0
        )
        passed = bool(
            source_verified
            and code_free
            and direct_lookup_empty
            and full_parent_displayed
            and not app.exception
        )
        results.append({
            "id": case["id"],
            "query": case["query"],
            "expected_source": case["expected_source"],
            "expected_table": case["expected_table"],
            "actual_source": actual_source,
            "actual_tables": [table["title"] for table in tables],
            "docling_source_verified": source_verified,
            "no_exact_billing_code": code_free,
            "no_direct_policy_or_condition_match": direct_lookup_empty,
            "full_parent_displayed": full_parent_displayed,
            "pass": passed,
            "errors": [e.message for e in app.exception],
        })
        print(f"{'PASS' if passed else 'FAIL'} {case['id']}: "
              f"{actual_source} / {[table['title'] for table in tables]}", flush=True)

    return {
        "eval_file": str(eval_file),
        "cases": len(results),
        "passed": sum(result["pass"] for result in results),
        "failed": sum(not result["pass"] for result in results),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_FILE)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_evaluation(args.eval_file, args.database_url)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
