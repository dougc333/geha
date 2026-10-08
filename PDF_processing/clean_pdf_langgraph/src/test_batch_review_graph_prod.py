"""Regression tests for labeled production batch-review failure cases."""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .error_detection_demo import build_demo_document, load_cases
from .batch_review_graph_prod import (
    ReviewStateError,
    build_graph,
    compare_html_candidate_node,
    correct_html_candidate_node,
    cycle_html_tables_node,
    finalize_table_node,
    initialize_review_node,
    prepare_table_node,
    render_html_candidate_node,
    validate_and_normalize_tables,
    validate_extraction_node,
    validate_review_inputs_node,
    write_review_html,
)


_CASE_FILE = Path(__file__).with_name("test_data") / "batch_review_graph_prod_cases.json"
_CASE_DOCUMENT = json.loads(_CASE_FILE.read_text(encoding="utf-8"))
_CASES = {item["id"]: item for item in _CASE_DOCUMENT["cases"]}


def case(case_id: str) -> dict:
    return _CASES[case_id]


def artifact(number: int = 1, page: int = 1) -> dict:
    return {
        "extractor": "docling",
        "number": number,
        "page": page,
        "markdown": "| Drug | Code |",
        "columns": ["Drug", "Code"],
        "rows": [["Ziihera", "J9276"]],
        "nearest_heading": "Coverage",
    }


def issue(table: int = 1) -> dict:
    return {
        "artifact": f"docling table {table}",
        "page": table,
        "kind": "wrong_cell",
        "pdf_evidence": "J9276",
        "extracted_evidence": "J0000",
        "explanation": "Extracted code does not match the PDF.",
    }


def prepared_state(tables: list[dict], temporary: Path) -> dict:
    state = {
        "pdf_path": str(temporary / "policy.pdf"),
        "output_dir": str(temporary),
        "docling_tables": tables,
        "page_images": [str(temporary / "page-1.png"), str(temporary / "page-2.png")],
        "vision_model": "test-model",
        "max_correction_attempts": 1,
        "review_validation_failures": [[] for _ in tables],
    }
    state.update(initialize_review_node(state))
    state.update(prepare_table_node(state))
    return state


class ProductionBatchReviewTests(unittest.TestCase):
    def test_production_graph_has_no_human_approval_interrupt(self) -> None:
        nodes = build_graph().get_graph().nodes
        self.assertIn("vision_gate", nodes)
        self.assertNotIn("human_review", nodes)

    def test_permanent_demo_contains_every_labeled_case(self) -> None:
        cases = load_cases()
        document = build_demo_document(cases)
        self.assertEqual(len(cases), len(_CASES))
        for case_id in _CASES:
            self.assertIn(case_id, document)
        self.assertIn('data-filter="error"', document)
        self.assertIn("verdict-match", document)
        self.assertIn("verdict-mismatch", document)
        self.assertIn("verdict-uncertain", document)

    def test_slideshow_has_pause_and_resume_control(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            temporary = Path(temporary_name)
            state = {
                "pdf_path": str(temporary / "policy.pdf"),
                "output_dir": str(temporary),
                "docling_tables": [artifact(1), artifact(2)],
            }
            with patch.dict(
                "os.environ",
                {"GEHA_NO_BROWSER": "1", "GEHA_SLIDESHOW_SECONDS": "5"},
            ):
                result = cycle_html_tables_node(state)
            document = Path(result["table_slideshow_html"]).read_text(encoding="utf-8")
            self.assertIn('id="pause"', document)
            self.assertIn("paused ? 'Resume' : 'Pause'", document)
            self.assertIn("pauseButton.addEventListener('click'", document)
            self.assertIn("if (paused || complete) return;", document)
            self.assertIn('aria-live="polite"', document)
            self.assertIn("5 seconds per table", document)

    def test_runtime_table_validation_cases(self) -> None:
        for case_id in ("VAL-001", "VAL-003", "VAL-005", "VAL-006"):
            spec = case(case_id)
            table = artifact()
            if spec["operation"] == "remove":
                table.pop(spec["field"])
            else:
                table[spec["field"]] = spec["value"]
            with self.subTest(case_id=case_id, condition=spec["condition"]):
                _, failures = validate_and_normalize_tables(
                    [table], spec.get("page_count", 2)
                )
                self.assertIn(
                    spec["expected_code"],
                    {failure["code"] for failure in failures[0]},
                    msg=f"{case_id}: {spec['condition']}",
                )

        spec = case("VAL-002")
        _, failures = validate_and_normalize_tables([artifact(1), artifact(1, 2)], 2)
        self.assertIn(
            spec["expected_code"],
            {failure["code"] for failure in failures[1]},
            msg=f"VAL-002: {spec['condition']}",
        )

    def test_ui_review_skips_empty_table_artifacts(self) -> None:
        empty = artifact(1)
        empty["columns"] = []
        empty["rows"] = []
        visible = artifact(2)
        state = {
            "docling_tables": [empty, visible],
            "review_validation_failures": [[], []],
        }
        state.update(initialize_review_node(state))
        self.assertEqual([table["number"] for table in state["docling_tables"]], [2])
        self.assertEqual(state["review_validation_failures"], [[]])

        with tempfile.TemporaryDirectory() as temporary_name:
            temporary = Path(temporary_name)
            state.update({
                "pdf_path": str(temporary / "policy.pdf"),
                "output_dir": str(temporary),
            })
            with patch.dict("os.environ", {"GEHA_NO_BROWSER": "1"}):
                result = cycle_html_tables_node(state)
            document = Path(result["table_slideshow_html"]).read_text(encoding="utf-8")
            self.assertNotIn("docling table 1", document)
            self.assertIn("docling table 2", document)

    def test_TEXT_001_to_TEXT_004_content_corruption(self) -> None:
        table = artifact()
        table["columns"] = ["Date", case("TEXT-002")["input"]]
        table["rows"] = [[
            case("TEXT-001")["input"],
            case("TEXT-003")["input"] + "; " + case("TEXT-004")["input"],
        ]]
        normalized, failures_by_table = validate_and_normalize_tables([table], 1)
        failures = failures_by_table[0]
        by_code = {failure["code"]: failure for failure in failures}
        for case_id in ("TEXT-001", "TEXT-002", "TEXT-003", "TEXT-004"):
            spec = case(case_id)
            self.assertIn(spec["expected_code"], by_code, msg=spec["condition"])
            self.assertEqual(
                by_code[spec["expected_code"]]["severity"], spec["expected_severity"]
            )
            self.assertFalse(by_code[spec["expected_code"]]["blocks_review"])

        with tempfile.TemporaryDirectory() as temporary_name:
            temporary = Path(temporary_name)
            state = {
                "pdf_path": str(temporary / "policy.pdf"),
                "output_dir": str(temporary),
                "docling_tables": normalized,
                "review_validation_failures": failures_by_table,
            }
            state.update(initialize_review_node(state))
            state.update(prepare_table_node(state))
            self.assertFalse(state["review_skip_current"])
            with patch.dict("os.environ", {"GEHA_NO_BROWSER": "1"}):
                result = cycle_html_tables_node(state)
            document = Path(result["table_slideshow_html"]).read_text(encoding="utf-8")
            self.assertIn("validation-error", document)
            for case_id in ("TEXT-001", "TEXT-002", "TEXT-003", "TEXT-004"):
                self.assertIn(case(case_id)["expected_code"], document)

            resumed = {
                "docling_tables": normalized,
                "review_validation_failures": [[]],
            }
            resumed.update(initialize_review_node(resumed))
            resumed_codes = {
                failure["code"] for failure in resumed["review_validation_failures"][0]
            }
            for case_id in ("TEXT-001", "TEXT-002", "TEXT-003", "TEXT-004"):
                self.assertIn(case(case_id)["expected_code"], resumed_codes)

    def test_GLOBAL_001_missing_extraction_artifact_is_fatal(self) -> None:
        spec = case("GLOBAL-001")
        with tempfile.TemporaryDirectory() as temporary_name:
            temporary = Path(temporary_name)
            pdf = temporary / "policy.pdf"
            pdf.write_bytes(b"%PDF-test")
            existing = temporary / "existing.md"
            existing.write_text("test", encoding="utf-8")
            state = {
                "pdf_path": str(pdf),
                "output_dir": str(temporary),
                "page_count": 1,
                "docling_tables": [artifact()],
                "docling_markdown": str(existing),
                "docling_chunks_markdown": str(existing),
                "docling_tables_markdown": str(temporary / "missing.md"),
            }
            with self.assertRaises(ReviewStateError, msg=spec["condition"]):
                validate_extraction_node(state)

    def test_IMAGE_001_and_IMAGE_002_page_image_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_name:
            temporary = Path(temporary_name)
            combined = temporary / "tables.html"
            combined.write_text("<table></table>", encoding="utf-8")
            png = temporary / "page-1.png"
            png.write_bytes(b"\x89PNG\r\n\x1a\ncontent")

            missing_spec = case("IMAGE-001")
            missing_state = {
                "docling_html": str(combined),
                "page_images": [str(png)],
                "docling_tables": [artifact(page=2)],
                "review_validation_failures": [[]],
            }
            missing = validate_review_inputs_node(missing_state)
            self.assertEqual(
                missing["review_validation_failures"][0][0]["code"],
                missing_spec["expected_code"],
            )

            invalid_spec = case("IMAGE-002")
            invalid = temporary / "not-a-png.png"
            invalid.write_text("not png", encoding="utf-8")
            invalid_state = {
                "docling_html": str(combined),
                "page_images": [str(invalid)],
                "docling_tables": [artifact()],
                "review_validation_failures": [[]],
            }
            result = validate_review_inputs_node(invalid_state)
            self.assertEqual(
                result["review_validation_failures"][0][0]["code"],
                invalid_spec["expected_code"],
            )

    def test_RENDER_001_render_warning_does_not_skip_comparison(self) -> None:
        spec = case("RENDER-001")
        with tempfile.TemporaryDirectory() as temporary_name:
            state = prepared_state([artifact()], Path(temporary_name))
            with patch(
                "src.batch_review_graph_prod.render_html_table_screenshot",
                side_effect=RuntimeError("renderer detail"),
            ):
                state.update(render_html_candidate_node(state))
            self.assertEqual(state["review_current_failures"][0]["code"], spec["expected_code"])
            self.assertEqual(
                state["review_current_failures"][0]["severity"], spec["expected_severity"]
            )
            with patch(
                "src.batch_review_graph_prod.compare_html_table",
                return_value=("match", []),
            ) as compare:
                state.update(compare_html_candidate_node(state))
            compare.assert_called_once()
            self.assertEqual(state["review_current_verdict"], "match")

    def test_COMPARE_001_failure_is_scoped_and_next_table_runs(self) -> None:
        spec = case("COMPARE-001")
        with tempfile.TemporaryDirectory() as temporary_name:
            state = prepared_state([artifact(1, 1), artifact(2, 2)], Path(temporary_name))
            with patch(
                "src.batch_review_graph_prod.compare_html_table",
                side_effect=TimeoutError("private service response"),
            ):
                state.update(compare_html_candidate_node(state))
            self.assertEqual(state["review_current_verdict"], spec["expected_verdict"])
            state.update(finalize_table_node(state))
            self.assertEqual(
                state["review_results"][0]["failures"][0]["code"], spec["expected_code"]
            )

            state.update(prepare_table_node(state))
            self.assertEqual(state["review_current_failures"], [])
            with patch(
                "src.batch_review_graph_prod.compare_html_table",
                return_value=("match", []),
            ) as compare:
                state.update(compare_html_candidate_node(state))
            compare.assert_called_once()
            self.assertEqual(state["review_current_verdict"], "match")
            self.assertEqual(
                state["review_results"][0]["failures"][0]["code"], spec["expected_code"]
            )

    def test_COMPARE_002_oversized_html_skips_model_call(self) -> None:
        spec = case("COMPARE-002")
        with tempfile.TemporaryDirectory() as temporary_name:
            state = prepared_state([artifact()], Path(temporary_name))
            state["review_current_markup"] = "x" * spec["markup_length"]
            with patch("src.batch_review_graph_prod.compare_html_table") as compare:
                state.update(compare_html_candidate_node(state))
            compare.assert_not_called()
            self.assertEqual(state["review_current_verdict"], spec["expected_verdict"])
            self.assertEqual(state["review_current_failures"][0]["code"], spec["expected_code"])

    def test_CORRECT_001_failure_preserves_mismatch(self) -> None:
        spec = case("CORRECT-001")
        with tempfile.TemporaryDirectory() as temporary_name:
            state = prepared_state([artifact()], Path(temporary_name))
            original_issue = issue()
            state.update({
                "review_current_verdict": "mismatch",
                "review_initial_verdict": "mismatch",
                "review_initial_issue_count": 1,
                "review_current_issues": [original_issue],
            })
            with patch(
                "src.batch_review_graph_prod.correct_html_table",
                side_effect=RuntimeError("private correction response"),
            ):
                state.update(correct_html_candidate_node(state))
            self.assertEqual(state["review_current_verdict"], spec["expected_verdict"])
            self.assertIn(original_issue, state["review_current_issues"])
            self.assertEqual(state["review_current_failures"][-1]["code"], spec["expected_code"])

    def test_CORRECT_002_attempt_limit_is_visible(self) -> None:
        spec = case("CORRECT-002")
        with tempfile.TemporaryDirectory() as temporary_name:
            state = prepared_state([artifact()], Path(temporary_name))
            state.update({
                "review_current_verdict": "mismatch",
                "review_initial_verdict": "mismatch",
                "review_initial_issue_count": 1,
                "review_current_issues": [issue()],
                "review_correction_attempts": spec["attempts"],
                "max_correction_attempts": spec["limit"],
            })
            result = finalize_table_node(state)["review_results"][0]
            self.assertEqual(result["verdict"], spec["expected_verdict"])
            self.assertIn(spec["expected_code"], {item["code"] for item in result["failures"]})

    def test_HTML_001_verdicts_and_failures_are_visible(self) -> None:
        spec = case("HTML-001")
        with tempfile.TemporaryDirectory() as temporary_name:
            temporary = Path(temporary_name)
            results = []
            for number, verdict in enumerate(("match", "mismatch", "uncertain"), 1):
                failures = []
                issues = []
                if verdict != "match":
                    failures = [{
                        "code": f"VISIBLE_{verdict.upper()}",
                        "table": number,
                        "page": number,
                        "stage": "compare",
                        "error_type": "VisibleTestError",
                        "severity": "error",
                        "explanation": f"Visible {verdict} explanation.",
                    }]
                    issues = [{
                        "artifact": f"docling table {number}",
                        "page": number,
                        "kind": "other",
                        "pdf_evidence": "",
                        "extracted_evidence": "",
                        "explanation": f"Visible {verdict} explanation.",
                    }]
                results.append({
                    "table": artifact(number, number),
                    "markup": "<table><tr><td>data</td></tr></table>",
                    "verdict": verdict,
                    "initial_verdict": verdict,
                    "initial_issue_count": len(issues),
                    "issues": issues,
                    "failures": failures,
                    "correction_attempts": 0,
                })
            output = write_review_html({
                "review_results": results,
                "output_dir": str(temporary),
                "pdf_path": str(temporary / "policy.pdf"),
            })
            document = Path(output).read_text(encoding="utf-8")
            for expected_class in spec["expected_classes"]:
                self.assertIn(expected_class, document)
            self.assertIn("Verified", document)
            self.assertIn("Mismatch", document)
            self.assertIn("Human review required", document)
            self.assertIn("Visible mismatch explanation.", document)

    def test_SAFE_001_raw_exception_body_is_not_persisted(self) -> None:
        spec = case("SAFE-001")
        with tempfile.TemporaryDirectory() as temporary_name:
            state = prepared_state([artifact()], Path(temporary_name))
            with patch(
                "src.batch_review_graph_prod.compare_html_table",
                side_effect=RuntimeError(spec["secret"]),
            ):
                state.update(compare_html_candidate_node(state))
            state.update(finalize_table_node(state))
            output = write_review_html(state)
            document = Path(output).read_text(encoding="utf-8")
            self.assertNotIn(spec["secret"], str(state))
            self.assertNotIn(spec["secret"], document)


if __name__ == "__main__":
    unittest.main()
