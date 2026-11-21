"""Provider-neutral multimodal model access for visual ingestion workflows."""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Iterator

from .claude_client import ask_claude, image_block


NOUS_BASE_URL = "https://inference-api.nousresearch.com/v1"
SUPPORTED_PROVIDERS = ("anthropic", "nous", "openai-compatible")
ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class ModelProviderConfig:
    provider: str = "anthropic"
    base_url: str | None = None
    api_key_env: str | None = None


_ACTIVE_PROVIDER: ContextVar[ModelProviderConfig] = ContextVar(
    "visual_model_provider",
    default=ModelProviderConfig(),
)


def validate_provider_config(
    provider: str,
    base_url: str | None = None,
    api_key_env: str | None = None,
) -> ModelProviderConfig:
    if provider not in SUPPORTED_PROVIDERS:
        raise ValueError(
            f"Unsupported provider {provider!r}; choose one of {SUPPORTED_PROVIDERS}"
        )
    if api_key_env is not None and not ENV_NAME.fullmatch(api_key_env):
        raise ValueError(f"Invalid API-key environment variable name: {api_key_env!r}")
    if provider == "nous":
        base_url = base_url or NOUS_BASE_URL
        api_key_env = api_key_env or "NOUS_API_KEY"
    if provider == "openai-compatible" and not base_url:
        raise ValueError("--base-url is required for --provider openai-compatible")
    return ModelProviderConfig(
        provider=provider,
        base_url=base_url.rstrip("/") if base_url else None,
        api_key_env=api_key_env,
    )


@contextmanager
def use_model_provider(
    provider: str,
    *,
    base_url: str | None = None,
    api_key_env: str | None = None,
) -> Iterator[ModelProviderConfig]:
    config = validate_provider_config(provider, base_url, api_key_env)
    token = _ACTIVE_PROVIDER.set(config)
    try:
        yield config
    finally:
        _ACTIVE_PROVIDER.reset(token)


def _openai_content(content: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for block in content:
        if block.get("type") == "text":
            converted.append({"type": "text", "text": str(block.get("text", ""))})
            continue
        if block.get("type") != "image":
            raise ValueError(f"Unsupported model content block: {block.get('type')!r}")
        source = block.get("source") or {}
        if source.get("type") != "base64":
            raise ValueError("Only base64 image blocks are supported")
        media_type = str(source.get("media_type", "image/png"))
        data = str(source.get("data", ""))
        converted.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:{media_type};base64,{data}",
                "detail": "high",
            },
        })
    return converted


def _response_text(response: Any) -> str:
    content = response.choices[0].message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text", "")) if isinstance(item, dict)
            else str(getattr(item, "text", ""))
            for item in content
        )
    raise RuntimeError("OpenAI-compatible provider returned no text content")


def _ask_openai_compatible(
    config: ModelProviderConfig,
    model: str,
    system: str,
    content: list[dict[str, Any]],
    *,
    schema: dict[str, Any] | None,
    max_tokens: int,
    timeout: float,
) -> str:
    from openai import OpenAI

    key_env = config.api_key_env or "OPENAI_API_KEY"
    api_key = os.getenv(key_env)
    local_endpoint = bool(
        config.base_url and re.match(r"^https?://(?:localhost|127\.0\.0\.1)(?::|/|$)",
                                     config.base_url)
    )
    if not api_key and not local_endpoint:
        raise RuntimeError(
            f"{key_env} is not set for openai-compatible provider {config.base_url}"
        )
    client = OpenAI(
        api_key=api_key or "not-required",
        base_url=config.base_url,
        max_retries=2,
        timeout=timeout,
    )
    params: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": _openai_content(content)},
        ],
        "max_tokens": max_tokens,
    }
    if schema is not None:
        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "visual_pipeline_response",
                "strict": True,
                "schema": schema,
            },
        }
    return _response_text(client.chat.completions.create(**params))


def ask_model(
    model: str,
    system: str,
    content: list[dict[str, Any]],
    *,
    schema: dict[str, Any] | None = None,
    max_tokens: int = 64_000,
    timeout: float = 600,
) -> str:
    """Call the provider active for the current visual-ingestion run."""
    config = _ACTIVE_PROVIDER.get()
    if config.provider == "anthropic":
        return ask_claude(
            model,
            system,
            content,
            schema=schema,
            max_tokens=max_tokens,
            timeout=timeout,
        )
    return _ask_openai_compatible(
        config,
        model,
        system,
        content,
        schema=schema,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def _parse_json_object(value: str) -> dict[str, Any]:
    cleaned = re.sub(r"<think>.*?</think>", "", value, flags=re.I | re.S).strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.I).strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            raise
        result = json.loads(cleaned[start:end + 1])
    if not isinstance(result, dict):
        raise ValueError("Structured model response must be a JSON object")
    return result


def ask_model_json(
    model: str,
    system: str,
    content: list[dict[str, Any]],
    schema: dict[str, Any],
    **kwargs: Any,
) -> dict[str, Any]:
    return _parse_json_object(ask_model(
        model,
        system,
        content,
        schema=schema,
        max_tokens=kwargs.pop("max_tokens", 16_000),
        **kwargs,
    ))
