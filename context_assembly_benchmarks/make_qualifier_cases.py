"""Generate qualifier eval cases: questions whose complete answer needs text next to the table.

Each case's required facts are labelled as either
  value      a table cell (drug name, preference) - present in flat chunks and parent tables
  qualifier  a footnote, exception or condition stored beside the table in the policy, e.g.
             "Preferred product requirements apply to new starts only", the authorization period,
             or Xgeva's "**Does not apply in the setting of Prostate or Breast Cancer"
Qualifier text is read from the verified docling Markdown (context_attachments), and table values
from the pgvector store, so nothing is typed in by hand.

    .venv/bin/python context_assembly_benchmarks/make_qualifier_cases.py
writes table_qualifier_evals.json next to this file.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from context_attachments import attached_notes
from table_rag import DEFAULT_DATABASE_URL, connect

DIRECTORY = Path(__file__).resolve().parent
NAMES = {
    "erythropoietin-stimulating-agents": "erythropoietin-stimulating agents",
    "gnrh-analogues-in-prostate-cancer": "GnRH analogues in prostate cancer",
    "long-acting-gcsfs": "long-acting G-CSFs",
    "short-acting-gcsfs": "short-acting G-CSFs",
    "non-muscle-invasive-bladder-cancer": "non-muscle invasive bladder cancer",
    "paclitaxel-protein-bound": "protein-bound paclitaxel",
    "taxotere-docivyx": "Taxotere/Docivyx",
}


def name_of(source: str) -> str:
    stem = source.removeprefix("geha-coverage-policy-").removesuffix(".pdf")
    return NAMES.get(stem, stem)


def preference(record: dict) -> str:
    return next((str(v) for k, v in record.items() if k.lower().startswith("preference")), "")


def scope_fact(after: str) -> dict | None:
    match = re.search(r"Preferred product requirements apply to ([^.]+)\.", after)
    if not match:
        return None
    scope = match.group(1).strip()
    reauth = "reauthorization" in scope.lower()
    return {"type": "qualifier", "kind": "requirement scope",
            "text": f"Preferred product requirements apply to {scope}.",
            "match": [scope, "new starts and reauthorizations" if reauth else "new starts only"],
            "meaning": ("the requirements also apply to reauthorizations" if reauth
                        else "the requirements apply to new starts only, not to reauthorizations")}


def main() -> None:
    cases = []
    with connect(os.getenv("GEHA_RAG_DATABASE_URL", DEFAULT_DATABASE_URL)) as connection:
        tables = connection.execute(
            "SELECT source, table_number, full_csv, rows_json FROM policy_tables "
            "WHERE title LIKE 'Drug preference%%' ORDER BY source").fetchall()
    for table in tables:
        source, number, name = table["source"], int(table["table_number"]), name_of(table["source"])
        notes = attached_notes(source, table["full_csv"])
        records = table["rows_json"]
        preferred = [r["Drug Name"] for r in records if preference(r).strip().lower().startswith("preferred")]
        scope = scope_fact(notes["after"])
        stem = source.removeprefix("geha-coverage-policy-").removesuffix(".pdf")

        # 1. Requirement scope: needs the preferred rows (table) + the scope note (beside the table).
        if scope and preferred:
            cases.append({
                "id": f"{stem}_scope", "kind": "Qualifier", "qualifier_type": "requirement scope",
                "query": (f"Which {name} products are preferred, and do the preferred-product "
                          f"requirements also apply to reauthorizations?"),
                "source": source, "table_number": number,
                "facts": [{"type": "value", "text": p, "match": [p]} for p in preferred] + [scope],
            })

        # 2. Authorization period: needs a row's prior-auth value + the paragraph before the table.
        months = re.search(r"issued for (\d+ \((\w+)\) months)", notes["before"])
        non_preferred = next((r for r in records if preference(r).strip().lower().startswith("non")), None)
        if months and non_preferred and stem in ("xgeva", "bendamustine", "trastuzumab"):
            drug = non_preferred["Drug Name"]
            number_months, word = months.group(1).split(" ")[0], months.group(2)
            cases.append({
                "id": f"{stem}_auth_period", "kind": "Qualifier", "qualifier_type": "authorization period",
                "query": f"Does {drug} require prior authorization, and for how long are authorizations issued?",
                "source": source, "table_number": number,
                "facts": [
                    {"type": "value", "text": f"{drug} requires prior authorization", "match": [drug]},
                    {"type": "qualifier", "kind": "authorization period",
                     "text": f"Authorizations are issued for {months.group(1)}.",
                     "match": [months.group(1), f"{number_months} months", f"{word} months"]},
                ],
            })

        # 3. Footnote: Xgeva's ** marker on every non-preferred biosimilar.
        footnote = re.search(r"\*\*\s*(Does not apply[^\n.]*\.)", notes["after"])
        if footnote:
            cases.append({
                "id": f"{stem}_footnote", "kind": "Qualifier", "qualifier_type": "footnote",
                "query": "Is Denosumab (Xgeva) non-preferred for a patient with breast cancer?",
                "source": source, "table_number": number,
                "facts": [
                    {"type": "value", "text": "Denosumab (Xgeva) is listed as Non-Preferred",
                     "match": ["Denosumab (Xgeva)"]},
                    {"type": "qualifier", "kind": "footnote", "text": footnote.group(1),
                     "match": ["does not apply in the setting of prostate or breast cancer"],
                     "meaning": "the non-preferred status does not apply for breast (or prostate) cancer"},
                ],
            })
    out = DIRECTORY / "table_qualifier_evals.json"
    out.write_text(json.dumps(cases, indent=2) + "\n")
    kinds: dict[str, int] = {}
    for case in cases:
        kinds[case["qualifier_type"]] = kinds.get(case["qualifier_type"], 0) + 1
    print(f"{len(cases)} qualifier cases -> {out}: {kinds}")


if __name__ == "__main__":
    main()
