#!/usr/bin/env python3
"""Display extracted policy-table HTML files as a timed QC slideshow."""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, unquote, urlparse


DEFAULT_SOURCE = Path("/Users/dc/geha/downloads/coverage-policies/html_tables")


def table_files(source: Path) -> list[Path]:
    """Return the browser-ready table files in stable filename order."""
    return sorted(path for path in source.glob("*.html") if path.is_file())


def viewer_html(interval_seconds: float) -> bytes:
    interval_ms = max(250, round(interval_seconds * 1000))
    document = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GEHA extracted-table QC</title>
  <style>
    :root {{ color-scheme: light; font-family: system-ui, -apple-system, sans-serif; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: #eef2f6; color: #10253f; }}
    header {{ display: grid; grid-template-columns: 1fr auto; gap: 12px; padding: 12px 16px;
      background: #06233e; color: white; align-items: center; }}
    h1 {{ margin: 0; font-size: 18px; }}
    #status {{ margin-top: 4px; color: #c8d7e6; font-size: 13px; }}
    .controls {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
    button {{ border: 1px solid #9fb2c4; border-radius: 7px; background: white; color: #10253f;
      padding: 7px 12px; cursor: pointer; font-weight: 650; }}
    button:hover {{ background: #e8f1f8; }}
    label {{ display: inline-flex; gap: 5px; align-items: center; font-size: 13px; }}
    main {{ height: calc(100vh - 76px); padding: 10px; }}
    iframe {{ width: 100%; height: 100%; border: 1px solid #b8c5d1; border-radius: 8px;
      background: white; box-shadow: 0 2px 8px rgb(15 35 55 / 10%); }}
    .error {{ padding: 2rem; color: #9f1d20; font-weight: 650; }}
  </style>
</head>
<body>
  <header>
    <div><h1 id="filename">Loading tables…</h1><div id="status"></div></div>
    <div class="controls">
      <button id="previous" type="button">◀ Previous</button>
      <button id="toggle" type="button">Pause</button>
      <button id="next" type="button">Next ▶</button>
      <label><input id="loop" type="checkbox" checked> Loop</label>
    </div>
  </header>
  <main id="stage"><iframe id="table" title="Extracted GEHA policy table"></iframe></main>
  <script>
    const intervalMs = {interval_ms};
    const frame = document.getElementById('table');
    const filename = document.getElementById('filename');
    const status = document.getElementById('status');
    const toggle = document.getElementById('toggle');
    let files = [];
    let index = 0;
    let playing = true;
    let timer = null;

    function schedule() {{
      clearTimeout(timer);
      if (playing && files.length > 1) timer = setTimeout(() => move(1), intervalMs);
    }}
    function show() {{
      if (!files.length) return;
      const name = files[index];
      filename.textContent = name;
      status.textContent = `Table ${{index + 1}} of ${{files.length}} • ${{intervalMs / 1000}} seconds`;
      frame.src = '/table/' + encodeURIComponent(name);
    }}
    function move(delta) {{
      const candidate = index + delta;
      if (candidate >= files.length && !document.getElementById('loop').checked) {{
        playing = false;
        toggle.textContent = 'Resume';
        clearTimeout(timer);
        return;
      }}
      index = (candidate + files.length) % files.length;
      show();
    }}
    frame.addEventListener('load', schedule);
    document.getElementById('previous').addEventListener('click', () => move(-1));
    document.getElementById('next').addEventListener('click', () => move(1));
    toggle.addEventListener('click', () => {{
      playing = !playing;
      toggle.textContent = playing ? 'Pause' : 'Resume';
      schedule();
    }});
    document.addEventListener('keydown', event => {{
      if (event.key === 'ArrowLeft') move(-1);
      if (event.key === 'ArrowRight') move(1);
      if (event.key === ' ') {{ event.preventDefault(); toggle.click(); }}
    }});
    fetch('/api/tables').then(response => response.json()).then(data => {{
      files = data.files;
      if (!files.length) throw new Error('No HTML table files were found.');
      show();
    }}).catch(error => {{
      document.getElementById('stage').innerHTML = `<div class="error">${{error.message}}</div>`;
      filename.textContent = 'Unable to start QC viewer';
    }});
  </script>
</body>
</html>"""
    return document.encode("utf-8")


def make_handler(source: Path, interval_seconds: float):
    source = source.resolve()

    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, data: bytes, content_type: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            route = urlparse(self.path).path
            if route == "/":
                self.send_bytes(viewer_html(interval_seconds), "text/html; charset=utf-8")
                return
            if route == "/api/tables":
                payload = json.dumps(
                    {"files": [path.name for path in table_files(source)]}
                ).encode("utf-8")
                self.send_bytes(payload, "application/json; charset=utf-8")
                return
            if route.startswith("/table/"):
                name = unquote(route.removeprefix("/table/"))
                candidate = (source / name).resolve()
                if (
                    candidate.parent != source
                    or candidate.suffix.lower() != ".html"
                    or not candidate.is_file()
                ):
                    self.send_error(HTTPStatus.NOT_FOUND, "Table not found")
                    return
                self.send_bytes(candidate.read_bytes(), "text/html; charset=utf-8")
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cycle through extracted policy-table HTML files in a browser."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds per table")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.interval <= 0:
        raise SystemExit("--interval must be greater than zero")
    if not args.source.is_dir():
        raise SystemExit(f"Table directory not found: {args.source}")
    files = table_files(args.source)
    if not files:
        raise SystemExit(f"No .html files found in: {args.source}")

    server = ThreadingHTTPServer(
        (args.host, args.port), make_handler(args.source, args.interval)
    )
    url = f"http://{args.host}:{server.server_port}/"
    print(f"Serving {len(files)} tables at {url}")
    print("Press Ctrl-C to stop.")
    if not args.no_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping QC viewer.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
