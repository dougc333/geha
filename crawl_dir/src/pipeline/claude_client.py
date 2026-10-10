"""Shared Claude (Anthropic Messages API) access for the ingestion pipeline."""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path
from typing import Any

CLAUDE_MODEL = "claude-sonnet-5-5"
# Route safety-classifier declines to a fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Claude accepts at most 5 MB per base64 image; keep headroom for encoding overhead.
MAX_IMAGE_BYTES = 3_700_000
MAX_IMAGE_SIDE = 7_900


def claude_credentials_available() -> bool:
    """True when the SDK can authenticate: an env credential or an `ant auth login` profile."""
    import os

    if os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN"):
        return True
    config_home = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return (config_home / "anthropic").is_dir()


class ClaudeRefusalError(RuntimeError):
    """Claude (and its fallback chain) declined the request."""


def text_block(text: str) -> dict[str, str]:
    return {"type": "text", "text": text}


def image_block(path: Path) -> dict[str, Any]:
    """Base64 image block; oversized renders are downscaled/re-encoded as JPEG."""
    data = path.read_bytes()
    media_type = "image/png"
    from PIL import Image

    with Image.open(io.BytesIO(data)) as opened:
        too_large = max(opened.size) > MAX_IMAGE_SIDE or len(data) > MAX_IMAGE_BYTES
        if too_large:
            image = opened.convert("RGB")
            if max(image.size) > MAX_IMAGE_SIDE:
                image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            for quality in (90, 80, 70, 60):
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=quality)
                data = buffer.getvalue()
                if len(data) <= MAX_IMAGE_BYTES:
                    break
            media_type = "image/jpeg"
    return {"type": "image", "source": {
        "type": "base64", "media_type": media_type,
        "data": base64.standard_b64encode(data).decode("ascii"),
    }}


# Claude structured outputs reject numeric/length/array-size constraints; callers
# validate those ranges themselves after parsing.
_UNSUPPORTED_SCHEMA_KEYS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
                            "multipleOf", "minLength", "maxLength", "minItems", "maxItems"}


def claude_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {key: claude_schema(value) for key, value in schema.items()
                if key not in _UNSUPPORTED_SCHEMA_KEYS}
    if isinstance(schema, list):
        return [claude_schema(item) for item in schema]
    return schema


def ask_claude(
    model: str,
    system: str,
    content: list[dict[str, Any]],
    *,
    schema: dict[str, Any] | None = None,
    max_tokens: int = 64_000,
    timeout: float = 600,
) -> str:
    """Send one user turn and return the response text (JSON text when ``schema`` is set)."""
    import anthropic

    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "betas": [FALLBACK_BETA],
        "fallbacks": "default",
    }
    if schema is not None:
        params["output_config"] = {"format": {"type": "json_schema",
                                              "schema": claude_schema(schema)}}
    client = anthropic.Anthropic(max_retries=2, timeout=timeout)
    # Streaming avoids HTTP timeouts on long HTML outputs.
    with client.beta.messages.stream(**params) as stream:
        message = stream.get_final_message()
    if message.stop_reason == "refusal":
        category = getattr(message.stop_details, "category", None) if message.stop_details else None
        raise ClaudeRefusalError(f"Claude declined the request (category: {category})")
    if message.stop_reason == "max_tokens":
        raise RuntimeError(f"Claude response hit max_tokens={max_tokens} and is incomplete")
    return "".join(block.text for block in message.content if block.type == "text")


def ask_claude_json(model: str, system: str, content: list[dict[str, Any]],
                    schema: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return json.loads(ask_claude(model, system, content, schema=schema,
                                 max_tokens=kwargs.pop("max_tokens", 16_000), **kwargs))
