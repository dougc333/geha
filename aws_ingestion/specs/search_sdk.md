# Spec: search as code (Python SDK)

Review status: DRAFT. Not implemented.

## Idea

Fetch, chunk, embed and retrieve are separate, typed, composable stages in a Python SDK. An agent (or a person) builds a search pipeline by writing code that wires stages together, instead of calling one fixed search endpoint. The SDK sits on the approved content produced by the ingestion pipelines.

## Principles

1. **Stages are small and swappable.** Each stage is a `Protocol` with one method. Implementations are plain classes.
2. **Pipelines are values.** A pipeline is an ordered composition of stages with a config hash, so it can be versioned, diffed, stored and replayed.
3. **The approval invariant is not optional.** Every `Source` and `Index` reads only approved page content (`approved` or `auto_approved`, see `review_app.md`). An agent cannot construct a pipeline that reaches unapproved content, because the filter lives in the storage adapter, not in the pipeline code.
4. **Every result is citable.** Each chunk carries `doc_sha256`, `page_no`, `block_id`, `content_sha256` and the approval id, so a citation resolves to the reviewed source block.
5. **Deterministic and offline-testable.** Fake embedder, fake index and in-memory source ship in the SDK so tests need no AWS or model.

## Core types

```python
@dataclass(frozen=True)
class Document:      # one approved page or block of text
    doc_sha256: str; page_no: int; block_id: str
    content_sha256: str; approval_id: str
    text: str; meta: Mapping[str, Any]

@dataclass(frozen=True)
class Chunk:
    id: str; text: str; parent: Document
    span: tuple[int, int]          # offsets into parent.text
    meta: Mapping[str, Any]

@dataclass(frozen=True)
class Hit:
    chunk: Chunk; score: float; stage: str   # which stage scored it
```

## Stage protocols

```python
class Source(Protocol):                      # fetch
    def fetch(self, query: SourceQuery) -> Iterable[Document]: ...

class Chunker(Protocol):                     # chunk
    def chunk(self, docs: Iterable[Document]) -> Iterable[Chunk]: ...

class Embedder(Protocol):                    # embed
    model_id: str; dim: int
    def embed(self, texts: Sequence[str]) -> list[list[float]]: ...

class Index(Protocol):                       # store + retrieve
    def upsert(self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]]) -> None: ...
    def search(self, vector: Sequence[float], k: int, filters: Filters | None = None) -> list[Hit]: ...

class Reranker(Protocol):                    # optional
    def rerank(self, query: str, hits: Sequence[Hit], k: int) -> list[Hit]: ...
```

Built-in implementations (first release):
- `Source`: `ApprovedPages` (Postgres, approved only), `InMemory`.
- `Chunker`: `ByBlock`, `FixedTokens(size, overlap)`, `ParentChild(parent_size, child_size)`.
- `Embedder`: `Bedrock(model_id)`, `Fake(dim)`.
- `Index`: `PgVector`, `InMemory`; hybrid keyword + vector as `Hybrid(PgVector, Postgres FTS)`.
- `Reranker`: `CrossEncoder`, `None`.

## Composition

```python
from search_sdk import Pipeline, ApprovedPages, ByBlock, Bedrock, PgVector

pipe = Pipeline(
    source=ApprovedPages(doc_ids=["geha-benefits-2025"]),
    chunker=ByBlock(max_tokens=400),
    embedder=Bedrock("amazon.titan-embed-text-v2:0"),
    index=PgVector(table="chunks_geha_v1"),
)
pipe.build()                                  # fetch -> chunk -> embed -> upsert (idempotent)
hits = pipe.retrieve("dental deductible", k=8, filters={"language": "en"})
```

Rules:
- `build()` is idempotent: chunk id = hash of `(content_sha256, chunker config)`, so re-running skips unchanged chunks.
- Changing the embedder or chunker config makes a new pipeline version and a separate index table, never an in-place mix of vectors.
- `retrieve()` returns `Hit`s with full citation fields. It never returns bare text.

## Agent surface

Agents get the SDK two ways:
1. **As code.** A sandboxed Python tool where the agent writes and runs a pipeline using the SDK only. No shell, no unrestricted network (matches the plan's agent guardrails).
2. **As tools.** Thin JSON-schema wrappers: `search.fetch`, `search.chunk`, `search.embed`, `search.retrieve`, `search.compare_pipelines`.

Agent-built pipelines are saved as `PipelineSpec` (JSON: stage names plus configs), registered under a name and version, and evaluated before use.

## Evaluation

- Each pipeline is scored on a labelled query set: recall@k, MRR, citation-resolves rate.
- RAGAS metrics (context recall and precision, faithfulness) are an optional `Evaluator`, see `ragas_eval.md`.
- `compare_pipelines(a, b, queries)` returns per-query wins and the aggregate, so agents choose pipelines by measured results.
- A pipeline cannot be promoted to the production alias unless it meets the thresholds and its cost per query stays under budget.

## Guardrails

- Approved-only filter enforced in `ApprovedPages` and in `PgVector` (row-level: join to approval). Not overridable from pipeline code.
- Per-pipeline budgets: max embed calls, max tokens, max rows fetched, wall-clock limit.
- Embedding model and chunker config recorded with every index; mixing dimensions raises an error.
- Every build and retrieve emits spans with `pipeline_id`, `pipeline_version`, `stage`, counts and latency (see observability in the AWS plan).
- No document text in logs.

## Package layout

```
search_sdk/
  types.py          # Document, Chunk, Hit
  protocols.py      # Source, Chunker, Embedder, Index, Reranker
  sources/ chunkers/ embedders/ indexes/ rerankers/
  pipeline.py       # Pipeline, PipelineSpec, build, retrieve
  eval.py           # metrics, compare_pipelines
  testing.py        # Fake embedder, in-memory source/index
```

It becomes the `search` package in the AWS plan's package boundaries and replaces the single-purpose Phase 6 chunk/embed code.

## Acceptance

- A pipeline built from fakes passes the same tests as one built from Bedrock and pgvector.
- Unapproved content is unreachable by any combination of stages (property test).
- `build()` twice produces identical chunk ids and no duplicate rows.
- Every `Hit` resolves to an approved page and block.
- Swapping the chunker produces a new index version and leaves the old one queryable.

## Open questions

- Hybrid retrieval: fuse in SQL, or fuse in the SDK?
- Whether agent-written pipeline code may define new stage classes, or may only compose built-in ones.
- Embedding model choice and whether to store multiple embeddings per chunk.
