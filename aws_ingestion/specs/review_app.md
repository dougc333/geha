# Spec: review app and approval gate

Review status: DRAFT.

## Stack

TypeScript, React 18, Tailwind, Vite, TanStack Query, pdf.js (source page), sandboxed `<iframe srcdoc>` (HTML).

## Screens

1. **Queue**: filter by document, status, risk, pipeline, `low_confidence`; default sort risk descending.
2. **Page review**
   - Left: source page. Right: rendered HTML. Synced zoom and scroll.
   - Modes: side-by-side, overlay with opacity slider, difference heatmap.
   - Hover a block to highlight its bbox on the PDF, and the reverse.
   - Pipeline selector: A, B, or A vs B. In A vs B, differing blocks are listed and the reviewer picks per block.
   - Residual errors panel: unresolved word and number diffs with crops.
   - Spec editor for pipeline 2 blocks; saving re-renders.
3. **Approval gate**: per-page checkmark.

## Keyboard

`A` approve, `R` reject (reason required), `J`/`K` next/previous page, `1`/`2`/`3` view mode.

## Approval rules

- States: `pending -> needs_review -> approved | rejected -> reprocess`.
- An approval stores `content_sha256` of the exact HTML and spec reviewed. Any later change voids it and returns the page to `needs_review`.
- Approval needs an authenticated reviewer id and is append-only (history kept).
- A document is `approved` when every page is approved, or when its configured policy is met: all high-risk pages approved and the random sample audit (default 5% of clean pages) passes with zero rejects. A sample reject re-opens neighbouring pages.
- Markdown export and RAG indexing MUST include approved pages only.

## API

```
GET  /documents/:id/pages?status=&sort=risk
GET  /pages/:doc/:n/runs
GET  /pages/:doc/:n/diff?a=1&b=2
PUT  /pages/:doc/:n/spec
POST /pages/:doc/:n/approval     {run_id, content_sha256, decision, note}
POST /documents/:id/export       approved pages only
```

## Data model

```
document(id, sha256, source_url, page_count)
page(doc_id, page_no, has_text_layer, risk_score, status)
run(doc_id, page_no, pipeline, version, iterations, errors_final, stop_reason, html_uri, spec_uri, md_uri)
approval(doc_id, page_no, run_id, content_sha256, reviewer, decision, note, at)
```

## Risk score inputs

Loop hit the cap, `low_confidence`, residual errors, table-heavy, numeric mismatch, pipeline A and B disagreement.
