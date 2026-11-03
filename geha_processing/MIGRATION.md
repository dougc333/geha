# Python centralization migration

The repository is being converted from independent demo implementations to one
shared Python package with thin application boundaries.

## Centralized

- PDF/Docling conversion and page splitting
- table-header detection, `0`/`1`/`2` repair, and continuation tables
- JSON, JSONL, atomic writes, and SHA-256 helpers
- Anthropic contextual-retrieval prompting and clients
- class-based RAG ingestion, splitting, retrievers, reranking, and clients
- Docling-versus-LangChain chunking benchmarks
- FHIR fraud analytics and deterministic scoring

## Thin compatibility paths

- `agentic_search/src/{rag_class,rag_client_class,reranking_models_class,app_class}.py`
- `agentic_search_corpus/src/{rag_class,rag_client_class,reranking_models_class,app_class}.py`
- `chunking_benchmarks_RAG/benchmark_chunkers.py`
- `context_assembly_benchmarks/benchmark_chunkers.py`
- `hapi/fraud/{tools,scoring}.py`
- `hapi/self-improving-agents/{tools,scoring}.py`

These files intentionally contain imports and entrypoint dispatch only.

## Remains local by design

- Streamlit, React-facing, and other UI adapters
- Lambda, MCP, server, and deployment entrypoints
- tests and evaluation fixtures
- project-specific schemas and artifact promotion rules
- algorithms that exist in only one application and are not yet reusable

When two applications need one of those algorithms, move its implementation to
the appropriate `geha_processing` namespace and leave a compatibility wrapper.
