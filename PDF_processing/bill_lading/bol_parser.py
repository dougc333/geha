"""Spec-driven bill-of-lading parser: one generic interpreter, one JSON spec per layout.

The spec (bill_of_lading_spec.json) describes a layout - blocks, field labels used as anchors,
value patterns, repeated cargo groups and cross-field rules - and never any one document's
values. This module reads OCR text per block (from any engine), extracts typed fields, and
validates them, so a misread is flagged instead of passed through.

    python bol_parser.py parse  --claude-dir claude_run_*/claude          # Claude structured cells
    python bol_parser.py parse  --text-dir block8_ocr_run_*/ocr           # plain text per block
    python bol_parser.py evaluate                                          # all saved engines vs gold

Extraction per field, in order:
  1. label anchor: text after the field's label, up to the next known label (or line end);
     this also splits OCR output where label and value run together ("VOYAGEMERIDIAN ...")
  2. if the field has a pattern, keep the part of that text that matches it
  3. otherwise search the whole block for the pattern (method "pattern_search")
Every value is then checked against its pattern/type; failures become errors, not silent output.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_SPEC = HERE / "bill_of_lading_spec.json"
DEFAULT_GOLD = HERE / "bill_of_lading_gold_fields.json"
WORDS = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5, "SIX": 6}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"\+\d[\d ()-]{6,}\d")


# ------------------------------------------------------------------ text helpers --

def clean(text: str) -> str:
    """Normalize quotes and spacing so labels match across engines."""
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    text = text.replace('"', "'")
    return re.sub(r"[ \t]+", " ", text)


def label_regex(field: dict) -> re.Pattern:
    if field.get("label_re"):
        source = field["label_re"]
    else:
        # flexible whitespace: "B/L NO." also matches Tesseract's "B/LNO."
        source = r"\s*".join(re.escape(part) for part in field["label"].split())
    return re.compile(source, re.IGNORECASE)


def collapse(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" |:;,\n")


# ------------------------------------------------------------------ checks --

def iso6346_ok(code: str) -> tuple[bool, str]:
    """ISO 6346 container number: 3-letter owner + category U/J/Z + 6 digits + check digit."""
    if not re.fullmatch(r"[A-Z]{4}\d{7}", code):
        return False, "not 4 letters + 7 digits"
    if code[3] not in "UJZ":
        return False, f"category letter {code[3]!r} is not U/J/Z (not a registered ISO 6346 number)"
    values, n = {}, 10
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        if n % 11 == 0:
            n += 1
        values[letter] = n
        n += 1
    total = sum((values[c] if c.isalpha() else int(c)) * 2 ** i for i, c in enumerate(code[:10]))
    check = total % 11 % 10
    return check == int(code[10]), "" if check == int(code[10]) else f"check digit should be {check}"


CHECKS = {"iso6346": iso6346_ok}


def cast(value: str, kind: str) -> Any:
    if kind == "int":
        return int(value)
    if kind == "date":
        return date.fromisoformat(value).isoformat()
    return value


# ------------------------------------------------------------------ extraction --

def all_labels(block: dict) -> list[re.Pattern]:
    patterns = [label_regex(f) for f in block["fields"] if f.get("label")]
    patterns += [re.compile(r"\s*".join(map(re.escape, c.split())), re.I) for c in block.get("constants", [])]
    return patterns


def after_label(text: str, field: dict, labels: list[re.Pattern]) -> str | None:
    match = label_regex(field).search(text)
    if not match:
        return None
    rest = text[match.end():]
    stops = [m.start() for p in labels for m in [p.search(rest)] if m and m.start() > 0]
    if field.get("line"):
        stops.append(rest.find("\n", 1) if rest.find("\n", 1) > 0 else len(rest))
    blank = re.search(r"\n\s*\n", rest)
    if blank:
        stops.append(blank.start())
    end = min(stops) if stops else len(rest)
    return rest[:end].strip(" :\n|")


def party_parts(raw: str) -> dict[str, str | None]:
    lines = [collapse(line) for line in raw.splitlines() if collapse(line)]
    body = [line for line in lines if not EMAIL_RE.search(line) and not PHONE_RE.search(line)]
    phone = PHONE_RE.search(raw)
    email = EMAIL_RE.search(raw)
    return {
        "name": body[0] if body else None,
        "address": body[1] if len(body) > 1 else None,
        "phone": collapse(phone.group(0)) if phone else None,
        "email": email.group(0) if email else None,
    }


def extract_field(text: str, field: dict, labels: list[re.Pattern]) -> dict[str, Any]:
    pattern = field.get("pattern")
    raw, method = None, None
    if field.get("label"):
        raw = after_label(text, field, labels)
        method = "label" if raw else None
    if field.get("kind") == "party":
        return {"value": party_parts(raw) if raw else None, "method": method, "errors": [] if raw else ["missing"]}
    if field.get("find"):
        match = re.search(field["find"], text)
        raw, method = (match.group(0), "find") if match else (None, None)
    if raw and pattern:
        whole = collapse(raw)
        if not re.fullmatch(pattern, whole):
            inner = re.search(pattern, whole)
            raw, method = (inner.group(0), "label+pattern") if inner else (None, None)
    if raw is None and pattern:
        inner = re.search(rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])", text)
        raw, method = (inner.group(0), "pattern_search") if inner else (None, None)
    if raw is None or not collapse(raw):
        return {"value": None, "method": None, "errors": ["missing"]}
    value, errors = collapse(raw), []
    if pattern and not re.fullmatch(pattern, value):
        errors.append(f"{value!r} doesn't match {pattern}")
    try:
        value = cast(value, field.get("type", "string"))
    except ValueError as error:
        errors.append(f"not a valid {field.get('type')}: {error}")
    return {"value": value, "method": method, "errors": errors}


def extract_group(text: str, group: dict) -> dict[str, Any]:
    columns = {f["name"]: re.findall(f["find"], text) for f in group["fields"]}
    count = max((len(v) for v in columns.values()), default=0)
    errors = []
    if any(len(v) != count for v in columns.values()):
        errors.append("field counts differ across containers: "
                      + ", ".join(f"{k}={len(v)}" for k, v in columns.items()))
    items = []
    for i in range(count):
        item, item_errors = {}, []
        for f in group["fields"]:
            values = columns[f["name"]]
            if i >= len(values):
                item[f["name"]] = None
                item_errors.append(f"{f['name']}: missing")
                continue
            value = collapse(values[i])
            try:
                item[f["name"]] = cast(value, f.get("type", "string"))
            except ValueError as error:
                item[f["name"]] = value
                item_errors.append(f"{f['name']}: {error}")
            if f.get("check"):
                ok, why = CHECKS[f["check"]](value)
                if not ok:
                    item_errors.append(f"{f['name']} {value}: {why} (warning)")
        items.append({"fields": item, "errors": item_errors})
    return {"items": items, "errors": errors}


def apply_rules(spec: dict, fields: dict, groups: dict) -> list[dict]:
    results = []
    for rule in spec["rules"]:
        ok, detail = None, ""
        if rule["check"] == "group_sum_equals":
            values = [item["fields"].get(rule["field"]) for item in groups[rule["group"]]["items"]]
            total = fields.get(rule["equals"], {}).get("value")
            if all(isinstance(v, int) for v in values) and isinstance(total, int):
                ok, detail = sum(values) == total, f"{' + '.join(map(str, values))} vs {total}"
        elif rule["check"] == "words_match_digit":
            value = fields.get(rule["field"], {}).get("value") or ""
            match = re.fullmatch(r"([A-Z]+) \((\d)\)", value)
            if match:
                ok, detail = WORDS.get(match.group(1)) == int(match.group(2)), value
        elif rule["check"] == "valid_date":
            value = fields.get(rule["field"], {}).get("value")
            ok = value is not None and not fields[rule["field"]]["errors"]
            detail = str(value)
        results.append({"rule": rule["name"], "passed": ok, "detail": detail, "message": rule["message"]})
    return results


def parse(blocks_text: dict[int, str], spec: dict) -> dict[str, Any]:
    fields, constants = {}, {}
    for block in spec["blocks"]:
        text = clean(blocks_text.get(block["block"], ""))
        labels = all_labels(block)
        for constant in block.get("constants", []):
            constants[constant] = bool(re.search(r"\s*".join(map(re.escape, constant.split())), text, re.I))
        for field in block["fields"]:
            fields[field["name"]] = extract_field(text, field, labels)
    groups = {g["name"]: extract_group(clean(blocks_text.get(g["block"], "")), g) for g in spec["groups"]}
    rules = apply_rules(spec, fields, groups)
    errors = [f"{name}: {e}" for name, r in fields.items() for e in r["errors"]]
    errors += [f"{name}: {e}" for name, g in groups.items() for e in g["errors"]]
    errors += [f"{name}[{i}].{e}" for name, g in groups.items() for i, item in enumerate(g["items"]) for e in item["errors"]]
    errors += [f"rule {r['rule']}: {r['message']} ({r['detail']})" for r in rules if r["passed"] is False]
    return {
        "template": spec["template"],
        "template_match": sum(constants.values()) / max(len(constants), 1),
        "fields": {name: r["value"] for name, r in fields.items()},
        "methods": {name: r["method"] for name, r in fields.items()},
        "containers": [item["fields"] for item in groups["containers"]["items"]],
        "rules": rules,
        "errors": errors,
        "valid": not [e for e in errors if "(warning)" not in e],
    }


# ------------------------------------------------------------------ inputs --

def load_claude_dir(directory: Path) -> dict[int, str]:
    """Claude runs save structured cells; keep each heading above its content."""
    blocks = {}
    for path in sorted(directory.glob("block_*.json")):
        data = json.loads(path.read_text())
        cells = data.get("structured_cells") or []
        text = "\n\n".join(f"{c.get('heading', '')}\n{c.get('content', '')}".strip() for c in cells)
        blocks[int(data["block"])] = text or data.get("text", "")
    return blocks


def load_text_dir(directory: Path) -> dict[int, str]:
    return {int(re.search(r"(\d+)", p.stem).group(1)): p.read_text() for p in sorted(directory.glob("block_*.txt"))}


# ------------------------------------------------------------------ evaluation --

def flatten(fields: dict, containers: list[dict]) -> dict[str, Any]:
    flat = {}
    for name, value in fields.items():
        if isinstance(value, dict):
            flat.update({f"{name}.{k}": v for k, v in value.items()})
        else:
            flat[name] = value
    for i, item in enumerate(containers):
        flat.update({f"containers[{i}].{k}": v for k, v in item.items()})
    return flat


def score(result: dict, gold: dict) -> dict[str, Any]:
    got = flatten(result["fields"], result["containers"])
    want = flatten(gold["fields"], gold["containers"])
    error_text = " ".join(result["errors"])
    rows = []
    for key, expected in want.items():
        value = got.get(key)
        status = "correct" if value == expected else ("missing" if value is None else "wrong")
        top = key.split(".")[0].split("[")[0]
        flagged = top in error_text or key.split(".")[-1] in error_text
        rows.append({"field": key, "expected": expected, "got": value, "status": status,
                     "flagged": status != "correct" and flagged})
    bad = [r for r in rows if r["status"] != "correct"]
    return {
        "correct": sum(r["status"] == "correct" for r in rows),
        "total": len(rows),
        "wrong": sum(r["status"] == "wrong" for r in rows),
        "missing": sum(r["status"] == "missing" for r in rows),
        "flagged_by_spec": sum(r["flagged"] for r in bad),
        "silent_errors": [r for r in bad if not r["flagged"]],
        "rows": rows,
    }


def evaluate(spec: dict, gold: dict) -> dict[str, Any]:
    engines = {}
    claude = sorted(HERE.glob("claude_run_*/claude"))
    if claude:
        engines["Claude Opus 5.5"] = load_claude_dir(claude[-1])
    tesseract = sorted(HERE.glob("block8_ocr_run_*/ocr"))
    if tesseract:
        engines["Tesseract 5.5.1"] = load_text_dir(tesseract[-1])
    report = {}
    for name, blocks in engines.items():
        result = parse(blocks, spec)
        report[name] = {"result": result, "score": score(result, gold)}
    return report


def markdown(report: dict) -> str:
    lines = ["| Engine | Fields correct | Wrong | Missing | Bad fields flagged by spec | Silent errors | Spec rules | Valid B/L? |",
             "|---|---:|---:|---:|---:|---:|---|---|"]
    for name, entry in report.items():
        s, r = entry["score"], entry["result"]
        bad = s["wrong"] + s["missing"]
        rules = ", ".join(f"{x['rule']} {'✓' if x['passed'] else ('✗' if x['passed'] is False else '–')}" for x in r["rules"])
        lines.append(f"| {name} | {s['correct']}/{s['total']} | {s['wrong']} | {s['missing']} | "
                     f"{s['flagged_by_spec']}/{bad} | {len(s['silent_errors'])} | {rules} | {'yes' if r['valid'] else 'no'} |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("parse", "evaluate"))
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--gold", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--claude-dir", type=Path)
    parser.add_argument("--text-dir", type=Path)
    parser.add_argument("--out", type=Path, help="write JSON here")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    if args.command == "parse":
        if not (args.claude_dir or args.text_dir):
            parser.error("give --claude-dir or --text-dir")
        blocks = load_claude_dir(args.claude_dir) if args.claude_dir else load_text_dir(args.text_dir)
        output = parse(blocks, spec)
    else:
        output = evaluate(spec, json.loads(args.gold.read_text()))
        print(markdown(output))
    text = json.dumps(output, indent=2, ensure_ascii=False, default=str)
    if args.out:
        args.out.write_text(text + "\n")
    elif args.command == "parse":
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
