from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from bill_of_lading_html_graph import (  # noqa: E402
    CELLS,
    assert_exact_cell_text,
    block_document,
    data_route,
    normalized_text,
    review_cell,
    schema_manifest,
    visual_route,
)


class BillOfLadingHtmlGraphTests(unittest.TestCase):
    def test_schema_contains_all_blocks_and_cells_in_reading_order(self):
        schema = schema_manifest()
        self.assertEqual([item["block"] for item in schema["blocks"]], list(range(1, 9)))
        for block in schema["blocks"]:
            expected = list(range(1, len(block["cells"]) + 1))
            self.assertEqual([cell["reading_order"] for cell in block["cells"]], expected)

    def test_generated_dom_preserves_cell_ids_and_escapes_text(self):
        values = {cell: f"{cell} <value>" for cell in CELLS[2]}
        document = block_document(2, values)
        for cell in CELLS[2]:
            self.assertIn(f'data-cell="{cell}"', document)
            self.assertIn(f"{cell} &lt;value&gt;", document)
        self.assertNotIn("<value>", document)

    def test_normalized_text_handles_html_and_entities(self):
        self.assertEqual(normalized_text("<b>TEL:</b>&nbsp; +1  23"), "tel: +1 23")

    def test_visual_repair_must_preserve_each_named_cell(self):
        values = {cell: f"text for {cell}" for cell in CELLS[3]}
        document = block_document(3, values)
        assert_exact_cell_text(document, values)
        altered = document.replace("text for port_loading", "wrong port", 1)
        with self.assertRaisesRegex(ValueError, "port_loading"):
            assert_exact_cell_text(altered, values)

    def test_data_route_requires_a_clean_data_stage(self):
        base = {
            "use_vision": True,
            "status": "data_mismatch",
            "data_passed": False,
            "data_iteration": 1,
            "max_data_iterations": 5,
        }
        self.assertEqual(data_route(base), "repair")
        self.assertEqual(data_route({**base, "data_passed": True}), "visual")
        self.assertEqual(data_route({**base, "data_iteration": 5}), "finish")
        self.assertEqual(data_route({**base, "status": "needs_human_review"}), "finish")

    def test_visual_route_stops_on_success_or_uncertainty(self):
        base = {
            "visual_passed": False,
            "visual_iteration": 1,
            "max_visual_iterations": 10,
            "visual_issues": [{"kind": "mismatch"}],
        }
        self.assertEqual(visual_route(base), "repair")
        self.assertEqual(visual_route({**base, "visual_passed": True}), "finish")
        self.assertEqual(
            visual_route({**base, "visual_issues": [{"kind": "uncertain"}]}), "finish"
        )

    def test_each_completed_cell_emits_incremental_feedback(self):
        client = Mock()
        client.responses.create.return_value.output_text = (
            '{"verdict":"match","errors":[],"corrected_text":"SHIPPER"}'
        )
        with (
            patch("bill_of_lading_html_graph.image_part", return_value={"type": "input_image"}),
            patch("bill_of_lading_html_graph.add_feedback") as feedback,
        ):
            result = review_cell(
                client=client,
                model="test-model",
                block=2,
                cell="shipper",
                source_png=Path("unused.png"),
                extracted_text="SHIPPER",
                iteration=1,
                progress_index=3,
                progress_total=12,
            )

        self.assertEqual(result["verdict"], "match")
        scores = feedback.call_args.kwargs
        self.assertTrue(scores["text_cell_match"])
        self.assertFalse(scores["text_cell_error"])
        self.assertFalse(scores["text_cell_uncertain"])
        self.assertEqual(scores["text_cell_progress"], 0.25)
        self.assertEqual(scores["text_cell_response_retries"], 0)
        self.assertGreaterEqual(scores["text_cell_latency_seconds"], 0)

    def test_empty_cell_responses_retry_then_become_uncertain(self):
        client = Mock()
        client.responses.create.return_value.output_text = ""
        client.responses.create.return_value.status = "completed"
        client.responses.create.return_value.incomplete_details = None
        with (
            patch("bill_of_lading_html_graph.image_part", return_value={"type": "input_image"}),
            patch("bill_of_lading_html_graph.add_feedback") as feedback,
            patch("builtins.print"),
        ):
            result = review_cell(
                client=client,
                model="test-model",
                block=2,
                cell="shipper",
                source_png=Path("unused.png"),
                extracted_text="SHIPPER",
                iteration=1,
                progress_index=1,
                progress_total=12,
            )

        self.assertEqual(client.responses.create.call_count, 3)
        self.assertEqual(result["verdict"], "uncertain")
        self.assertEqual(result["corrected_text"], "SHIPPER")
        scores = feedback.call_args.kwargs
        self.assertTrue(scores["text_cell_error"])
        self.assertTrue(scores["text_cell_uncertain"])
        self.assertEqual(scores["text_cell_response_retries"], 2)


if __name__ == "__main__":
    unittest.main()
