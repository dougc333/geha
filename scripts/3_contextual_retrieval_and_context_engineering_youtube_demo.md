# YouTube Demo Script: Contextual Retrieval and Context Engineering

**Target length:** 12–15 minutes  
**Primary application:** `contextual_retrieval_dashboard`  
**Related demos:** `hybrid_docling_chunking`, `context_assembly_benchmarks`, and optional `context_compiler`  
**Audience:** AI context engineers, RAG engineers, and solution architects  
**Central message:** Retrieval quality depends on the entire context lifecycle: create structurally sound chunks, add document-level retrieval context without altering the evidence, verify cache behavior and generated annotations, and assemble complete evidence for generation.

## Recommended video title

**Why Good Chunks Still Fail: Contextual Retrieval, Prompt Caching, and Context Assembly**

## Thumbnail text

**Chunk + Whole Document = Better Retrieval**

## What this video should prove

1. A chunk can be faithful to its source and still be hard to retrieve because it lost document identity.
2. Contextual retrieval adds a short document-aware annotation for indexing while preserving the original evidence for citations.
3. Prompt caching is a measurable provider response, not an assumption based on prompt shape.
4. Contextualization is billable per chunk, so chunk-count analysis belongs before the model loop.
5. Better retrieval text does not solve context assembly; parent tables, qualifiers, and notes may still need to be expanded before generation.

## Before recording

### Start the Contextual Retrieval Workbench

```bash
cd /Users/dc/geha/contextual_retrieval_dashboard

export ANTHROPIC_API_KEY="..."
docker compose up --build
```

Open <http://127.0.0.1:8511>.

If port 8511 is occupied:

```bash
CONTEXTUAL_RETRIEVAL_PORT=8512 docker compose up --build
```

Then open <http://127.0.0.1:8512>.

### Start the Context Assembly Benchmarks

Use a stable PostgreSQL password if an existing volume has already been initialized.

```bash
cd /Users/dc/geha/context_assembly_benchmarks
export GEHA_POSTGRES_PASSWORD="<the password used to initialize this volume>"
docker compose up --build
```

Open:

- React results dashboard: <http://127.0.0.1:5174>
- Interactive Streamlit comparison: <http://127.0.0.1:8507>

### Prepare the local companion artifacts

The hybrid-chunking and context-compiler demos do not require model calls for their checked-in examples.

```bash
cd /Users/dc/geha
source .venv/bin/activate

# Show chunk-count results without calling Claude.
python hybrid_docling_chunking/count_hybrid_chunks.py \
  aws_data_workflow/runtime/documents/doc-673098c8003e/source.pdf \
  --output-dir hybrid_docling_chunking/artifacts/kentucky-medicaid-pa-criteria \
  --max-tokens 380 512 800

# Optional agent-context comparison.
python context_compiler/demo.py --episodes 20 --plot context_compiler/cost.png
```

### Recording checklist

- Confirm the workbench reports a ready Claude credential and the expected model.
- Choose one document marked **MD ready** with a modest estimated call count.
- Reopen at least one completed item from **Past contextual runs** so the inspector is populated before recording.
- If demonstrating EY figures, confirm the configured saved visual run is available.
- Remember that **Run 2-call test**, contextualization, and judging use billable model requests.
- Use the one-document action for the recording. Do not click **Run all 35** unless the full-corpus cost is intentional.
- Hide credentials, terminal history containing secrets, and unrelated browser tabs.
- Record at 1440p or higher so chunk text and cache telemetry remain readable.

## Main recording script

### 0:00–0:40 — Hook: the missing identity problem

**On screen**

- Start in the chunk inspector with the original chunk on the left and contextual annotation on the right.
- Highlight a short source chunk whose meaning depends on the document title or section.

**Narration**

> A chunk can contain accurate source text and still be difficult to retrieve. It may say “coverage requires prior authorization,” but omit the policy name, procedure, population, date, or section that tells us what that statement applies to.
>
> Increasing the embedding model size does not restore identity that is absent from the text. Contextual retrieval addresses this by giving the model the whole document plus one target chunk and asking for a short retrieval-oriented annotation. The source chunk remains unchanged; the annotation is added only to the text used for search.

**On-screen callout**

```text
whole document + target chunk
              ↓
short retrieval context + original evidence
              ↓
contextual BM25 and contextual embeddings
```

### 0:40–1:35 — Define the three stored fields

**On screen**

- Point to the two inspector panels.
- Expand **Text used for contextual BM25 + embeddings**.

**Narration**

> The application keeps three fields with different responsibilities.
>
> `text` is the preserved source evidence. It is what we show to users and what we use for citation and faithfulness checks.
>
> `retrieval_context` is generated text that situates the chunk within the complete document.
>
> `contextual_retrieval_text` concatenates that short annotation with the original evidence. This combined field is the representation intended for BM25 and embeddings.
>
> The generated annotation is an indexing aid. It is not promoted to authoritative evidence and must never replace the source text.

### 1:35–2:30 — Tour the run controls and cost boundary

**On screen**

- Show the document selector and readiness badges.
- Point to **MD ready**, estimated calls, cost acknowledgement, **Run 1 document**, **Run all 35**, and **Run EY figures**.
- Do not start the run yet.

**Narration**

> The workbench supports canonical policy text and saved visual figures. A policy can run only after canonical non-empty Markdown exists. This preflight check prevents spending money contextualizing an unusable extraction.
>
> Cost is explicit because the workflow makes approximately one Claude request per final chunk or selected figure. The interface shows the current estimate and requires acknowledgement before it enables a run.
>
> For a demo, I use one document first. The full 35-document batch is an operational option, not a button to click casually.

### 2:30–3:15 — Why chunk sizing comes first

**On screen**

- Briefly show `hybrid_docling_chunking/artifacts/kentucky-medicaid-pa-criteria/summary.json`, or a prepared table with the checked-in baseline.

| Token budget | Hybrid chunks | Chunks spanning pages | Median tokens |
| ---: | ---: | ---: | ---: |
| 380 | 1,058 | 60 | 68 |
| 512 | 985 | 73 | 61 |
| 800 | 885 | 77 | 54 |

**Narration**

> Before paying for contextual retrieval, measure the chunks. The companion Hybrid Docling experiment converts a document once, then compares multiple token budgets locally without making Claude, embedding, or AWS calls.
>
> In the checked-in Kentucky Medicaid example, the 290-page document produced 1,058 chunks at a 380-token budget and 885 chunks at an 800-token budget. Many chunks remained short because the document contains many tables and small structural elements.
>
> This matters because one final chunk means roughly one contextualization request. Chunking quality is therefore both a retrieval decision and a cost-control decision.

**On-screen callout**

`Finalize chunks before starting one-call-per-chunk contextualization`

### 3:15–4:30 — Start or replay one contextual run

**On screen**

- Select a document marked **MD ready**.
- Check the cost acknowledgement.
- Either click **Run 1 document** or choose a saved entry under **Past contextual runs**.
- Show the live event stream or restored progress.

**Narration for a live run**

> I will now run a single document. The backend invokes the canonical ingestion contract, verifies the new document Markdown, reads the canonical chunks, and sends the complete document with one changing target chunk to Claude.
>
> Each result is checkpointed immediately in `contextual-chunks.jsonl`. If the process stops, completed records remain available and matching records can be reused.

**Narration for a saved run**

> I am reopening a durable saved run so the recording is not dependent on live model latency. The dashboard reconstructs this history from disk after restarts. These are persisted outputs, not mocked UI state.

### 4:30–6:00 — Inspect original evidence versus contextual text

**On screen**

- Select a completed document.
- Move among two or three chunks with the chunk dropdown.
- Read one original chunk and its generated annotation aloud.
- Expand the combined indexing text and deterministic provenance string.

**Narration**

> The left panel is the canonical Docling chunk. The right panel is the generated contextual annotation plus the exact text that would be sent to contextual BM25 and the embedding model.
>
> A useful annotation adds missing identity: the document, policy, section, population, or relationship that helps retrieval. It should not answer a hypothetical user question, add unsupported policy facts, or rewrite the evidence.
>
> Notice that the original text remains separately available. Retrieval can use an enriched representation while generation and citation stay bound to the source evidence.

**Suggested example commentary**

> Without context, this sentence is lexically valid but underspecified. The annotation connects it to the relevant policy and section. A code-specific BM25 query can now match the explicit identity, while a semantic query can benefit from the same added description.

### 6:00–7:25 — Open the prompt inspector and prove prompt caching

**On screen**

- Open **Prompt + cache**.
- Highlight:
  1. stable system instructions;
  2. cached whole-document system block;
  3. changing per-chunk user message.
- Click **Run 2-call test** if you intend to incur the two billable requests.
- Show first-call cache creation tokens and second-call cache-read tokens.

**Narration**

> The expensive repeated prefix is the complete document. The prompt therefore places stable instructions first, the entire document in an ephemeral cache block second, and the changing target chunk last.
>
> But sending the same prompt shape does not prove a cache hit. The live diagnostic makes two real requests with the same document prefix. It passes only when the provider reports a nonzero `cache_read_input_tokens` value on the second response.
>
> Prompt caching reduces repeated input processing. It does not eliminate the per-chunk model request, and it does not make generated context authoritative.

**On-screen callout**

`Cache verified = second response reports cache_read_input_tokens > 0`

### 7:25–8:35 — Demonstrate saved visual-figure contextualization

**On screen**

- Choose a saved run labeled **VISUAL**, or click **Run EY figures** if a live run is intended.
- Show the authoritative page PDF on the left.
- Show the highest-numbered saved figure iteration and Claude context on the right.

**Narration**

> Contextual retrieval is not limited to plain text chunks. Visual mode reads an existing completed ingestion run. It pairs the authoritative page PDF with the latest saved figure rendering and optional literal source evidence.
>
> Claude receives the page and the selected figure, then generates retrieval context for that visual artifact. The workflow does not regenerate or repair the figure here. It only contextualizes durable artifacts produced by the ingestion system.
>
> Reuse is hash-bound. A record is reused only when the page hash, figure hash, model, and prompt version still match, so changing one artifact invalidates only the affected contextual record.

### 8:35–9:20 — Explain the evaluation gap

**On screen**

- Keep one original/contextual pair visible.
- Add a title card: **Retrieval context can still be wrong**.

**Narration**

> Contextual retrieval can improve searchability, but the generated annotation can still be incomplete or unsupported. That creates two evaluation questions.
>
> First, is the original extracted evidence clean enough to trust? Second, is the generated retrieval context grounded in that evidence?
>
> Those checks should remain separate. A clean source can receive a bad annotation, and a grounded annotation cannot repair corrupt source extraction. Visual fidelity against PDF pixels requires a separate vision comparison.

### 9:20–11:05 — Related demo: context assembly after retrieval

**On screen**

- Switch to the Context Assembly React dashboard at <http://127.0.0.1:5174>.
- Show the saved 59-question comparison.
- Filter or select examples for flat rows, table-aware parents, and table-aware plus attached notes.
- Optionally open the live Streamlit comparison at <http://127.0.0.1:8507>.

**Narration**

> Contextual retrieval improves what gets indexed and ranked. It does not guarantee that the final evidence sent to the language model is complete.
>
> This companion benchmark holds retrieval constant. BM25 and pgvector rank the same child rows, and reciprocal-rank fusion combines those lists. The experiment then changes only context assembly: return flat rows, expand to the parent table, or attach the nearby explanatory notes.
>
> In the saved 59-question run, flat rows achieved 40.7 percent complete context. Parent-table expansion reached 69.5 percent. Parent tables with attached notes reached 100 percent context completeness and 93.2 percent answer completeness.
>
> That last gap matters. If all required facts are present in context but missing from the answer, it is a generation drop. If a required fact is absent from context, it is a retrieval or assembly failure. If the answer introduces a fact absent from evidence, it is an unsupported claim.

**On-screen table**

| Strategy | Context complete | Answer complete | Average context tokens |
|---|---:|---:|---:|
| Flat row chunks | 40.7% | 40.7% | 299 |
| Table-aware | 69.5% | 69.5% | 476 |
| Table-aware + attached notes | 100.0% | 93.2% | 896 |

**Accuracy note to say aloud**

> These are configuration-bound results from the checked-in October 16, 2026 run. They are evidence for this corpus and benchmark, not a universal claim about all RAG systems.

### 11:05–12:05 — Optional related demo: context compiler for long-running agents

**On screen**

- Show `/Users/dc/geha/context_compiler/cost.png` and a terminal run of `context_compiler/demo.py`.

**Narration**

> This final companion demo is related to prompt construction but solves a different problem. Contextual retrieval enriches document chunks for search. A context compiler manages an agent's growing working history.
>
> The compiler keeps a complete append-only event log and builds a purpose-specific prompt for each call. The cache-friendly version freezes older event representations so the provider can reuse a stable prefix.
>
> In the scripted 160-call comparison, the plain agent cost 10 dollars and 60 cents, compiler version one cost 5 dollars and 31 cents, and the cache-stable version two cost 2 dollars and 19 cents while maintaining the benchmark's fact-recall check.
>
> This is a synthetic cost and recall model, not a production task-success evaluation. Its lesson is architectural: shorter prompts do not automatically reduce cost if they keep changing early tokens and destroying the cacheable prefix.

### 12:05–13:10 — Summarize the full context lifecycle

**On screen**

```text
PDF
 ↓
Canonical extraction and structure-aware chunking
 ↓
Measure chunk count, size, and provenance
 ↓
Whole document + target chunk
 ↓
Generated retrieval context
 ↓
Contextual BM25 + contextual embeddings
 ↓
Retrieve child evidence
 ↓
Expand parent tables, qualifiers, and notes
 ↓
Generate from preserved source evidence
 ↓
Evaluate assembly errors, generation drops, and unsupported claims
```

**Narration**

> The complete workflow begins before the vector database and ends after generation.
>
> First, preserve structure during extraction. Second, finalize and measure chunks before paying for per-chunk model calls. Third, enrich the retrieval representation with whole-document context while preserving original evidence. Fourth, verify prompt-cache telemetry instead of assuming it. Fifth, assemble complete parent evidence for the model. Finally, evaluate retrieval, context completeness, answer completeness, and groundedness as separate stages.
>
> This separation makes failures diagnosable. Instead of saying “RAG failed,” we can identify whether the source was corrupt, the chunk lacked identity, retrieval missed it, context assembly dropped a qualifier, or generation ignored available evidence.

### 13:10–13:35 — Close

**On screen**

- Return to the contextual chunk inspector.
- Display the repository paths:
  - `contextual_retrieval_dashboard`
  - `hybrid_docling_chunking`
  - `context_assembly_benchmarks`
  - `context_compiler`

**Narration**

> Context engineering is not the act of putting more tokens into a prompt. It is the controlled construction of the smallest complete, grounded, and inspectable context for the current task. These demos expose each stage so its cost and failure modes can be measured independently.

## Optional 90-second version

> A source chunk can be accurate and still be hard to retrieve because it lost the document name, section, population, date, or policy identity.
>
> In this workbench, contextual retrieval gives Claude the complete document plus one target chunk. Claude returns a short retrieval annotation. The source evidence remains unchanged for citations, while the annotation plus the original text becomes the representation used by BM25 and embeddings.
>
> The prompt inspector shows why the complete document comes before the changing chunk: that stable prefix can be cached. A real two-call diagnostic passes only when the provider reports nonzero cache-read tokens on the second response.
>
> The workflow checkpoints every chunk and can also contextualize saved visual figures by pairing an authoritative page PDF with the latest figure rendering.
>
> But better retrieval text is only one layer. A separate context-assembly benchmark holds retrieval constant and shows that flat rows often omit parent-table relationships and nearby qualifiers. Parent expansion and attached notes improve completeness, at the cost of more tokens.
>
> The goal is not maximum context. It is complete, grounded, traceable context whose failures can be assigned to extraction, chunking, retrieval, assembly, or generation.

## Suggested YouTube chapters

```text
00:00 Why faithful chunks can still be hard to retrieve
00:40 Source evidence versus retrieval context
01:35 Cost controls and document readiness
02:30 Measure chunks before model calls
03:15 Run or restore contextual retrieval
04:30 Inspect original and contextual chunks
06:00 Prove prompt caching with telemetry
07:25 Contextual retrieval for visual figures
08:35 Evaluate source integrity and grounding separately
09:20 Context assembly after retrieval
11:05 Optional context compiler comparison
12:05 The complete context lifecycle
13:10 Summary
```

## Accuracy and recording notes

- Use the spelling **contextual retrieval**, not “context retrieval.”
- The dashboard processes public curated documents and is not production- or HIPAA-ready.
- A contextual annotation is generated indexing metadata, not source evidence.
- Prompt caching reduces repeated prefix processing; it does not eliminate one request per chunk.
- Cache success requires reported cache-read tokens. Prompt structure alone is not proof.
- The React workbench supports text and saved visual modes. Visual mode currently targets the saved run configured by the backend rather than an arbitrary run picker.
- The dashboard checkpoints results, but its live SSE connection does not resume after a backend restart. Durable history remains recoverable.
- Do not describe reciprocal-rank fusion as a learned reranker. It combines ranked lists.
- The context-assembly benchmark deliberately holds retrieval constant so assembly strategies can be compared.
- The attached-notes benchmark reaches 100 percent context completeness partly because qualifier cases are defined from those notes; retain that qualification.
- The context compiler is an agent-history demo, not document RAG and not a production task-success benchmark.
- When showing a saved run, call it a durable saved run rather than a live execution.
- Hide API keys and avoid clicking full-corpus or cache-test actions unless their billable calls are intentional.

## Suggested repository links for the video description

```text
Contextual Retrieval Workbench:
contextual_retrieval_dashboard/

Pre-contextualization chunk analysis:
hybrid_docling_chunking/

Post-retrieval context assembly benchmark:
context_assembly_benchmarks/

Optional long-session agent context comparison:
context_compiler/
```
