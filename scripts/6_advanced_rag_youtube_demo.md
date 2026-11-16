# YouTube Demo Script: Advanced RAG with Document Routing, Contextual Retrieval, and Quality Gates

**Target length:** 12–14 minutes  
**Application:** `advanced_rag`  
**Audience:** AI context engineers, RAG engineers, and solution architects  
**Central message:** Reliable RAG begins before retrieval. This demo routes different document and query types to appropriate processing paths, preserves original evidence, adds retrieval-only context, and uses explicit quality gates before anything can enter a trusted index.

## Recommended video title

**Advanced RAG: Route, Extract, Contextualize, Judge, and Index**

## Thumbnail text

**RAG Before Retrieval**

## What this video should demonstrate

1. The React application separates query routing, document ingestion, and contextual retrieval into three inspectable workspaces.
2. Queries are routed across six document clusters with TypeSafe Jev when configured and a visibly labeled deterministic fallback otherwise.
3. PDF ingestion runs Docling first and sends only low-quality pages to the selected DeepSeek or LlamaParse fallback.
4. Tables, figures, page Markdown, source PDFs, manifests, and errors remain inspectable rather than being collapsed into opaque text.
5. Narrative pages receive document-aware retrieval context while forms remain a single whole-document retrieval unit.
6. Generated context is used for retrieval, but preserved original text remains the evidence used for answers and citations.
7. A separate LLM judge checks extraction integrity and context grounding before content is considered indexable.
8. The local application is implemented; the S3, Step Functions, Fargate, DynamoDB, and EventBridge design is a target AWS architecture, not a deployed production stack.

## Before recording

### Start the application

The simplest reproducible path is Docker Compose:

```bash
cd /Users/dc/geha/advanced_rag
source ~/.zshrc
docker compose up --build
```

Open:

```text
http://127.0.0.1:8000
```

The same process serves the compiled React interface and FastAPI endpoints. Swagger is available at:

```text
http://127.0.0.1:8000/docs
```

Stop the application with `Ctrl-C`, then cleanly remove the container with:

```bash
docker compose down
```

### Optional local-development startup

```bash
cd /Users/dc/geha/advanced_rag
source /Users/dc/geha/.venv/bin/activate
PYTHONPATH=..:src python -m aws_data_workflow.server
```

For live frontend editing, run Vite separately:

```bash
cd /Users/dc/geha/advanced_rag/web
npm install
npm run dev
```

Open `http://localhost:5175`; Vite proxies API requests to port 8000.

### Verify the offline contracts

```bash
cd /Users/dc/geha/advanced_rag
source /Users/dc/geha/.venv/bin/activate
PYTHONPATH=..:src python -m unittest discover -s tests -v
```

The offline suite covers routing, Docling preprocessing, table normalization, contextual retrieval, whole-document forms, policy RAG, run artifacts, and the API contract.

### Provider configuration

The demo can open and inspect saved runs without making new paid model calls. Live operations need only the provider used by that operation:

- `TYPESAFE_API_KEY` for Jev query routing;
- `ANTHROPIC_API_KEY` for page or whole-document contextualization and the context judge;
- `NOUS_KEY` or `NOUS_API_KEY` for the DeepSeek vision fallback;
- `LLAMA_CLOUD_API_KEY` for LlamaParse fallback; and
- AWS credentials plus enabled Bedrock models only for the optional Bedrock-oriented worker paths.

Never show `.zshrc`, provider keys, AWS credentials, or private source documents during the recording.

### Prepare the recording views

1. Open the **Query & Cluster Debugging** tab.
2. Open the **Ingestion** tab with one completed or saved document run.
3. Open the **Contextual Retrieval** tab with one contextualized, judged document.
4. Keep `/Users/dc/geha/advanced_rag/advanced_rag_no_reranker_jev.png` ready as the architecture figure.
5. Keep `/Users/dc/geha/advanced_rag/README.md` ready at the target AWS workflow and artifact layouts.
6. Use saved runs for expensive steps; perform a live provider call only when latency and credentials are acceptable.

### Reliable query-router examples

Enter one JSON object per line:

```jsonl
{"user_input":"Which employer benefits surveys report premium changes?"}
{"query":"What are the prior authorization criteria?"}
{"question":"Where can I find the Medicaid application form?"}
```

Expected destinations are `benefits_research`, `policy`, and `forms_directory`. Always point out whether the result says **JEV online** or **JEV unavailable · fallback active**. Do not present fallback output as a Jev result.

## Main recording script

### 0:00–0:45 — Hook: advanced RAG starts before vector search

**On screen**

- Move across the three application tabs.
- End on a contextualized page with original text, generated retrieval context, and a judge verdict.

**Narration**

> Most RAG diagrams begin with chunks and a vector database. That skips the hardest production questions: Was the document extracted correctly? Should a form be split at all? Which corpus should answer the query? Did generated context introduce an unsupported claim? And should this content be allowed into the index?
>
> This application makes those decisions visible. It routes queries, processes documents with bounded fallbacks, preserves source artifacts, adds retrieval-only context, judges that context, and exposes the state transition before indexing.

### 0:45–1:45 — System overview and honest deployment boundary

**On screen**

- Show `advanced_rag_no_reranker_jev.png`.
- Then show the target workflow in the README.

**Narration**

> The local system has a React control plane backed by FastAPI and a persistent runtime artifact store. It implements query routing, ingestion monitoring, Docling-first extraction, fallback OCR, table repair, contextual retrieval, whole-document form handling, an LLM judge, and reference hybrid policy retrieval.
>
> The production-oriented design maps those contracts onto S3, EventBridge, Step Functions, Fargate, DynamoDB, and CloudWatch. That AWS infrastructure is still a target architecture. I will not describe it as deployed. The value of the local implementation is that the artifacts, state transitions, and tests define what a later cloud deployment must preserve.

**On-screen callout**

```text
query → cluster router → selected corpus

PDF → Docling → quality gate → optional fallback → reviewable artifacts
                                                ↓
original evidence → contextualize → judge → approved retrieval representation
```

### 1:45–3:20 — Query and cluster routing

**On screen**

- Open **Query & Cluster Debugging**.
- Show the six cluster cards and document counts.
- Paste the three JSONL examples and click **Route query**.
- Expand the routing evidence, probabilities, destination, and event stages.

**Narration**

> Searching every document for every question increases latency and gives irrelevant chunks more opportunities to outrank the right evidence. This router partitions the demonstration corpus into policy, clinical guidance, population health, benefits research, forms and directories, and general research.
>
> The API validates each JSONL record, classifies the requested evidence, applies narrow deterministic guardrails for overlapping categories, and returns a destination with probabilities and evidence signals. Every run is persisted and can be replayed from the previous-run selector.
>
> When the TypeSafe SDK and API key are available, Jev performs the classification. Otherwise the application uses a transparent keyword scorer. The interface reports that distinction prominently because a fallback result must never be misrepresented as a model result.

### 3:20–4:20 — Why routing is not retrieval

**On screen**

- Keep the selected cluster highlighted.
- Point to `cluster/policy` or `cluster/forms_directory` in the destination field.

**Narration**

> This stage does not retrieve an answer. It selects the collection and processing contract that should be searched next.
>
> A prior-authorization question belongs in policy. A request for an application belongs in forms and directories. An employer-benefits survey should not compete against general population-health reports merely because both mention premiums or prevalence.
>
> Routing reduces the candidate universe, but retrieval quality still needs its own BM25, vector, fusion, grounding, and citation evaluation. A correct route can still be followed by a bad retrieval.

### 4:20–6:15 — Docling-first ingestion with bounded fallback

**On screen**

- Open **Ingestion**.
- Select a completed document.
- Show stage, route, OCR engine, page progress, review issues, and run artifacts.
- Use the page comparison viewer to place the source page beside the selected Markdown.
- If safe, show the OCR selector without starting an expensive run.

**Narration**

> Every PDF is split into single-page source PDFs before extraction begins. Docling processes each page first. A deterministic quality gate compares its Markdown with embedded PDF text and checks recall, replacement characters, suspiciously short output, and scan-like pages with too little text.
>
> Accepted pages remain Docling output. Only pages that fail the gate go to the selected DeepSeek or LlamaParse fallback. This is a bounded cascade: the expensive provider is not called for every page.
>
> The original page, candidate Markdown, metadata, quality decision, selected output, and errors are stored separately. The viewer advances source and Markdown together, so an operator can inspect the exact artifact that would become retrieval input.

**On-screen callout**

```text
source page PDF
   ↓
Docling Markdown
   ↓ deterministic quality gate
   ├── pass  → retain Docling
   └── fail  → DeepSeek or LlamaParse fallback
```

### 6:15–7:15 — Tables, figures, and review gates

**On screen**

- Show a table artifact or `table-postprocess.json`.
- Show a figure crop and its metadata if a saved example exists.
- Highlight `needs review` or the review issue count.

**Narration**

> Tables and figures are not treated as ordinary prose. The table pass detects placeholder headers such as zero, one, two or unnamed columns. It can inherit headers from an adjacent continuation or normalize a clear key-value table. When the repair is uncertain, it records `review_required` rather than guessing.
>
> Figures retain their crops and native text and require a structured vision description when a vision provider is configured. Failed table or figure validation increments the review count. A policy document with unresolved visual evidence is held at review instead of silently entering embeddings.
>
> Raw extraction is never overwritten. Normalized artifacts live beside it, preserving the evidence needed to diagnose a later answer failure.

### 7:15–9:10 — Contextual retrieval without corrupting evidence

**On screen**

- Open **Contextual Retrieval**.
- Select a completed narrative document.
- Show the document list, page selector, original extracted chunk, and contextual representation.
- Point to cache-created and cache-read token counts.

**Narration**

> A page can be locally clear but globally ambiguous. Contextual retrieval asks Claude for a short annotation that situates the page inside the complete document. The retrieval representation is that context plus the unchanged page text.
>
> The complete document is the stable prompt prefix and the page is the changing suffix. Prompt caching can therefore reuse the document across page requests. A nonzero cache-read token count is the evidence that caching actually occurred; repeating a prompt is not enough to claim a cache hit.
>
> Most importantly, generated context is not authoritative evidence. It can improve BM25 and embeddings, but answer generation and citations must use the preserved original text. This separation prevents an indexing annotation from becoming a policy fact.

**On-screen callout**

```text
retrieval text = generated document context + original page text
answer evidence = original page text only
```

### 9:10–10:10 — Forms use whole-document context

**On screen**

- Select one of the six registered forms.
- Point out the `1 unit` badge and **Run whole form** action.
- Show the unchanged source link and the generated contextual record.

**Narration**

> Forms and applications use a different context strategy. Splitting blank fields, instructions, certifications, and signatures into unrelated chunks destroys the relationships that define the form.
>
> The router therefore keeps each confirmed form as one retrieval unit. Claude produces a concise description of its issuer, purpose, applicant, major sections, required information, and submission instructions. A local BGE model embeds that context, while the database record retains the context and complete unchanged form.
>
> This is not universal chunking. It is document-type-aware context assembly.

### 10:10–11:20 — Judge source integrity and context grounding separately

**On screen**

- Return to a page-based document.
- Show a saved **Judge contexts** run.
- Highlight source-integrity status, context-grounding status, combined verdict, rationale, and page dots.

**Narration**

> Context generation introduces a new failure surface, so the application evaluates two independent questions.
>
> Source integrity asks whether the extracted Markdown is clean, suspect, or corrupt. It looks for gibberish, duplicated fragments, broken reading order, and synthetic headers. Context grounding asks whether the generated annotation is grounded, partially grounded, or unsupported by the supplied source.
>
> The combined result is pass, review, or fail. Results are checkpointed per page and reused only when the source hash, context hash, model, and prompt version still match. This is a text-grounding judge, not a pixel-level extraction proof; validating against the rendered page still requires the vision-review path.

### 11:20–12:15 — State, restartability, and audit artifacts

**On screen**

- Show the lifecycle label `EXTRACTED → CONTEXTUALIZED → JUDGED → INDEXED`.
- Show a run directory or the README artifact tree.
- Show the previous-run selectors.

**Narration**

> Each transition produces an artifact rather than only a log message. Page extraction, normalization, contextualization, and judgments checkpoint incrementally. Interrupted processing resumes from valid hashes instead of repeating every paid call.
>
> Immutable run directories preserve the source reference, selected page outputs, visual artifacts, run manifest, quality report, and structured errors. Previous query-router and ingestion runs remain inspectable in the UI.
>
> That makes error analysis stage-specific: route error, extraction error, table repair error, unsupported context, retrieval error, or answer-generation error.

### 12:15–13:15 — Retrieval contract and current limitations

**On screen**

- Show the Policy RAG flow in the README.
- Highlight reviewed-chunk filtering and original-text generation.

**Narration**

> The reference policy path runs BM25 over contextual retrieval text, vector similarity over contextual embeddings, reciprocal-rank fusion, and citation-bound answer generation. By default, only approved or passed chunks are searchable.
>
> This local ranker is a testable contract, not the final managed search service. The AWS state machine and service mapping are planned, not deployed. The corpus is a demonstration corpus, provider calls can incur cost, and the LLM judge must not be mistaken for human review or pixel-ground-truth validation.
>
> The architectural result is still useful: retrieval begins only after document routing, extraction, normalization, contextualization, and review have produced inspectable evidence.

### 13:15–13:45 — Close

**On screen**

- Return to the three tabs.
- End on the original-versus-context inspector.

**Narration**

> Advanced RAG is not a pile of optional model calls. It is a set of explicit contracts around evidence.
>
> Route to the right corpus. Choose a document-aware extraction strategy. Preserve the original. Add context only for retrieval. Judge the transformation. Gate uncertain content. Then retrieve, generate, and cite.
>
> That is how context engineering turns a vector-search demo into an auditable RAG system.

## Error-analysis segment if a live step fails

Do not hide a failed run. Classify the first failing stage:

| Visible symptom | First stage to inspect | Evidence to open |
| --- | --- | --- |
| Query enters the wrong cluster | Query classification or guardrail | Router signals, probabilities, method, and saved router run |
| Correct page has broken or missing text | Extraction | Source page, `docling.md`, quality JSON, and fallback Markdown |
| Table meaning is lost | Table normalization | Raw and normalized table artifacts plus `table-postprocess.json` |
| Context adds an unsupported statement | Context generation | Original page, generated context, judge rationale, source/context hashes |
| Context run repeats paid work | Cache or invalidation | Prompt version, hashes, cache-read tokens, and page checkpoint status |
| Correct evidence is indexed but not retrieved | BM25/vector/fusion | Ranked candidates and reviewed-chunk filter |
| Correct evidence is present but answer is wrong | Generation or citation binding | Exact original chunks supplied to the answer model |

Follow the error-analysis principle used throughout the repository: inspect individual failures, assign each to the earliest failing stage, and improve that stage before changing the entire architecture.

## Claims to avoid

- Do not say the AWS stack is deployed; the README labels it as a target architecture.
- Do not call the deterministic router fallback a Jev result.
- Do not claim a prompt-cache hit unless cache-read tokens are nonzero.
- Do not treat generated retrieval context as source evidence.
- Do not claim the text-only judge proves visual extraction accuracy.
- Do not claim Docling, DeepSeek, or LlamaParse is universally best from a small demonstration corpus.
- Do not imply that a passed LLM judgment replaces human review for regulated or high-impact documents.

## Post-recording cleanup

```bash
cd /Users/dc/geha/advanced_rag
docker compose down
```

Do not delete `runtime/` if the recorded runs, contextual records, judgments, or form-vector database should remain available for later demonstrations.
