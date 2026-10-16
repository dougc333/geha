# Contextual retrieval ingestion dashboard

This is the corpus-wide, deterministic ingestion UI. It runs the canonical
Docling `HybridChunker`, preserves `candidate/chunks.jsonl`, and writes Claude
annotations to the separate `candidate/contextual-chunks.jsonl` artifact.

> **Separate demo:** Datroway and Elrexfio use the visual ReAct correction
> workflow in `/Users/dc/geha/document_ingestion_workflow` (port 8510). That
> agent demo chooses visual tools and repairs page renderings. This dashboard
> (port 8511) monitors the canonical 35-document coverage-policy batch and does
> not substitute the ReAct output for canonical Docling chunks.

## What each Claude call receives

For every canonical chunk, Claude receives:

1. the **entire extracted document** in a prompt-cacheable `<document>` block;
2. one target Docling chunk in a `<chunk>` block; and
3. an instruction to return only a short, retrieval-oriented context.

The result is stored as `retrieval_context` and prepended to the original chunk
in `contextual_retrieval_text`. Use that combined field for contextual BM25 and
contextual embeddings. Keep `text` as the evidence shown to users and used by
faithfulness checks.

The dashboard requires a cost acknowledgment because this is one Claude call
per chunk. It checkpoints after every chunk and reuses matching completed
records when the same batch is resumed.

The **Prompt + cache** sidebar shows the exact system blocks, the changing user
chunk template, and the `cache_control: {"type": "ephemeral"}` breakpoint on
the complete document. Its live two-call diagnostic uses one real canonical
document and reports Anthropic's `cache_creation_input_tokens` and
`cache_read_input_tokens`. It passes only when the second call reports a cache
read greater than zero.

## Run

```bash
cd /Users/dc/geha/contextual_retrieval_dashboard/ui
npm install
npm run build

cd /Users/dc/geha
uv run python -m contextual_retrieval_dashboard.backend
```

Open <http://127.0.0.1:8511>. For frontend development, run `npm run dev` and
open <http://127.0.0.1:5175>; Vite proxies `/api` to the backend.

Use the **One-document test** dropdown to select any of the 35 source PDFs and
run the complete canonical-plus-contextual workflow for only that document.
The adjacent **Run all 35** button preserves the full-corpus option. Both modes
use the same pipeline and durable artifact contracts; the dropdown is a source
filter, not a simplified demo path.

Gemcitabine is the default one-document test. Datroway and Elrexfio are labeled
as ReAct-converted sources because their original PDFs were image-oriented and
were handled in the separate visual workflow. Before either run mode can start,
the backend verifies that every selected source already has a non-empty
canonical batch `candidate/document.md`. It verifies the newly generated
run-specific Markdown again immediately before the first Claude call and emits
a `canonical_markdown_verified` audit event. Missing or empty Markdown prevents
Claude from being called.

Anthropic credentials must be visible to the backend through
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, or `ant auth login`.

## Durable artifacts

- Canonical input: `candidate/chunks.jsonl`
- Whole-document extraction: `candidate/document.md`
- Contextual output: `candidate/contextual-chunks.jsonl`
- Contextual run metadata: `candidate/contextual-retrieval.json`
- Batch progress: `crawl_dir/runs/<batch-id>.json`

Candidates remain unpromoted and still require the repository's normal visual
review and promotion gates.
