"""Check the bill-of-lading OCR request without calling a paid model."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from crawl_dir.src.pipeline.claude_client import ask_claude
from .bill_of_lading_workflow import (
    BILL_OF_LADING_OCR_EFFORT,
    BILL_OF_LADING_OCR_MODEL,
    _extract_block_cells,
)


class BillOfLadingClaudeOcrTests(unittest.TestCase):
    def test_opus_ocr_keeps_degree_symbols_and_column_guidance(self):
        with TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for name in ("region-06.png", "description.png"):
                Image.new("RGB", (20, 20), "white").save(directory / name)
            block = {
                "reading_order": 6,
                "image": "region-06.png",
                "cells": [{"id": "description_column", "image": "description.png"}],
            }
            captured = {}

            def fake_ask_claude(model, system, content, **kwargs):
                captured.update(model=model, system=system, content=content, **kwargs)
                return json.dumps({"description_column": "SET TEMP: +2°C\nSET TEMP: +1°C"})

            with patch(
                "crawl_dir.src.pipeline.claude_client.ask_claude", fake_ask_claude
            ):
                result = _extract_block_cells(block, directory, "gpt-4.1-mini")

        self.assertEqual(result["description_column"], "SET TEMP: +2°C\nSET TEMP: +1°C")
        self.assertEqual(captured["model"], BILL_OF_LADING_OCR_MODEL)
        self.assertEqual(captured["effort"], BILL_OF_LADING_OCR_EFFORT)
        self.assertFalse(captured["allow_fallback"])
        self.assertEqual(captured["schema"]["required"], ["description_column"])
        self.assertTrue(any(
            "five full-height vertical columns" in part.get("text", "")
            for part in captured["content"]
        ))

    def test_claude_request_sends_medium_effort_without_fallback(self):
        captured = {}

        class FakeStream:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def get_final_message(self):
                return SimpleNamespace(
                    stop_reason="end_turn", stop_details=None,
                    content=[SimpleNamespace(type="text", text='{"value":"+2°C"}')],
                )

        class FakeMessages:
            def stream(self, **params):
                captured.update(params)
                return FakeStream()

        fake_client = SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages()))
        fake_module = SimpleNamespace(Anthropic=lambda **_kwargs: fake_client)
        with patch.dict(sys.modules, {"anthropic": fake_module}):
            response = ask_claude(
                BILL_OF_LADING_OCR_MODEL, "literal OCR", [{"type": "text", "text": "read"}],
                schema={"type": "object", "properties": {"value": {"type": "string"}},
                        "required": ["value"], "additionalProperties": False},
                effort=BILL_OF_LADING_OCR_EFFORT, allow_fallback=False,
            )

        self.assertEqual(json.loads(response)["value"], "+2°C")
        self.assertEqual(captured["model"], "claude-opus-5-5")
        self.assertEqual(captured["output_config"]["effort"], "medium")
        self.assertEqual(captured["output_config"]["format"]["type"], "json_schema")
        self.assertNotIn("fallbacks", captured)


if __name__ == "__main__":
    unittest.main()
