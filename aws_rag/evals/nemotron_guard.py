"""Nemotron 3.5 Content Safety as a guard backend, run locally for evaluation (not in Lambda).

The 4.3B model (8.6 GB) runs on Apple Silicon (MPS) or CUDA. Inputs are classified as the
user turn; answers as the assistant turn under a neutral user prompt. Returns the same
Verdict as query/guard.py. Model terms: OpenMDW 1.1 + Gemma Terms of Use.

    uv run --no-project --python 3.12 --with torch --with "transformers>=4.57.1,<=4.57.6" \
        --with pillow --with accelerate python aws_rag/evals/run_guard_eval.py nemotron
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "query"))
from guard import Verdict  # noqa: E402

MODEL_ID = "nvidia/Nemotron-3.5-Content-Safety"
NEUTRAL_PROMPT = "Answer my question about the research papers in the library."


@lru_cache(maxsize=1)
def _load():
    import torch
    from transformers import AutoProcessor, Gemma3ForConditionalGeneration

    device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
    # Gemma 3 is unstable in float16; use bfloat16 where the GPU supports it (A100/L4/A10G/H100).
    if device == "cpu":
        dtype = torch.float32
    elif device == "cuda" and not torch.cuda.is_bf16_supported():
        import warnings
        warnings.warn("GPU lacks bfloat16 (e.g. T4): falling back to float16; verify outputs look sane")
        dtype = torch.float16
    else:
        dtype = torch.bfloat16
    model = Gemma3ForConditionalGeneration.from_pretrained(MODEL_ID, torch_dtype=dtype).to(device).eval()
    return AutoProcessor.from_pretrained(MODEL_ID), model, device


def raw(prompt: str, response: str | None = None) -> str:
    """The model's text output, e.g. 'User Safety: unsafe\\nSafety Categories: PII/Privacy'."""
    import torch

    processor, model, device = _load()
    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    if response is not None:
        messages.append({"role": "assistant", "content": [{"type": "text", "text": response}]})
    inputs = processor.apply_chat_template(messages, add_generation_prompt=True, tokenize=True, return_dict=True,
                                           return_tensors="pt", request_categories="/categories",
                                           enable_thinking=False).to(device)
    with torch.inference_mode():
        out = model.generate(**inputs, max_new_tokens=60, do_sample=False)
    return processor.decode(out[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip()


def check(text: str, direction: str) -> Verdict:
    out = raw(text) if direction == "input" else raw(NEUTRAL_PROMPT, text)
    field = "User Safety" if direction == "input" else "Response Safety"
    label = re.search(rf"{field}:\s*(safe|unsafe)", out, re.I)
    if not label:  # unparseable output fails closed
        return Verdict(False, f"nemotron:unparsed:{out[:60]}", text, backend="nemotron")
    cats = re.search(r"Safety Categories:\s*(.+)", out)
    if label.group(1).lower() == "unsafe":
        return Verdict(False, "nemotron:" + (cats.group(1).strip() if cats else "unsafe"), text, backend="nemotron")
    return Verdict(True, "ok", text, backend="nemotron")
