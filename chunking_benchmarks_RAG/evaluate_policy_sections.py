"""Evaluate direct policy-section retrieval without embeddings or OpenAI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:  # Support module and direct-script execution.
    from .medical_claims_advisor import (
        build_policy_summary,
        is_revision_table,
        retrieve_policy_sections,
        retrieve_tables_for_named_condition,
        should_expand_universal,
    )
    from .table_rag import DEFAULT_DATABASE_URL, connect
except ImportError:  # pragma: no cover - exercised by direct CLI use
    from medical_claims_advisor import (
        build_policy_summary,
        is_revision_table,
        retrieve_policy_sections,
        retrieve_tables_for_named_condition,
        should_expand_universal,
    )
    from table_rag import DEFAULT_DATABASE_URL, connect


DEFAULT_EVAL_FILE = Path(__file__).with_name("policy_section_evals.json")
DEFAULT_NAME_EVAL_FILE = Path(__file__).with_name("policy_name_section_evals.json")


def section_facts(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "chunk_number": section["chunk_number"],
            "section_type": section["section_type"],
            "condition": section["condition"],
        }
        for section in sections
    ]


def run_evaluation(
    eval_path: Path, database_url: str, name_eval_path: Path = DEFAULT_NAME_EVAL_FILE
) -> dict[str, Any]:
    fixture = json.loads(eval_path.read_text(encoding="utf-8"))
    name_fixture = json.loads(name_eval_path.read_text(encoding="utf-8"))
    cases = fixture["cases"]
    with connect(database_url) as connection:
        corpus = connection.execute(
            """
            SELECT count(DISTINCT source_pdf) AS source_files, count(*) AS chunks
            FROM policy_chunks
            """
        ).fetchone()
        stored_sources = {
            row["source_pdf"]
            for row in connection.execute(
                "SELECT DISTINCT source_pdf FROM policy_chunks"
            ).fetchall()
        }
        stored_only = name_fixture["stored_only"]
        nested_sections = connection.execute(
            """
            SELECT chunk_number, section_type, condition
            FROM policy_chunks
            WHERE source_pdf = %s AND section_type IN ('indication', 'universal')
            ORDER BY chunk_number
            """,
            (stored_only["source"],),
        ).fetchall()
        nested_table_count = connection.execute(
            "SELECT count(*) AS n FROM policy_tables WHERE source = %s",
            (stored_only["source"],),
        ).fetchone()["n"]
    expected_sources = {
        case["source"] for case in name_fixture["cases"]
    } | {stored_only["source"]}
    source_inventory_pass = stored_sources == expected_sources
    corpus_pass = all(
        corpus[key] == expected for key, expected in fixture["corpus"].items()
    ) and source_inventory_pass
    stored_only_pass = (
        section_facts(nested_sections) == stored_only["expected_sections"]
        and nested_table_count == 0
    )

    results: list[dict[str, Any]] = []
    for index, case in enumerate(cases, 1):
        tables = retrieve_tables_for_named_condition(case["query"], database_url)
        summary = build_policy_summary(case["query"], tables)
        source = summary["source"] if summary else None
        sections = (
            retrieve_policy_sections(database_url, source, case["query"])
            if source else []
        )
        indications = [
            section for section in sections if section["section_type"] == "indication"
        ]
        universal = [
            section for section in sections if section["section_type"] == "universal"
        ]
        by_number = {str(section["chunk_number"]): section for section in sections}
        text_checks = {
            f"chunk_{number}:{phrase}": (
                number in by_number
                and phrase.casefold() in by_number[number]["content"].casefold()
            )
            for number, phrases in case.get("required_text", {}).items()
            for phrase in phrases
        }
        checks = {
            "source": source == case["source"],
            "indication_chunks": [
                section["chunk_number"] for section in indications
            ] == case["indication_chunks"],
            "conditions": [
                section["condition"] for section in indications
            ] == case["conditions"],
            "universal_chunks": [
                section["chunk_number"] for section in universal
            ] == case["universal_chunks"],
            "universal_expanded": should_expand_universal(case["query"])
            == case["universal_expanded"],
            "preferred": summary is not None
            and summary["preferred"] == case["preferred"],
            "non_preferred": summary is not None
            and summary["non_preferred"] == case["non_preferred"],
            "criteria_only": all(
                section["section_type"] in {"indication", "universal"}
                for section in sections
            ),
            "revision_excluded": summary is not None
            and all(
                not is_revision_table(table["title"])
                for table in summary["tables"]
            ),
            **text_checks,
        }
        passed = bool(checks) and all(checks.values())
        results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_source": case["source"],
                "actual_source": source,
                "returned_sections": section_facts(sections),
                "checks": checks,
                "pass": passed,
            }
        )
        print(
            f"[{index:02d}/{len(cases)}] {'PASS' if passed else 'FAIL'} {case['id']}",
            flush=True,
        )

    named_results: list[dict[str, Any]] = []
    for index, case in enumerate(name_fixture["cases"], 1):
        tables = retrieve_tables_for_named_condition(case["query"], database_url)
        summary = build_policy_summary(case["query"], tables)
        source = summary["source"] if summary else None
        sections = (
            retrieve_policy_sections(database_url, source, case["query"])
            if source else []
        )
        checks = {
            "source": source == case["source"],
            "exact_sections": section_facts(sections) == case["expected_sections"],
            "criteria_only": all(
                section["section_type"] in {"indication", "universal"}
                for section in sections
            ),
            "revision_excluded": summary is not None
            and all(
                not is_revision_table(table["title"])
                for table in summary["tables"]
            ),
        }
        passed = all(checks.values())
        named_results.append(
            {
                "id": case["id"],
                "query": case["query"],
                "expected_source": case["source"],
                "actual_source": source,
                "returned_sections": section_facts(sections),
                "checks": checks,
                "pass": passed,
            }
        )
        print(
            f"[name {index:02d}/{len(name_fixture['cases'])}] "
            f"{'PASS' if passed else 'FAIL'} {case['id']}",
            flush=True,
        )

    passed_count = sum(result["pass"] for result in results)
    named_passed = sum(result["pass"] for result in named_results)
    total = len(results) + len(named_results)
    total_passed = passed_count + named_passed
    return {
        "eval_files": [str(eval_path), str(name_eval_path)],
        "corpus": {
            "expected": fixture["corpus"],
            "actual": dict(corpus),
            "missing_sources": sorted(expected_sources - stored_sources),
            "unexpected_sources": sorted(stored_sources - expected_sources),
            "pass": corpus_pass,
        },
        "stored_only": {
            "source": stored_only["source"],
            "reason": stored_only["reason"],
            "table_count": nested_table_count,
            "returned_sections": section_facts(nested_sections),
            "pass": stored_only_pass,
        },
        "summary": {
            "cases": total,
            "passed": total_passed,
            "failed": total - total_passed,
            "pass_rate": total_passed / total if total else 0.0,
            "focused_cases": len(results),
            "focused_passed": passed_count,
            "filename_cases": len(named_results),
            "filename_passed": named_passed,
            "corpus_pass": corpus_pass,
            "stored_only_pass": stored_only_pass,
        },
        "results": [
            {"suite": "focused", **result} for result in results
        ] + [
            {"suite": "filename_lookup", **result} for result in named_results
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval-file", type=Path, default=DEFAULT_EVAL_FILE)
    parser.add_argument("--name-eval-file", type=Path, default=DEFAULT_NAME_EVAL_FILE)
    parser.add_argument("--database-url", default=DEFAULT_DATABASE_URL)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run_evaluation(args.eval_file, args.database_url, args.name_eval_file)
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")
    print(json.dumps(
        {
            "corpus": report["corpus"],
            "stored_only": report["stored_only"],
            "summary": report["summary"],
        },
        indent=2,
    ))
    if (
        report["summary"]["failed"]
        or not report["corpus"]["pass"]
        or not report["stored_only"]["pass"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
