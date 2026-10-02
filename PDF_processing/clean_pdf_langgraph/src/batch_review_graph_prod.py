"""Production batch review graph with runtime validation and visible failures.

This module intentionally leaves ``batch_review_graph.py`` unchanged.  It uses
the same extraction and human-approval workflow while keeping every recoverable
failure on the table that caused it.  Invalid document-level state raises a
controlled exception; invalid individual tables are marked unverified and the
graph continues.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .batch_review_graph import (
    EXTRACTORS,
    cycle_html_tables_node,
    docling_node,
    human_review_node,
    html_node,
    render_pages_node,
)
from .extractors import write_new
from .html_vision_review import (
    compare_html_table,
    correct_html_table,
    render_html_table_screenshot,
)
from .paths import BATCH_RUNS_DIR, PDF_DIR
from .raw_table_html import RAW_TABLE_CSS, raw_table_markup
from .schema import CleaningState, ReviewIssue, TableArtifact
from .vision_review import images_for_pages


ReviewVerdict = Literal["match", "mismatch", "uncertain"]
ReviewStage = Literal["validation", "render", "compare", "correct"]
ReviewSeverity = Literal["warning", "error"]


class ReviewStateError(RuntimeError):
    """The document-level graph state is invalid and cannot be reviewed safely."""


class ReviewFailure(TypedDict):
    code: str
    table: int
    page: int
    stage: ReviewStage
    error_type: str
    severity: ReviewSeverity
    explanation: str
    blocks_review: NotRequired[bool]


class ReviewedTable(TypedDict):
    table: TableArtifact
    markup: str
    verdict: ReviewVerdict
    initial_verdict: ReviewVerdict
    initial_issue_count: int
    issues: list[ReviewIssue]
    failures: list[ReviewFailure]
    correction_attempts: int


class ProdBatchReviewState(CleaningState, total=False):
    docling_html: str
    extractor_reviews: dict[str, dict[str, Any]]
    error_reports: dict[str, str]
    vision_approved: bool
    table_slideshow_html: str
    corrected_docling_html: str
    review_table_index: int
    review_current_markup: str
    review_current_verdict: ReviewVerdict
    review_initial_verdict: ReviewVerdict
    review_initial_issue_count: int
    review_current_issues: list[ReviewIssue]
    review_current_failures: list[ReviewFailure]
    review_html_screenshot: str
    review_correction_attempts: int
    review_correction_failed: bool
    review_skip_current: bool
    review_validation_failures: list[list[ReviewFailure]]
    review_results: list[ReviewedTable]


def _safe_int(value: object, fallback: int = 0) -> int:
    return value if type(value) is int else fallback


def table_has_content(table: TableArtifact) -> bool:
    """Return true when a table has at least one nonblank header or cell."""
    return any(column.strip() for column in table["columns"]) or any(
        cell.strip() for row in table["rows"] for cell in row
    )


def _failure(
    *, code: str, table: int, page: int, stage: ReviewStage,
    error_type: str, severity: ReviewSeverity, explanation: str,
    blocks_review: bool | None = None,
) -> ReviewFailure:
    failure: ReviewFailure = {
        "code": code,
        "table": table,
        "page": page,
        "stage": stage,
        "error_type": error_type,
        "severity": severity,
        "explanation": explanation,
    }
    if blocks_review is not None:
        failure["blocks_review"] = blocks_review
    return failure


def _issue_for_failure(failure: ReviewFailure) -> ReviewIssue:
    return {
        "artifact": f"docling table {failure['table']}",
        "page": failure["page"],
        "kind": "other",
        "pdf_evidence": "",
        "extracted_evidence": "",
        "explanation": failure["explanation"],
    }


def _validation_failure(
    code: str, table: int, page: int, explanation: str,
) -> ReviewFailure:
    return _failure(
        code=code,
        table=table,
        page=page,
        stage="validation",
        error_type="TableValidationError",
        severity="error",
        explanation=explanation,
    )


def _content_failure(
    code: str, table: int, page: int, explanation: str,
    *, severity: ReviewSeverity = "warning",
) -> ReviewFailure:
    """Flag suspicious extracted text without preventing vision comparison."""
    return _failure(
        code=code,
        table=table,
        page=page,
        stage="validation",
        error_type="ContentQualityError",
        severity=severity,
        explanation=explanation,
        blocks_review=False,
    )


def _content_quality_failures(
    table: int, page: int, columns: list[str], rows: list[list[str]],
) -> list[ReviewFailure]:
    failures: list[ReviewFailure] = []
    values = [
        *((f"column {index + 1}", value) for index, value in enumerate(columns)),
        *((f"row {row_index + 1}, column {column_index + 1}", value)
          for row_index, row in enumerate(rows)
          for column_index, value in enumerate(row)),
    ]
    for location, value in values:
        if "\ufffd" in value:
            failures.append(_content_failure(
                "TEXT_REPLACEMENT_CHARACTER", table, page,
                f"{location} contains the Unicode replacement character (�), indicating lost text.",
                severity="error",
            ))
        if location.startswith("column ") and re.match(r"^[!|]+[A-Za-z]", value):
            failures.append(_content_failure(
                "SUSPICIOUS_HEADER_PREFIX", table, page,
                f"{location} begins with suspicious punctuation: {value!r}.",
            ))
        if re.search(r"\b[A-Z]&[A-Z](?=[a-z])", value):
            failures.append(_content_failure(
                "MISSING_WHITESPACE_AFTER_ACRONYM", table, page,
                f"{location} may be missing whitespace after an acronym: {value!r}.",
            ))
        if re.search(r"\bbv\b", value, flags=re.IGNORECASE):
            failures.append(_content_failure(
                "POSSIBLE_OCR_SUBSTITUTION", table, page,
                f"{location} contains suspicious OCR token 'bv'; verify whether the PDF says 'by'.",
            ))
    return failures


def validate_and_normalize_tables(
    tables: object, page_count: object,
) -> tuple[list[TableArtifact], list[list[ReviewFailure]]]:
    """Return safe table objects plus failures aligned to their source indices."""
    if type(page_count) is not int or page_count < 1:
        raise ReviewStateError("page_count must be a positive integer")
    if not isinstance(tables, list):
        raise ReviewStateError("docling_tables must be a list")

    normalized: list[TableArtifact] = []
    failures_by_table: list[list[ReviewFailure]] = []
    seen_numbers: set[int] = set()
    required = {
        "extractor", "number", "page", "markdown", "columns", "rows",
        "nearest_heading",
    }

    for index, source_value in enumerate(tables):
        source = source_value if isinstance(source_value, dict) else {}
        table_number = _safe_int(source.get("number"), index + 1)
        page = _safe_int(source.get("page"), 0)
        failures: list[ReviewFailure] = []

        missing = sorted(required - source.keys())
        for field in missing:
            failures.append(_validation_failure(
                f"MISSING_{field.upper()}", table_number, page,
                f"Required table field '{field}' is missing.",
            ))
        if not isinstance(source_value, dict):
            failures.append(_validation_failure(
                "TABLE_NOT_OBJECT", table_number, page,
                "The extracted table must be a mapping.",
            ))
        if type(source.get("number")) is not int or source.get("number", 0) < 1:
            failures.append(_validation_failure(
                "INVALID_TABLE_NUMBER", table_number, page,
                "Table number must be a positive integer.",
            ))
        elif table_number in seen_numbers:
            failures.append(_validation_failure(
                "DUPLICATE_TABLE_NUMBER", table_number, page,
                f"Table number {table_number} is duplicated.",
            ))
        else:
            seen_numbers.add(table_number)
        if type(source.get("page")) is not int or not 1 <= page <= page_count:
            failures.append(_validation_failure(
                "INVALID_PAGE_NUMBER", table_number, page,
                f"Table page must be between 1 and {page_count}.",
            ))
        if source.get("extractor") != "docling":
            failures.append(_validation_failure(
                "INVALID_EXTRACTOR", table_number, page,
                "Production review accepts only Docling table artifacts.",
            ))

        raw_columns = source.get("columns")
        columns = raw_columns if isinstance(raw_columns, list) else []
        if not columns:
            failures.append(_validation_failure(
                "EMPTY_COLUMNS", table_number, page,
                "Table must contain at least one column.",
            ))
        if any(not isinstance(column, str) for column in columns):
            failures.append(_validation_failure(
                "NON_STRING_COLUMN", table_number, page,
                "Every column label must be a string.",
            ))

        raw_rows = source.get("rows")
        rows = raw_rows if isinstance(raw_rows, list) else []
        if not isinstance(raw_rows, list):
            failures.append(_validation_failure(
                "ROWS_NOT_LIST", table_number, page,
                "Table rows must be a list.",
            ))
        safe_rows: list[list[str]] = []
        for row_index, row in enumerate(rows):
            if not isinstance(row, list):
                failures.append(_validation_failure(
                    "ROW_NOT_LIST", table_number, page,
                    f"Row {row_index} must be a list.",
                ))
                continue
            if len(row) != len(columns):
                failures.append(_validation_failure(
                    "ROW_WIDTH_MISMATCH", table_number, page,
                    f"Row {row_index} has {len(row)} cells for {len(columns)} columns.",
                ))
            if any(not isinstance(cell, str) for cell in row):
                failures.append(_validation_failure(
                    "NON_STRING_CELL", table_number, page,
                    f"Row {row_index} contains a non-string cell.",
                ))
            safe_rows.append([cell if isinstance(cell, str) else str(cell) for cell in row])

        safe_columns = [column if isinstance(column, str) else str(column) for column in columns]
        failures.extend(_content_quality_failures(
            table_number, page, safe_columns, safe_rows
        ))

        normalized.append({
            "extractor": "docling",
            "number": table_number,
            "page": page,
            "markdown": source.get("markdown") if isinstance(source.get("markdown"), str) else "",
            "columns": safe_columns,
            "rows": safe_rows,
            "nearest_heading": source.get("nearest_heading")
            if isinstance(source.get("nearest_heading"), str) else "",
        })
        failures_by_table.append(failures)

    return normalized, failures_by_table


def validate_extraction_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    """Validate global extraction state and normalize individual table artifacts."""
    source = Path(state.get("pdf_path", ""))
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ReviewStateError("Source PDF is missing or is not a PDF")
    output_value = state.get("output_dir")
    if not isinstance(output_value, str) or not output_value:
        raise ReviewStateError("Output directory is missing")
    output_dir = Path(output_value)
    if not output_dir.is_dir():
        raise ReviewStateError("Output directory does not exist")
    for key in ("docling_markdown", "docling_chunks_markdown", "docling_tables_markdown"):
        value = state.get(key)
        if not isinstance(value, str) or not Path(value).is_file():
            raise ReviewStateError(f"Required extraction artifact is missing: {key}")

    normalized, failures = validate_and_normalize_tables(
        state.get("docling_tables"), state.get("page_count")
    )
    retained = [
        (table, table_failures)
        for table, table_failures in zip(normalized, failures)
        if table_has_content(table)
    ]
    return {
        "docling_tables": [table for table, _ in retained],
        "review_validation_failures": [items for _, items in retained],
    }


def _is_png(path: Path) -> bool:
    try:
        return path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    except OSError:
        return False


def validate_review_inputs_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    """Attach page-image failures to tables; reject wholly unusable documents."""
    html_path = state.get("docling_html")
    if not isinstance(html_path, str) or not Path(html_path).is_file():
        raise ReviewStateError("Combined Docling HTML artifact is missing")
    page_images = state.get("page_images")
    if not isinstance(page_images, list) or not page_images:
        raise ReviewStateError("No rendered PDF page images are available")
    paths = [Path(value) for value in page_images if isinstance(value, str)]
    if not any(path.is_file() for path in paths):
        raise ReviewStateError("All rendered PDF page images are missing")

    failures_by_table = [list(items) for items in state["review_validation_failures"]]
    for index, table in enumerate(state["docling_tables"]):
        page = table["page"]
        image_value = page_images[page - 1] if 1 <= page <= len(page_images) else None
        if not isinstance(image_value, str) or not Path(image_value).is_file():
            failures_by_table[index].append(_validation_failure(
                "MISSING_PAGE_IMAGE", table["number"], page,
                f"Rendered image for PDF page {page} is missing.",
            ))
        elif not _is_png(Path(image_value)):
            failures_by_table[index].append(_validation_failure(
                "INVALID_PAGE_IMAGE", table["number"], page,
                f"Rendered image for PDF page {page} is not a valid PNG.",
            ))
    return {"review_validation_failures": failures_by_table}


def initialize_review_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    source_tables = state["docling_tables"]
    validation_failures = [
        list(items) for items in state.get("review_validation_failures", [])
    ]
    while len(validation_failures) < len(source_tables):
        validation_failures.append([])
    retained = [
        (table, validation_failures[index])
        for index, table in enumerate(source_tables)
        if table_has_content(table)
    ]
    tables = [table for table, _ in retained]
    validation_failures = [items for _, items in retained]
    for index, table in enumerate(tables):
        detected = _content_quality_failures(
            table["number"], table["page"], table["columns"], table["rows"]
        )
        existing = {
            (failure["code"], failure["explanation"])
            for failure in validation_failures[index]
        }
        validation_failures[index].extend(
            failure for failure in detected
            if (failure["code"], failure["explanation"]) not in existing
        )
    return {
        "review_table_index": 0,
        "review_current_markup": "",
        "review_current_verdict": "uncertain",
        "review_initial_verdict": "uncertain",
        "review_initial_issue_count": 0,
        "review_current_issues": [],
        "review_current_failures": [],
        "review_html_screenshot": "",
        "review_correction_attempts": 0,
        "review_correction_failed": False,
        "review_skip_current": False,
        "docling_tables": tables,
        "review_validation_failures": validation_failures,
        "review_results": [],
    }


def review_work_route(state: ProdBatchReviewState) -> Literal["prepare", "finish"]:
    return "prepare" if state["review_table_index"] < len(state["docling_tables"]) else "finish"


def prepare_table_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    index = state["review_table_index"]
    table = state["docling_tables"][index]
    failures = list(state["review_validation_failures"][index])
    issues = [_issue_for_failure(item) for item in failures]
    return {
        "review_current_markup": raw_table_markup(table["columns"], table["rows"]),
        "review_current_verdict": "uncertain",
        "review_initial_verdict": "uncertain",
        "review_initial_issue_count": len(issues),
        "review_current_issues": issues,
        "review_current_failures": failures,
        "review_html_screenshot": "",
        "review_correction_attempts": 0,
        "review_correction_failed": False,
        "review_skip_current": any(
            failure.get("blocks_review", failure["severity"] == "error")
            for failure in failures
        ),
    }


def prepare_route(state: ProdBatchReviewState) -> Literal["render", "finalize"]:
    return "finalize" if state["review_skip_current"] else "render"


def render_html_candidate_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    table = state["docling_tables"][state["review_table_index"]]
    screenshot = Path(state["output_dir"]) / (
        f"{Path(state['pdf_path']).stem}_docling_table_{table['number']}_html_"
        f"{state['review_correction_attempts']}.png"
    )
    try:
        render_html_table_screenshot(state["review_current_markup"], screenshot)
    except Exception as error:
        failure = _failure(
            code="HTML_RENDER_FAILED",
            table=table["number"],
            page=table["page"],
            stage="render",
            error_type=type(error).__name__,
            severity="warning",
            explanation="The HTML screenshot could not be rendered; comparison continued without it.",
        )
        return {
            "review_html_screenshot": "",
            "review_current_failures": [*state["review_current_failures"], failure],
        }
    return {"review_html_screenshot": str(screenshot)}


def _validate_comparison(
    verdict: object, issues: object,
) -> tuple[ReviewVerdict, list[ReviewIssue]]:
    if verdict not in {"match", "mismatch", "uncertain"}:
        raise ValueError("Invalid comparison verdict")
    if not isinstance(issues, list) or any(not isinstance(issue, dict) for issue in issues):
        raise ValueError("Invalid comparison issues")
    if verdict == "match" and issues:
        raise ValueError("Match verdict cannot contain issues")
    if verdict == "mismatch" and not issues:
        raise ValueError("Mismatch verdict requires issues")
    return verdict, issues  # type: ignore[return-value]


def compare_html_candidate_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    table = state["docling_tables"][state["review_table_index"]]
    artifact = f"docling table {table['number']}"
    failures = list(state["review_current_failures"])
    issues: list[ReviewIssue] = []
    verdict: ReviewVerdict = "uncertain"
    if len(state["review_current_markup"]) > 20_000:
        failure = _failure(
            code="HTML_REVIEW_LIMIT",
            table=table["number"], page=table["page"], stage="compare",
            error_type="ReviewLimitError", severity="error",
            explanation="HTML table exceeds the 20,000-character review limit.",
        )
        failures.append(failure)
        issues.append(_issue_for_failure(failure))
    else:
        try:
            screenshot = state.get("review_html_screenshot")
            verdict, issues = _validate_comparison(*compare_html_table(
                artifact=artifact,
                table_html=state["review_current_markup"],
                pdf_images=images_for_pages(state["page_images"], [table["page"]]),
                html_screenshot=Path(screenshot) if screenshot else None,
                model=state["vision_model"],
            ))
            if verdict == "uncertain" and not issues:
                issues = [{
                    "artifact": artifact,
                    "page": table["page"],
                    "kind": "other",
                    "pdf_evidence": "",
                    "extracted_evidence": "",
                    "explanation": "Vision comparison could not verify this table.",
                }]
        except Exception as error:
            failure = _failure(
                code="VISION_COMPARE_FAILED",
                table=table["number"], page=table["page"], stage="compare",
                error_type=type(error).__name__, severity="error",
                explanation="Vision comparison failed; this table remains unverified.",
            )
            failures.append(failure)
            issues = [_issue_for_failure(failure)]
            verdict = "uncertain"

    update: ProdBatchReviewState = {
        "review_current_verdict": verdict,
        "review_current_issues": issues,
        "review_current_failures": failures,
    }
    if state["review_correction_attempts"] == 0:
        update["review_initial_verdict"] = verdict
        update["review_initial_issue_count"] = len(issues)
    return update


def comparison_route(state: ProdBatchReviewState) -> Literal["correct", "finalize"]:
    if (
        state["review_current_verdict"] == "mismatch"
        and state["review_correction_attempts"] < state["max_correction_attempts"]
    ):
        return "correct"
    return "finalize"


def correct_html_candidate_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    table = state["docling_tables"][state["review_table_index"]]
    attempts = state["review_correction_attempts"] + 1
    try:
        markup = correct_html_table(
            artifact=f"docling table {table['number']}",
            table_html=state["review_current_markup"],
            pdf_images=images_for_pages(state["page_images"], [table["page"]]),
            issues=state["review_current_issues"],
            model=state["vision_model"],
        )
        if "<table" not in markup.lower() or "</table>" not in markup.lower():
            raise ValueError("Corrected markup is not a complete table")
    except Exception as error:
        failure = _failure(
            code="HTML_CORRECTION_FAILED",
            table=table["number"], page=table["page"], stage="correct",
            error_type=type(error).__name__, severity="error",
            explanation="HTML correction failed; the original mismatch was preserved.",
        )
        return {
            "review_correction_attempts": attempts,
            "review_current_failures": [*state["review_current_failures"], failure],
            "review_current_issues": [
                *state["review_current_issues"], _issue_for_failure(failure),
            ],
            "review_correction_failed": True,
        }
    return {
        "review_current_markup": markup,
        "review_correction_attempts": attempts,
        "review_html_screenshot": "",
        "review_correction_failed": False,
    }


def correction_route(state: ProdBatchReviewState) -> Literal["render", "finalize"]:
    return "finalize" if state["review_correction_failed"] else "render"


def finalize_table_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    table = state["docling_tables"][state["review_table_index"]]
    failures = list(state["review_current_failures"])
    issues = list(state["review_current_issues"])
    if (
        state["review_current_verdict"] == "mismatch"
        and state["review_correction_attempts"] >= state["max_correction_attempts"]
        and not any(item["code"] == "CORRECTION_LIMIT_REACHED" for item in failures)
    ):
        failure = _failure(
            code="CORRECTION_LIMIT_REACHED",
            table=table["number"], page=table["page"], stage="correct",
            error_type="CorrectionLimitError", severity="error",
            explanation=(
                "Mismatch remains after "
                f"{state['review_correction_attempts']} correction attempt(s)."
            ),
        )
        failures.append(failure)
        issues.append(_issue_for_failure(failure))
    result: ReviewedTable = {
        "table": table,
        "markup": state["review_current_markup"],
        "verdict": state["review_current_verdict"],
        "initial_verdict": state["review_initial_verdict"],
        "initial_issue_count": state["review_initial_issue_count"],
        "issues": issues,
        "failures": failures,
        "correction_attempts": state["review_correction_attempts"],
    }
    return {
        "review_table_index": state["review_table_index"] + 1,
        "review_results": [*state["review_results"], result],
    }


_VERDICT_LABELS = {
    "match": "Verified",
    "mismatch": "Mismatch",
    "uncertain": "Human review required",
}


def _result_section(result: ReviewedTable) -> str:
    table = result["table"]
    verdict = result["verdict"]
    alerts = []
    for failure in result["failures"]:
        alert_class = "failure-error" if failure["severity"] == "error" else "failure-warning"
        alerts.append(
            f'<li class="{alert_class}"><strong>{html.escape(failure["code"])}</strong>: '
            f'{html.escape(failure["explanation"])}</li>'
        )
    for issue in result["issues"]:
        if not any(issue["explanation"] == failure["explanation"] for failure in result["failures"]):
            alerts.append(f'<li class="review-issue">{html.escape(issue["explanation"])}</li>')
    alert_html = (
        f'<ul class="review-alert" role="alert">{"".join(alerts)}</ul>' if alerts else ""
    )
    return (
        f'<section class="review-card verdict-{verdict}" data-verdict="{verdict}" '
        f'data-table="{table["number"]}">'
        f'<header><h2>Docling table {table["number"]} · PDF page {table["page"]}</h2>'
        f'<span class="review-badge">{_VERDICT_LABELS[verdict]}</span></header>'
        f'<p class="table-source">Nearest heading: <strong>'
        f'{html.escape(table.get("nearest_heading") or "none")}</strong></p>'
        f'{alert_html}<div class="table-wrap">{result["markup"]}</div></section>'
    )


def write_review_html(state: ProdBatchReviewState) -> str | None:
    results = state.get("review_results", [])
    if not results or not state.get("output_dir"):
        return None
    source = Path(state["pdf_path"])
    path = Path(state["output_dir"]) / f"{source.stem}_docling_tables_corrected.html"
    sections = "\n".join(_result_section(item) for item in results)
    css = f"""{RAW_TABLE_CSS}
.review-card{{border:4px solid #64748b;border-radius:10px;padding:16px;margin:24px 0;background:#fff}}
.review-card>header{{display:flex;align-items:center;justify-content:space-between;gap:16px}}
.review-card h2{{margin:0}}
.review-badge{{font-weight:700;border:2px solid currentColor;border-radius:999px;padding:4px 10px}}
.verdict-match{{border-color:#16803c}}.verdict-match .review-badge{{color:#116530}}
.verdict-mismatch{{border-color:#c62828;background:#fff7f7}}.verdict-mismatch .review-badge{{color:#9f1d20}}
.verdict-uncertain{{border-color:#b26a00;background:#fffaf0}}.verdict-uncertain .review-badge{{color:#8a5200}}
.review-alert{{margin:12px 0;padding:10px 12px 10px 30px;border-left:5px solid #b26a00;background:#fff}}
.failure-error{{color:#9f1d20}}.failure-warning{{color:#8a5200}}.review-issue{{color:#9f1d20}}
"""
    write_new(path, (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Production Docling review</title>"
        f"<style>{css}</style></head><body><main>"
        f"<h1>Production Docling review – {html.escape(source.name)}</h1>"
        f"{sections}</main></body></html>"
    ))
    return str(path)


def finish_review_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    results = state["review_results"]
    issues = [issue for result in results for issue in result["issues"]]
    failures = [failure for result in results for failure in result["failures"]]
    counts = {
        verdict: sum(result["verdict"] == verdict for result in results)
        for verdict in ("match", "mismatch", "uncertain")
    }
    review = {
        "table_count": len(state["docling_tables"]),
        "results": results,
        "verdicts": [
            {"table": result["table"]["number"], "page": result["table"]["page"],
             "verdict": result["verdict"]}
            for result in results
        ],
        "initial_results": [
            {"table": result["table"]["number"], "page": result["table"]["page"],
             "verdict": result["initial_verdict"],
             "issue_count": result["initial_issue_count"],
             "correction_attempts": result["correction_attempts"]}
            for result in results
        ],
        "counts": counts,
        "issues": issues,
        "failures": failures,
        "status": "passed" if results and all(
            result["verdict"] == "match"
            and not any(failure["severity"] == "error" for failure in result["failures"])
            for result in results
        ) else "needs_human_review",
    }
    update: ProdBatchReviewState = {"extractor_reviews": {"docling": review}}
    corrected = write_review_html(state)
    if corrected:
        update["corrected_docling_html"] = corrected
    return update


def decline_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    results: list[ReviewedTable] = []
    for table in state["docling_tables"]:
        failure = _failure(
            code="VISION_REVIEW_DECLINED", table=table["number"], page=table["page"],
            stage="compare", error_type="ReviewDeclined", severity="error",
            explanation="Reviewer declined the vision data transfer.",
        )
        results.append({
            "table": table,
            "markup": raw_table_markup(table["columns"], table["rows"]),
            "verdict": "uncertain",
            "initial_verdict": "uncertain",
            "initial_issue_count": 1,
            "issues": [_issue_for_failure(failure)],
            "failures": [failure],
            "correction_attempts": 0,
        })
    prepared = {**state, "review_results": results}
    return {"use_vision": False, **finish_review_node(prepared)}


def report_node(state: ProdBatchReviewState) -> ProdBatchReviewState:
    source = Path(state["pdf_path"])
    review = state["extractor_reviews"]["docling"]
    path = Path(state["output_dir"]) / f"{source.stem}_docling_errors.md"
    lines = [
        f"# Production Docling review: {source.name}", "",
        f"- Source SHA-256: `{state['source_sha256']}`",
        f"- Review status: {review['status']}",
        f"- Tables: {review['table_count']}",
        f"- Matches: {review['counts']['match']}",
        f"- Mismatches: {review['counts']['mismatch']}",
        f"- Unverified: {review['counts']['uncertain']}",
        f"- Failures and warnings: {len(review['failures'])}", "",
    ]
    for result in review["results"]:
        table = result["table"]
        lines.extend([
            f"## Table {table['number']} · PDF page {table['page']} · {result['verdict']}", "",
        ])
        for failure in result["failures"]:
            lines.append(
                f"- [{failure['severity']}] {failure['code']} ({failure['stage']}; "
                f"{failure['error_type']}): {failure['explanation']}"
            )
        for issue in result["issues"]:
            lines.append(f"- Issue ({issue['kind']}): {issue['explanation']}")
        lines.append("")
    if not review["issues"] and not review["failures"]:
        lines.extend(["No differences or processing failures were reported.", ""])
    write_new(path, "\n".join(lines))
    return {"error_reports": {"docling": str(path)}}


def build_graph(checkpointer=None):
    graph = StateGraph(ProdBatchReviewState)
    graph.add_node("docling_extract", docling_node)
    graph.add_node("validate_extraction", validate_extraction_node)
    graph.add_node("build_combined_html", html_node)
    graph.add_node("render_pdf_pages", render_pages_node)
    graph.add_node("validate_review_inputs", validate_review_inputs_node)
    graph.add_node("cycle_html_tables", cycle_html_tables_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("initialize_review", initialize_review_node)
    graph.add_node("prepare_table", prepare_table_node)
    graph.add_node("render_html_candidate", render_html_candidate_node)
    graph.add_node("compare_html_candidate", compare_html_candidate_node)
    graph.add_node("correct_html_candidate", correct_html_candidate_node)
    graph.add_node("finalize_table", finalize_table_node)
    graph.add_node("finish_review", finish_review_node)
    graph.add_node("vision_declined", decline_node)
    graph.add_node("write_extractor_reports", report_node)
    graph.add_edge(START, "docling_extract")
    graph.add_edge("docling_extract", "validate_extraction")
    graph.add_edge("validate_extraction", "build_combined_html")
    graph.add_edge("build_combined_html", "render_pdf_pages")
    graph.add_edge("render_pdf_pages", "validate_review_inputs")
    graph.add_edge("validate_review_inputs", "cycle_html_tables")
    graph.add_edge("cycle_html_tables", "human_review")
    graph.add_conditional_edges(
        "human_review", lambda state: "approved" if state["vision_approved"] else "declined",
        {"approved": "initialize_review", "declined": "vision_declined"},
    )
    graph.add_conditional_edges(
        "initialize_review", review_work_route,
        {"prepare": "prepare_table", "finish": "finish_review"},
    )
    graph.add_conditional_edges(
        "prepare_table", prepare_route,
        {"render": "render_html_candidate", "finalize": "finalize_table"},
    )
    graph.add_edge("render_html_candidate", "compare_html_candidate")
    graph.add_conditional_edges(
        "compare_html_candidate", comparison_route,
        {"correct": "correct_html_candidate", "finalize": "finalize_table"},
    )
    graph.add_conditional_edges(
        "correct_html_candidate", correction_route,
        {"render": "render_html_candidate", "finalize": "finalize_table"},
    )
    graph.add_conditional_edges(
        "finalize_table", review_work_route,
        {"prepare": "prepare_table", "finish": "finish_review"},
    )
    graph.add_edge("finish_review", "write_extractor_reports")
    graph.add_edge("vision_declined", "write_extractor_reports")
    graph.add_edge("write_extractor_reports", END)
    return graph.compile(checkpointer=checkpointer)


def run_pdf(
    pdf_path: Path, output_dir: Path, *, vision_model: str = "gpt-4o",
    use_vision: bool = True, max_correction_attempts: int = 1,
) -> ProdBatchReviewState:
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Output directory is not empty: {output_dir}")
    if max_correction_attempts < 0:
        raise ValueError("max_correction_attempts cannot be negative")
    output_dir.mkdir(parents=True, exist_ok=True)
    initial: ProdBatchReviewState = {
        "pdf_path": str(pdf_path.resolve()),
        "output_dir": str(output_dir.resolve()),
        "vision_model": vision_model,
        "use_vision": use_vision,
        "iteration": 1,
        "max_iterations": 1,
        "max_correction_attempts": max_correction_attempts,
    }
    from langgraph.checkpoint.sqlite import SqliteSaver
    with SqliteSaver.from_conn_string(str(output_dir / "checkpoint.sqlite")) as saver:
        graph = build_graph(checkpointer=saver)
        config = {"configurable": {"thread_id": output_dir.name}}
        return graph.invoke(initial, config=config)


def resume_pdf(output_dir: Path, *, approve: bool) -> ProdBatchReviewState:
    output_dir = output_dir.expanduser().resolve()
    checkpoint = output_dir / "checkpoint.sqlite"
    if not checkpoint.is_file():
        raise FileNotFoundError(f"No saved review checkpoint: {checkpoint}")
    from langgraph.checkpoint.sqlite import SqliteSaver
    with SqliteSaver.from_conn_string(str(checkpoint)) as saver:
        graph = build_graph(checkpointer=saver)
        config = {"configurable": {"thread_id": output_dir.name}}
        snapshot = graph.get_state(config)
        if not any(task.interrupts for task in snapshot.tasks):
            raise ValueError(f"No pending human review in {output_dir}")
        return graph.invoke(Command(resume=approve), config=config)


def run_batch(
    input_dir: Path, run_dir: Path, *, pdf_name: str | None = None,
    vision_model: str = "gpt-4o", use_vision: bool = True,
    limit: int | None = None, max_correction_attempts: int = 1,
) -> dict[str, Any]:
    input_dir = input_dir.expanduser().resolve()
    run_dir = run_dir.expanduser().resolve()
    if not input_dir.is_dir():
        raise NotADirectoryError(input_dir)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"Run directory is not empty: {run_dir}")
    if pdf_name is not None:
        if Path(pdf_name).name != pdf_name or not pdf_name.lower().endswith(".pdf"):
            raise ValueError("--pdf must be a filename in the input directory")
        pdfs = [input_dir / pdf_name]
    else:
        pdfs = sorted(input_dir.glob("*.pdf"))
    if limit is not None:
        if limit < 1:
            raise ValueError("--limit must be positive")
        pdfs = pdfs[:limit]
    if not pdfs or any(not pdf.is_file() for pdf in pdfs):
        raise FileNotFoundError("No matching top-level PDF files were found")
    run_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for pdf_path in pdfs:
        output_dir = run_dir / pdf_path.stem
        try:
            state = run_pdf(
                pdf_path, output_dir, vision_model=vision_model,
                use_vision=use_vision,
                max_correction_attempts=max_correction_attempts,
            )
            if "__interrupt__" in state:
                item = {
                    "pdf": pdf_path.name,
                    "status": "awaiting_human_approval",
                    "output_dir": str(output_dir),
                    "docling_html": state["docling_html"],
                    "page_images": state["page_images"],
                }
            else:
                review_status = state["extractor_reviews"]["docling"]["status"]
                item = {
                    "pdf": pdf_path.name,
                    "status": "vision_declined" if state.get("vision_approved") is False
                    else review_status,
                    "docling_tables": len(state["docling_tables"]),
                    "output_dir": str(output_dir),
                    "error_reports": state["error_reports"],
                }
        except Exception as error:
            output_dir.mkdir(parents=True, exist_ok=True)
            failure_path = output_dir / f"{pdf_path.stem}_processing_errors.md"
            write_new(failure_path, (
                f"# Processing failed: {pdf_path.name}\n\n"
                f"Exception type: {type(error).__name__}\n\n"
                "No visual verification was completed for this PDF.\n"
            ))
            item = {
                "pdf": pdf_path.name,
                "status": "processing_error",
                "output_dir": str(output_dir),
                "error_report": str(failure_path),
            }
        results.append(item)
        print(json.dumps(item, ensure_ascii=False), flush=True)
    summary = {
        "input_dir": str(input_dir),
        "run_dir": str(run_dir),
        "vision_model": vision_model if use_vision else None,
        "pdf_count": len(pdfs),
        "results": results,
    }
    write_new(run_dir / "batch_summary.json", json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=PDF_DIR)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--pdf")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--vision-model", default="gpt-4o")
    parser.add_argument("--max-correction-attempts", type=int, default=1)
    parser.add_argument("--resume", type=Path)
    decision = parser.add_mutually_exclusive_group()
    decision.add_argument("--approve", action="store_true")
    decision.add_argument("--reject", action="store_true")
    args = parser.parse_args()
    if args.resume:
        if not (args.approve or args.reject):
            parser.error("--resume requires --approve or --reject")
        state = resume_pdf(args.resume, approve=args.approve)
        print(json.dumps({
            "pdf": Path(state["pdf_path"]).name,
            "status": state["extractor_reviews"]["docling"]["status"],
            "error_reports": state["error_reports"],
        }, indent=2), flush=True)
        return
    if args.approve or args.reject:
        parser.error("--approve and --reject require --resume")
    run_dir = args.output_dir or (
        BATCH_RUNS_DIR /
        f"prod-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    )
    summary = run_batch(
        args.input_dir, run_dir, pdf_name=args.pdf,
        vision_model=args.vision_model, use_vision=True,
        limit=args.limit, max_correction_attempts=args.max_correction_attempts,
    )
    print(json.dumps({
        "summary": str(run_dir / "batch_summary.json"),
        "pdf_count": summary["pdf_count"],
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
