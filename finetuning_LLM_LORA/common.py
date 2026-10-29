"""Shared paths and helpers for the GEHA LoRA generator experiment."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import torch

from geha_processing.io import read_jsonl as _read_jsonl, write_jsonl as _write_jsonl


HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
RESULTS_DIR = HERE / "results"
ADAPTER_DIR = HERE / "models/geha-dental-generator-lora"
BASE_MODEL = "Qwen/Qwen2.5-1.5B-Instruct"
SPLITS = ("train", "validation", "test")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return _read_jsonl(path)


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _write_jsonl(path, rows)


def pick_device(name: str | None = None) -> torch.device:
    if name:
        return torch.device(name)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


DTYPES = {"bf16": torch.bfloat16, "fp16": torch.float16, "fp32": torch.float32}


def pick_dtype(name: str, device: torch.device, *, training: bool) -> torch.dtype:
    """``auto``: bf16 on GPUs that support it (A100, L4), else fp32 for training
    (fp16 LoRA without a grad scaler can diverge; T4) or fp16 for inference.
    MPS and CPU always get fp32 (M1 has no native bf16)."""
    if name != "auto":
        return DTYPES[name]
    if device.type != "cuda":
        return torch.float32
    if torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float32 if training else torch.float16


def chat_ids(tokenizer, messages: list[dict], **kwargs) -> list[int]:
    ids = tokenizer.apply_chat_template(messages, tokenize=True, **kwargs)
    # transformers 5 can return a BatchEncoding instead of a list of ids.
    return list(ids["input_ids"]) if hasattr(ids, "keys") else list(ids)
