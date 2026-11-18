"""Field verification uses saved OCR, with no model calls."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from document_ingestion_workflow.bill_of_lading_workflow import (
    ROOT,
    verify_bill_of_lading_fields,
)


def _fixture(run_dir: Path) -> Path:
    claude_dir = ROOT / "PDF_processing/bill_lading/claude_run_20260929T220854Z/claude"
    blocks = []
    cargo_keys = ("container_column", "packages_column", "description_column",
                  "gross_weight_column", "measurement_column")
    header_keys = ("container_header", "packages_header", "description_header",
                   "gross_weight_header", "measurement_header")
    for number in range(1, 9):
        source = json.loads((claude_dir / f"block_{number}.json").read_text(encoding="utf-8"))
        cells = source["structured_cells"]
        keys = cargo_keys if number == 6 else header_keys if number == 5 else tuple(
            f"cell_{index}" for index in range(len(cells))
        )
        blocks.append({"block": number, "cells": {
            key: "\n".join(part for part in (cell.get("heading", ""), cell.get("content", "")) if part)
            for key, cell in zip(keys, cells)
        }})
    ocr_path = run_dir / "pages/page-001/segments/structured-ocr.json"
    ocr_path.parent.mkdir(parents=True)
    ocr_path.write_text(json.dumps({"blocks": blocks}), encoding="utf-8")
    (run_dir / "qc-report.json").write_text(
        json.dumps({"status": "needs_visual_review", "structural_errors": []}), encoding="utf-8"
    )
    rendered = "\n".join(str(value) for block in blocks for value in block["cells"].values())
    (run_dir / "pages/page-001/final.html").write_text(rendered, encoding="utf-8")
    (run_dir / "candidate").mkdir()
    (run_dir / "candidate/document.md").write_text(rendered, encoding="utf-8")
    return ocr_path


def test_verified_cargo_rows() -> None:
    with TemporaryDirectory() as directory:
        run_dir = Path(directory)
        _fixture(run_dir)
        verification = verify_bill_of_lading_fields(run_dir)
        rows = json.loads((run_dir / "candidate/bill_of_lading_fields.json").read_text())["containers"]
        qc = json.loads((run_dir / "qc-report.json").read_text())
        assert verification["status"] == "passed"
        assert [row["commodity"] for row in rows] == ["FRESH APPLES", "FRESH PEARS"]
        assert [row["set_temp"] for row in rows] == ["+2°C", "+1°C"]
        assert qc["field_verification"]["row_count"] == 2
        assert qc["status"] == "needs_visual_review"


def test_package_column_disagreement_fails_qc() -> None:
    with TemporaryDirectory() as directory:
        run_dir = Path(directory)
        ocr_path = _fixture(run_dir)
        record = json.loads(ocr_path.read_text())
        record["blocks"][5]["cells"]["packages_column"] = "20\n19"
        ocr_path.write_text(json.dumps(record), encoding="utf-8")
        verification = verify_bill_of_lading_fields(run_dir)
        qc = json.loads((run_dir / "qc-report.json").read_text())
        assert verification["status"] == "failed"
        assert "packages_column counts do not match" in " ".join(verification["failures"])
        assert qc["status"] == "failed"


def test_missing_unit_or_bad_degree_fails_qc() -> None:
    with TemporaryDirectory() as directory:
        run_dir = Path(directory)
        ocr_path = _fixture(run_dir)
        record = json.loads(ocr_path.read_text())
        cargo = record["blocks"][5]["cells"]
        cargo["gross_weight_column"] = cargo["gross_weight_column"].replace("KGS", "", 1)
        cargo["description_column"] = cargo["description_column"].replace("°C", "\x03C", 1)
        ocr_path.write_text(json.dumps(record), encoding="utf-8")
        verification = verify_bill_of_lading_fields(run_dir)
        assert verification["status"] == "failed"
        assert any("gross_weight_column" in error for error in verification["failures"])
        assert any("control character" in error for error in verification["failures"])
