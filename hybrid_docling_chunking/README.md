# Hybrid Docling chunking experiment

This directory measures document-level Docling `HybridChunker` output before
any contextual-retrieval model is called. It is intentionally separate from
`aws_data_workflow` so changing chunk sizes does not mutate ingestion runs.

The workflow is:

```text
source.pdf
  -> one full-document Docling conversion
  -> structure-aware hybrid chunks
  -> chunk counts and JSONL artifacts
  -> later: one LLM-generated retrieval context per final chunk
```

The counting step is local and makes **no Claude, Argon, embedding, or AWS
calls**. Docling's `chunker.contextualize()` only adds structural breadcrumbs
such as headings and captions; it is not Anthropic contextual retrieval.

## Run the Kentucky document

Use the existing GEHA environment, which already contains Docling and its
chunking dependencies:

```bash
cd /Users/dc/geha
source .venv/bin/activate

python hybrid_docling_chunking/count_hybrid_chunks.py \
  aws_data_workflow/runtime/documents/doc-673098c8003e/source.pdf \
  --output-dir hybrid_docling_chunking/artifacts/kentucky-medicaid-pa-criteria \
  --max-tokens 380 512 800
```

The PDF is converted once. Each token budget is then evaluated against the
same `DoclingDocument`.

## Outputs

```text
artifacts/<document>/
├── document.md
├── document.json
├── chunks-380.jsonl
├── chunks-512.jsonl
├── chunks-800.jsonl
└── summary.json
```

Each JSONL row retains raw chunk text, Docling's heading-aware retrieval text,
token count, headings, captions, and source page numbers. `summary.json`
compares the resulting chunk counts and token distributions.

## Contextual retrieval comes afterward

Once a chunk size is selected, contextual retrieval should generate a short,
chunk-specific annotation for every final chunk using the complete document as
stable context. The retrieval representation becomes:

```text
LLM-generated retrieval context

original Docling hybrid chunk
```

That combined representation is embedded and indexed for BM25. Keep the
original chunk unchanged for citations and answer grounding.

## Kentucky baseline (October 20, 2026)

The 290-page Kentucky Medicaid prior-authorization document produced:

| Token budget | Hybrid chunks | Chunks spanning pages | Median tokens |
| ---: | ---: | ---: | ---: |
| 380 | 1,058 | 60 | 68 |
| 512 | 985 | 73 | 61 |
| 800 | 885 | 77 | 54 |

No LLM calls were made. The high number of short chunks comes largely from the
document's many tables and small structural elements. Review or merge those
units before paying to contextualize every chunk.

## Full 50-document corpus run

`run_corpus.py` resolves the exact 50 source PDFs from
`aws_data_workflow/evals/cluster_manifest.json`. It excludes the three local
smoke-test documents automatically. Each PDF is converted as one complete
Docling document and then passed to `HybridChunker`, which applies hierarchical
document structure followed by token-aware refinement.

Create or inspect the run plan without processing documents:

```bash
cd /Users/dc/geha/hybrid_docling_chunking
/Users/dc/geha/.venv/bin/python run_corpus.py --plan
```

Run the corpus sequentially (safest for memory):

```bash
/Users/dc/geha/.venv/bin/python run_corpus.py --workers 1
```

The resumable run is written under:

```text
runs/hybrid_chunker_fulldoc/
├── run.json
└── documents/
    └── doc-XXXXXXXXXXXX/
        ├── document-run.json
        ├── document.json
        ├── document.md
        ├── chunks-512.jsonl
        └── summary.json
```

Every run and document record contains:

```json
{
  "run_label": "hybrid_chunker_fulldoc",
  "chunker": "docling.HybridChunker",
  "chunking_scope": "full_document",
  "hierarchy_aware": true,
  "token_aware": true,
  "annotation_status": "not_started",
  "llm_calls_made": 0
}
```

