"""Shared PDF inputs and local extraction-output locations."""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
PDF_DIR = PROJECT_DIR.parent / "downloads" / "coverage-policies"
FIRST_PASS_DIR = PROJECT_DIR / "first_pass"
BATCH_RUNS_DIR = PROJECT_DIR / "review_runs"
RAW_TABLES_DIR = PROJECT_DIR / "raw_tables"
