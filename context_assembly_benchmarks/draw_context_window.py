"""Draw the LLM context window filled two ways: flat row chunks (left) vs table-aware RAG (right).

Uses the real Xgeva coverage-policy tables from the verified docling Markdown in crawl_dir, so
every row in the figure is real. The flat-chunk side shows four plausible top-ranked rows for the
question; the table-aware side shows the complete parent table those rows point to.

    .venv/bin/python context_assembly_benchmarks/draw_context_window.py
writes context_window_flat_vs_table.png and .svg next to this file.
"""

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

HERE = Path(__file__).resolve().parent
DOC = (HERE.parent / "crawl_dir/verified/coverage-policies/geha-coverage-policy-xgeva"
       / "geha-coverage-policy-xgeva.docling.md")
SOURCE = "geha-coverage-policy-xgeva.pdf"
QUESTION = "Is Denosumab-bmwo (Q5157) preferred, and does it need prior authorization?"

INK, MUTED, LINE, SURFACE = "#1f1f1e", "#6b6a64", "#d9d8d2", "#fcfcfb"
FLAT, FLAT_TINT = "#2a78d6", "#e7f0fb"          # categorical slot 1 (blue)
TABLE, TABLE_TINT = "#1baf7a", "#ddf3ea"        # categorical slot 3 (aqua)
HIT = "#fff3c4"                                  # rows that matched the query
MONO = "DejaVu Sans Mono"


def md_tables(text: str) -> list[list[list[str]]]:
    tables, current = [], []
    for line in text.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r"-+", c) for c in cells):
                current.append(cells)
        elif current:
            tables.append(current)
            current = []
    return tables + ([current] if current else [])


def clean(cell: str) -> str:
    return re.sub(r"\s+", " ", cell.replace("Non- Preferred**", "Non-preferred").replace("Requi res", "Requires"))


tables = md_tables(DOC.read_text())
pref = [[clean(c) for c in row] for row in tables[0]]      # Preference | Requires PA | Drug | HCPCS | Description
billing = [[clean(c) for c in row] for row in tables[1]]   # Drug | HCPCS | Description


def pref_chunk(row):
    return (f"Source: {SOURCE}\nTable: Drug preference and prior authorization\n"
            f"Drug Name: {row[2]}\nHCPCS Code: {row[3]}\nPreference: {row[0]}\nPrior Authorization: {row[1]}")


def billing_chunk(row):
    return f"Source: {SOURCE}\nTable: Billing codes\nDrug Name: {row[0]}\nHCPCS Code: {row[1]}\nDescription: {row[2]}"


def find(rows, col, value):
    return next(r for r in rows[1:] if r[col] == value)


# Four plausible top-ranked rows for the question: both Q5157 rows of table 1, the Q5157 billing
# row (table 2), and a near-miss biosimilar row (Q5158).
chunks = [pref_chunk(find(pref, 2, "Denosumab-bmwo (Osenvelt)")),
          pref_chunk(find(pref, 2, "Denosumab-bmwo (Denosumab-Celtrion)")),
          billing_chunk(find(billing, 0, "Denosumab-bmwo (Osenvelt)")),
          pref_chunk(find(pref, 2, "Denosumab-bnht (Bomyntra)"))]
table_md = "\n".join("| " + " | ".join(r) + " |" for r in pref)
flat_tokens = sum(len(c) for c in chunks) // 4
table_tokens = (len(table_md) + len(SOURCE) + 60) // 4

fig, ax = plt.subplots(figsize=(18, 11), dpi=200)
fig.patch.set_facecolor(SURFACE)
ax.set_xlim(0, 180)
ax.set_ylim(0, 110)
ax.axis("off")


def box(x, y, w, h, fc, ec, lw=1.2, r=1.2, z=1):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z))


def arrow(x0, y0, x1, y1, color, lw=1.8):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=14,
                                 color=color, lw=lw, zorder=5))


def pipeline(x, steps, color, tint):
    y = 76
    for i, step in enumerate(steps):
        box(x, y, 34, 6.2, tint, color, lw=1.1, r=1)
        ax.text(x + 17, y + 3.1, step, ha="center", va="center", fontsize=9.5, color=INK, zorder=3)
        if i < len(steps) - 1:
            arrow(x + 17, y, x + 17, y - 3.4, color, lw=1.3)
        y -= 9.6
    return y + 9.6


# --- title ------------------------------------------------------------------------------
ax.text(90, 106, "Retrieval LLM context window: flat row chunks vs table-aware RAG",
        ha="center", va="center", fontsize=17, color=INK, weight="bold")
ax.text(90, 102, f"Same question, same Xgeva coverage policy ({SOURCE}). Real rows from the verified extraction.",
        ha="center", va="center", fontsize=10.5, color=MUTED)

# --- left: flat row chunks pipeline ---------------------------------------------------------
ax.text(23, 92, "1  Flat row chunks", ha="center", fontsize=13.5, color=FLAT, weight="bold")
ax.text(23, 88.2, "each table row is its own chunk,\nwith source and table title copied in",
        ha="center", va="top", fontsize=9, color=MUTED, linespacing=1.3)
last = pipeline(6, ["Question", "Embed and rank all row chunks", "Take the top-k rows", "Send those rows only"],
                FLAT, FLAT_TINT)
arrow(40, last + 3.1, 45.5, last + 3.1, FLAT, lw=2.2)
ax.text(23, 38.5, "Flat chunks are smaller and cheaper,\nbut can omit related rows, headers,\nqualifiers, or exceptions.",
        ha="center", va="top", fontsize=10, color=INK, weight="bold", linespacing=1.35)
ax.text(23, 28.5, "Headers repeat in every chunk.\nRows arrive without the rest\nof their table.",
        ha="center", va="top", fontsize=9.5, color=INK, linespacing=1.35)

# --- right: table-aware pipeline ------------------------------------------------------------
ax.text(158, 92, "2  Table-aware RAG", ha="center", fontsize=13.5, color=TABLE, weight="bold")
ax.text(158, 88.2, "rows are searched, but the\nwhole parent table is returned",
        ha="center", va="top", fontsize=9, color=MUTED, linespacing=1.3)
last = pipeline(141, ["Question", "Rank child rows", "Find each row's table_id", "Load complete parent table",
                      "Send complete table"], TABLE, TABLE_TINT)
arrow(141, last + 3.1, 135.5, last + 3.1, TABLE, lw=2.2)
ax.text(158, 29.5, "Parent-table expansion preserves\nmore structure, but consumes more\ntokens and can introduce unrelated\nsibling rows.",
        ha="center", va="top", fontsize=10, color=INK, weight="bold", linespacing=1.35)
ax.text(158, 17.5, "Headers appear once.\nThe model sees every row,\nincluding the preferred alternative.",
        ha="center", va="top", fontsize=9.5, color=INK, linespacing=1.35)

# --- center: the context window ----------------------------------------------------------------
X0, X1, Y0, Y1, MID = 44, 137, 6, 97, 88
box(X0, Y0, X1 - X0, Y1 - Y0, "white", INK, lw=2.2, r=2.2)
ax.text((X0 + X1) / 2, Y1 - 3.2, "LLM context window", ha="center", va="center", fontsize=13, color=INK, weight="bold")
box(X0 + 1.5, 86.5, X1 - X0 - 3, 4.2, "#f1f0ec", LINE, lw=0.8, r=0.8, z=2)
ax.text((X0 + X1) / 2, 88.6, "System prompt: answer only from the retrieved policy text and cite the source",
        ha="center", va="center", fontsize=8.6, color=MUTED, zorder=3)
box(X0 + 1.5, 81.4, X1 - X0 - 3, 4.2, "#f1f0ec", LINE, lw=0.8, r=0.8, z=2)
ax.text((X0 + X1) / 2, 83.5, f"Question: {QUESTION}", ha="center", va="center", fontsize=8.6, color=INK, zorder=3)
ax.plot([MID, MID], [Y0 + 9.5, 79.8], color=LINE, lw=1.2, ls=(0, (4, 3)), zorder=2)
ax.text((X0 + MID) / 2, 77.8, "Retrieved context: 4 flat row chunks", ha="center", fontsize=9.8,
        color=FLAT, weight="bold")
ax.text((MID + X1) / 2, 77.8, "Retrieved context: 1 complete table", ha="center", fontsize=9.8,
        color=TABLE, weight="bold")

# left half: stacked chunk cards ("Key: value" lines, as the chunks are actually stored)
CH = 0.705                       # width of one 6.9pt monospace character, in axis units
y = 75.2
for chunk in chunks:
    lines = []
    for line in chunk.split("\n"):
        key, _, val = line.partition(": ")
        room = int((MID - X0 - 6) / CH) - len(key) - 2
        wrapped = textwrap.wrap(val, room) or [""]
        lines += [(key, wrapped[0])] + [("", part) for part in wrapped[1:]]
    h = 1.36 * len(lines) + 1.6
    box(X0 + 1.8, y - h, MID - X0 - 3.6, h, HIT if "Q5157" in chunk else FLAT_TINT, FLAT, lw=1, r=0.8, z=2)
    for j, (key, val) in enumerate(lines):
        indent = X0 + 3 + CH * (len(key) + 2 if key else len("Description: "))
        if key:
            ax.text(X0 + 3, y - 1.4 - 1.36 * j, key + ":", ha="left", va="center", fontsize=6.9,
                    family=MONO, color=MUTED, zorder=3)
        ax.text(indent, y - 1.4 - 1.36 * j, val, ha="left", va="center", fontsize=6.9,
                family=MONO, color=INK, zorder=3)
    y -= h + 1.3

# right half: the complete table (Description column omitted for width)
ax.text(MID + 1.8, 74.6, f"Source: {SOURCE}", ha="left", fontsize=6.9, family=MONO, color=MUTED)
ax.text(MID + 1.8, 72.9, "Table 1: Drug preference and prior authorization", ha="left", fontsize=6.9,
        family=MONO, color=MUTED)
cols = [(0, "Preference", 0.0), (1, "PA", 9.4), (2, "Drug name", 12.4), (3, "HCPCS", 41.4)]
ty, row_h = 70.6, 2.55
for i, row in enumerate(pref):
    header = i == 0
    fill = "#eceae4" if header else (HIT if row[3] == "Q5157" else (TABLE_TINT if i % 2 else "white"))
    box(MID + 1.5, ty - row_h + 0.35, X1 - MID - 3, row_h - 0.2, fill, LINE if not header else MUTED,
        lw=0.6, r=0.3, z=2)
    for c, label, dx in cols:
        text = label if header else row[c]
        ax.text(MID + 2.2 + dx, ty - row_h / 2 + 0.25, text, ha="left", va="center", fontsize=6.2,
                family=MONO, color=INK, weight="bold" if header else "normal", zorder=3)
    ty -= row_h
ax.text(MID + 1.8, ty - 0.6, "PA = requires prior authorization.\n(+ Description column, omitted here for width)", ha="left", va="top",
        fontsize=6.6, family=MONO, color=MUTED)

# footer notes inside the window
ax.text((X0 + MID) / 2, Y0 + 6.5, f"~{flat_tokens} tokens  ·  4 rows from 2 tables",
        ha="center", fontsize=9.5, color=INK, weight="bold")
ax.text((X0 + MID) / 2, Y0 + 2.6, "Source/table header repeated 4x.\nThe preferred alternative never reaches the model.",
        ha="center", fontsize=8.3, color=MUTED, linespacing=1.3)
ax.text((MID + X1) / 2, Y0 + 6.5, f"~{table_tokens} tokens  ·  1 table, {len(pref) - 1} rows",
        ha="center", fontsize=9.5, color=INK, weight="bold")
ax.text((MID + X1) / 2, Y0 + 2.6, "Header once. Can answer \"what is preferred instead?\"\n(Zoledronic Acid: Preferred, no prior auth).",
        ha="center", fontsize=8.3, color=MUTED, linespacing=1.3)

# legend
box(3, 4, 3, 2.2, HIT, MUTED, lw=0.8, r=0.4)
ax.text(7, 5.1, "row that matched the question (Q5157)", va="center", fontsize=8.6, color=MUTED)
ax.text(177, 5.1, "Token counts are estimates (characters / 4).", ha="right", va="center", fontsize=8.6,
        color=MUTED)

for ext in ("png", "svg"):
    fig.savefig(HERE / f"context_window_flat_vs_table.{ext}", facecolor=SURFACE, bbox_inches="tight")
print(f"flat ~{flat_tokens} tokens, table ~{table_tokens} tokens -> context_window_flat_vs_table.png/.svg")
