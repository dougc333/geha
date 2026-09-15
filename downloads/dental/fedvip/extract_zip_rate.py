import csv
import re
from pathlib import Path

import pdfplumber


SOURCE = Path(
    "/Users/dc/geha/downloads/dental/fedvip/2026-geha-dental-benefits-guide.pdf"
)
OUTPUT = Path(
    "/Users/dc/geha/downloads/dental/fedvip/"
    "2026_geha_dental_zip_to_rate_code.csv"
)


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


with pdfplumber.open(SOURCE) as pdf:
    tables = pdf.pages[9].extract_tables()

if len(tables) != 3:
    raise RuntimeError(f"Expected 3 table sections on page 10, found {len(tables)}")

expected_header = ["State", "First 3 digits of ZIP code", "Rate code"]
rows: list[list[str | int]] = []

for table in tables:
    header = [clean(cell) for cell in table[0]]
    if header != expected_header:
        raise RuntimeError(f"Unexpected table header: {header}")

    for source_row in table[1:]:
        if len(source_row) != 3:
            raise RuntimeError(f"Unexpected row width: {source_row}")
        state, zip_rule, rate_code = [clean(cell) for cell in source_row]
        if not state or not zip_rule or rate_code not in {"1", "2", "3", "4", "5"}:
            raise RuntimeError(f"Invalid extracted row: {source_row}")
        rows.append([state, zip_rule, int(rate_code)])

if len(rows) != 90:
    raise RuntimeError(f"Expected 90 data rows, found {len(rows)}")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT.open("w", newline="", encoding="utf-8") as stream:
    writer = csv.writer(stream)
    writer.writerow(expected_header)
    writer.writerows(rows)

with OUTPUT.open(newline="", encoding="utf-8") as stream:
    verified = list(csv.reader(stream))

if len(verified) != 91 or verified[0] != expected_header:
    raise RuntimeError("CSV round-trip validation failed")

checks = {
    ("AK", "Entire state", "5"),
    ("AL", "Entire state", "1"),
    ("AR", "Entire state", "1"),
    ("AZ", "850-853, 864", "3"),
    ("AZ", "Rest of state", "2"),
    ("CA", "900-908, 910-928, 930-931, 933-935, 939-952, 954, 956-959", "5"),
    ("CA", "Rest of state", "4"),
    ("CO", "Entire state", "4"),
    ("CT", "060-063", "4"),
    ("CT", "064-069", "5"),
    ("DC", "Entire state", "4"),
    ("DE", "Entire state", "3"),
    ("FL", "329-334, 349", "3"),
    ("FL", "Rest of state", "2"),
    ("GA", "300-303, 305-306, 311, 399", "3"),
    ("GA", "Rest of state", "2"),
    ("GU", "Entire area", "1"),
    ("HI", "Entire state", "3"),
    ("IA", "Entire state", "1"),
    ("ID", "Entire state", "2"),
    ("IL", "600-609, 613", "3"),
    ("IL", "620, 622", "2"),
    ("IL", "Rest of state", "1"),
    ("IN", "460-462, 470, 472-473", "2"),
    ("IN", "463, 464", "3"),
    ("IN", "Rest of state", "1"),
    ("KS", "660-662, 666", "2"),
    ("KS", "Rest of state", "1"),
    ("KY", "410", "2"),
    ("KY", "Rest of state", "1"),
    ("LA", "Entire state", "2"),
    ("MA", "012", "2"),
    ("MA", "010-011, 013-027, 055", "4"),
    ("MD", "205-212, 214, 216-217", "4"),
    ("MD", "219", "3"),
    ("MD", "Rest of state", "2"),
    ("ME", "039-042", "4"),
    ("ME", "Rest of state", "3"),
    ("MI", "480-485", "3"),
    ("MI", "Rest of state", "2"),
    ("MN", "550-551, 553-555, 563", "3"),
    ("MN", "Rest of state", "2"),
    ("MO", "Rest of state", "2"),
    ("MO", "726", "1"),
    ("MS", "Entire state", "1"),
    ("MT", "Entire state", "2"),
    ("NC", "Entire state", "2"),
    ("ND", "Entire state", "1"),
    ("NE", "Entire state", "1"),
    ("NH", "Entire state", "4"),
    ("NJ", "080-084", "3"),
    ("NJ", "070-079, 085-089", "5"),
    ("NM", "Entire state", "3"),
    ("NV", "897", "5"),
    ("NV", "Rest of state", "3"),
    ("NY", "005, 100-119, 124-126", "5"),
    ("NY", "063", "4"),
    ("NY", "120-123, 128, 140-143", "2"),
    ("NY", "Rest of state", "1"),
    ("OH", "430-433, 437, 440-443, 446-447, 450-455, 459", "2"),
    ("OH", "Rest of state", "1"),
    ("OK", "Entire state", "2"),
    ("OR", "Entire state", "3"),
    ("PA", "172-174", "4"),
    ("PA", "180-181, 183", "5"),
    ("PA", "189-196", "3"),
    ("PA", "Rest of state", "1"),
    ("PR", "Entire area", "1"),
    ("RI", "Entire state", "4"),
    ("SC", "Entire state", "2"),
    ("SD", "Entire state", "2"),
    ("TN", "Entire state", "2"),
    ("TX", "739, 750-754, 760-762, 770, 772-775, 780-782", "2"),
    ("TX", "733, 786-787", "3"),
    ("TX", "Rest of state", "1"),
    ("UT", "Entire state", "2"),
    ("VA", "201, 205, 220-227", "4"),
    ("VA", "Rest of state", "2"),
    ("VI", "Entire area", "1"),
    ("VT", "Entire state", "2"),
    ("WA", "980-985", "5"),
    ("WA", "986", "3"),
    ("WA", "Rest of state", "4"),
    ("WI", "540", "3"),
    ("WI", "Rest of state", "2"),
    ("WV", "254", "4"),
    ("WV", "Rest of state", "1"),
    ("WY", "834", "2"),
    ("WY", "Rest of state", "1"),
    ("INTL", "International", "5"),
}
actual = {tuple(row) for row in verified[1:]}
if len(checks) != 90:
    raise RuntimeError(f"Expected 90 unique reference rows, found {len(checks)}")
if len(actual) != len(verified) - 1:
    raise RuntimeError("Duplicate rows found in CSV export")
missing = checks - actual
unexpected = actual - checks
if missing or unexpected:
    raise RuntimeError(
        f"CSV export differs from reference rows; "
        f"missing={sorted(missing)}, unexpected={sorted(unexpected)}"
    )

print(f"Wrote {len(rows)} rows to {OUTPUT}")
