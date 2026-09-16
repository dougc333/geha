"""Exercise every billing-code query through Streamlit's chat-input UI."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

from streamlit.testing.v1 import AppTest


HERE = Path(__file__).resolve().parent
ANSWER_RE = re.compile(
    r"^- Billing Code: ([A-Z]\d{4}|\d{5}); Source document: ([^;\n]+); "
    r"Table: ([^\n]+)$",
    re.MULTILINE,
)


def run_evaluation(fixture_path: Path, limit: int | None = None) -> dict:
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    expected = defaultdict(set)
    billing_items = defaultdict(dict)
    for case in fixture["cases"]:
        key = (case["source_document"], case["table_name"])
        expected[case["billing_code"]].add(key)
        billing_items[case["billing_code"]][key] = case["items"]

    app = AppTest.from_file(HERE / "medical_claims_advisor_ui.py", default_timeout=20).run()
    if app.exception:
        raise RuntimeError(f"Streamlit failed to start: {[str(e.message) for e in app.exception]}")

    results = []
    codes = sorted(expected)
    if limit is not None:
        codes = codes[:limit]
    for index, code in enumerate(codes, 1):
        app.session_state["claims_messages"] = []
        app.chat_input[0].set_value(code).run()
        answers = [item.value for item in app.markdown if "Billing Code:" in item.value]
        rendered = answers[-1] if answers else ""
        actual = {
            (source, table)
            for found_code, source, table in ANSWER_RE.findall(rendered)
            if found_code == code
        }
        passed = (
            not app.exception
            and len(answers) == 1
            and actual == expected[code]
            and "no exact match" not in rendered
        )
        results.append({
            "query": code,
            "expected": sorted(expected[code]),
            "actual": sorted(actual),
            "matched_policy_names": sorted(
                source.removeprefix("geha-coverage-policy-").removesuffix(".pdf")
                for source, _ in actual
            ),
            "billing_table_items": [
                {"source_document": source, "table_name": table, "items": items}
                for (source, table), items in sorted(billing_items[code].items())
            ],
            "pass": passed,
            "error": [str(e.message) for e in app.exception],
        })
        if index % 10 == 0 or not passed or index == len(codes):
            print(f"Streamlit code queries: {index}/{len(codes)}; "
                  f"passed {sum(item['pass'] for item in results)}", flush=True)
    return {
        "documents": len(fixture["documents"]),
        "unique_code_queries": len(results),
        "passed": sum(item["pass"] for item in results),
        "source_table_cases": sum(len(expected[code]) for code in codes),
        "results": results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=HERE / "billing_code_evals.json")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_evaluation(args.fixture, args.limit)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
    if report["passed"] != report["unique_code_queries"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
