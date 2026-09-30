#!/usr/bin/env python3
"""Trace server for the fraud agent: starts runs and streams their events to the React UI.

    python server.py            # http://localhost:8765 (serves ui/dist when built)

POST /api/runs {question}        start a run, returns {run_id}
GET  /api/runs                   saved runs (newest first)
GET  /api/runs/{id}/events       Server-Sent Events: every event so far, then live ones
GET  /api/answer_key             the planted schemes (for scoring in the UI)

Runs are kept in memory while the server runs and saved to traces/<id>.json when done.
Binds to 127.0.0.1 only.
"""

from __future__ import annotations

import asyncio
import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agent import QUESTION, investigate

HERE = Path(__file__).resolve().parent
TRACES = HERE / "traces"
TRACES.mkdir(exist_ok=True)
DIST = HERE / "ui" / "dist"

app = FastAPI(title="Fraud agent trace server")
runs: dict[str, dict] = {}


class RunRequest(BaseModel):
    question: str = Field(default=QUESTION, min_length=5, max_length=2000)


async def execute(run_id: str) -> None:
    run = runs[run_id]

    async def emit(event: dict) -> None:
        event = {"t": round((datetime.now(timezone.utc) - run["started"]).total_seconds(), 2), **event}
        run["events"].append(event)
        run["changed"].set()

    try:
        await investigate(run["question"], emit)
    except Exception as exc:  # the UI shows the error; the trace is still saved
        await emit({"type": "error", "message": f"{type(exc).__name__}: {exc}",
                    "detail": traceback.format_exc()[-2000:]})
    finally:
        run["done"] = True
        run["changed"].set()
        (TRACES / f"{run_id}.json").write_text(json.dumps({
            "run_id": run_id, "question": run["question"], "started": run["started"].isoformat(),
            "events": run["events"]}, indent=1, default=str))


@app.post("/api/runs")
async def start_run(request: RunRequest) -> dict:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:6]
    runs[run_id] = {"question": request.question, "events": [], "done": False,
                    "changed": asyncio.Event(), "started": datetime.now(timezone.utc)}
    asyncio.create_task(execute(run_id))
    return {"run_id": run_id}


def summarize(data: dict, key: dict | None) -> dict:
    """One row of the run history: outcome, effort, and score against the answer key."""
    events = data["events"]
    done = next((e for e in events if e["type"] == "done"), {})
    error = next((e for e in events if e["type"] == "error"), None)
    final = next((e for e in events if e["type"] == "final"), None)
    calls = [e for e in events if e["type"] == "tool_call"]
    findings = (final or {}).get("findings") or []
    score = None
    if key and final:
        score = sum(any(f.get("provider") == s["provider"] and f.get("scheme") == name for f in findings)
                    for name, s in key["schemes"].items())
    return {"run_id": data["run_id"], "started": data.get("started"), "question": data["question"][:160],
            "status": "error" if error else ("done" if done else "incomplete"),
            "error": error["message"][:300] if error else None,
            "model_steps": done.get("model_steps") or max((e.get("step", 0) for e in events), default=0),
            "tool_calls": len(calls), "seconds": done.get("seconds") or (events[-1]["t"] if events else None),
            "input_tokens": (done.get("usage") or {}).get("input_tokens"),
            "output_tokens": (done.get("usage") or {}).get("output_tokens"),
            "findings": len(findings), "score": score,
            "score_of": len(key["schemes"]) if key else None}


@app.get("/api/runs")
def list_runs() -> list[dict]:
    key_path = HERE / "answer_key.json"
    key = json.loads(key_path.read_text()) if key_path.exists() else None
    return [summarize(json.loads(p.read_text()), key) for p in sorted(TRACES.glob("*.json"), reverse=True)]


@app.get("/api/runs/{run_id}/events")
async def stream_events(run_id: str) -> StreamingResponse:
    if run_id not in runs:
        path = TRACES / f"{run_id}.json"
        if not path.exists():
            raise HTTPException(404, "unknown run")
        saved = json.loads(path.read_text())
        runs[run_id] = {"question": saved["question"], "events": saved["events"], "done": True,
                        "changed": asyncio.Event(), "started": datetime.fromisoformat(saved["started"])}

    async def events():
        run, sent = runs[run_id], 0
        while True:
            while sent < len(run["events"]):
                yield f"data: {json.dumps(run['events'][sent], default=str)}\n\n"
                sent += 1
            if run["done"]:
                yield "event: end\ndata: {}\n\n"
                return
            run["changed"].clear()
            try:
                await asyncio.wait_for(run["changed"].wait(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/answer_key")
def answer_key() -> dict:
    key = json.loads((HERE / "answer_key.json").read_text())
    return {"providers": key["providers"], "schemes": key["schemes"]}


@app.get("/api/default_question")
def default_question() -> dict:
    return {"question": QUESTION}


if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(DIST / "index.html")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765)
