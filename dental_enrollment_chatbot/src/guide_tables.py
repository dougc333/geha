"""Parse the 2026 GEHA dental benefits guide tables used by the enrollment POC."""

from __future__ import annotations

import re
from pathlib import Path


DEFAULT_GUIDE_DIR = Path(
    "/Users/dc/geha/downloads/dental/fedvip/2026-geha-dental-benefits-guide_pages"
)


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


class GuideTables:
    """Authoritative local rate-code and premium lookups from guide pages 10-11."""

    def __init__(self, guide_dir: Path = DEFAULT_GUIDE_DIR):
        self.guide_dir = Path(guide_dir)
        self.rate_rows = self._load_rate_rows()
        self.premiums = self._load_premiums()

    def _load_rate_rows(self) -> list[tuple[str, str, str]]:
        rows = _rows(self.guide_dir / "page-010.md")
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
        lines = (self.guide_dir / "page-011.md").read_text(encoding="utf-8").splitlines()
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
