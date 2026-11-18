"""Test Docling chart-to-CSV on one PDF page, with an optional dependency override."""

import argparse
import csv
import sys
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, default=11, help="One-based PDF page number")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent)
    parser.add_argument("--compat-site-packages", type=Path)
    args = parser.parse_args()
    if args.compat_site_packages:
        sys.path.insert(0, str(args.compat_site_packages))

    import pymupdf
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import ImageRefMode

    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        page_pdf = Path(temporary) / "source.pdf"
        with pymupdf.open(args.pdf) as source:
            if args.page < 1 or args.page > len(source):
                raise ValueError(f"Page must be between 1 and {len(source)}")
            page = pymupdf.open()
            page.insert_pdf(source, from_page=args.page - 1, to_page=args.page - 1)
            page.save(page_pdf)
        options = PdfPipelineOptions(
            do_chart_extraction=True, generate_page_images=True, generate_picture_images=True
        )
        result = DocumentConverter(
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
        ).convert(str(page_pdf))
    if result.status.value != "success":
        raise RuntimeError(f"Docling conversion status: {result.status}")

    stem = f"chart-page-{args.page:03}"
    (args.output / f"{stem}.md").write_text(
        result.document.export_to_markdown(image_mode=ImageRefMode.EMBEDDED), encoding="utf-8"
    )
    for index, picture in enumerate(result.document.pictures, 1):
        image = picture.get_image(result.document)
        if image is not None:
            image.save(args.output / f"{stem}-image-{index:02}.png")
        chart = picture.meta.tabular_chart if picture.meta else None
        if chart is None:
            continue
        data = chart.chart_data
        grid = [[""] * data.num_cols for _ in range(data.num_rows)]
        for cell in data.table_cells:
            grid[cell.start_row_offset_idx][cell.start_col_offset_idx] = cell.text
        with (args.output / f"{stem}-{index:02}.csv").open("w", newline="") as stream:
            csv.writer(stream, lineterminator="\n").writerows(grid)
        print(f"Chart {index}: {data.num_rows} rows x {data.num_cols} columns")


if __name__ == "__main__":
    main()
