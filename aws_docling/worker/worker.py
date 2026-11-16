"""One PDF per ECS task; the process exits after conversion."""

import os
import tempfile
from pathlib import Path
from threading import Event, Thread
from time import monotonic
from urllib.request import Request, urlopen

from docling.document_converter import DocumentConverter


def _heartbeat(stop: Event, stage: list[str], started: float) -> None:
    while not stop.wait(15):
        elapsed = int(monotonic() - started)
        print(f"heartbeat stage={stage[0]} elapsed={elapsed}s", flush=True)


def main() -> None:
    stop = Event()
    stage = ["downloading"]
    started = monotonic()
    print("worker started", flush=True)
    monitor = Thread(target=_heartbeat, args=(stop, stage, started), daemon=True)
    monitor.start()
    try:
        _convert(stage)
        print(f"worker completed in {int(monotonic() - started)}s", flush=True)
    finally:
        stop.set()
        monitor.join(timeout=1)


def _convert(stage: list[str]) -> None:
    with tempfile.TemporaryDirectory() as directory:
        pdf = Path(directory) / "source.pdf"
        with urlopen(os.environ["SOURCE_URL"], timeout=120) as response:
            pdf.write_bytes(response.read())

        stage[0] = "converting"
        print("conversion started", flush=True)
        result = DocumentConverter().convert(str(pdf))
        if result.status.value != "success":
            raise RuntimeError(f"Docling conversion status: {result.status}")
        markdown = result.document.export_to_markdown()
        if not markdown.strip():
            raise RuntimeError("Docling returned empty Markdown")

        stage[0] = "uploading"
        print(f"uploading Markdown ({len(markdown.encode('utf-8'))} bytes)", flush=True)
        request = Request(
            os.environ["OUTPUT_URL"],
            data=markdown.encode("utf-8"),
            headers={"Content-Type": "text/markdown; charset=utf-8"},
            method="PUT",
        )
        with urlopen(request, timeout=120):
            pass


if __name__ == "__main__":
    main()
