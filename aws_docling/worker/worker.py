"""One PDF per ECS task; the process exits after conversion."""

import os
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

from docling.document_converter import DocumentConverter


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        pdf = Path(directory) / "source.pdf"
        with urlopen(os.environ["SOURCE_URL"], timeout=120) as response:
            pdf.write_bytes(response.read())

        result = DocumentConverter().convert(str(pdf))
        if result.status.value != "success":
            raise RuntimeError(f"Docling conversion status: {result.status}")
        markdown = result.document.export_to_markdown()
        if not markdown.strip():
            raise RuntimeError("Docling returned empty Markdown")

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
