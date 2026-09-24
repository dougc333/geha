"""Streamlit inventory for PDF text quality and Docling extraction risk."""

from pathlib import Path
import re
from typing import Any

import pandas as pd
import pymupdf
import streamlit as st


DEFAULT_INPUT_DIR = Path("/Users/dc/geha/downloads/coverage-policies")


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+[\w'-]*\b", text))


def _heading_count(page: pymupdf.Page, page_text: str, max_font_size: float) -> int:
    """Estimate headings from short, prominent text spans."""
    count = 0
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = " ".join(span.get("text", "").split())
                if not text or len(text) > 140 or len(text.split()) > 18:
                    continue
                prominent = span.get("size", 0) >= max(11.0, max_font_size * 1.12)
                uppercase = text.isupper() and any(ch.isalpha() for ch in text)
                if (prominent or uppercase) and not text.endswith((".", ":", ";", ",")):
                    count += 1
    return count


def scan_pdf(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    page_rows: list[dict[str, Any]] = []
    total_chars = total_words = total_headings = total_images = total_blocks = total_tables = 0
    max_font = 0.0
    with pymupdf.open(path) as doc:
        for page_number, page in enumerate(doc, start=1):
            text = page.get_text("text") or ""
            chars = len(text.strip())
            words = _word_count(text)
            spans = [
                span
                for block in page.get_text("dict").get("blocks", [])
                for line in block.get("lines", [])
                for span in line.get("spans", [])
            ]
            page_max_font = max((float(s.get("size", 0)) for s in spans), default=0.0)
            headings = _heading_count(page, text, page_max_font)
            images = len(page.get_images(full=True))
            blocks = len(page.get_text("blocks"))
            try:
                tables = len(page.find_tables().tables)
            except Exception:
                # Table detection can fail on unusual/scanned pages; keep the
                # inventory usable and let Docling handle those pages later.
                tables = 0
            has_text = chars > 0
            page_rows.append({
                "file_name": path.name,
                "page": page_number,
                "has_text": has_text,
                "characters": chars,
                "words": words,
                "headings_estimate": headings,
                "images": images,
                "text_blocks": blocks,
                "tables_estimate": tables,
            })
            total_chars += chars
            total_words += words
            total_headings += headings
            total_images += images
            total_blocks += blocks
            total_tables += tables
            max_font = max(max_font, page_max_font)

        pages = len(doc)

    pages_with_text = sum(int(row["has_text"]) for row in page_rows)
    pages_without_text = pages - pages_with_text
    coverage = (pages_with_text / pages * 100) if pages else 0.0
    if pages_without_text:
        risk = "high"
    elif total_chars < 1000:
        risk = "medium"
    else:
        risk = "low"
    summary = {
        "file_name": path.name,
        "path": str(path),
        "pages": pages,
        "pages_with_text": pages_with_text,
        "pages_without_text": pages_without_text,
        "text_present": "yes" if total_chars else "no",
        "text_on_all_pages": "yes" if pages and pages_without_text == 0 else "no",
        "text_coverage_pct": round(coverage, 1),
        "image_only_pages": pages_without_text,
        "total_characters": total_chars,
        "total_words": total_words,
        "avg_chars_per_page": round(total_chars / pages, 1) if pages else 0,
        "headings_estimate": total_headings,
        "images": total_images,
        "text_blocks": total_blocks,
        "tables_estimate": total_tables,
        "max_font_size": round(max_font, 1),
        "docling_risk": risk,
    }
    return summary, page_rows


@st.cache_data(show_spinner=False)
def scan_directory(directory: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = Path(directory).expanduser()
    summaries: list[dict[str, Any]] = []
    pages: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.pdf")):
        try:
            summary, page_rows = scan_pdf(path)
            summaries.append(summary)
            pages.extend(page_rows)
        except Exception as exc:  # keep one corrupt PDF from hiding the rest
            summaries.append({
                "file_name": path.name,
                "path": str(path),
                "pages": 0,
                "pages_with_text": 0,
                "pages_without_text": 0,
                "text_present": "no",
                "text_on_all_pages": "no",
                "text_coverage_pct": 0.0,
                "image_only_pages": 0,
                "total_characters": 0,
                "total_words": 0,
                "avg_chars_per_page": 0.0,
                "headings_estimate": 0,
                "images": 0,
                "text_blocks": 0,
                "tables_estimate": 0,
                "max_font_size": 0.0,
                "docling_risk": "error",
                "error": f"{type(exc).__name__}: {exc}",
            })
    return pd.DataFrame(summaries), pd.DataFrame(pages)


st.set_page_config(page_title="PDF extraction inventory", layout="wide")
st.title("PDF extraction inventory")
st.caption("Text coverage and layout signals that affect Docling table extraction.")

with st.sidebar:
    directory = st.text_input("PDF directory", str(DEFAULT_INPUT_DIR))
    if st.button("Rescan PDFs"):
        scan_directory.clear()
        st.rerun()

summary_df, page_df = scan_directory(directory)
if summary_df.empty:
    st.error(f"No top-level PDF files found in {directory}")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
col1.metric("PDF files", len(summary_df))
col2.metric("Pages", int(summary_df["pages"].sum()))
col3.metric("PDFs with image-only pages", int((summary_df["pages_without_text"] > 0).sum()))
col4.metric("Total extracted characters", f"{int(summary_df['total_characters'].sum()):,}")

risk_values = ["high", "medium", "low", "error"]
selected_risks = st.multiselect("Show Docling risk", risk_values, default=risk_values)
filtered = summary_df[summary_df["docling_risk"].isin(selected_risks)].copy()
display_columns = [
    "file_name", "pages", "pages_with_text", "pages_without_text",
    "text_present", "text_on_all_pages",
    "text_coverage_pct", "total_characters", "total_words",
    "headings_estimate", "tables_estimate", "images", "text_blocks",
    "avg_chars_per_page", "image_only_pages",
    "docling_risk", "path",
]
st.subheader("Per-file results")
st.dataframe(filtered[display_columns], use_container_width=True, hide_index=True)
st.download_button(
    "Download CSV",
    filtered.to_csv(index=False).encode("utf-8"),
    "pdf_inventory.csv",
    "text/csv",
)

if not page_df.empty:
    selected_file = st.selectbox("Inspect page-level details", filtered["file_name"].tolist())
    details = page_df[page_df["file_name"] == selected_file]
    st.subheader(f"Pages: {selected_file}")
    st.dataframe(details, use_container_width=True, hide_index=True)
    st.caption("A page with has_text=False is likely scanned/image-only and needs OCR or vision-assisted extraction.")
