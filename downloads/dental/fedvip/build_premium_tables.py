"""Build 2026 GEHA FEDVIP dental premium CSVs from the four rate screenshots.

Four classes of enrollee, keyed by employment status:
  * Employed (active Federal employee)  -> BIWEEKLY rates
  * Retired (annuitant)                 -> MONTHLY rates
Each class has both plan options: STANDARD and HIGH.

Source: /Users/dc/geha/downloads/dental/fedvip/*.png (4 premium screenshots).
Output: one CSV per screenshot, named by class, plus one tidy long-format file.

Layout of each CSV mirrors the image exactly:
  rows    = enrollment type (Self Only / Self Plus One / Self and Family)
  columns = Rate code 1 .. Rate code 5
"""

import csv
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

OUT_DIR = Path("/Users/dc/geha/downloads/dental/fedvip")


def as_monthly(biweekly: float) -> float:
    """Biweekly -> monthly exactly as the carrier rounds it: x 26 / 12, half up."""
    value = (Decimal(str(biweekly)) * 26 / 12).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(value)

ENROLLMENT_TYPES = ["Self Only", "Self Plus One", "Self and Family"]
RATE_CODES = [1, 2, 3, 4, 5]
WIDE_HEADER = (
    ["Plan Option", "Employment Status", "Pay Frequency", "Enrollment Type"]
    + [f"Rate Code {c}" for c in RATE_CODES]
)

# (plan option, employment status) -> (pay frequency, filename, rates)
# The key IS the identifier columns, so the two can never drift apart.
CLASSES = {
    ("STANDARD", "EMPLOYED"): (
        "Biweekly",
        "2026_geha_dental_standard_employed_biweekly.csv",
        {  # rate code -> {enrollment type: premium}
            1: {"Self Only": 10.82, "Self Plus One": 21.61, "Self and Family": 32.41},
            2: {"Self Only": 12.11, "Self Plus One": 24.22, "Self and Family": 36.24},
            3: {"Self Only": 13.27, "Self Plus One": 26.48, "Self and Family": 39.75},
            4: {"Self Only": 14.81, "Self Plus One": 29.60, "Self and Family": 44.39},
            5: {"Self Only": 16.00, "Self Plus One": 32.00, "Self and Family": 48.00},
        },
    ),
    ("STANDARD", "RETIRED"): (
        "Monthly",
        "2026_geha_dental_standard_retired_monthly.csv",
        {
            1: {"Self Only": 23.44, "Self Plus One": 46.82, "Self and Family": 70.22},
            2: {"Self Only": 26.24, "Self Plus One": 52.48, "Self and Family": 78.52},
            3: {"Self Only": 28.75, "Self Plus One": 57.37, "Self and Family": 86.13},
            4: {"Self Only": 32.09, "Self Plus One": 64.13, "Self and Family": 96.18},
            5: {"Self Only": 34.67, "Self Plus One": 69.33, "Self and Family": 104.00},
        },
    ),
    ("HIGH", "EMPLOYED"): (
        "Biweekly",
        "2026_geha_dental_high_employed_biweekly.csv",
        {
            1: {"Self Only": 18.97, "Self Plus One": 37.92, "Self and Family": 56.88},
            2: {"Self Only": 21.32, "Self Plus One": 42.62, "Self and Family": 63.95},
            3: {"Self Only": 23.26, "Self Plus One": 46.53, "Self and Family": 69.79},
            4: {"Self Only": 26.05, "Self Plus One": 52.08, "Self and Family": 78.13},
            5: {"Self Only": 28.23, "Self Plus One": 56.46, "Self and Family": 84.63},
        },
    ),
    ("HIGH", "RETIRED"): (
        "Monthly",
        "2026_geha_dental_high_retired_monthly.csv",
        {
            1: {"Self Only": 41.10, "Self Plus One": 82.16, "Self and Family": 123.24},
            2: {"Self Only": 46.19, "Self Plus One": 92.34, "Self and Family": 138.56},
            3: {"Self Only": 50.40, "Self Plus One": 100.82, "Self and Family": 151.21},
            4: {"Self Only": 56.44, "Self Plus One": 112.84, "Self and Family": 169.28},
            5: {"Self Only": 61.17, "Self Plus One": 122.33, "Self and Family": 183.37},
        },
    ),
}


def validate() -> None:
    """Structural + arithmetic checks before anything is written."""
    for (option, status), (freq, _, rates) in CLASSES.items():
        label = f"{option}/{status}"
        if freq not in {"Biweekly", "Monthly"}:
            raise RuntimeError(f"{label}: unexpected pay frequency {freq!r}")
        if sorted(rates) != RATE_CODES:
            raise RuntimeError(f"{label}: expected rate codes {RATE_CODES}, got {sorted(rates)}")
        for code, row in rates.items():
            if list(row) != ENROLLMENT_TYPES:
                raise RuntimeError(f"{label} rate code {code}: unexpected enrollment types {list(row)}")

        # self only < self plus one < self and family, at every rate code
        for code, row in rates.items():
            if not row["Self Only"] < row["Self Plus One"] < row["Self and Family"]:
                raise RuntimeError(f"{label} rate code {code}: tiers not ascending: {row}")
        # monotonic across rate codes
        for tier in ENROLLMENT_TYPES:
            series = [rates[c][tier] for c in RATE_CODES]
            if series != sorted(series) or len(set(series)) != 5:
                raise RuntimeError(f"{label} {tier}: not strictly increasing: {series}")

    # The published rule: monthly = biweekly x 26 / 12, rounded to the cent.
    for option in ("STANDARD", "HIGH"):
        bw = CLASSES[(option, "EMPLOYED")][2]
        mo = CLASSES[(option, "RETIRED")][2]
        for code in RATE_CODES:
            for tier in ENROLLMENT_TYPES:
                derived = as_monthly(bw[code][tier])
                if derived != mo[code][tier]:
                    raise RuntimeError(
                        f"{option} rate code {code} {tier}: biweekly {bw[code][tier]} -> "
                        f"expected monthly {derived}, table says {mo[code][tier]}"
                    )


def write_one(option: str, status: str, freq: str, filename: str, rates: dict) -> list[list]:
    path = OUT_DIR / filename
    rows: list[list] = []
    for tier in ENROLLMENT_TYPES:
        rows.append(
            [option, status, freq, tier]
            + [f"{rates[c][tier]:.2f}" for c in RATE_CODES]
        )
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(WIDE_HEADER)
        writer.writerows(rows)

    # round-trip verification against the in-memory table
    with path.open(newline="", encoding="utf-8") as stream:
        read_back = list(csv.reader(stream))
    if read_back[0] != WIDE_HEADER:
        raise RuntimeError(f"{filename}: header round-trip failed")
    if read_back[1:] != rows:
        raise RuntimeError(f"{filename}: body round-trip failed")
    if len(rows) != 3 or any(len(r) != 9 for r in rows):
        raise RuntimeError(f"{filename}: unexpected shape {[len(r) for r in rows]}")
    print(f"Wrote {path.name}: {len(rows)} rows x {len(WIDE_HEADER)} cols")
    return rows


def write_long() -> None:
    path = OUT_DIR / "2026_geha_dental_premiums_all_classes.csv"
    header = [
        "Plan Option",
        "Employment Status",
        "Pay Frequency",
        "Enrollment Type",
        "Rate Code",
        "Premium",
    ]
    rows = []
    for (option, status), (freq, _, rates) in CLASSES.items():
        for tier in ENROLLMENT_TYPES:
            for code in RATE_CODES:
                rows.append([option, status, freq, tier, code, f"{rates[code][tier]:.2f}"])
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
    with path.open(newline="", encoding="utf-8") as stream:
        read_back = list(csv.reader(stream))
    if read_back[0] != header or len(read_back) != 61 or len(rows) != 60:
        raise RuntimeError("long-format round-trip failed")
    print(f"Wrote {path.name}: {len(rows)} rows x {len(header)} cols")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    validate()
    print("validation passed: structure, tier ordering, rate-code ordering, monthly = biweekly x 26/12")
    for (option, status), (freq, filename, rates) in CLASSES.items():
        write_one(option, status, freq, filename, rates)
    write_long()
