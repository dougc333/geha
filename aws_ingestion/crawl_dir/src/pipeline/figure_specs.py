"""Deterministic semantic HTML for chart figures described by authored data specs.

A figure spec records what a chart shows (labels, values, colours, page position).
This module checks every spec against the immutable PDF text inside the figure's
box, renders standalone semantic HTML without a model, assembles the page from
native PDF text blocks plus the verified figures, and plugs into
``process_scanned_document`` through its segmenter/generator/reviewer hooks.
"""

from __future__ import annotations

import html
import json
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pymupdf

from .artifact_io import atomic_json, run_id

TOOL_ID = "authored_figure_spec_html"
WORKFLOW = "authored_figure_spec_semantic_html"
BAND_GAP_PT = 18
BULLET_GLYPHS = r"[■▪●•◦]"
PERCENT = re.compile(r"\d+(?:\.\d+)?%")
QUOTES = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-"})

FIGURE_CSS = """
:root { color-scheme: light; }
body { font-family: Arial, Helvetica, sans-serif; color: #2e2e38; background: #fff;
       margin: 0; padding: 24px 16px; line-height: 1.45; }
main { max-width: 960px; margin: 0 auto; }
h1 { font-size: 34px; font-weight: 400; margin: 0 0 8px; }
h2 { font-size: 22px; margin: 0 0 16px; }
h3 { font-size: 16px; margin: 20px 0 8px; }
p, li { font-size: 15px; }
.fig-group > header .kicker, figure.chart .kicker { font-size: 12px; font-weight: bold; margin: 0; }
.fig-group > header h2 { font-size: 19px; margin: 2px 0 16px; }
.fig-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 32px; }
figure.chart { margin: 28px 0; }
figure.chart figcaption .title { font-size: 19px; font-weight: bold; margin: 2px 0 6px; }
figure.chart .question { font-size: 14px; margin: 0 0 12px; }
figure.chart .notes { font-size: 12px; font-style: italic; color: #555; margin: 8px 0 0; }
.legend { list-style: none; margin: 8px 0 14px; padding: 6px 10px; border: 1px solid #ccc;
          display: inline-flex; flex-wrap: wrap; gap: 4px 16px; font-size: 13px; }
.legend li { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.sw { width: 10px; height: 10px; display: inline-block; flex: none; }
.pies { display: flex; flex-wrap: wrap; gap: 24px; justify-content: space-around; }
.pie { text-align: center; }
.pie h4 { margin: 0 0 4px; font-size: 15px; }
.pie svg { width: 220px; max-width: 100%; font-size: 9px; }
.hbars { display: grid; grid-template-columns: minmax(120px, 42%) 1fr; gap: 4px 10px;
         font-size: 12px; align-items: center; }
.hbars .lab { text-align: right; }
.hbars .grp { grid-column: 1 / -1; font-weight: bold; font-size: 14px; margin-top: 10px;
              border-bottom: 1px solid #2e2e38; }
.track { display: flex; height: 16px; }
.track.multi { flex-direction: column; height: auto; gap: 2px; }
.track .seg { display: flex; align-items: center; justify-content: center; overflow: hidden;
              white-space: nowrap; font-size: 11px; }
.bar-line { display: flex; align-items: center; gap: 4px; height: 12px; font-size: 11px; }
.bar-line .seg { height: 100%; }
.vbars { display: flex; gap: 28px; align-items: flex-end; justify-content: center;
         padding: 0 40px; }
.vcol { display: flex; flex-direction: column; align-items: center; width: 120px; }
.vstack { position: relative; width: 70px; height: 220px; display: flex;
          flex-direction: column-reverse; }
.vstack .seg { display: flex; align-items: center; justify-content: center; font-size: 12px; }
.vstack .out { position: absolute; left: 76px; font-size: 12px; white-space: nowrap; }
.vstack .bracket { position: absolute; border: 1px solid #2e2e38; width: 8px; font-size: 12px; }
.vstack .bracket.left { left: -14px; border-right: none; }
.vstack .bracket.right { right: -14px; border-left: none; }
.vstack .bracket span { position: absolute; top: 50%; transform: translateY(-50%); }
.vstack .bracket.left span { right: 12px; }
.vstack .bracket.right span { left: 12px; }
.vcol .cat { font-size: 12px; text-align: center; margin-top: 6px; }
.vcol .callout { font-size: 12px; margin-bottom: 4px; text-align: center; }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px;
         margin: 0; }
.stats div { text-align: center; }
.stats dd { font-size: 40px; font-weight: bold; margin: 0; }
.stats dt { font-size: 14px; }
table.data { border-collapse: collapse; margin: 14px 0 0; font-size: 12px; }
table.data caption { text-align: left; font-size: 12px; color: #555; padding-bottom: 4px; }
table.data th, table.data td { border: 1px solid #ddd; padding: 3px 8px; text-align: left; }
table.data td { text-align: right; }
table.data tbody th[scope=rowgroup] { background: #f2f2f2; }
table.heat td { text-align: center; }
.harveys { display: flex; flex-wrap: wrap; gap: 12px 20px; justify-content: center; }
.harvey { display: flex; flex-direction: column; align-items: center; width: 80px;
          font-size: 12px; text-align: center; }
svg.cycle { display: block; width: 280px; max-width: 100%; margin: 8px auto; }
.cycle-list { font-size: 14px; }
ol.steps { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px 28px;
           padding-left: 1.4em; }
ol.steps > li::marker { font-weight: bold; color: #b8a400; }
ol.steps h4 { margin: 0 0 4px; font-size: 16px; }
ol.steps ul { margin: 0; padding-left: 1.1em; }
.quotes { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; }
.quotes blockquote { margin: 0; padding: 8px 14px; border-left: 4px solid #FFE600; font-family: Georgia, serif; }
"""


# --------------------------------------------------------------------------- specs

def load_page_spec(specs_dir: Path, page: int) -> dict[str, Any] | None:
    path = specs_dir / f"page-{page:03d}.json"
    if not path.is_file():
        return None
    spec = json.loads(path.read_text(encoding="utf-8"))
    if spec.get("page") != page:
        raise ValueError(f"{path} declares page {spec.get('page')}, expected {page}")
    return spec


def spec_pages(specs_dir: Path) -> list[int]:
    return sorted(int(path.stem.split("-")[1]) for path in specs_dir.glob("page-*.json"))


def _value(item: Any) -> tuple[float | None, bool]:
    """Return (value, printed) for a spec value: number, null, or {value, printed}."""
    if item is None:
        return None, False
    if isinstance(item, dict):
        return float(item["value"]), bool(item.get("printed", True))
    return float(item), True


def _fmt(value: float) -> str:
    return f"{value:g}%"


def _figure_texts(figure: dict[str, Any]) -> list[str]:
    chart = figure["chart"]
    # A grouped figure's label/title belong to the shared group header, verified separately.
    heading = [] if figure.get("group") else [figure.get("label", ""), figure["title"]]
    texts = [*heading, figure.get("question", ""), figure.get("description", ""),
             *figure.get("notes", [])]
    texts += [series["name"] for series in chart.get("series", []) if series.get("printed", True)]
    texts += [entry["name"] for entry in chart.get("legend", [])]
    texts += [panel.get("label", "") for panel in chart.get("panels", [])]
    texts += [category["label"] for category in chart.get("categories", [])]
    texts += [category.get("group", "") for category in chart.get("categories", [])]
    texts += [note["text"] for note in chart.get("annotations", [])]
    texts += chart.get("columns", [])
    texts += [row["label"] for row in chart.get("rows", [])]
    texts += [chart.get("heading", ""), *chart.get("scale_labels", [])]
    texts += [item["label"] for item in chart.get("items", [])]
    texts += [bullet for item in chart.get("items", []) for bullet in item.get("bullets", [])]
    return [text for text in texts if text]


def _figure_values(figure: dict[str, Any]) -> list[tuple[float | None, bool]]:
    chart = figure["chart"]
    values: list[tuple[float | None, bool]] = []
    for collection in ("panels", "categories", "rows"):
        for entry in chart.get(collection, []):
            values.extend(_value(item) for item in entry["values"])
    values.extend(_value(item["value"]) for item in chart.get("items", []) if "value" in item)
    return values


# ---------------------------------------------------------------- verification

def native_box_evidence(page_pdf: Path, box_pt: list[float]) -> dict[str, Any]:
    """Native PDF words whose centre lies inside the figure box (PDF points)."""
    with pymupdf.open(page_pdf) as document:
        page = document[0]
        words = [
            word for word in page.get_text("words", sort=True)
            if box_pt[0] <= (word[0] + word[2]) / 2 <= box_pt[2]
            and box_pt[1] <= (word[1] + word[3]) / 2 <= box_pt[3]
        ]
    text = " ".join(str(word[4]) for word in words)
    return {
        "schema_version": 1,
        "method": "pymupdf_native_words_centred_in_box",
        "source_pdf": str(page_pdf),
        "box_pdf_points": box_pt,
        "word_count": len(words),
        "literal_text": text,
        "percent_tokens": PERCENT.findall(text),
        "authoritative": bool(words),
    }


def _words(text: str) -> list[str]:
    # The PDF text layer glues list bullet glyphs onto the first word ("■Ability").
    cleaned = re.sub(BULLET_GLYPHS, " ", text.translate(QUOTES)).casefold()
    return [word for word in (part.strip(".,:;()\"'?!") for part in cleaned.split()) if word]


def verify_figure(figure: dict[str, Any], evidence: dict[str, Any]) -> tuple[list[dict], list[str]]:
    """Return (errors, warnings) comparing a spec with native evidence in its box."""
    errors: list[dict[str, Any]] = []
    warnings: list[str] = []
    acknowledged = {item["text"] for item in figure.get("acknowledged_text_differences", [])}
    for item in figure.get("acknowledged_text_differences", []):
        warnings.append(f"Acknowledged text-layer difference for {item['text']!r}: {item['reason']}")
    raster = figure.get("value_evidence") == "raster_visual_read"
    evidence_words = set(_words(evidence["literal_text"]))
    for text in _figure_texts(figure):
        if text in acknowledged or (raster and text in figure.get("raster_texts", [])):
            continue
        missing = [word for word in _words(text) if word not in evidence_words]
        if missing:
            errors.append({
                "category": "missing_text",
                "source_evidence": f"Native PDF words in box: {len(evidence_words)} distinct",
                "html_evidence": text,
                "correction": f"Words not printed inside the figure box: {missing}",
            })
    if raster:
        warnings.append("Content read visually from a raster image; native PDF has no text for it.")
    else:
        spec_tokens = Counter(PERCENT.findall(" ".join(_figure_texts(figure))))
        spec_tokens.update(_fmt(value) for value, printed in _figure_values(figure)
                           if value is not None and printed)
        source_tokens = Counter(evidence["percent_tokens"])
        if spec_tokens != source_tokens:
            errors.append({
                "category": "chart_data",
                "source_evidence": f"Printed percentages: {sorted(source_tokens.elements())}",
                "html_evidence": f"Spec percentages: {sorted(spec_tokens.elements())}",
                "correction": (f"Missing from spec: {dict(source_tokens - spec_tokens)}; "
                               f"not printed in PDF: {dict(spec_tokens - source_tokens)}"),
            })
    estimated = [value for value, printed in _figure_values(figure)
                 if value is not None and not printed]
    if estimated:
        warnings.append(f"{len(estimated)} unlabeled values estimated by "
                        f"{figure['chart'].get('estimate_method', 'unspecified method')}.")
    chart = figure["chart"]
    if chart["type"] in {"pie"} or chart.get("mode") == "stacked_100":
        for entry in chart.get("panels", chart.get("categories", [])):
            total = sum(value for value, _ in map(_value, entry["values"]) if value is not None)
            if abs(total - 100) > 2:
                warnings.append(f"{entry.get('label', 'panel')}: values sum to {total:g}%")
    return errors, warnings


# -------------------------------------------------------------------- rendering

def _e(text: Any) -> str:
    return html.escape(str(text))


def _text_colour(fill: str) -> str:
    red, green, blue = (int(fill[index:index + 2], 16) for index in (1, 3, 5))
    return "#ffffff" if (0.299 * red + 0.587 * green + 0.114 * blue) < 140 else "#2e2e38"


def _legend(entries: list[dict[str, str]]) -> str:
    items = "".join(f'<li><span class="sw" style="background:{entry["color"]}"></span>'
                    f'{_e(entry["name"])}</li>' for entry in entries)
    return f'<ul class="legend" aria-hidden="true">{items}</ul>'


def _cell(item: Any) -> str:
    if isinstance(item, dict) and "text" in item:
        return _e(item["text"])
    value, printed = _value(item)
    if value is None:
        return "—"
    return _fmt(value) if printed else f"≈{_fmt(value)} (not printed)"


def _data_table(figure: dict[str, Any], header: list[str], rows: list[tuple[str, str, list[Any]]]) -> str:
    head = "".join(f'<th scope="col">{_e(name)}</th>' for name in header)
    body: list[str] = []
    group = None
    for row_group, label, values in rows:
        if row_group and row_group != group:
            group = row_group
            body.append(f'<tr><th scope="rowgroup" colspan="{len(header)}">{_e(group)}</th></tr>')
        cells = "".join(f"<td>{_cell(value)}</td>" for value in values)
        body.append(f'<tr><th scope="row">{_e(label)}</th>{cells}</tr>')
    caption = f'{_e(figure.get("label") or figure["title"])} data'
    return (f'<table class="data"><caption>{caption}</caption><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def _pie_svg(series: list[dict[str, str]], values: list[Any], title: str) -> str:
    import math

    numbers = [_value(item)[0] or 0.0 for item in values]
    total = sum(numbers) or 1.0
    parts, start = [], 0.0
    for entry, number in zip(series, numbers):
        if number <= 0:
            continue
        end = start + number / total

        def point(fraction: float, radius: float) -> tuple[float, float]:
            angle = 2 * math.pi * fraction - math.pi / 2
            return 100 + radius * math.cos(angle), 100 + radius * math.sin(angle)

        x0, y0 = point(start, 96)
        x1, y1 = point(end, 96)
        large = 1 if end - start > 0.5 else 0
        parts.append(f'<path d="M100,100 L{x0:.2f},{y0:.2f} A96,96 0 {large} 1 {x1:.2f},{y1:.2f} Z" '
                     f'fill="{entry["color"]}"><title>{_e(entry["name"])}: {_fmt(number)}</title></path>')
        lx, ly = point((start + end) / 2, 80 if number < 10 else 64)
        parts.append(f'<text x="{lx:.1f}" y="{ly:.1f}" fill="{_text_colour(entry["color"])}" '
                     f'text-anchor="middle" dominant-baseline="central">{_fmt(number)}</text>')
        start = end
    label = ", ".join(f"{entry['name']} {_fmt(number)}" for entry, number in zip(series, numbers))
    return (f'<svg viewBox="0 0 200 200" role="img" aria-label="{_e(title)}: {_e(label)}">'
            f'{"".join(parts)}</svg>')


def _render_pie(figure: dict[str, Any]) -> str:
    chart = figure["chart"]
    series = chart["series"]
    panels = []
    for panel in chart["panels"]:
        heading = f'<h4>{_e(panel["label"])}</h4>' if panel.get("label") else ""
        panels.append(f'<div class="pie">{heading}'
                      f'{_pie_svg(series, panel["values"], panel.get("label") or figure["title"])}</div>')
    header = ["Response", *[panel.get("label") or "Share" for panel in chart["panels"]]]
    rows = [("", entry["name"], [panel["values"][index] for panel in chart["panels"]])
            for index, entry in enumerate(series)]
    return (_legend(series) + f'<div class="pies">{"".join(panels)}</div>' +
            _data_table(figure, header, rows))


def _segment(entry: dict[str, str], item: Any, scale: float, horizontal: bool,
             show_label: bool = True) -> str:
    value, printed = _value(item)
    if not value:
        return ""
    size = f'{"width" if horizontal else "height"}:{value / scale * 100:.2f}%'
    text = _fmt(value) if printed and show_label else ""
    title = _fmt(value) if printed else f"≈{_fmt(value)} (not printed)"
    return (f'<span class="seg" style="{size};background:{entry["color"]};'
            f'color:{_text_colour(entry["color"])}" title="{_e(entry["name"])}: {title}">{text}</span>')


def _render_hbar(figure: dict[str, Any]) -> str:
    chart = figure["chart"]
    series = chart["series"]
    stacked = chart["mode"] == "stacked_100"
    scale = 100.0 if stacked else float(chart.get("axis_max") or max(
        _value(item)[0] or 0 for category in chart["categories"] for item in category["values"]
    ) * 1.12)
    rows, group = [], None
    for category in chart["categories"]:
        if category.get("group") and category["group"] != group:
            group = category["group"]
            rows.append(f'<div class="grp">{_e(group)}</div>')
        if stacked:
            segments = "".join(_segment(entry, item, scale, True, (_value(item)[0] or 0) >= 4)
                               for entry, item in zip(series, category["values"]))
            track = f'<div class="track">{segments}</div>'
        else:
            lines = []
            for entry, item in zip(series, category["values"]):
                colour = category.get("color", entry["color"])
                value, _ = _value(item)
                bar = _segment({**entry, "color": colour}, item, scale, True, False)
                lines.append(f'<div class="bar-line">{bar}<span>{_fmt(value)}</span></div>')
            track = f'<div class="track multi">{"".join(lines)}</div>'
        rows.append(f'<div class="lab">{_e(category["label"])}</div>{track}')
    legend = chart.get("legend") or (series if len(series) > 1 else [])
    header = [chart.get("category_heading", "Category"), *[entry["name"] for entry in series]]
    if chart.get("legend"):
        header.append("Highlight")
    table_rows = []
    for category in chart["categories"]:
        values = list(category["values"])
        if chart.get("legend"):
            note = next((entry["name"] for entry in chart["legend"]
                         if entry["color"] == category.get("color")), "")
            values.append({"text": note or "—"})
        table_rows.append((category.get("group", ""), category["label"], values))
    table = _data_table(figure, header, table_rows)
    return ((_legend(legend) if legend else "") +
            f'<div class="hbars" aria-hidden="true">{"".join(rows)}</div>' + table)


def _render_vbar(figure: dict[str, Any]) -> str:
    chart = figure["chart"]
    series = chart["series"]
    scale = 100.0
    columns = []
    for category in chart["categories"]:
        segments, outside, offset = [], [], 0.0
        for entry, item in zip(series, category["values"]):
            value, printed = _value(item)
            if not value:
                continue
            small = value < 6
            segments.append(_segment(entry, item, scale, False, not small))
            if small and printed:
                outside.append(f'<span class="out" style="bottom:{offset + value / 2:.1f}%;'
                               f'transform:translateY(50%)">{_fmt(value)}</span>')
            offset += value
        for note in chart.get("annotations", []):
            if note.get("category") != category["label"] or note["type"] != "bracket":
                continue
            names = [entry["name"] for entry in series]
            low, high = names.index(note["from"]), names.index(note["to"])
            numbers = [_value(item)[0] or 0 for item in category["values"]]
            bottom = sum(numbers[:low])
            height = sum(numbers[low:high + 1])
            outside.append(f'<span class="bracket {note.get("side", "left")}" '
                           f'style="bottom:{bottom:.1f}%;height:{height:.1f}%">'
                           f'<span>{_e(note["text"])}</span></span>')
        callouts = "".join(f'<div class="callout">{_e(note["text"])}</div>'
                           for note in chart.get("annotations", [])
                           if note["type"] == "callout" and note.get("category") == category["label"])
        columns.append(f'<div class="vcol">{callouts}<div class="vstack">{"".join(segments)}'
                       f'{"".join(outside)}</div><div class="cat">{_e(category["label"])}</div></div>')
    header = [chart.get("category_heading", "Category"), *[entry["name"] for entry in series]]
    rows = [("", category["label"], category["values"]) for category in chart["categories"]]
    notes = [note for note in chart.get("annotations", []) if note["type"] in {"bracket", "callout"}]
    annotation_list = ""
    if notes:
        annotation_list = ('<ul class="notes">' + "".join(
            f'<li>{_e(note.get("category", ""))}: {_e(note["text"])}'
            f'{" — " + _e(note["meaning"]) if note.get("meaning") else ""}</li>' for note in notes
        ) + "</ul>")
    return (_legend(list(reversed(series)) if chart.get("legend_reversed") else series) +
            f'<div class="vbars" aria-hidden="true">{"".join(columns)}</div>' +
            _data_table(figure, header, rows) + annotation_list)


def _heat_colour(value: float, low: float, high: float) -> str:
    middle = (low + high) / 2
    if value <= middle:
        fraction = (value - low) / ((middle - low) or 1)
        start, end = (240, 110, 110), (255, 255, 255)
    else:
        fraction = (value - middle) / ((high - middle) or 1)
        start, end = (255, 255, 255), (80, 190, 120)
    rgb = [round(a + (b - a) * fraction) for a, b in zip(start, end)]
    return "#%02X%02X%02X" % tuple(rgb)


def _render_heatmap(figure: dict[str, Any]) -> str:
    chart = figure["chart"]
    numbers = [_value(item)[0] for row in chart["rows"] for item in row["values"]]
    low, high = min(numbers), max(numbers)
    head = "".join(f'<th scope="col">{_e(name)}</th>' for name in chart["columns"])
    body = []
    for row in chart["rows"]:
        cells = "".join(
            f'<td style="background:{_heat_colour(_value(item)[0], low, high)}">{_cell(item)}</td>'
            for item in row["values"])
        body.append(f'<tr><th scope="row">{_e(row["label"])}</th>{cells}</tr>')
    scale = " → ".join(_e(label) for label in chart.get("scale_labels", []))
    return (f'<table class="data heat"><caption>{_e(figure.get("label") or figure["title"])} '
            f'(heat map: {scale})</caption><thead><tr><th scope="col">Benefit</th>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table>')


def _render_stats(figure: dict[str, Any]) -> str:
    chart = figure["chart"]
    heading = f'<p class="question"><strong>{_e(chart["heading"])}</strong></p>' if chart.get("heading") else ""
    items = "".join(f'<div><dd>{_fmt(_value(item["value"])[0])}</dd><dt>{_e(item["label"])}</dt></div>'
                    for item in chart["items"])
    return f'{heading}<dl class="stats">{items}</dl>'


def _harvey_svg(fill: float, colour: str) -> str:
    import math

    if fill >= 1:
        wedge = f'<circle cx="20" cy="20" r="15" fill="{colour}"/>'
    elif fill <= 0:
        wedge = ""
    else:
        angle = 2 * math.pi * fill - math.pi / 2
        x, y = 20 + 15 * math.cos(angle), 20 + 15 * math.sin(angle)
        wedge = (f'<path d="M20,20 L20,5 A15,15 0 {1 if fill > 0.5 else 0} 1 {x:.2f},{y:.2f} Z" '
                 f'fill="{colour}"/>')
    return (f'<svg viewBox="0 0 40 40" width="40" height="40" aria-hidden="true">'
            f'<circle cx="20" cy="20" r="15" fill="none" stroke="{colour}" stroke-width="2"/>{wedge}</svg>')


def _render_harvey(figure: dict[str, Any]) -> str:
    """Partly filled circles ("Harvey balls") rating each item on an ordinal scale."""
    chart = figure["chart"]
    colour = chart.get("color", "#FFE600")
    fractions = {0.25: "¼", 0.5: "½", 0.75: "¾", 1.0: "full"}
    cells = "".join(f'<div class="harvey">{_harvey_svg(item["fill"], colour)}'
                    f'<span>{_e(item["label"])}</span></div>' for item in chart["items"])
    low, high = chart["scale_labels"]
    legend = (f'<p class="notes">Scale: empty circle = {_e(low)}; full circle = {_e(high)}.</p>')
    rows = "".join(f'<tr><th scope="row">{_e(item["label"])}</th>'
                   f'<td>{fractions.get(item["fill"], item["fill"])} filled</td></tr>'
                   for item in chart["items"])
    method = chart.get("estimate_method", "")
    table = (f'<table class="data"><caption>{_e(figure.get("label") or figure["title"])} data '
             f'(circle fill{"; " + _e(method) if method else ""})</caption><thead><tr>'
             f'<th scope="col">{_e(chart.get("category_heading", "Area"))}</th>'
             f'<th scope="col">Relevance (circle fill)</th></tr></thead><tbody>{rows}</tbody></table>')
    return f'<div class="harveys">{cells}</div>{legend}{table}'


def _render_cycle(figure: dict[str, Any]) -> str:
    """Labelled wheel diagram: equal segments in reading order, plus a plain list."""
    import math

    chart = figure["chart"]
    labels = [item["label"] for item in chart["items"]]
    count = len(labels)
    parts = []
    for index, label in enumerate(labels):
        start = 2 * math.pi * index / count - math.pi / 2 + chart.get("start_offset", 0)
        end = start + 2 * math.pi / count
        x0, y0 = 100 + 90 * math.cos(start), 100 + 90 * math.sin(start)
        x1, y1 = 100 + 90 * math.cos(end), 100 + 90 * math.sin(end)
        middle = (start + end) / 2
        parts.append(f'<path d="M100,100 L{x0:.2f},{y0:.2f} A90,90 0 0 1 {x1:.2f},{y1:.2f} Z" '
                     f'fill="#F3F3F5" stroke="{chart.get("color", "#FFE600")}" stroke-width="4"/>')
        parts.append(f'<text x="{100 + 55 * math.cos(middle):.1f}" y="{100 + 55 * math.sin(middle):.1f}" '
                     f'text-anchor="middle" dominant-baseline="central" font-size="13">{_e(label)}</text>')
    svg = (f'<svg class="cycle" viewBox="0 0 200 200" role="img" '
           f'aria-label="{_e(figure["title"])}: {_e(", ".join(labels))}">{"".join(parts)}</svg>')
    items = "".join(f"<li>{_e(label)}</li>" for label in labels)
    return f'{svg}<ul class="cycle-list">{items}</ul>'


def _render_steps(figure: dict[str, Any]) -> str:
    """Numbered steps/stages, each with a heading and bullet points."""
    steps = []
    for item in figure["chart"]["items"]:
        bullets = "".join(f"<li>{_e(bullet)}</li>" for bullet in item.get("bullets", []))
        steps.append(f'<li value="{int(item["number"])}"><h4>{_e(item["label"])}</h4>'
                     f'<ul>{bullets}</ul></li>')
    return f'<ol class="steps">{"".join(steps)}</ol>'


def _render_quotes(figure: dict[str, Any]) -> str:
    """Pull-quote panel whose PDF text blocks overlap and cannot be read in order."""
    quotes = "".join(f'<blockquote><p>{_e(item["label"])}</p></blockquote>'
                     for item in figure["chart"]["items"])
    return f'<div class="quotes">{quotes}</div>'


RENDERERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "pie": _render_pie, "hbar": _render_hbar, "vbar": _render_vbar,
    "heatmap": _render_heatmap, "stats": _render_stats, "harvey": _render_harvey,
    "cycle": _render_cycle, "quotes": _render_quotes, "steps": _render_steps,
}


def render_figure(figure: dict[str, Any], *, in_group: bool = False) -> str:
    """Render one figure as a self-contained <figure> fragment."""
    body = RENDERERS[figure["chart"]["type"]](figure)
    kicker = "" if in_group or not figure.get("label") else f'<p class="kicker">{_e(figure["label"])}</p>'
    title = "" if in_group else f'<p class="title">{_e(figure["title"])}</p>'
    question = (f'<p class="question"><strong>QUESTION:</strong> {_e(figure["question"])}</p>'
                if figure.get("question") else "")
    description = (f'<p class="description">{_e(figure["description"])}</p>'
                   if figure.get("description") else "")
    notes = "".join(f'<p class="notes">{_e(note)}</p>' for note in figure.get("notes", []))
    return (f'<figure class="chart" id="{_e(figure["id"])}" data-figure="{_e(figure.get("label", ""))}">'
            f'<figcaption>{kicker}{title}{question}{description}</figcaption>{body}{notes}</figure>')


def standalone_html(title: str, body: str) -> str:
    return (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<title>{_e(title)}</title>\n<style>{FIGURE_CSS}</style>\n</head>\n'
            f'<body>\n<main>\n{body}\n</main>\n</body>\n</html>\n')


# ------------------------------------------------------------- page assembly

def _block_html(block: dict[str, Any]) -> tuple[str, str]:
    """Classify one PyMuPDF text block; return (kind, html)."""
    spans = [span for line in block["lines"] for span in line["spans"]]
    size = max(span["size"] for span in spans)
    bold = all("Bold" in span["font"] or span["flags"] & 16 for span in spans if span["text"].strip())
    lines = []
    for line in block["lines"]:
        parts = []
        for span in line["spans"]:
            text = span["text"]
            if not text.strip():
                parts.append(text)
                continue
            escaped = _e(text)
            if ("Bold" in span["font"] or span["flags"] & 16) and not bold:
                escaped = f"<strong>{escaped}</strong>"
            elif "Italic" in span["font"] or span["flags"] & 2:
                escaped = f"<em>{escaped}</em>"
            parts.append(escaped)
        lines.append("".join(parts).strip())
    joined = ""
    for line in lines:
        if not line:
            continue
        if joined.endswith("-"):
            joined += line
        else:
            joined += (" " if joined else "") + line
    joined = re.sub(r"</strong>\s*<strong>", " ", joined).replace("\t", " ").strip()
    plain = re.sub(r"<[^>]+>", "", joined)
    if plain.startswith("■"):
        return "li", joined.replace("■", "", 1).strip()
    if size >= 24:
        return "h1", joined
    if size >= 14:
        return "h2", re.sub(r"</?strong>", "", joined)
    if bold and size >= 9.5 and len(plain) < 90 and not plain.endswith("."):
        return "h3", joined
    return "p", joined


def _split_by_font_size(block: dict[str, Any]) -> list[dict[str, Any]]:
    """Split a block whose lines change font size (e.g. 'Key finding 1' + its subtitle)."""
    runs: list[list[dict[str, Any]]] = []
    previous = None
    for line in block["lines"]:
        sizes = [span["size"] for span in line["spans"] if span["text"].strip()]
        if not sizes:
            if runs:
                runs[-1].append(line)
            continue
        size = round(max(sizes))
        if previous is None or abs(size - previous) > 1:
            runs.append([])
        runs[-1].append(line)
        previous = size
    return [{**block, "lines": lines,
             "bbox": [min(line["bbox"][0] for line in lines), min(line["bbox"][1] for line in lines),
                      max(line["bbox"][2] for line in lines), max(line["bbox"][3] for line in lines)]}
            for lines in runs]


def _is_running_footer(block: dict[str, Any], page_height: float) -> bool:
    text = " ".join(span["text"] for line in block["lines"] for span in line["spans"]).strip()
    return block["bbox"][1] > page_height - 40 and (
        "Workforce Benefits Study" in text or text.isdigit())


def _inside(bbox: list[float], box: list[float]) -> bool:
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def assemble_page_html(page_pdf: Path, spec: dict[str, Any], figure_html: dict[str, str]) -> str:
    """Native text blocks outside figure boxes, in column-aware order, plus figures."""
    groups = spec.get("groups", {})
    boxes = [figure["box_pt"] for figure in spec["figures"]]
    boxes += [group["box_pt"] for group in groups.values()]
    with pymupdf.open(page_pdf) as document:
        page = document[0]
        width, height = page.rect.width, page.rect.height
        blocks = [block for block in page.get_text("dict", sort=False)["blocks"]
                  if block["type"] == 0 and block["bbox"][1] >= 0]
    items: list[dict[str, Any]] = []
    for block in blocks:
        text = "".join(span["text"] for line in block["lines"] for span in line["spans"]).strip()
        if not text or _is_running_footer(block, height) or any(_inside(block["bbox"], box) for box in boxes):
            continue
        for part in _split_by_font_size(block):
            kind, markup = _block_html(part)
            items.append({"bbox": list(part["bbox"]), "kind": kind, "html": markup})
    placed_groups: set[str] = set()
    for figure in spec["figures"]:
        group_id = figure.get("group")
        if group_id:
            if group_id in placed_groups:
                continue
            placed_groups.add(group_id)
            group = groups[group_id]
            members = [item for item in spec["figures"] if item.get("group") == group_id]
            inner = "".join(figure_html[item["id"]] for item in members)
            markup = (f'<section class="fig-group" id="{_e(group_id)}"><header>'
                      f'<p class="kicker">{_e(group["label"])}</p><h2>{_e(group["title"])}</h2></header>'
                      f'<div class="fig-grid">{inner}</div></section>')
            bbox = [min(item["box_pt"][0] for item in members), group["box_pt"][1],
                    max(item["box_pt"][2] for item in members), max(item["box_pt"][3] for item in members)]
            items.append({"bbox": bbox, "kind": "figure", "html": markup})
        else:
            items.append({"bbox": figure["box_pt"], "kind": "figure", "html": figure_html[figure["id"]]})
    middle = width / 2

    def column(bbox: list[float]) -> int:
        if bbox[2] <= middle + 12:
            return 0
        if bbox[0] >= middle - 12:
            return 1
        return -1

    # A band is a horizontal stripe read column by column; it ends at a full-width item
    # or a vertical gap wider than paragraph spacing (e.g. text above side-by-side figures).
    bands: list[list[dict[str, Any]]] = []
    bottom = -1.0
    for item in sorted(items, key=lambda entry: (entry["bbox"][1], entry["bbox"][0])):
        full = column(item["bbox"]) == -1
        if (not bands or full or item["bbox"][1] > bottom + BAND_GAP_PT or
                any(column(other["bbox"]) == -1 for other in bands[-1])):
            bands.append([])
            bottom = item["bbox"][3]
        bands[-1].append(item)
        bottom = max(bottom, item["bbox"][3])
    ordered = [item for band in bands
               for item in sorted(band, key=lambda entry: (max(column(entry["bbox"]), 0), entry["bbox"][1]))]
    parts: list[str] = []
    in_list = False
    bullet_x0 = 0.0
    for item in ordered:
        if item["kind"] == "li":
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{item['html']}</li>")
            bullet_x0 = item["bbox"][0]
            continue
        # A wrapped bullet line is its own PDF block, indented past the bullet glyph.
        if in_list and item["kind"] == "p" and item["bbox"][0] >= bullet_x0 + 8:
            parts[-1] = parts[-1][:-5] + " " + item["html"] + "</li>"
            continue
        if in_list:
            parts.append("</ul>")
            in_list = False
        if item["kind"] == "figure":
            parts.append(item["html"])
        elif (item["kind"] == "p" and parts and parts[-1].startswith("<p>")
              and not re.search(r"[.?!:”\"’)]\s*(</\w+>)?</p>$", parts[-1])):
            # A paragraph without terminal punctuation continues in the next column block.
            parts[-1] = parts[-1][:-4] + " " + item["html"] + "</p>"
        else:
            parts.append(f"<{item['kind']}>{item['html']}</{item['kind']}>")
    if in_list:
        parts.append("</ul>")
    title = spec.get("page_title") or f"Page {spec['page']}"
    return standalone_html(title, "\n".join(parts))


# ------------------------------------------------------------ pipeline hooks

def _page_number(path: Path) -> int:
    match = re.fullmatch(r"page-(\d+)", path.parent.name)
    if not match:
        raise ValueError(f"Cannot infer page number from {path}")
    return int(match.group(1))


def make_spec_segmenter(specs_dir: Path) -> Callable[[Path, Path, str, str], dict[str, Any]]:
    """page_segmenter hook: regions come from the authored spec, not a model."""
    from PIL import Image, ImageDraw

    def segment(source_png: Path, output_dir: Path, _model: str, _hint: str) -> dict[str, Any]:
        page = _page_number(source_png)
        spec = load_page_spec(specs_dir, page)
        if spec is None:
            raise FileNotFoundError(f"No figure spec for page {page} in {specs_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(source_png.with_name("source.pdf")) as document:
            page_width, page_height = document[0].rect.width, document[0].rect.height
        regions = []
        with Image.open(source_png) as opened:
            image = opened.convert("RGB")
            sx, sy = image.width / page_width, image.height / page_height
            overlay = image.copy()
            draw = ImageDraw.Draw(overlay)
            for index, figure in enumerate(spec["figures"], start=1):
                x0, y0, x1, y1 = figure["box_pt"]
                pixel_box = [round(x0 * sx), round(y0 * sy), round(x1 * sx), round(y1 * sy)]
                filename = f"figure-{index:02d}-{figure['id']}.png"
                image.crop(tuple(pixel_box)).save(output_dir / filename)
                draw.rectangle(pixel_box, outline=(34, 211, 238), width=4)
                draw.text((pixel_box[0] + 6, pixel_box[1] + 6), f"{index}: {figure['id']}",
                          fill=(8, 47, 73))
                regions.append({
                    "id": figure["id"], "kind": figure["chart"].get("kind", "chart"),
                    "title": " ".join(filter(None, [figure.get("label"), figure["title"]])),
                    "reading_order": index,
                    "x1": round(x0 / page_width * 1000), "y1": round(y0 / page_height * 1000),
                    "x2": round(x1 / page_width * 1000), "y2": round(y1 / page_height * 1000),
                    "label": f"{index}: {figure['id']}", "pixel_box": pixel_box,
                    "box_pdf_points": figure["box_pt"], "image": filename,
                })
            overlay.save(output_dir / "figures-overlay.png")
        result = {
            "reason": f"Regions declared by authored figure spec page-{page:03d}.json",
            "regions": regions,
            "page_type": "chart_figure_regions",
            "segmentation_recommended": bool(regions),
            "coordinate_system": "normalized_0_1000",
            "source_image": str(source_png),
            "overlay": "figures-overlay.png",
            "tool_id": TOOL_ID,
            "spec": str(specs_dir / f"page-{page:03d}.json"),
            "spec_author": spec.get("author"),
        }
        atomic_json(output_dir / "regions.json", result)
        return result

    return segment


def _render_png(html_path: Path, png_path: Path) -> float:
    from .scanned_ingestion import _render_html

    started = time.perf_counter()
    _render_html(html_path, png_path)
    return round((time.perf_counter() - started) * 1000, 1)


def make_spec_generator(
    specs_dir: Path,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> Callable[[Path, dict[str, Any], Path, str], str]:
    """segmented_generator hook: verify + render each figure, then assemble the page."""
    emit = event_sink or (lambda _event: None)

    def generate(source_png: Path, segmentation: dict[str, Any], segment_dir: Path, _model: str) -> str:
        page = _page_number(source_png)
        spec = load_page_spec(specs_dir, page)
        page_pdf = source_png.with_name("source.pdf")
        batch_path = segment_dir / "batch.json"
        batch: dict[str, Any] = {
            "schema_version": 1, "workflow": WORKFLOW, "model": spec.get("author"),
            "spec": segmentation.get("spec"),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "max_iterations_per_figure": 1,
            "completion_requirement": "every printed percentage and label in the spec matches "
                                      "native PDF text inside the figure box",
            "status": "running", "figures": [],
            "summary": {"figure_count": len(spec["figures"]), "passed": 0, "failed": 0,
                        "total_iterations": 0, "remaining_errors": 0},
        }
        figure_html: dict[str, str] = {}
        group_errors: dict[str, list[dict[str, Any]]] = {}
        for group_id, group in spec.get("groups", {}).items():
            group_words = set(_words(native_box_evidence(page_pdf, group["box_pt"])["literal_text"]))
            missing = [word for word in _words(f"{group['label']} {group['title']}")
                       if word not in group_words]
            group_errors[group_id] = [{
                "category": "missing_text", "source_evidence": "Native PDF words in group header box",
                "html_evidence": group["title"], "correction": f"Words not printed: {missing}",
            }] if missing else []
        for index, (figure, region) in enumerate(zip(spec["figures"], segmentation["regions"]), start=1):
            output = segment_dir / f"figure-{index:02d}"
            output.mkdir(parents=True, exist_ok=True)
            evidence = native_box_evidence(page_pdf, figure["box_pt"])
            atomic_json(output / "native-evidence.json", evidence)
            errors, warnings = verify_figure(figure, evidence)
            errors += group_errors.pop(figure.get("group", ""), [])
            fragment = render_figure(figure)
            figure_html[figure["id"]] = render_figure(figure, in_group=bool(figure.get("group")))
            document = standalone_html(figure.get("label") or figure["title"], fragment)
            for name in ("iteration-01.html", "final.html"):
                (output / name).write_text(document, encoding="utf-8")
            latency = _render_png(output / "iteration-01.html", output / "iteration-01.png")
            status = "failed" if errors else "passed"
            batch["figures"].append({
                "figure": index, "id": figure["id"], "kind": region["kind"], "title": region["title"],
                "source_png": region["image"], "bounding_box": region["pixel_box"],
                "output_directory": output.name,
                "native_evidence": f"{output.name}/native-evidence.json",
                "native_evidence_word_count": evidence["word_count"],
                "value_evidence": figure.get("value_evidence", "native_pdf_text"),
                "status": status,
                "iterations": [{
                    "iteration": 1, "html": f"{output.name}/iteration-01.html",
                    "rendered_png": f"{output.name}/iteration-01.png",
                    "verdict": "mismatch" if errors else "match", "error_count": len(errors),
                    "errors": errors, "warnings": warnings, "render_latency_ms": latency,
                }],
                **({"remaining_errors": errors} if errors else {}),
                "selected_iteration": 1, "selected_error_count": len(errors),
                "final_html": f"{output.name}/final.html",
                "final_rendered_png": f"{output.name}/iteration-01.png",
            })
            batch["summary"][status] += 1
            batch["summary"]["total_iterations"] += 1
            batch["summary"]["remaining_errors"] += len(errors)
            atomic_json(batch_path, batch)
            emit({"type": "figure_segment_review", "page": page, "figure": index,
                  "title": region["title"], "iteration": 1,
                  "verdict": "mismatch" if errors else "match", "errors": errors,
                  "warnings": warnings})
        batch["status"] = "passed" if batch["summary"]["failed"] == 0 else "failed"
        batch["completed_at"] = datetime.now(timezone.utc).isoformat()
        atomic_json(batch_path, batch)
        emit({"type": "figure_segments_complete", "page": page, "status": batch["status"],
              "figure_count": batch["summary"]["figure_count"],
              "iterations": batch["summary"]["total_iterations"], "batch": str(batch_path)})
        return assemble_page_html(page_pdf, spec, figure_html)

    return generate


def spec_reviewer(source_png: Path, _html_png: Path, candidate: str, _model: str) -> dict[str, Any]:
    """reviewer hook: page passes when every figure verified and appears in the page HTML."""
    batch = json.loads((source_png.parent / "segments" / "batch.json").read_text(encoding="utf-8"))
    errors = [error for figure in batch["figures"] for error in figure.get("remaining_errors", [])]
    for figure in batch["figures"]:
        if f'id="{figure["id"]}"' not in candidate:
            errors.append({"category": "missing_figure", "source_evidence": figure["title"],
                           "html_evidence": "absent", "correction": "Insert the verified figure HTML."})
    return {"verdict": "match" if not errors else "mismatch", "errors": errors}


def process_document_with_figure_specs(
    *, root: Path, family: str, document: str, document_version: str, specs_dir: Path,
    plan_year: int | None = None, requested_run_id: str | None = None,
    event_sink: Callable[[dict[str, Any]], None] | None = None,
) -> Path:
    """Run the canonical ingestion with authored figure specs for every spec page."""
    from .scanned_ingestion import process_scanned_document

    def unused_generator(_source_png: Path, _model: str) -> str:
        raise RuntimeError("Every visual page must have a figure spec")

    specs_dir = specs_dir.resolve()
    return process_scanned_document(
        root=root, family=family, document=document, document_version=document_version,
        plan_year=plan_year, model=TOOL_ID, max_corrections=0,
        requested_run_id=requested_run_id or f"{run_id()}-figspec",
        initial_generator=unused_generator,
        reviewer=spec_reviewer,
        page_segmenter=make_spec_segmenter(specs_dir),
        segmented_generator=make_spec_generator(specs_dir),
        additional_visual_pages=spec_pages(specs_dir),
        event_sink=event_sink,
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--family", required=True)
    parser.add_argument("--document", required=True, help="PDF path relative to raw/<family>")
    parser.add_argument("--document-version", required=True)
    parser.add_argument("--specs", type=Path, required=True, help="Directory of page-NNN.json specs")
    parser.add_argument("--plan-year", type=int)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    run_dir = process_document_with_figure_specs(
        root=args.root, family=args.family, document=args.document,
        document_version=args.document_version, specs_dir=args.specs,
        plan_year=args.plan_year, requested_run_id=args.run_id,
        event_sink=lambda event: print(json.dumps(event), flush=True),
    )
    print(run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
