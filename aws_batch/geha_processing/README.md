# GEHA processing library

`geha_processing` is the repository-wide home for reusable document-processing
primitives. Applications and pipelines keep their own orchestration, schemas,
provider adapters, and user interfaces; shared mechanics live here.

## Modules

- `io.py`: deterministic JSON/JSONL reads and writes, atomic replacement, and
  SHA-256 helpers.
- `pdf.py`: native-text and OCR Docling converter setup, embedded-text quality
  checks, and PDF page splitting.
- `tables.py`: detection and repair of placeholder table headers such as
  `0`, `1`, `2`, including embedded-header promotion and continuation tables.
- `contextual.py`: the shared contextual-retrieval prompt and Anthropic client
  call.
- `rag/`: reusable PDF ingestion, splitting, vector/keyword retrieval,
  reranking, answer generation, and CLI services.
- `benchmarks/`: reusable chunking benchmark implementations; project folders
  retain only command entrypoints.
- `fraud/`: reusable FHIR claims analytics and deterministic fraud scoring.

## Consumers

The shared package is used by `advanced_rag`, `aws_rag`, `crawl_dir`,
`chunking_benchmarks_RAG`, `bounding_box`, `e2e_RAG`, `e2e_bm25vector`,
`contextual_retrieval_dashboard`, `finetuning`, `finetuning_LLM_LORA`, and
`hybrid_docling_chunking`.

Run scripts with the repository root on `PYTHONPATH`. For example:

```bash
cd /Users/dc/geha/advanced_rag
PYTHONPATH=..:src python -m unittest discover -s tests -p 'test_*.py'
```

New generally useful processing behavior should be added and tested here first.
Directory-specific wrappers are appropriate when an older public function
signature must remain stable.

## Ownership rule

Project directories may retain Python only when it is an application boundary:
a CLI entrypoint, Streamlit/UI adapter, Lambda or MCP handler, deployment glue,
test, or a compatibility import. Reusable algorithms and services belong under
`geha_processing`.

The `legacy/` subtree contains centralized rollback copies from mechanical
migrations. Nothing should import from it; active compatibility modules import
the canonical packages above.
