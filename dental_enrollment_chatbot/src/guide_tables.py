"""Parse the 2026 GEHA dental benefits guide tables used by the enrollment POC."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
from crawl_dir.src.consumer_paths import page_root

DEFAULT_GUIDE_DIR = page_root(
    "dental", "fedvip/2026-geha-dental-benefits-guide.pdf", allow_candidate=True
)


def _page_markdown(guide_dir: Path, page: int) -> Path:
    nested = guide_dir / f"page-{page:03d}" / "page.md"
    return nested if nested.is_file() else guide_dir / f"page-{page:03d}.md"


def _canonical_page_tables(guide_dir: Path, page: int) -> list[dict]:
    if not (guide_dir / "page-001").is_dir():
        return []
    artifact_root = guide_dir.parent
    table_dir = (
        artifact_root / "tables"
        if (artifact_root / "tables").is_dir()
        else artifact_root / "candidate" / "tables"
    )
    return [
        table
        for path in sorted(table_dir.glob("table-*.json"))
        if page in (table := json.loads(path.read_text(encoding="utf-8"))).get("source_pages", [])
    ]


def _rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or re.match(r"^\|\s*-", line):
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows


def _prefix_matches(spec: str, prefix: int) -> bool:
    for token in (part.strip() for part in spec.split(",")):
        if re.fullmatch(r"\d{3}", token) and prefix == int(token):
            return True
        if match := re.fullmatch(r"(\d{3})-(\d{3})", token):
            if int(match.group(1)) <= prefix <= int(match.group(2)):
                return True
    return False


def _split_merged_rate_row(state: str, spec: str, code: str) -> list[tuple[str, str, str]]:
    """Recover two PDF table rows that the extractor merged into one set of cells.

    The source table occasionally yields cells such as ``MO MO``, ``Rest of 726``
    and ``2 1``. The visual order in the source is still recoverable: the ZIP
    prefix appears before or after the ``Rest of state`` entry in the same order
    as the two states and rate codes.
    """
    states = re.findall(r"\b(?:[A-Z]{2}|INTL)\b", state)
    codes = re.findall(r"\b[1-5]\b", code)
    prefix = re.search(r"\b\d{3}(?:-\d{3})?\b", spec)
    rest = re.search(r"\brest\s+of(?:\s+state)?\b", spec, flags=re.I)
    if len(states) != 2 or len(codes) != 2 or not prefix or not rest:
        return []
    specs = (
        ["Rest of state", prefix.group(0)]
        if rest.start() < prefix.start()
        else [prefix.group(0), "Rest of state"]
    )
    return list(zip(states, specs, codes))


class GuideTables:
    """Authoritative local rate-code and premium lookups from guide pages 10-11."""

    def __init__(self, guide_dir: Path = DEFAULT_GUIDE_DIR):
        self.guide_dir = Path(guide_dir)
        self.rate_rows = self._load_rate_rows()
        self.premiums = self._load_premiums()

    def _load_rate_rows(self) -> list[tuple[str, str, str]]:
        canonical = _canonical_page_tables(self.guide_dir, 10)
        if canonical:
            output: list[tuple[str, str, str]] = []
            table = canonical[0]
            for suffix in ("", ".1", ".2"):
                current_state = ""
                current_code = ""
                pending_specs: list[str] = []
                for row in table.get("rows") or []:
                    state = str(row.get(f"State{suffix}", "")).strip().upper()
                    spec = str(row.get(f"First 3 digits of ZIP code{suffix}", "")).strip()
                    code = str(row.get(f"Rate code{suffix}", "")).strip()
                    if code.endswith(".0"):
                        code = code[:-2]
                    if merged := _split_merged_rate_row(state, spec, code):
                        output.extend((row_state, row_spec, row_code) for row_state, row_spec, row_code in merged)
                        current_state, _, current_code = merged[-1]
                    elif state and code.isdigit():
                        output.extend((state, pending, code) for pending in pending_specs)
                        pending_specs.clear()
                        output.append((state, spec, code))
                        current_state, current_code = state, code
                    elif spec and current_state and current_code:
                        output.append((current_state, spec, current_code))
                    elif spec:
                        pending_specs.append(spec)
                    if spec.casefold() in {"rest of state", "entire state", "entire area"}:
                        current_state = current_code = ""
            return output
        rows = _rows(_page_markdown(self.guide_dir, 10))
        output: list[tuple[str, str, str]] = []
        for row in rows[1:]:
            for offset in (0, 3, 6):
                if len(row) >= offset + 3 and row[offset] and row[offset + 2].isdigit():
                    output.append((row[offset].upper(), row[offset + 1], row[offset + 2]))
        return output

    def rate_code(self, state: str, zip_code: str) -> str:
        state = state.strip().upper()
        if not re.fullmatch(r"[A-Z]{2}", state):
            raise ValueError("Enter a two-letter state or territory abbreviation.")
        if not re.fullmatch(r"\d{5}(?:-\d{4})?", zip_code.strip()):
            raise ValueError("Enter a five-digit ZIP code.")
        prefix = int(zip_code[:3])
        entries = [(spec, code) for row_state, spec, code in self.rate_rows if row_state == state]
        if not entries:
            raise ValueError("That state or territory is not in the 2026 rate-code table.")
        for spec, code in entries:
            if _prefix_matches(spec, prefix):
                return code
        for spec, code in entries:
            if spec.lower() in {"entire state", "entire area", "rest of state"}:
                return code
        raise ValueError("That ZIP prefix is not listed for the selected state.")

    def _load_premiums(self) -> dict[tuple[str, str, str, str], str]:
        canonical = _canonical_page_tables(self.guide_dir, 11)
        if canonical:
            premiums: dict[tuple[str, str, str, str], str] = {}
            for table in canonical:
                headers = [str(value) for value in table.get("headers") or []]
                if not headers:
                    continue
                first = headers[0]
                status = "Employed" if "employed" in first.casefold() else "Retired"
                rows = table.get("rows") or []
                marker = " ".join(str(row.get(first, "")) for row in rows).upper()
                source_numbers = table.get("source_table_numbers") or []
                plan = (
                    "High"
                    if "HIGH" in marker or (source_numbers and int(source_numbers[0]) >= 7)
                    else "Standard"
                )
                for row in rows:
                    enrollment = re.sub(
                        r"^(?:HIGH|STANDARD)\s+", "", str(row.get(first, "")), flags=re.I
                    ).strip()
                    if enrollment not in {"Self Only", "Self Plus One", "Self and Family"}:
                        continue
                    for rate_code in range(1, 6):
                        value = str(row.get(f"Rate code {rate_code}", "")).strip()
                        if value:
                            premiums[(plan, status, enrollment, str(rate_code))] = value
            return premiums
        lines = _page_markdown(self.guide_dir, 11).read_text(encoding="utf-8").splitlines()
        premiums: dict[tuple[str, str, str, str], str] = {}
        current: tuple[str, str] | None = None
        for line in lines:
            if match := re.match(r"\| (Standard|High) - (Employed|Retired) (?:biweekly|monthly) \|", line):
                current = (match.group(1), match.group(2))
                continue
            if not current or not line.startswith("|") or re.match(r"^\|\s*-", line):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells[0] not in {"Self Only", "Self Plus One", "Self and Family"} or len(cells) < 6:
                continue
            for index, value in enumerate(cells[1:6], 1):
                premiums[(current[0], current[1], cells[0], str(index))] = value
        return premiums

    def premium(self, plan: str, status: str, enrollment: str, rate_code: str) -> str:
        key = (plan.title(), status.title(), enrollment, str(rate_code))
        try:
            return self.premiums[key]
        except KeyError as error:
            raise ValueError(f"No 2026 premium found for {key}.") from error

    @staticmethod
    def period(status: str) -> str:
        return "biweekly" if status.lower() == "employed" else "monthly"
