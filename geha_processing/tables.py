"""Shared table-header detection and conservative repair rules."""

from __future__ import annotations

import re
from typing import Any


KNOWN_COLUMN_HEADERS = {
    "preference",
    "requirespriorauth",
    "drugname",
    "servicetype",
    "serviceorcategory",
    "procedurecode",
    "code",
    "hcpcscode",
    "cpthcpcscode",
    "cpthcpcscodes",
    "description",
    "date",
    "update",
    "updates",
    "ndc",
    "ndccode",
    "productname",
    "brandname",
    "genericname",
}


def normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).casefold())


def table_headers_are_default(columns: list[Any]) -> bool:
    """Detect pandas/Docling placeholders while allowing real year headers."""
    labels = [str(column).strip() for column in columns]
    if not labels:
        return False
    indexes: list[int] = []
    for label in labels:
        match = re.fullmatch(r"(?:Unnamed:\s*)?(\d+)", label, flags=re.IGNORECASE)
        if match is None:
            return False
        indexes.append(int(match.group(1)))
    return indexes in (
        list(range(len(indexes))),
        list(range(1, len(indexes) + 1)),
    )


def promote_embedded_header(frame: Any) -> tuple[Any, bool]:
    """Promote a recognizable first row when the parser emits 0, 1, 2."""
    column_count = frame.shape[1]
    if frame.shape[0] < 2 or column_count < 2:
        return frame, False
    if not table_headers_are_default(list(frame.columns)):
        return frame, False
    candidate = [str(value).strip() for value in frame.iloc[0].fillna("")]
    keys = [normalized(value) for value in candidate]
    if not all(candidate) or len(set(keys)) != column_count:
        return frame, False
    recognized = sum(key in KNOWN_COLUMN_HEADERS for key in keys)
    if recognized < max(2, (column_count + 1) // 2):
        return frame, False
    repaired = frame.iloc[1:].copy().reset_index(drop=True)
    repaired.columns = candidate
    return repaired, True


def inherit_continuation_header(
    frame: Any,
    previous_frame: Any | None,
    *,
    heading: str,
    previous_heading: str | None,
    page_number: int | None,
    previous_page: int | None,
) -> tuple[Any, bool]:
    """Carry a prior table schema to a confidently matched next-page fragment."""
    if previous_frame is None or previous_frame.empty or frame.shape[1] == 0:
        return frame, False
    if (
        not isinstance(page_number, int)
        or not isinstance(previous_page, int)
        or page_number != previous_page + 1
        or not heading
        or normalized(heading) in {"table", "extractedtable"}
        or normalized(heading) != normalized(previous_heading)
        or frame.shape[1] != previous_frame.shape[1]
    ):
        return frame, False
    prior_labels = [str(column).strip() for column in previous_frame.columns]
    prior_keys = [normalized(label) for label in prior_labels]
    if (
        not all(prior_labels)
        or len(set(prior_keys)) != len(prior_keys)
        or sum(key in KNOWN_COLUMN_HEADERS for key in prior_keys) < 2
    ):
        return frame, False
    current_labels = [str(column).strip() for column in frame.columns]
    if table_headers_are_default(current_labels):
        if frame.empty:
            return frame, False
        first_row_keys = [normalized(value) for value in frame.iloc[0].fillna("")]
        if sum(key in KNOWN_COLUMN_HEADERS for key in first_row_keys) >= 2:
            return frame, False
        inherited = frame.copy()
        inherited.columns = previous_frame.columns.copy()
        return inherited, True
    code_positions = [
        index
        for index, key in enumerate(prior_keys)
        if key in {"hcpcscode", "cpthcpcscode", "cpthcpcscodes", "procedurecode", "code"}
    ]
    if not code_positions or not all(current_labels):
        return frame, False
    if sum(normalized(label) in KNOWN_COLUMN_HEADERS for label in current_labels) >= 2:
        return frame, False
    if not any(
        re.fullmatch(r"(?:[A-Z]\d{4}|\d{5}|[A-Z]\d{4,5})", current_labels[index], re.IGNORECASE)
        for index in code_positions
    ):
        return frame, False
    restored_rows = [current_labels, *frame.itertuples(index=False, name=None)]
    inherited = frame.__class__(restored_rows, columns=prior_labels)
    return inherited, True


def choose_replacement_headers(
    headers: list[Any],
    *,
    previous_headers: list[str] | None,
    page: int | None,
    previous_page: int | None,
    allow_two_column_schema: bool = True,
) -> tuple[list[str] | None, str | None]:
    """Choose a conservative replacement for default structured-table headers."""
    if not table_headers_are_default(headers):
        return [str(value) for value in headers], None
    if (
        previous_headers is not None
        and len(previous_headers) == len(headers)
        and page is not None
        and previous_page is not None
        and page == previous_page + 1
        and not table_headers_are_default(previous_headers)
    ):
        return list(previous_headers), "inherited_previous_page"
    if allow_two_column_schema and len(headers) == 2:
        return ["Field", "Details"], "two_column_key_value_schema"
    return None, None
