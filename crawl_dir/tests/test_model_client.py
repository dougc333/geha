from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from crawl_dir.src.pipeline.model_client import (
    NOUS_BASE_URL,
    ask_model_json,
    use_model_provider,
    validate_provider_config,
)


class ModelClientTests(unittest.TestCase):
    def test_openai_compatible_requires_base_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "--base-url is required"):
            validate_provider_config("openai-compatible")

    def test_nous_provider_supplies_endpoint_and_key_name(self) -> None:
        config = validate_provider_config("nous")
        self.assertEqual(config.base_url, NOUS_BASE_URL)
        self.assertEqual(config.api_key_env, "NOUS_API_KEY")

    def test_openai_compatible_converts_images_and_schema(self) -> None:
        captured = {}

        class FakeCompletions:
            def create(self, **kwargs):
                captured.update(kwargs)
                return SimpleNamespace(choices=[SimpleNamespace(
                    message=SimpleNamespace(content='<think>done</think>{"ok": true}')
                )])

        class FakeOpenAI:
            def __init__(self, **kwargs):
                captured["client"] = kwargs
                self.chat = SimpleNamespace(completions=FakeCompletions())

        content = [
            {"type": "text", "text": "inspect"},
            {"type": "image", "source": {
                "type": "base64", "media_type": "image/png", "data": "YWJj",
            }},
        ]
        schema = {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        }
        with patch.dict(os.environ, {"NOUS_API_KEY": "secret"}), patch(
            "openai.OpenAI", FakeOpenAI
        ), use_model_provider(
            "openai-compatible",
            base_url="https://example.test/v1/",
            api_key_env="NOUS_API_KEY",
        ):
            result = ask_model_json("hermes", "system", content, schema)

        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["client"]["base_url"], "https://example.test/v1")
        image = captured["messages"][1]["content"][1]
        self.assertEqual(image["type"], "image_url")
        self.assertEqual(image["image_url"]["url"], "data:image/png;base64,YWJj")
        self.assertEqual(
            captured["response_format"]["json_schema"]["schema"], schema
        )

    def test_local_openai_compatible_endpoint_does_not_require_key(self) -> None:
        config = validate_provider_config(
            "openai-compatible", "http://127.0.0.1:8000/v1"
        )
        self.assertEqual(config.base_url, "http://127.0.0.1:8000/v1")


if __name__ == "__main__":
    unittest.main()
