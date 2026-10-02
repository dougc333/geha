#!/usr/bin/env python3
"""Build docs/conversation_replay.html from the conversation test set results.

    cd /Users/dc/geha
    PYTHONPATH=e2e_RAG/src .venv/bin/python e2e_RAG/evals/run_benefits_conversations.py
    .venv/bin/python e2e_RAG/evals/build_replay.py
"""

from __future__ import annotations

import html
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    report = json.loads((HERE / "benefits_conversations_results.json").read_text())
    data = [{"id": r["id"], "category": r["category"], "ok": r["joint"] and r["quote"] and r["phrases"],
             "wrong": [f"{k}: expected {v['expected']}, got {v['got']}" for k, v in r["wrong"].items()]
             + ([] if r["quote"] else ["quote wrong or missing"]),
             "turns": r["transcript"]} for r in report["results"]]
    summary = f"{sum(d['ok'] for d in data)}/{len(data)} fully right"
    page = (HERE / "conversation_replay.template.html").read_text()
    page = page.replace("__DATA__", json.dumps(data).replace("</", "<\\/")).replace("__SUMMARY__", html.escape(summary))
    out = HERE.parent / "docs" / "conversation_replay.html"
    out.write_text(page)
    print(f"{out}: {summary}")


if __name__ == "__main__":
    main()
