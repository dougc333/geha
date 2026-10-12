"""Persona fixtures, typing frames, and deterministic policy-answer scoring."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from policy_qa import PolicyChunk


def load_personas(path: str | Path) -> list[dict[str, Any]]:
    personas = json.loads(Path(path).read_text())
    required = {"id", "name", "description", "query", "required_facts"}
    for persona in personas:
        missing = required - set(persona)
        if missing:
            raise ValueError(f"Persona {persona.get('id', '<unknown>')} is missing {sorted(missing)}")
        if not any(key in persona for key in ("expected_page", "expected_pages", "expected_page_groups")):
            raise ValueError(
                f"Persona {persona['id']} requires expected_page, expected_pages, or expected_page_groups"
            )
    return personas


def typing_frames(text: str, stride: int = 1) -> Iterable[str]:
    """Yield incremental text with a visible caret for Streamlit animation."""
    if stride < 1:
        raise ValueError("stride must be at least 1")
    for end in range(stride, len(text) + stride, stride):
        yield text[: min(end, len(text))] + ("▌" if end < len(text) else "")


def _normalize(text: str) -> str:
    text = text.lower().replace("–", "-").replace(",", "")
    text = re.sub(
        r"(\d+)\s*%\s*(?:-|to)\s*(\d+)\s*%",
        r"\1 to \2 percent",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def evaluate_persona_result(
    persona: dict[str, Any],
    answer: str,
    chunks: list[PolicyChunk],
) -> dict[str, Any]:
    normalized = _normalize(answer)
    missing_facts = [
        alternatives
        for alternatives in persona["required_facts"]
        if not any(_normalize(alternative) in normalized for alternative in alternatives)
    ]
    if "expected_page_groups" in persona:
        expected_page_groups = [
            [int(page) for page in group] for group in persona["expected_page_groups"]
        ]
    else:
        expected_pages = [
            int(page)
            for page in persona.get("expected_pages", [persona.get("expected_page")])
        ]
        expected_page_groups = [[page] for page in expected_pages]
    retrieved_pages = {chunk.page for chunk in chunks}
    missing_page_groups = [
        group for group in expected_page_groups if not retrieved_pages.intersection(group)
    ]
    missing_citation_groups = [
        [f"[p. {page}]" for page in group]
        for group in expected_page_groups
        if not any(f"[p. {page}]" in answer.lower() for page in group)
    ]
    return {
        "passed": not missing_page_groups and not missing_citation_groups and not missing_facts,
        "expected_page_groups": expected_page_groups,
        "retrieved_pages": [chunk.page for chunk in chunks],
        "missing_page_groups": missing_page_groups,
        "missing_citation_groups": missing_citation_groups,
        "citation_present": not missing_citation_groups,
        "missing_facts": missing_facts,
    }
