"""Shared PDF inputs and local extraction-output locations."""

from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
# Default source directory for the GEHA coverage-policy PDFs.  The CLI still
# accepts --input-dir when a different source location is needed.
PDF_DIR = Path("/Users/dc/geha/downloads/coverage-policies")
FIRST_PASS_DIR = PROJECT_DIR / "first_pass"
BATCH_RUNS_DIR = PROJECT_DIR / "review_runs"
RAW_TABLES_DIR = PROJECT_DIR / "raw_tables"
