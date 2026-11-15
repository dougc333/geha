"""Minimal client for the Unstructured managed Partition API."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import requests

DEFAULT_API_URL = "https://api.unstructured.io/general/v0/general"


class ExtractionError(RuntimeError):
    """Raised when the extraction service returns an invalid response."""


def extract_document(
    document: str | Path,
    *,
    api_key: str,
    api_url: str = DEFAULT_API_URL,
    strategy: str = "hi_res",
    infer_table_structure: bool = True,
    include_page_breaks: bool = True,
    timeout_seconds: int = 300,
    session: requests.Session | None = None,
) -> list[dict[str, Any]]:
    """Upload one document and return Unstructured element dictionaries."""

    path = Path(document).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Document does not exist: {path}")
    if not api_key.strip():
        raise ValueError("UNSTRUCTURED_API_KEY is empty")

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    headers = {
        "accept": "application/json",
        "unstructured-api-key": api_key,
    }
    form = {
        "strategy": strategy,
        "infer_table_structure": str(infer_table_structure).lower(),
        "include_page_breaks": str(include_page_breaks).lower(),
        "unique_element_ids": "true",
    }

    http = session or requests.Session()
    with path.open("rb") as stream:
        response = http.post(
            api_url,
            headers=headers,
            files={"files": (path.name, stream, content_type)},
            data=form,
            timeout=(15, timeout_seconds),
        )

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text[:1000].strip()
        raise ExtractionError(
            f"Unstructured API returned HTTP {response.status_code}: {detail}"
        ) from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise ExtractionError("Unstructured API returned non-JSON output") from exc

    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ExtractionError("Expected a JSON list of document elements")
    return payload

