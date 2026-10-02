#!/usr/bin/env python3
"""Run the Vercel app locally without the Vercel CLI: public/ as static files, POST /api/chat.

    cd /Users/dc/geha/e2e_RAG/benefits_vercel && ../../.venv/bin/python local_server.py [port]
"""

from __future__ import annotations

import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from api.chat import handler as ChatHandler  # noqa: E402


class LocalHandler(SimpleHTTPRequestHandler):
    def do_POST(self) -> None:
        if self.path.split("?")[0] == "/api/chat":
            return ChatHandler.do_POST(self)
        self.send_error(404)

    _send = ChatHandler._send


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    server = ThreadingHTTPServer(("127.0.0.1", port), partial(LocalHandler, directory=str(HERE / "public")))
    print(f"http://localhost:{port}")
    server.serve_forever()
