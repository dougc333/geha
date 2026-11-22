"""Split every benefits-research PDF using the shared GEHA page splitter."""

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from geha_processing.pdf import split_pdf_pages  # noqa: E402


def main() -> None:
    source_root = REPO_ROOT / "minimal" / "benefits_research"
    output_root = Path(__file__).resolve().parent
    sources = sorted(source_root.rglob("*.pdf"))
    if not sources:
        raise FileNotFoundError(f"No PDFs under {source_root}")

    total_pages = 0
    for source in sources:
        destination = output_root / source.relative_to(source_root).with_suffix("")
        pages = split_pdf_pages(source, destination)
        total_pages += len(pages)
        print(f"{source.name}: {len(pages)} pages -> {destination}")
    print(f"Done: {len(sources)} PDFs, {total_pages} single-page PDFs")


if __name__ == "__main__":
    main()
