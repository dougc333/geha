"""Remove member PII before data is sent to observability systems."""

from __future__ import annotations

import re
from typing import Any


SENSITIVE_KEYS = {
    "address",
    "date_of_birth",
    "dob",
    "email",
    "first_name",
    "last_name",
    "member_id",
    "member_ref",
    "name",
    "phone",
    "postal_code",
    "ssn",
}

PATTERNS = (
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "[EMAIL]"),
    (re.compile(r"(?<!\d)(?:\+?1[-. (]*)?\d{3}[-. )]*\d{3}[-. ]*\d{4}(?!\d)"), "[PHONE]"),
)


def redact_text(value: str) -> str:
    redacted = value
    for pattern, replacement in PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def sanitize(value: Any, key: str | None = None) -> Any:
    if key and key.lower() in SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        return {name: sanitize(item, name) for name, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize(item) for item in value)
    return value

