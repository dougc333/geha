"""Generate a permanent UI showing every simulated production error case."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CASES = Path(__file__).with_name("test_data") / "batch_review_graph_prod_cases.json"
DEFAULT_OUTPUT = PROJECT_DIR / "error_detection_demo.html"


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return document["cases"]


def _status(case: dict[str, Any]) -> tuple[str, str]:
    case_id = case["id"]
    if case_id.startswith("RENDER-"):
        return "warning", "Warning"
    if case_id.startswith(("HTML-", "SAFE-")):
        return "passed", "Protection verified"
    return "error", "Detected error"


def _expected(case: dict[str, Any]) -> str:
    parts = []
    if value := case.get("expected_code"):
        parts.append(f"Code: {value}")
    if value := case.get("expected_verdict"):
        parts.append(f"Verdict: {value}")
    if value := case.get("expected_severity"):
        parts.append(f"Severity: {value}")
    if values := case.get("expected_classes"):
        parts.append("Classes: " + ", ".join(values))
    if case.get("expected_absent"):
        parts.append("Raw exception body: suppressed")
    if value := case.get("expected_exception"):
        parts.append(f"Exception: {value}")
    return " · ".join(parts) or "Expected outcome recorded by the regression test"


def _sample(case: dict[str, Any], status: str) -> str:
    if case["id"] == "HTML-001":
        return """
        <div class="mini-grid" aria-label="Verdict style examples">
          <div class="mini verdict-match"><strong>Verified</strong><span>PDF and HTML match</span></div>
          <div class="mini verdict-mismatch"><strong>Mismatch</strong><span>Correction or review required</span></div>
          <div class="mini verdict-uncertain"><strong>Human review required</strong><span>Comparison was inconclusive</span></div>
        </div>"""
    label = {
        "passed": "Sensitive exception detail removed",
        "warning": "Comparison continues without screenshot",
        "error": "Affected table requires review",
    }[status]
    return f"""
      <div class="sample-table" role="img" aria-label="{html.escape(label)}">
        <div class="sample-head"><span>Field</span><span>Extracted value</span></div>
        <div class="sample-row"><span>Example</span><span>{html.escape(case['id'])}</span></div>
        <div class="sample-alert">{html.escape(label)}</div>
      </div>"""


def _case_card(case: dict[str, Any]) -> str:
    status, status_label = _status(case)
    searchable = " ".join((
        case["id"], case["condition"], case["test_method"], _expected(case)
    )).lower()
    return f"""
    <article class="case-card status-{status}" data-status="{status}"
      data-search="{html.escape(searchable, quote=True)}">
      <header class="case-header">
        <div><span class="case-id">{html.escape(case['id'])}</span>
          <span class="category">{html.escape(case['id'].split('-', 1)[0])}</span></div>
        <span class="status-badge">{html.escape(status_label)}</span>
      </header>
      <h2>{html.escape(case['condition'])}</h2>
      <p class="expected">{html.escape(_expected(case))}</p>
      {_sample(case, status)}
      <details>
        <summary>Regression-test mapping</summary>
        <dl>
          <dt>Case ID</dt><dd><code>{html.escape(case['id'])}</code></dd>
          <dt>Test method</dt><dd><code>{html.escape(case['test_method'])}</code></dd>
          <dt>Fixture source</dt><dd><code>batch_review_graph_prod_cases.json</code></dd>
        </dl>
      </details>
    </article>"""


def build_demo_document(cases: list[dict[str, Any]]) -> str:
    counts = {name: 0 for name in ("error", "warning", "passed")}
    for case in cases:
        counts[_status(case)[0]] += 1
    cards = "\n".join(_case_card(case) for case in cases)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Error detection demo · Production batch review</title>
<style>
:root{{--ink:#08233c;--muted:#5f6f7f;--surface:#fff;--canvas:#eaf0f5;--green:#16803c;--red:#c62828;--amber:#b26a00}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--canvas);color:var(--ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
header.hero{{padding:34px max(24px,calc((100vw - 1440px)/2));background:#06233d;color:#fff}}
.hero h1{{margin:0 0 8px;font-size:clamp(2rem,4vw,3.4rem)}} .hero p{{max-width:900px;margin:0;color:#d8e5ef;font-size:1.05rem;line-height:1.5}}
main{{width:min(1440px,calc(100% - 32px));margin:24px auto 60px}}
.summary{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}}
.metric{{background:#fff;border-radius:12px;padding:16px;box-shadow:0 4px 16px #08233c12}} .metric strong{{display:block;font-size:1.75rem}} .metric span{{color:var(--muted)}}
.toolbar{{position:sticky;top:0;z-index:3;display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:#eaf0f5ee;backdrop-filter:blur(8px);padding:12px 0}}
.toolbar input{{flex:1;min-width:260px;border:1px solid #9badbc;border-radius:8px;padding:10px 12px;font:inherit}}
.filter{{border:1px solid #163a63;border-radius:999px;background:#fff;color:#163a63;padding:8px 14px;font:inherit;font-weight:700;cursor:pointer}} .filter.active{{background:#163a63;color:#fff}}
.case-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}}
.case-card{{border:4px solid #64748b;border-radius:14px;background:var(--surface);padding:18px;box-shadow:0 8px 25px #08233c12}}
.case-card.status-error{{border-color:var(--red);background:#fff8f8}} .case-card.status-warning{{border-color:var(--amber);background:#fffbf2}} .case-card.status-passed{{border-color:var(--green);background:#f7fff9}}
.case-header{{display:flex;align-items:center;justify-content:space-between;gap:12px}}
.case-id{{font:800 1.05rem ui-monospace,SFMono-Regular,Menlo,monospace}} .category{{margin-left:8px;color:var(--muted);font-size:.78rem}}
.status-badge{{border:2px solid currentColor;border-radius:999px;padding:4px 9px;font-weight:800;font-size:.78rem}}
.status-error .status-badge{{color:#9f1d20}} .status-warning .status-badge{{color:#8a5200}} .status-passed .status-badge{{color:#116530}}
.case-card h2{{font-size:1.15rem;line-height:1.35;margin:15px 0 7px}} .expected{{color:var(--muted);min-height:2.7em;margin:0 0 14px}}
.sample-table{{border:1px solid #b8c5d1;border-radius:9px;overflow:hidden;background:#fff;margin:12px 0}}
.sample-head,.sample-row{{display:grid;grid-template-columns:1fr 1fr}} .sample-head{{background:#082f51;color:#fff;font-weight:800}} .sample-head span,.sample-row span{{padding:9px 11px}} .sample-row span+span{{border-left:1px solid #d7e0e7}}
.sample-alert{{padding:9px 11px;font-weight:750;border-top:1px solid #d7e0e7}} .status-error .sample-alert{{color:#9f1d20;background:#fff0f0}} .status-warning .sample-alert{{color:#8a5200;background:#fff8df}} .status-passed .sample-alert{{color:#116530;background:#edfff2}}
.mini-grid{{display:grid;gap:8px;margin:12px 0}} .mini{{display:flex;justify-content:space-between;gap:10px;border:3px solid;border-radius:8px;padding:10px;background:#fff}} .mini span{{color:var(--muted);text-align:right}} .verdict-match{{border-color:var(--green)}} .verdict-mismatch{{border-color:var(--red)}} .verdict-uncertain{{border-color:var(--amber)}}
details{{margin-top:12px;border-top:1px solid #cbd6df;padding-top:10px}} summary{{cursor:pointer;font-weight:750}} dl{{display:grid;grid-template-columns:max-content 1fr;gap:7px 12px;margin-bottom:0}} dt{{color:var(--muted)}} dd{{margin:0;overflow-wrap:anywhere}}
.empty{{display:none;background:#fff;border-radius:12px;padding:24px;text-align:center;color:var(--muted)}}
@media(max-width:850px){{.case-grid{{grid-template-columns:1fr}}.summary{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body>
<header class="hero"><h1>Production error-detection demo</h1>
<p>Permanent visual catalog of every simulated runtime-validation, rendering, comparison, correction, HTML-cue, and safety case. The case IDs map directly to the fixture and regression tests.</p></header>
<main>
  <section class="summary" aria-label="Case summary">
    <div class="metric"><strong>{len(cases)}</strong><span>Total simulated cases</span></div>
    <div class="metric"><strong>{counts['error']}</strong><span>Detected errors</span></div>
    <div class="metric"><strong>{counts['warning']}</strong><span>Warnings</span></div>
    <div class="metric"><strong>{counts['passed']}</strong><span>Protection/UI checks</span></div>
  </section>
  <div class="toolbar">
    <input id="search" type="search" placeholder="Search case ID, condition, code, or test…" aria-label="Search simulated cases">
    <button class="filter active" data-filter="all">All</button>
    <button class="filter" data-filter="error">Errors</button>
    <button class="filter" data-filter="warning">Warnings</button>
    <button class="filter" data-filter="passed">Passed checks</button>
  </div>
  <section class="case-grid" id="cases">{cards}</section>
  <p class="empty" id="empty">No cases match the current filters.</p>
</main>
<script>
const cards=[...document.querySelectorAll('.case-card')];
const search=document.getElementById('search');
const empty=document.getElementById('empty');
let filter='all';
function applyFilters(){{
  const query=search.value.trim().toLowerCase(); let visible=0;
  cards.forEach(card=>{{
    const show=(filter==='all'||card.dataset.status===filter)&&card.dataset.search.includes(query);
    card.hidden=!show; if(show) visible+=1;
  }});
  empty.style.display=visible?'none':'block';
}}
search.addEventListener('input',applyFilters);
document.querySelectorAll('.filter').forEach(button=>button.addEventListener('click',()=>{{
  filter=button.dataset.filter;
  document.querySelectorAll('.filter').forEach(item=>item.classList.toggle('active',item===button));
  applyFilters();
}}));
</script></body></html>"""


def generate_demo(cases_path: Path = DEFAULT_CASES, output_path: Path = DEFAULT_OUTPUT) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_demo_document(load_cases(cases_path)), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(generate_demo(args.cases, args.output))


if __name__ == "__main__":
    main()
