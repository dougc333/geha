"""FEHB medical tables parsed from GEHA's 2026 PDFs: premiums and the SBC benefit grids.

- Premiums and enrollment codes: the 2026 FEHB medical benefits guide prints, for each plan
  option, "Self Only CODE 251 Elevate Plus $205.13 $444.45" (federal employees biweekly,
  retired monthly). FEHB premiums are national, so there is no ZIP or rate code.
- Benefits: each plan option's Summary of Benefits and Coverage (SBC) uses the same federal
  form. Its grid is read by position: the drawn row rules give the rows, and the column
  rules give service / network / out-of-network / limitations.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


FEHB_DIR = Path(os.environ.get("FEHB_DIR", "/Users/dc/geha/downloads/medical/fehb"))
GUIDE = FEHB_DIR / "2026-geha-fehb-medical-benefits-guide.pdf"
SBC_FILES = {
    "Elevate": "2026-geha-fehb-elevate-summary-of-benefits-and-coverage.pdf",
    "Elevate Plus": "2026-geha-fehb-elevate-plus-summary-of-benefits-and-coverage.pdf",
    "HDHP": "2026-geha-fehb-hdhp-summary-of-benefits-and-coverage.pdf",
    "Standard": "2026-geha-fehb-standard-option-summary-of-benefits-and-coverage.pdf",
    "High": "2026-geha-fehb-high-option-summary-of-benefits-and-coverage.pdf",
}
PLANS = tuple(SBC_FILES)
ENROLLMENT = ("Self Only", "Self Plus One", "Self and Family")
PREMIUM = re.compile(r"(Self Only|Self Plus One|Self and Family) CODE (\w+) (.+?) \$([\d,]+\.\d\d) \$([\d,]+\.\d\d)")


@dataclass(frozen=True)
class Premium:
    plan: str
    enrollment: str
    code: str
    employed_biweekly: float
    retired_monthly: float


@dataclass(frozen=True)
class SbcRow:
    plan: str
    page: int
    event: str          # "If you visit a healthcare provider's office or clinic"
    service: str        # "Specialist visit"
    network: str        # "$50* / visit"
    out_of_network: str
    limits: str


def parse_premiums(pdf: Path = GUIDE) -> dict[tuple[str, str], Premium]:
    out = {}
    import pymupdf  # only needed to parse the PDFs, not to load tables from JSON

    with pymupdf.open(pdf) as doc:
        for page in doc:
            for m in PREMIUM.finditer(" ".join(page.get_text().split())):
                enrollment, code, plan, emp, ret = m.groups()
                out[(plan, enrollment)] = Premium(plan, enrollment, code, float(emp.replace(",", "")),
                                                  float(ret.replace(",", "")))
    return out


def _rules(page) -> list[tuple[float, float, float]]:
    """Horizontal rules (y, x0, x1) wider than a glossary underline."""
    out = []
    for drawing in page.get_drawings():
        for item in drawing["items"]:
            if item[0] == "re" and item[1].height < 2 and item[1].width > 50:
                out.append((round(item[1].y0), round(item[1].x0), round(item[1].x1)))
            elif item[0] == "l" and abs(item[1].y - item[2].y) < 1 and abs(item[1].x - item[2].x) > 50:
                out.append((round(item[1].y), round(min(item[1].x, item[2].x)), round(max(item[1].x, item[2].x))))
    return out


def _text(words: list, x0: float, x1: float, y0: float, y1: float) -> str:
    inside = [w for w in words if x0 - 2 <= w[0] < x1 - 2 and y0 - 2 <= w[1] < y1 - 2]
    inside.sort(key=lambda w: (round(w[1] / 3), w[0]))
    return " ".join(w[4] for w in inside).replace(" / ", " / ").strip()


def parse_sbc_grid(plan: str, pdf: Path) -> list[SbcRow]:
    rows: list[SbcRow] = []
    import pymupdf  # only needed to parse the PDFs, not to load tables from JSON

    with pymupdf.open(pdf) as doc:
        for number in range(2, doc.page_count + 1):
            page = doc[number - 1]
            if "Services You May Need" not in page.get_text():
                continue
            rules = _rules(page)
            words = page.get_text("words")
            billed = [w for w in words if w[4] == "billed)"]               # last line of the column headings
            if not billed:
                continue
            header = min(w[3] for w in billed)
            heads = {w[4]: w[0] for w in words if w[3] <= header + 2}
            # cell borders repeat on many rows; heading underlines and links do not
            seen: dict[int, set] = {}
            for y, x0, x1 in rules:
                seen.setdefault(x0, set()).add(y)
            starts = sorted(x for x, ys in seen.items() if len(ys) >= 3)
            snap = lambda x: max((s for s in starts if s <= x + 2), default=x)
            try:
                event_x = min(starts)
                service_x, network_x = snap(heads["Services"]), snap(heads["Network"])
                oon_x, limits_x = snap(heads["Out-of-Network"]), snap(heads["Limitations,"])
            except KeyError:
                continue
            right = max(x1 for _, _, x1 in rules)
            footer = [r.y0 for r in page.search_for("For more information about limitations") if r.y0 > header]
            bottom = min(footer) if footer else max(w[3] for w in words) + 4
            # Row rules: across the service column, or across the event column (where an event
            # ends, the service rule is not drawn separately). The first rule under the headings opens row one.
            below = sorted(y for y, _, _ in rules if header - 3 <= y < bottom)
            edges = {y for y, x0, x1 in rules if header - 3 <= y < bottom
                     and ((x0 <= service_x + 2 and x1 >= service_x + 60) or abs(x0 - event_x) <= 2)}
            edges = sorted(edges | set(below[:1])) + [bottom]
            event = rows[-1].event if rows else ""
            for top, low in zip(edges, edges[1:]):
                service = _text(words, service_x, network_x, top, low)
                if not service:
                    continue
                event = _text(words, event_x, service_x, top, low) or event
                network = _text(words, network_x, oon_x, top, low)
                oon, limits = _text(words, oon_x, limits_x, top, low), _text(words, limits_x, right, top, low)
                # a wrapped line of the row above: no in-network value, or a "(x-ray, blood work)" tail
                if rows and rows[-1].page == number and (not network or service.startswith("(")):
                    last = rows.pop()
                    join = lambda a, b: f"{a} {b}".strip()
                    rows.append(SbcRow(plan, number, last.event, join(last.service, service), join(last.network, network),
                                       join(last.out_of_network, oon), join(last.limits, limits)))
                    continue
                rows.append(SbcRow(plan, number, event, service, network, oon, limits))
    return rows


def parse_important_questions(pdf: Path) -> dict[str, str]:
    """Page 1: deductible, out-of-pocket limit and the other "Important Questions"."""
    import pymupdf  # only needed to parse the PDFs, not to load tables from JSON

    with pymupdf.open(pdf) as doc:
        text = " ".join(doc[0].get_text().split())
    out = {}
    for key, pattern in {
        "deductible": r"What is the overall deductible\? (.+?) Generally, you must pay",
        "out_of_pocket_limit": r"What is the out-of-pocket limit for this plan\? (.+?) The out-of-pocket limit",
        "specialist_referral": r"Do you need a referral to see a specialist\? (.+?) You ",
    }.items():
        if m := re.search(pattern, text):
            out[key] = m.group(1).replace("$ ", "$").strip()
    return out


class MedicalTables:
    def __init__(self, guide: Path = GUIDE, folder: Path = FEHB_DIR, data: dict | None = None):
        """Parse the PDFs, or load tables exported earlier with to_dict() (no PDFs needed)."""
        if data is None:
            self.premiums = parse_premiums(guide)
            self.grid = {plan: parse_sbc_grid(plan, folder / name) for plan, name in SBC_FILES.items()}
            self.questions = {plan: parse_important_questions(folder / name) for plan, name in SBC_FILES.items()}
        else:
            self.premiums = {(p["plan"], p["enrollment"]): Premium(**p) for p in data["premiums"]}
            self.grid = {plan: [SbcRow(**row) for row in rows] for plan, rows in data["grid"].items()}
            self.questions = data["questions"]

    def to_dict(self) -> dict:
        from dataclasses import asdict
        return {"premiums": [asdict(p) for p in self.premiums.values()],
                "grid": {plan: [asdict(r) for r in rows] for plan, rows in self.grid.items()},
                "questions": self.questions}

    def premium(self, plan: str, status: str, enrollment: str) -> dict:
        p = self.premiums.get((plan, enrollment))
        if not p:
            return {"error": f"No premium for {plan}, {enrollment}."}
        retired = status == "RETIRED"
        value, period = (p.retired_monthly, "monthly") if retired else (p.employed_biweekly, "biweekly")
        return {"plan": plan, "enrollment": enrollment, "enrollment_code": p.code, "value": value, "period": period,
                "source": "2026 GEHA FEHB medical benefits guide"}

    def find(self, plan: str, words: list[str]) -> list[SbcRow]:
        """SBC rows whose service or event text contains any of the words."""
        hits = []
        for row in self.grid.get(plan, []):
            text = f"{row.event} {row.service}".lower()
            if any(w in text for w in words):
                hits.append(row)
        return hits
