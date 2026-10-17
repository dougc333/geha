"""Text linked to a table in its source document: the paragraph before it and the notes after it.

The pgvector store keeps only table cells, so qualifiers that sit next to a table (footnotes such
as "**Does not apply in the setting of Prostate or Breast Cancer", "Preferred product requirements
apply to new starts only", the authorization period) never reach the model. This module finds the
same table in the verified docling Markdown under crawl_dir and returns its neighbouring text, for
the "table-aware + attached notes" context strategy.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
VERIFIED = REPO / "crawl_dir" / "verified" / "coverage-policies"
TOKEN_RE = re.compile(r"[a-z0-9]+")
MAX_CHARS = 1500


def _tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(text.casefold()) if len(t) > 2}


@lru_cache(maxsize=None)
def _blocks(source: str) -> list[dict[str, Any]]:
    """The document as a list of {kind: table|text|heading, lines, start}."""
    stem = Path(source).stem
    path = VERIFIED / stem / f"{stem}.docling.md"
    if not path.is_file():
        return []
    blocks: list[dict[str, Any]] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("<!--"):
            if blocks and blocks[-1]["kind"] == "text":
                blocks[-1]["closed"] = True
            continue
        kind = "table" if line.startswith("|") else "heading" if line.startswith("#") else "text"
        last = blocks[-1] if blocks else None
        if last and last["kind"] == kind and kind == "table":
            last["lines"].append(line)
        elif last and kind == "text" and last["kind"] == "text" and not last.get("closed") \
                and not line.lstrip().startswith("-"):
            last["lines"].append(line)
        else:
            blocks.append({"kind": kind, "lines": [line], "start": number})
    return blocks


def _match_table(blocks: list[dict[str, Any]], table_text: str) -> int | None:
    wanted = _tokens(table_text)
    best, best_score = None, 0.0
    for index, block in enumerate(blocks):
        if block["kind"] != "table":
            continue
        found = _tokens(" ".join(block["lines"]))
        score = len(wanted & found) / max(len(wanted), 1)
        if score > best_score:
            best, best_score = index, score
    return best if best_score >= 0.5 else None


def attached_notes(source: str, table_text: str) -> dict[str, str]:
    """{'before': paragraph above the table, 'after': notes below it} for one DB table."""
    blocks = _blocks(source)
    index = _match_table(blocks, table_text)
    if index is None:
        return {"before": "", "after": ""}
    before = ""
    for block in reversed(blocks[:index]):
        if block["kind"] == "heading":
            break
        if block["kind"] == "text":
            before = " ".join(line.strip() for line in block["lines"])
            break
    after: list[str] = []
    for block in blocks[index + 1:]:
        if block["kind"] in ("heading", "table"):
            break
        after.extend(line.strip() for line in block["lines"])
    after_text = "\n".join(after)
    return {"before": before[:MAX_CHARS], "after": after_text[:MAX_CHARS]}


def with_notes(table: dict[str, Any]) -> str:
    """A parent table's CSV with its linked notes, labelled so the model can cite them."""
    notes = attached_notes(str(table["source"]), str(table["full_csv"]))
    parts = []
    if notes["before"]:
        parts.append(f"TEXT BEFORE TABLE:\n{notes['before']}")
    parts.append(str(table["full_csv"]))
    if notes["after"]:
        parts.append(f"NOTES AFTER TABLE:\n{notes['after']}")
    return "\n".join(parts)
