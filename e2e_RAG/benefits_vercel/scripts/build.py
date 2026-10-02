#!/usr/bin/env python3
"""Prepare the Vercel app: export the PDF tables to JSON and copy the bot modules.

Run after changing the bot or the PDFs (needs PyMuPDF and the PDFs; Vercel needs neither):

    cd /Users/dc/geha/e2e_RAG/benefits_vercel && ../../.venv/bin/python scripts/build.py

- tables.json: the dental tables (rate codes, premiums) and medical tables (premiums,
  enrollment codes, SBC grids, deductibles) parsed from GEHA's 2026 PDFs
- benefits/: unchanged copies of the bot modules from ../src (the function imports these)
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SRC = APP.parent / "src"
MODULES = ("benefits_bot.py", "dental_enrollment.py", "dental_tables.py", "medical_tables.py")


def main() -> None:
    sys.path.insert(0, str(SRC))
    from dental_tables import DentalTables
    from medical_tables import MedicalTables

    tables = {"dental": DentalTables().to_dict(), "medical": MedicalTables().to_dict()}
    (APP / "tables.json").write_text(json.dumps(tables, indent=1) + "\n")
    for name in MODULES:
        shutil.copy2(SRC / name, APP / "benefits" / name)
    d, m = tables["dental"], tables["medical"]
    print(f"tables.json: {len(d['rate_codes'])} rate-code rows, {len(d['premiums'])} dental premiums, "
          f"{len(m['premiums'])} medical premiums, {sum(len(r) for r in m['grid'].values())} SBC rows")
    print(f"copied {', '.join(MODULES)} to benefits/")


if __name__ == "__main__":
    main()
