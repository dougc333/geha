#!/usr/bin/env python3
"""Review every extracted HTML table beside its source PDF page.

The table window controls a three-second slideshow. Click Open PDF window once
to create a second browser window that follows the same table and source page.
Only loopback HTTP is allowed; nothing is uploaded or changed in the source data.
"""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


DEFAULT_TABLE_DIR = Path("/Users/dc/geha/downloads/coverage-policies/html_tables")


def load_items(table_dir: Path, pdf_dir: Path) -> list[dict[str, object]]:
    """Keep manifest order, grouping tables by PDF and omitting excluded tables."""
    manifest = json.loads((table_dir / "manifest.json").read_text(encoding="utf-8"))
    items: list[dict[str, object]] = []
    for result in manifest["results"]:
        pdf = result["pdf"]
        pdf_path = (pdf_dir / pdf).resolve()
        if pdf_path.parent != pdf_dir or pdf_path.suffix.lower() != ".pdf":
            raise ValueError(f"Unsafe source PDF name: {pdf}")
        if not pdf_path.is_file():
            continue  # The manifest may retain a policy that was later removed.
        for table in result.get("outputs", []):
            html = table["html"]
            html_path = (table_dir / html).resolve()
            if html_path.parent != table_dir or html_path.suffix.lower() != ".html":
                raise ValueError(f"Unsafe extracted table name: {html}")
            if not html_path.is_file():
                continue  # Review only tables still present on disk.
            page = table["page"]
            if not isinstance(page, int) or page < 1:
                raise ValueError(f"Invalid PDF page for {html}: {page!r}")
            items.append({
                "pdf": pdf, "page": page, "html": html,
                "heading": table["heading"], "table_number": table["table_number"],
            })
    return items


def table_window_html(interval_ms: int) -> bytes:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GEHA paired table review</title><style>
*{{box-sizing:border-box}}body{{margin:0;font-family:system-ui,sans-serif;color:#10253f;background:#edf2f6}}
header{{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:12px 18px;background:#082b49;color:white}}
h1{{margin:0;font-size:18px}}#status{{font-size:13px;color:#d0dfeb;margin-top:4px}}
.controls{{display:flex;flex-wrap:wrap;gap:7px;align-items:center}}button{{padding:7px 11px;border:0;border-radius:6px;background:#fff;color:#10253f;font-weight:650;cursor:pointer}}
button:hover{{background:#d9eaf6}}label{{font-size:13px}}main{{padding:8px;height:calc(100vh - 78px)}}iframe{{width:100%;height:100%;border:1px solid #b8c5d1;border-radius:8px;background:white}}
@media(max-width:950px){{header{{align-items:start;flex-direction:column}}main{{height:calc(100vh - 130px)}}}}
</style></head><body>
<header><div><h1 id="title">Loading extracted tables…</h1><div id="status"></div></div>
<div class="controls"><button id="pdf-window">Open PDF window</button><button id="previous">◀ Previous</button>
<button id="toggle">Pause</button><button id="next">Next ▶</button><label><input id="loop" type="checkbox" checked> Loop</label></div></header>
<main><iframe id="table" title="Extracted policy table"></iframe></main>
<script>
const intervalMs={interval_ms};
const storageKey='geha-paired-qc-index';
const frame=document.getElementById('table'), title=document.getElementById('title'), status=document.getElementById('status');
const toggle=document.getElementById('toggle');
let items=[], index=0, playing=true, timer=null;
function schedule(){{clearTimeout(timer);if(playing&&items.length>1)timer=setTimeout(()=>move(1),intervalMs);}}
function show(){{
  const item=items[index];if(!item)return;
  title.textContent=item.heading+' · '+item.pdf;
  status.textContent=`Table ${{index+1}} of ${{items.length}} · PDF page ${{item.page}} · ${{intervalMs/1000}} seconds per table`;
  localStorage.setItem(storageKey,String(index));
  frame.src='/table/'+encodeURIComponent(item.html);
}}
function move(delta){{
  const candidate=index+delta;
  if(candidate>=items.length&&!document.getElementById('loop').checked){{playing=false;toggle.textContent='Resume';clearTimeout(timer);return;}}
  index=(candidate+items.length)%items.length;show();
}}
frame.addEventListener('load',schedule);
document.getElementById('previous').onclick=()=>move(-1);
document.getElementById('next').onclick=()=>move(1);
toggle.onclick=()=>{{playing=!playing;toggle.textContent=playing?'Pause':'Resume';schedule();}};
document.getElementById('pdf-window').onclick=()=>{{
  const pdfWindow=window.open('/pdf-view','geha-policy-pdf','popup=yes,width=1100,height=850');
  if(!pdfWindow)alert('Allow pop-ups for this local viewer, then click Open PDF window again.');
  else pdfWindow.focus();
}};
document.addEventListener('keydown',event=>{{if(event.key==='ArrowLeft')move(-1);if(event.key==='ArrowRight')move(1);if(event.key===' '){{event.preventDefault();toggle.click();}}}});
fetch('/api/items').then(r=>{{if(!r.ok)throw Error('Cannot load table catalog');return r.json();}}).then(data=>{{
  items=data.items;if(!items.length)throw Error('No extracted tables found');show();
}}).catch(error=>{{title.textContent='Unable to start reviewer';status.textContent=error.message;}});
</script></body></html>""".encode("utf-8")


def pdf_window_html() -> bytes:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GEHA source PDF</title><style>
*{box-sizing:border-box}body{margin:0;font-family:system-ui,sans-serif;background:#edf2f6;color:#10253f}
header{padding:12px 18px;background:#082b49;color:white;min-height:65px}h1{margin:0;font-size:18px}
#status{margin-top:4px;font-size:13px;color:#d0dfeb}iframe{display:block;width:100%;height:calc(100vh - 65px);border:0;background:white}
</style></head><body><header><h1 id="title">Loading source PDF…</h1><div id="status"></div></header>
<iframe id="pdf" title="Source policy PDF"></iframe><script>
const storageKey='geha-paired-qc-index';
let items=[],shown=-1;
function show(){
  const index=Number(localStorage.getItem(storageKey)??0);
  if(!Number.isInteger(index)||index<0||index>=items.length||index===shown)return;
  shown=index;const item=items[index];
  document.getElementById('title').textContent=item.pdf;
  document.getElementById('status').textContent=`Table ${index+1} of ${items.length} · ${item.heading} · page ${item.page}`;
  document.getElementById('pdf').src='/pdf/'+encodeURIComponent(item.pdf)+'#page='+item.page+'&view=FitH';
}
window.addEventListener('storage',event=>{if(event.key===storageKey)show();});
fetch('/api/items').then(r=>r.json()).then(data=>{items=data.items;show();});
</script></body></html>""".encode("utf-8")


def make_handler(table_dir: Path, pdf_dir: Path, items: list[dict[str, object]], interval_ms: int):
    table_names = {str(item["html"]) for item in items}
    pdf_names = {str(item["pdf"]) for item in items}

    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, content: bytes, content_type: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route == "/":
                self.send_bytes(table_window_html(interval_ms), "text/html; charset=utf-8")
            elif route == "/pdf-view":
                self.send_bytes(pdf_window_html(), "text/html; charset=utf-8")
            elif route == "/api/items":
                self.send_bytes(json.dumps({"items": items}).encode("utf-8"), "application/json; charset=utf-8")
            elif route.startswith("/table/"):
                name = unquote(route.removeprefix("/table/"))
                if name not in table_names:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.send_bytes((table_dir / name).read_bytes(), "text/html; charset=utf-8")
            elif route.startswith("/pdf/"):
                name = unquote(route.removeprefix("/pdf/"))
                if name not in pdf_names:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self.send_bytes((pdf_dir / name).read_bytes(), "application/pdf")
            else:
                self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tables", type=Path, default=DEFAULT_TABLE_DIR)
    parser.add_argument("--pdfs", type=Path, help="Source PDF directory (default: parent of --tables)")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds per table")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval must be greater than zero")
    table_dir = args.tables.resolve()
    pdf_dir = (args.pdfs or table_dir.parent).resolve()
    items = load_items(table_dir, pdf_dir)
    if not items:
        parser.error("No extracted tables found in manifest.json")
    server = ThreadingHTTPServer(
        ("127.0.0.1", args.port),
        make_handler(table_dir, pdf_dir, items, round(args.interval * 1000)),
    )
    url = f"http://127.0.0.1:{server.server_port}/"
    manifest = json.loads((table_dir / "manifest.json").read_text(encoding="utf-8"))
    listed = sum(len(result.get("outputs", [])) for result in manifest["results"])
    print(f"Serving {len(items)} tables from {len({item['pdf'] for item in items})} PDFs at {url}")
    if listed != len(items):
        print(f"Skipping {listed - len(items)} stale manifest entries whose table or PDF is absent.")
    print("Click 'Open PDF window' in the table window. Press Ctrl-C here to stop.")
    if not args.no_browser:
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
