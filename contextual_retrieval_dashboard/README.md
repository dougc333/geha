# Contextual retrieval ingestion dashboard

This is the corpus-wide, deterministic ingestion UI. It runs the canonical
Docling `HybridChunker`, preserves `candidate/chunks.jsonl`, and writes Claude
annotations to the separate `candidate/contextual-chunks.jsonl` artifact.

> **Two artifact modes:** coverage policies use canonical Docling text chunks.
> The saved EY/LIMRA agent demo uses visual page/figure artifacts created by
> `/Users/dc/geha/document_ingestion_workflow`. This dashboard reads those
> durable artifacts but does not alter or rerun the visual repair workflow.

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

## EY visual figure mode

The **Run EY figures** action reads the saved run at:

```text
crawl_dir/runs/research/ey-limra-workforce-benefits-study-final-2025/
  agent-demo-20261010T125607Z-e93043/
```

It walks `pages/page-NNN/segments`, finds every `figure-NN` (or `fig-NN`)
directory, and chooses the highest numbered `iteration-NN.png`. Each Claude
call receives that page's `source.pdf` as the document and the selected PNG as
the target figure chunk. The current run contains 26 figure chunks, so a fresh
run is approximately 26 Claude calls. Matching completed outputs are reused by
PDF hash, figure hash, model, and prompt version.

The chunk inspector displays the original page PDF in panel **01**. Panel
**02** displays the selected latest figure iteration, its Claude retrieval
annotation, and the combined text intended for contextual BM25 and embeddings.
Outputs are checkpointed in `visual-contextual-chunks.jsonl`; run metadata is
stored in `visual-contextual-retrieval.json`.

## Run

### Docker Compose (recommended)

The image builds the React UI and preloads the BGE tokenizer used by the
canonical Docling chunker. Source PDFs are mounted read-only; durable runs and
the page-split cache are mounted read-write so prior runs remain visible.

```bash
cd contextual_retrieval_dashboard
docker compose up --build
```

Compose prints the dashboard URL when the backend is ready. Open
<http://127.0.0.1:8511>. To run in the background, use `docker compose up -d
--build`, then inspect startup output with `docker compose logs -f`.

Anthropic credentials exported by the shell are passed into the container. If
port 8511 is occupied, choose another host port without changing the container:

```bash
CONTEXTUAL_RETRIEVAL_PORT=8512 docker compose up --build
```

Stop the service with `docker compose down`. This does not delete source PDFs,
runs, or cache files because they remain in the repository bind mounts.

### Local development

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
- Visual contextual output: `<saved-agent-run>/visual-contextual-chunks.jsonl`
- Visual contextual metadata: `<saved-agent-run>/visual-contextual-retrieval.json`

Candidates remain unpromoted and still require the repository's normal visual
review and promotion gates.

## Saved-run history

The backend reconstructs history from durable
`runs/coverage-policies/*/*/candidate/contextual-chunks.jsonl` artifacts; it
does not depend on the in-memory SSE registry. On startup, the UI restores the
latest contextual run for each document, opens the newest run in the chunk
viewer, and lists every saved run in **Past contextual runs**. Backend restarts
therefore do not hide already-paid Claude results.
