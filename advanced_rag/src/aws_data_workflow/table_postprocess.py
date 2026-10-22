"""Normalize table headers after first-pass page extraction.

Raw Docling artifacts remain unchanged. Retrieval-safe normalized copies and an
auditable report are written alongside them.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from .visual_processing import table_headers_are_default


SEPARATOR_CELL = re.compile(r"^:?-{3,}:?$")


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    cells = _cells(line)
    return bool(cells) and all(
        SEPARATOR_CELL.fullmatch(cell.replace(" ", "")) for cell in cells
    )


def _escape(cell: str) -> str:
    return cell.replace("|", r"\|")


def normalize_markdown_tables(
    markdown: str,
    previous_headers: list[str] | None = None,
) -> tuple[str, list[str] | None, list[dict[str, Any]]]:
    """Repair placeholder Markdown headers using conservative deterministic rules."""
    lines = markdown.splitlines()
    findings: list[dict[str, Any]] = []
    last_headers = previous_headers
    for index in range(len(lines) - 1):
        if not lines[index].lstrip().startswith("|") or not _is_separator(lines[index + 1]):
            continue
        headers = _cells(lines[index])
        if table_headers_are_default(headers):
            if last_headers is not None and len(last_headers) == len(headers):
                replacement = last_headers
                method = "inherited_previous_table"
            elif len(headers) == 2:
                replacement = ["Field", "Details"]
                method = "two_column_key_value_schema"
            else:
                findings.append({
                    "line": index + 1,
                    "columns": len(headers),
                    "original_headers": headers,
                    "status": "review_required",
                    "reason": "default_headers_without_confident_replacement",
                })
                last_headers = None
                continue
            lines[index] = "| " + " | ".join(_escape(cell) for cell in replacement) + " |"
            findings.append({
                "line": index + 1,
                "columns": len(headers),
                "original_headers": headers,
                "normalized_headers": replacement,
                "status": "normalized",
                "method": method,
            })
            headers = replacement
        if not table_headers_are_default(headers) and any(headers):
            last_headers = headers
    suffix = "\n" if markdown.endswith("\n") else ""
    return "\n".join(lines) + suffix, last_headers, findings


def _write_normalized_table(
    table_dir: Path,
    headers: list[str],
    rows: list[list[str]],
) -> dict[str, str]:
    csv_path = table_dir / "table.normalized.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(headers)
        writer.writerows(rows)
    records = [
        {header: row[index] if index < len(row) else "" for index, header in enumerate(headers)}
        for row in rows
    ]
    json_path = table_dir / "table.normalized.json"
    json_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    markdown_path = table_dir / "table.normalized.md"
    markdown_lines = [
        "| " + " | ".join(_escape(cell) for cell in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    markdown_lines.extend(
        "| " + " | ".join(_escape(cell) for cell in row) + " |" for row in rows
    )
    markdown_path.write_text("\n".join(markdown_lines) + "\n", encoding="utf-8")
    return {
        "normalized_csv": csv_path.name,
        "normalized_json": json_path.name,
        "normalized_markdown": markdown_path.name,
    }


def postprocess_document(document_dir: Path) -> dict[str, Any]:
    """Normalize page Markdown and structured table artifacts for one document."""
    findings: list[dict[str, Any]] = []
    previous_headers: list[str] | None = None
    previous_page: int | None = None
    pages_dir = document_dir / "pages"
    for source in sorted(pages_dir.glob("page-*/docling.md")):
        page = int(source.parent.name.removeprefix("page-"))
        if previous_page is None or page != previous_page + 1:
            previous_headers = None
        raw = source.read_text(encoding="utf-8")
        normalized, previous_headers, page_findings = normalize_markdown_tables(
            raw, previous_headers
        )
        (source.parent / "docling.normalized.md").write_text(
            normalized, encoding="utf-8"
        )
        for item in page_findings:
            findings.append({
                "artifact": str(source.relative_to(document_dir)),
                "page": page,
                **item,
            })
        previous_page = page

    previous_visual_headers: list[str] | None = None
    previous_visual_page: int | None = None
    table_pattern = document_dir / "visuals" / "tables"
    for csv_path in sorted(table_pattern.glob("table-*/table.csv")):
        with csv_path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            headers = next(reader, [])
            rows = list(reader)
        metadata_path = csv_path.parent / "metadata.json"
        metadata = (
            json.loads(metadata_path.read_text(encoding="utf-8"))
            if metadata_path.is_file()
            else {}
        )
        provenance = metadata.get("provenance") or []
        page = int(provenance[0].get("page_no")) if provenance else None
        if table_headers_are_default(headers):
            if (
                previous_visual_headers is not None
                and len(previous_visual_headers) == len(headers)
                and page is not None
                and previous_visual_page is not None
                and page == previous_visual_page + 1
            ):
                normalized_headers = previous_visual_headers
                method = "inherited_previous_page"
            elif len(headers) == 2:
                normalized_headers = ["Field", "Details"]
                method = "two_column_key_value_schema"
            else:
                normalized_headers = None
                method = None
            finding: dict[str, Any] = {
                "artifact": str(csv_path.relative_to(document_dir)),
                "page": page,
                "original_headers": headers,
            }
            if normalized_headers is None:
                finding.update(
                    status="review_required",
                    reason="default_headers_without_confident_replacement",
                )
                metadata["review_status"] = "review_required"
                issues = metadata.setdefault("issues", [])
                if "table_headers_are_default" not in issues:
                    issues.append("table_headers_are_default")
            else:
                artifacts = _write_normalized_table(
                    csv_path.parent, normalized_headers, rows
                )
                metadata.setdefault("artifacts", {}).update(artifacts)
                metadata["header_normalization"] = {
                    "status": "normalized",
                    "method": method,
                    "original_headers": headers,
                    "normalized_headers": normalized_headers,
                }
                finding.update(
                    status="normalized",
                    method=method,
                    normalized_headers=normalized_headers,
                )
                previous_visual_headers = normalized_headers
            findings.append(finding)
            if metadata_path.is_file():
                metadata_path.write_text(
                    json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
                )
        elif headers:
            previous_visual_headers = headers
        previous_visual_page = page

    report = {
        "schema_version": "1.0",
        "document_id": document_dir.name,
        "normalized": sum(item["status"] == "normalized" for item in findings),
        "review_required": sum(
            item["status"] == "review_required" for item in findings
        ),
        "findings": findings,
    }
    (document_dir / "table-postprocess.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def postprocess_runtime(
    runtime_root: Path, document_ids: list[str] | None = None
) -> dict[str, Any]:
    documents_root = runtime_root / "documents"
    directories = (
        [documents_root / document_id for document_id in document_ids]
        if document_ids is not None
        else sorted(path for path in documents_root.glob("doc-*") if path.is_dir())
    )
    reports = [postprocess_document(path) for path in directories if path.is_dir()]
    return {
        "documents": len(reports),
        "normalized": sum(report["normalized"] for report in reports),
        "review_required": sum(report["review_required"] for report in reports),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, default=Path("runtime"))
    parser.add_argument("--document-id", action="append", dest="document_ids")
    args = parser.parse_args()
    print(json.dumps(postprocess_runtime(args.runtime_root, args.document_ids), indent=2))


if __name__ == "__main__":
    main()
