"""Vercel Python function: POST /api/chat runs one turn of the benefits state machine.

Request:  {"message": "retired, me and my wife", "state": {...state from the last reply...}}
Response: {"reply": "...", "state": {...send this back next turn...}, "slots": {...}}

Serverless functions keep no memory between requests, so the conversation state travels
with each request. It holds only slot values and the last question asked; it is checked
here before use, since it comes from the browser.
"""

from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benefits"))

from benefits_bot import BenefitsBot  # noqa: E402
from dental_tables import DentalTables  # noqa: E402
from medical_tables import MedicalTables  # noqa: E402

_TABLES = json.loads((ROOT / "tables.json").read_text())
BOT = BenefitsBot(DentalTables(data=_TABLES["dental"]), MedicalTables(data=_TABLES["medical"]))
MAX_BODY = 20_000
MAX_MESSAGE = 500
SLOT_KEYS = {"line", "status", "enrollment", "zip", "state", "rate_code", "dental_plan", "medical_plan"}
STAGES = {"", "quote", "ask_line", "ask_zip", "ask_state", "ask_status", "ask_enrollment",
          "ask_dental_plan", "ask_medical_plan"}


class BadRequest(ValueError):
    pass


def clean_state(raw) -> dict:
    """Keep only well-formed state fields; anything else is dropped."""
    if not isinstance(raw, dict):
        return {}
    out: dict = {}
    slots = raw.get("slots")
    if isinstance(slots, dict):
        out["slots"] = {k: v for k, v in slots.items() if k in SLOT_KEYS and (
            (isinstance(v, str) and len(v) <= 40) or (isinstance(v, int) and not isinstance(v, bool) and 1 <= v <= 5))}
    if isinstance(raw.get("candidates"), list):
        out["candidates"] = [c for c in raw["candidates"][:10] if isinstance(c, str) and re.fullmatch(r"[A-Z]{2}", c)]
    if isinstance(raw.get("topics"), list):
        out["topics"] = [t for t in raw["topics"][:20]
                         if isinstance(t, str) and len(t) <= 60 and re.match(r"(dental|medical|either):", t)]
    if isinstance(raw.get("quoted"), str) and len(raw["quoted"]) <= 300:
        out["quoted"] = raw["quoted"]
    if raw.get("stage") in STAGES:
        out["stage"] = raw["stage"]
    return out


def chat(body: dict) -> dict:
    message = body.get("message") if isinstance(body, dict) else None
    if not isinstance(message, str) or not message.strip():
        raise BadRequest("message is required")
    if len(message) > MAX_MESSAGE:
        raise BadRequest(f"message is longer than {MAX_MESSAGE} characters")
    reply, state = BOT.step(message.strip(), clean_state(body.get("state")))
    return {"reply": reply, "state": state, "slots": state.get("slots", {})}


class handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        self._send(200, {"ok": True, "service": "benefits chat"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            return self._send(413, {"error": "request too large"})
        try:
            self._send(200, chat(json.loads(self.rfile.read(length) or b"{}")))
        except (BadRequest, json.JSONDecodeError) as error:
            self._send(400, {"error": str(error)})
