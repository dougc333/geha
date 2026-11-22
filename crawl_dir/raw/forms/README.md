# Bill of lading: red cell boxes and per-item row separators

`bill-of-lading.pdf` is a scanned image (no vector lines). The cell boxes were found by
detecting the ruled lines in a 1.5x render of the page. The red overlay is drawn on top
as 3pt vector lines.

## Files

| File | What it is |
| --- | --- |
| `bill-of-lading.pdf` | Original source PDF (unchanged). |
| `2rows.pdf` | Source with red boxes around every ruled cell and per-item row separators in the 5-column table. |
| `2rows.png` | `2rows.pdf` rendered at 1.5x (1602x2688 px). |
| `bill-of-lading-boxed.pdf` | Same content as `2rows.pdf` (earlier name). |
| `cells.json` | 31 detected cell boxes as `[x0, y0, x1, y1]` in PDF points (page is 1068x1792). Includes the logo square. |
| `bill-of-lading-items.json` | The two cargo items with a consistent schema (no blank fields). |
| `2rows-boxes.json` | Page size, the 5 separator lines, the 10 column-by-item cells with field values, and all 31 ruled cells. Coordinates are in points (`_pt`) and pixels (`_px`, 1.5x). |
| `recreate_2rows.py` | Rebuilds the red-line PDF from `bill-of-lading.pdf` and `2rows-boxes.json`. |

## Recreate the PDF

Requires PyMuPDF:

```bash
pip install pymupdf
```

Run from this folder:

```bash
python3 recreate_2rows.py
```

This writes `2rows_recreated.pdf`. It rendered pixel-identical to `2rows.pdf` when checked.
The script skips the logo square and draws every other ruled cell as a red 3pt rectangle,
then draws the five separator segments from `separators`.

## Item schema

Each item has: `container_no`, `seal_no`, `marks`, `num_pkgs`, `package_type`,
`commodity`, `cargo_class`, `hs_code`, `stowage_temp_c`, `gross_weight_kgs`,
`measurement_cbm`.

## Notes and limits

- The text in the cargo table does not line up across columns in the scan, so the row
  separator is a separate segment per column, each placed in that column's gap between
  item 1 and item 2. It is not one straight line.
- Separator y positions (points): container 920, no. pkgs 845, description 1003,
  gross weight 858, measurement 858.
- The item row boxes in `2rows-boxes.json` run from the table top (y=781) to the
  separator, or from the separator to the table bottom (y=1370). They are approximate.
- The container and description cells hold several fields each. They are not split into
  per-field boxes.
- Cell boxes come from line detection and were checked by eye only, not reviewed as
  training labels.
- Matching packages, weights and measurements to items is by order on the page.
