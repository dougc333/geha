"""Rate-code and premium tables parsed from the GEHA 2026 dental benefits guide.

Page 10 ("Find your rate code") maps a state and the first three ZIP digits to a rate
code 1-5; page 11 gives the premium for each plan, employment status, enrollment type
and rate code. Lookups are exact table reads, never model output.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

GUIDE = Path(os.environ.get("DENTAL_GUIDE", "/Users/dc/geha/downloads/dental/fedvip/2026-geha-dental-benefits-guide.pdf"))
REST = {"Entire state", "Entire area", "Rest of state", "International"}
ENROLLMENT = ("Self Only", "Self Plus One", "Self and Family")
PHONE = "1-855-572-1636"
# USPS first-three-digit ZIP prefixes by state, used only to tell which state a ZIP is in.
# Military APO/FPO prefixes (090-099, 340, 962-966) are left out.
ZIP3_STATE = [
    (5, 5, "NY"), (6, 7, "PR"), (8, 8, "VI"), (9, 9, "PR"), (10, 27, "MA"), (28, 29, "RI"), (30, 38, "NH"),
    (39, 49, "ME"), (50, 54, "VT"), (55, 55, "MA"), (56, 59, "VT"), (60, 69, "CT"), (70, 89, "NJ"),
    (100, 149, "NY"), (150, 196, "PA"), (197, 199, "DE"), (200, 200, "DC"), (201, 201, "VA"), (202, 205, "DC"),
    (206, 219, "MD"), (220, 246, "VA"), (247, 268, "WV"), (270, 289, "NC"), (290, 299, "SC"), (300, 319, "GA"),
    (320, 339, "FL"), (341, 349, "FL"), (350, 369, "AL"), (370, 385, "TN"), (386, 397, "MS"), (398, 399, "GA"),
    (400, 427, "KY"), (430, 459, "OH"), (460, 479, "IN"), (480, 499, "MI"), (500, 528, "IA"), (530, 549, "WI"),
    (550, 567, "MN"), (569, 569, "DC"), (570, 577, "SD"), (580, 588, "ND"), (590, 599, "MT"), (600, 629, "IL"),
    (630, 658, "MO"), (660, 679, "KS"), (680, 693, "NE"), (700, 714, "LA"), (716, 729, "AR"), (730, 731, "OK"),
    (733, 733, "TX"), (734, 749, "OK"), (750, 799, "TX"), (800, 816, "CO"), (820, 831, "WY"), (832, 838, "ID"),
    (840, 847, "UT"), (850, 865, "AZ"), (870, 884, "NM"), (885, 885, "TX"), (889, 898, "NV"), (900, 961, "CA"),
    (967, 968, "HI"), (969, 969, "GU"), (970, 979, "OR"), (980, 994, "WA"), (995, 999, "AK"),
]


@dataclass(frozen=True)
class RateRow:
    state: str
    zips: str        # as printed, e.g. "850-853, 864" or "Rest of state"
    code: int

    def covers(self, zip3: int) -> bool:
        if self.zips in REST:
            return False
        for part in self.zips.split(","):
            lo, _, hi = part.strip().partition("-")
            if int(lo) <= zip3 <= int(hi or lo):
                return True
        return False


def _page(n: int, pdf: Path = GUIDE) -> list[str]:
    with pymupdf.open(pdf) as doc:
        return [line.strip() for line in doc[n - 1].get_text("text").splitlines() if line.strip()]


def parse_rate_codes(pdf: Path = GUIDE) -> list[RateRow]:
    """Page 10: rows are a state line, one or more ZIP lines, then a rate code line."""
    rows, state, zips = [], None, []
    for line in _page(10, pdf):
        if re.fullmatch(r"[A-Z]{2}|INTL", line):
            state, zips = line, []
        elif state and re.fullmatch(r"[1-5]", line):
            rows.append(RateRow(state, " ".join(zips).replace(", ", ",").replace(",", ", ").strip(", "), int(line)))
            state = None
        elif state:
            zips.append(line)
    return rows


def parse_premiums(pdf: Path = GUIDE) -> dict[tuple[str, str, str, int], float]:
    """Page 11: (plan, EMPLOYED|RETIRED, enrollment type, rate code) -> premium."""
    lines, out = _page(11, pdf), {}
    status = plan = None
    for i, line in enumerate(lines):
        if line.startswith("EMPLOYED"):
            status = "EMPLOYED"
        elif line.startswith("RETIRED"):
            status = "RETIRED"
        elif line in ("STANDARD", "HIGH"):
            plan = line
        elif line in ENROLLMENT and status and plan:
            for code, value in enumerate(lines[i + 1:i + 6], 1):
                out[(plan, status, line, code)] = float(value.lstrip("$").replace(",", ""))
    return out


class DentalTables:
    def __init__(self, pdf: Path = GUIDE):
        self.rows = parse_rate_codes(pdf)
        self.premiums = parse_premiums(pdf)
        self.states = {r.state for r in self.rows}

    def _code_for(self, state: str, zip3: int) -> RateRow | None:
        rows = [r for r in self.rows if r.state == state]
        return next((r for r in rows if r.covers(zip3)), None) or next((r for r in rows if r.zips in REST), None)

    def rate_code(self, zip_code: str, state: str | None = None) -> dict:
        """Rate code for a ZIP. If the ZIP prefix could be in states with different codes, asks for the state."""
        digits = re.sub(r"\D", "", zip_code)
        if len(digits) < 3:
            return {"error": "Need at least the first three digits of a US ZIP code."}
        zip3 = int(digits[:3])
        if state:
            candidates = [state.upper()]
        else:
            candidates = [s for lo, hi, s in ZIP3_STATE if lo <= zip3 <= hi]
            candidates += [r.state for r in self.rows if r.covers(zip3) and r.state not in candidates]
        found = {s: row for s in candidates if (row := self._code_for(s, zip3))}
        if not found:
            return {"error": f"ZIP prefix {digits[:3]} is not in the rate-code table. Please call G.E.H.A at {PHONE}."}
        codes = {row.code for row in found.values()}
        if len(codes) > 1:
            return {"ask_state": sorted(found), "zip3": digits[:3],
                    "note": "This ZIP prefix has different rate codes by state; ask which state."}
        state, row = next(iter(found.items()))
        return {"zip3": digits[:3], "state": state if len(found) == 1 else "/".join(sorted(found)),
                "rate_code": row.code, "table_row": f"{row.state} | {row.zips} | {row.code}",
                "source": "2026 GEHA dental benefits guide, page 10"}

    def premium(self, rate_code: int, status: str, enrollment: str, plan: str | None = None) -> dict:
        status = "RETIRED" if status.strip().lower().startswith("retire") else "EMPLOYED"
        match = {e.lower(): e for e in ENROLLMENT}.get(enrollment.strip().lower())
        if not match:
            return {"error": f"Enrollment type must be one of: {', '.join(ENROLLMENT)}."}
        plans = [plan.upper()] if plan else ["HIGH", "STANDARD"]
        per = "biweekly" if status == "EMPLOYED" else "monthly"
        quotes = {p: self.premiums.get((p, status, match, int(rate_code))) for p in plans}
        if None in quotes.values():
            return {"error": "No premium for that combination; rate code must be 1-5 and plan High or Standard."}
        return {"rate_code": int(rate_code), "status": status, "enrollment": match, "period": per,
                "premiums": {p.title(): f"${v:,.2f} {per}" for p, v in quotes.items()},
                "source": "2026 GEHA dental benefits guide, page 11"}


# Page 5 benefits grid (plus cleanings from pages 6-7), as printed. Values are what the
# member pays. test_dental_enrollment.py checks every value appears in the PDF text.
BENEFITS = {
    "preventive": {"label": "Basic, Class A: exams, cleanings, bitewing X-rays", "page": 5,
                   "High": "$0 (in or out of network)", "Standard in-network": "$0",
                   "Standard out-of-network": "25%"},
    "teledentistry": {"label": "Teledentistry.com: one oral evaluation per 12 months", "page": 5,
                      "High": "$0", "Standard in-network": "$0", "Standard out-of-network": "N/A"},
    "intermediate": {"label": "Intermediate, Class B: restorations, extractions, periodontal maintenance", "page": 5,
                     "High": "20%", "Standard in-network": "45%", "Standard out-of-network": "50%"},
    "major": {"label": "Major, Class C: root canals, crowns, bridges, dentures, periodontal surgery", "page": 5,
              "High": "50%", "Standard in-network": "65%", "Standard out-of-network": "70%"},
    "orthodontics": {"label": "Orthodontic, Class D: children and adults, no waiting period", "page": 5,
                     "High": "30% with $3,500 lifetime maximum", "Standard in-network": "50% with $2,500 lifetime maximum",
                     "Standard out-of-network": "50% with $1,500 lifetime maximum"},
    "annual_maximum": {"label": "Calendar year maximum (Class A, B and C)", "page": 5,
                       "High": "Unlimited per person", "Standard in-network": "$2,500 per person",
                       "Standard out-of-network": "$2,000 per person"},
    "deductible": {"label": "Deductible", "page": 5, "High": "no deductibles",
                   "Standard in-network": "No in-network deductibles",
                   "Standard out-of-network": "$75 out-of-network deductible per person with no family limit"},
    "implants": {"label": "Implants", "page": 5, "High": "$2,500 per person per year in-network or out-of-network",
                 "Standard in-network": "$2,500 per person per year in-network",
                 "Standard out-of-network": "$2,000 per person per year out-of-network"},
    "cleanings": {"label": "Preventive cleanings per year", "page": "6-7",
                  "High": "Three preventive cleanings per year included for adults",
                  "Standard in-network": "Two preventive cleanings per year included",
                  "Standard out-of-network": "Two preventive cleanings per year included"},
}
BENEFIT_NOTES = [
    "No in-network deductibles and no waiting periods (page 5).",
    "Bitewing X-rays: two sets per year for members 22 and under, one set for ages 23+ (page 5).",
    "Out of network you also pay any amount above G.E.H.A's plan allowance (page 5).",
]


def pdf_text(pdf: Path = GUIDE) -> str:
    with pymupdf.open(pdf) as doc:
        return " ".join(" ".join(page.get_text("text").split()) for page in doc)
