from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import pymupdf

from crawl_dir.src.pipeline.figure_specs import (
    assemble_page_html,
    native_box_evidence,
    render_figure,
    verify_figure,
)


FIGURE = {
    "id": "fig1",
    "label": "Figure 1",
    "title": "Most say yes.",
    "question": "Do you agree?",
    "box_pt": [20, 200, 400, 400],
    "chart": {"type": "pie",
              "series": [{"name": "Yes", "color": "#747480"}, {"name": "No", "color": "#FFE600"}],
              "panels": [{"values": [60, 40]}]},
}


def _page(path: Path) -> Path:
    document = pymupdf.open()
    page = document.new_page(width=612, height=792)
    page.insert_text((30, 80), "Intro paragraph outside the figure.", fontsize=10)
    page.insert_text((30, 220), "Figure 1", fontsize=8)
    page.insert_text((30, 235), "Most say yes.", fontsize=12)
    page.insert_text((30, 250), "QUESTION: Do you agree?", fontsize=9)
    page.insert_text((30, 300), "Yes No", fontsize=8)
    page.insert_text((200, 330), "60%", fontsize=8)
    page.insert_text((260, 330), "40%", fontsize=8)
    page.insert_text((30, 770), "4 | 2025 Workforce Benefits Study", fontsize=7)
    document.save(path)
    return path


class FigureSpecVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.pdf = _page(Path(self.directory.name) / "source.pdf")
        self.evidence = native_box_evidence(self.pdf, FIGURE["box_pt"])

    def tearDown(self) -> None:
        self.directory.cleanup()

    def test_matching_spec_passes(self):
        errors, warnings = verify_figure(FIGURE, self.evidence)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_value_not_printed_in_pdf_is_rejected(self):
        figure = copy.deepcopy(FIGURE)
        figure["chart"]["panels"][0]["values"] = [61, 39]
        errors, _ = verify_figure(figure, self.evidence)
        self.assertEqual([error["category"] for error in errors], ["chart_data"])

    def test_invented_label_is_rejected(self):
        figure = copy.deepcopy(FIGURE)
        figure["chart"]["series"][0]["name"] = "Traditional employer"
        errors, _ = verify_figure(figure, self.evidence)
        self.assertEqual([error["category"] for error in errors], ["missing_text"])

    def test_raster_values_skip_numeric_check_with_warning(self):
        figure = copy.deepcopy(FIGURE)
        figure["chart"]["panels"][0]["values"] = [61, 39]
        figure["value_evidence"] = "raster_visual_read"
        errors, warnings = verify_figure(figure, self.evidence)
        self.assertEqual(errors, [])
        self.assertTrue(any("raster" in warning for warning in warnings))

    def test_unprinted_estimates_are_excluded_from_token_match(self):
        figure = copy.deepcopy(FIGURE)
        figure["chart"]["series"].append({"name": "Yes", "color": "#C4C4CD"})
        figure["chart"]["panels"][0]["values"] = [60, 40, {"value": 3, "printed": False}]
        errors, warnings = verify_figure(figure, self.evidence)
        self.assertEqual(errors, [])
        self.assertTrue(any("estimated" in warning for warning in warnings))


class FigureSpecRenderingTests(unittest.TestCase):
    def test_pie_renders_svg_and_data_table(self):
        markup = render_figure(FIGURE)
        self.assertIn('<figure class="chart" id="fig1"', markup)
        self.assertIn("<svg", markup)
        self.assertIn('<th scope="row">Yes</th><td>60%</td>', markup)

    def test_harvey_cycle_and_quote_panels_render_their_items(self):
        harvey = {"id": "h", "title": "Areas", "chart": {
            "type": "harvey", "scale_labels": ["Low", "High"],
            "items": [{"label": "Claims", "fill": 0.75}, {"label": "Service", "fill": 1.0}]}}
        cycle = {"id": "c", "title": "Wheel", "chart": {
            "type": "cycle", "items": [{"label": "Physical"}, {"label": "Mental"}]}}
        quotes = {"id": "q", "title": "Quotes", "chart": {
            "type": "quotes", "items": [{"label": "AI should serve people."}]}}
        self.assertIn('<th scope="row">Claims</th><td>¾ filled</td>', render_figure(harvey))
        self.assertIn("<li>Mental</li>", render_figure(cycle))
        self.assertIn("<blockquote><p>AI should serve people.</p></blockquote>", render_figure(quotes))

    def test_steps_render_numbered_items_with_bullets(self):
        steps = {"id": "s", "title": "Uses", "chart": {"type": "steps", "items": [
            {"number": 1, "label": "Product", "bullets": ["Offerings"]},
            {"number": 2, "label": "Distribution", "bullets": ["Tools", "Quoting"]}]}}
        markup = render_figure(steps)
        self.assertIn('<li value="1"><h4>Product</h4><ul><li>Offerings</li></ul></li>', markup)
        self.assertLess(markup.index("Product"), markup.index("Distribution"))

    def test_bullet_glyphs_in_pdf_text_do_not_fail_verification(self):
        figure = {"id": "s", "title": "Uses", "box_pt": [0, 0, 612, 792], "chart": {
            "type": "steps", "items": [{"number": 1, "label": "Product",
                                        "bullets": ["Ability to quickly create"]}]}}
        evidence = {"literal_text": "Uses 1 Product \u25a0Ability to quickly create",
                    "percent_tokens": []}
        errors, _ = verify_figure(figure, evidence)
        self.assertEqual(errors, [])

    def test_page_assembly_replaces_figure_text_and_drops_footer(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = _page(Path(directory) / "source.pdf")
            spec = {"page": 4, "figures": [FIGURE]}
            page = assemble_page_html(pdf, spec, {"fig1": render_figure(FIGURE)})
        self.assertIn("Intro paragraph outside the figure.", page)
        self.assertNotIn("Workforce Benefits Study", page)
        self.assertEqual(page.count("QUESTION:"), 1)
        self.assertLess(page.index("Intro paragraph"), page.index('id="fig1"'))


if __name__ == "__main__":
    unittest.main()
