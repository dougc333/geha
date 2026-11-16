# YouTube Demo Script: AWS Hybrid RAG with BM25, pgvector, Reranking, Tables, and Figures

**Target length:** 14–16 minutes  
**Application:** `aws_rag`  
**Audience:** AI solution architects, RAG engineers, and cloud platform teams  
**Central message:** A useful production RAG system is more than a vector database. This demo separates ingestion, retrieval, reranking, generation, evaluation, observability, reliability, and cost controls so each stage can be measured independently.

## Recommended video title

**Building Hybrid RAG on AWS: BM25 + pgvector + Bedrock Reranking**

## Thumbnail text

**BM25 + Vector + Rerank**

## What this video should demonstrate

1. S3 events, SQS queues, Lambda workers, Bedrock models, and Postgres/pgvector form an asynchronous ingestion and query architecture.
2. BM25 and vector search retrieve different evidence; reciprocal-rank fusion combines their rankings.
3. Amazon Rerank jointly scores the query and candidate chunks before generation.
4. Retrieval-only inspection makes ranking errors visible before an LLM can hide them behind a fluent answer.
5. Table-aware and figure-aware representations improve answerability when the evidence is not ordinary prose.
6. Offline evaluation, Langfuse traces, alarms, DLQs, budgets, and concurrency limits make the demo operationally credible.

## Before recording

### Confirm the deployed stack

```bash
cd /Users/dc/geha/aws_rag

aws sts get-caller-identity
aws cloudformation describe-stacks \
  --stack-name sam-app \
  --region us-west-2 \
  --query "Stacks[0].Outputs" \
  --output table
```

### Check whether the query API is paused

```bash
FN=$(aws cloudformation describe-stacks \
  --stack-name sam-app \
  --region us-west-2 \
  --query "Stacks[0].Outputs[?OutputKey=='QueryFunctionName'].OutputValue" \
  --output text)

aws lambda get-function-concurrency \
  --region us-west-2 \
  --function-name "$FN"
```

If `ReservedConcurrentExecutions` is `0`, the API is intentionally paused. Resume it for the recording:

```bash
aws lambda put-function-concurrency \
  --region us-west-2 \
  --function-name "$FN" \
  --reserved-concurrent-executions 10
```

Pause it again after the recording if desired:

```bash
aws lambda put-function-concurrency \
  --region us-west-2 \
  --function-name "$FN" \
  --reserved-concurrent-executions 0
```

### Open the demo pages

```bash
URL=$(aws cloudformation describe-stacks \
  --stack-name sam-app \
  --region us-west-2 \
  --query "Stacks[0].Outputs[?OutputKey=='QueryUrl'].OutputValue" \
  --output text)

open "$URL"
open "${URL}chat"
open "${URL}backends"
```

The first API request opens an in-page access-key dialog. Copy the shared key without printing it into a recorded terminal:

```bash
aws ssm get-parameter \
  --region us-west-2 \
  --name /rag-demo/api-key \
  --with-decryption \
  --query Parameter.Value \
  --output text | pbcopy
```

Paste it into the password field. The browser stores it in local storage for later requests.

### Prepare the recording tabs

1. Open the architecture diagram: `/Users/dc/geha/aws_rag/docs/architecture.png`.
2. Open the RAG Architecture Lab at the stack's root URL.
3. Open Paper Chat at `/chat`.
4. Open Postgres versus Weaviate at `/backends`.
5. Open the relevant Langfuse project if you want to show live traces.
6. Open the AWS CloudWatch dashboard pages for Lambda metrics, alarms, and SQS DLQs if showing operations.
7. Keep `/Users/dc/geha/aws_rag/evals/results.md` ready for the evaluation segment.
8. Hide AWS account IDs, database URLs, API keys, SSM values, and unrelated browser tabs.

### Use these reliable demo questions

| Type | Question | Expected evidence or answer |
|---|---|---|
| Table | What is the development accuracy of the BERT LARGE model in the SWAG dataset? | 86.6 |
| Figure | According to the YOLO error analysis chart, what percentage of YOLO's top detections are correct? | 65.5% |
| Fact | What is the default value of p used in the inverse distance weighted average interpolation in PointNet++? | 2 |
| Open | How does the SELF-RAG model utilize reflection tokens to enhance its text generation process? | Retrieval and critique/reflection tokens |
| Chat | What is Orca? | Cited explanation from the Orca paper |
| Follow-up | How was it evaluated? | Standalone rewrite using chat history |
| Library | Which papers are by Kaiming He? | Deterministic SQL-backed list |

### Reserve these known failures for the error-analysis chapter

This is the most importnt part of the video. Create enough error cases to fill out a table. 
https://learn.deeplearning.ai/courses/agentic-ai/lesson/pu5xbl/evaluations-(evals)?utm_campaign=The%20Batch&utm_source=hs_email&utm_medium=email

The error table describes the 3 areas where RAG can fail. (see slide deck)

| Eval case | Query | Observed failure | Initial category |
|---|---|---|---|
| `q41` | What learning rate did the Transformer paper use with the Adam optimizer? | Retrieval surfaces Scaling Laws and SGDR evidence instead of the Transformer optimizer section. | Retrieval or document-scope failure |
| `t03` | What is the top-1 validation error for ConvNet configuration E using the multi-crop evaluation method? | The answer returns `7.1%`, the top-5 value, instead of the expected `24.6%` top-1 value. | Table relationship or generation-selection failure |

These labels are hypotheses until the full trace is inspected. For example, `t03` is a context-assembly failure if the selected evidence omitted the row/column relationship, but it is a generation failure if the complete table was present and the model still selected the wrong cell.

## Main recording script

### 0:00–0:40 — Hook: inspect retrieval before trusting generation

**On screen**

- Begin in the RAG Architecture Lab.
- Keep **Generate answer** off.
- Show a list of ranked chunks with page, score, and latency.

**Narration**

> A fluent answer can hide a bad retrieval decision. So I am starting with generation turned off.
>
> This AWS RAG system lets me hold the document and question constant, switch among BM25, vector, and hybrid retrieval, add Bedrock reranking, and inspect the exact chunks before asking a language model to write anything.
>
> The goal is not to call more models. The goal is to assign every failure to the correct stage: ingestion, keyword retrieval, vector retrieval, rank fusion, reranking, or answer generation.

### 0:40–1:45 — Architecture overview

**On screen**

- Show `docs/architecture.png`.
- Move left to right through ingestion, stores, and query.

**Narration**

> The ingestion side is event driven. A PDF in the raw S3 bucket produces an S3 event, which enters an SQS queue. The chunker Lambda writes page-aware JSONL into the chunks bucket. That object event enters a second queue, and the embedder Lambda calls Titan Text Embeddings V2 and replaces the document's rows in Neon Postgres.
>
> Both queues have dead-letter queues. The embedder is capped at two concurrent Lambdas to protect database connections and Bedrock quotas.
>
> Postgres is the source of truth. It stores document metadata, text, table and figure chunks, 1,024-dimensional Titan vectors with an HNSW index, and the `rag_terms` inverted index used for BM25. Weaviate holds a comparison copy of the same chunks and vectors.
>
> The query application is FastAPI running in Lambda through Mangum. It performs routing, retrieval, reciprocal-rank fusion, Amazon Rerank, and cited answer generation with Nova Lite. The browser reaches it through a Lambda Function URL protected at the API layer by a shared key.

**On-screen callout**

```text
S3 → SQS → Chunker Lambda → S3 JSONL → SQS → Embedder Lambda
                                                ↓
                              Neon Postgres + pgvector + BM25
                                                ↓
                      Query Lambda → Rerank → cited Bedrock answer
```

### 1:45–2:30 — Explain the ingestion variants honestly

**On screen**

- Keep the architecture visible.
- Highlight the local Docling and figure-description path separately from the Lambda flat-text path.

**Narration**

> There are two ingestion paths in this project.
>
> The basic S3-triggered Lambda path uses PyMuPDF page text with 350-word chunks and 50-word overlap. 
>
> The Docling chunker, preserves tables as Markdown chunks, extracts figure images, and asks Nova Lite to describe what is visibly present. Those JSONL artifacts are then uploaded to the chunks bucket and enter the same embedder path. The AWS docling EC2 implementation costs $200/month so instead the extraction is done on a macbook. This is the default chunking strategy.  
>
> For validated GEHA documents, a cryptographically bound sidecar supplies page text only after visual comparison has passed. Missing or mismatched sidecars fail into the retry and dead-letter path rather than silently falling back. Not part of teh job posting but you have to verify the steps and thsi is where PII filtering takes place if necessary. 

### 2:30–4:35 — Retrieval laboratory: vector versus BM25 versus hybrid

**On screen**

- Select the paper containing the BERT SWAG table.
- Enter: **What is the development accuracy of the BERT LARGE model in the SWAG dataset?**
- Keep **Generate answer** and **Reranker** off.
- Run Vector, then BM25, then Hybrid.
- Pause on rankings and timing for each run.

**Narration**

> Vector retrieval embeds the question with Titan and searches the pgvector HNSW index by cosine similarity. It is useful when the question paraphrases the source.
>
> BM25 uses an inverted index in Postgres and scores exact query terms with term frequency, inverse document frequency, and document-length normalization. It is strong for model names, dataset names, codes, numbers, and uncommon terminology.
>
> Hybrid retrieval does not average raw BM25 and cosine scores because those scores are not on the same scale. Instead, reciprocal-rank fusion combines the two ranked lists. A chunk receives credit for appearing near the top of either list.
>
> I am comparing evidence before generation. The correct table chunk should keep 86.6 adjacent to the BERT LARGE row and the development-accuracy column. A flat page extraction can retrieve the right page while losing that row-and-column relationship.

**On-screen callout**

`Hybrid = BM25 rank + vector rank → reciprocal-rank fusion`

### 4:35–5:35 — Add Amazon Rerank

**On screen**

- Stay on the same document and question.
- Enable **Reranker**.
- Run Hybrid again.
- Compare the order and point out `rerank_score` and rerank latency.

**Narration**

This is an example of the canonical RAG system. This hasn't been optimized for tool calls. We cover 3 things in the expanded demo:
1) how to do error analysis which is the most important part of the system
2) Ablation analysis between Weviate/Postgres, safety guards using Nemotron safety model, table and figure analysis, retriveal methods: BM25, vector, hybrid RRF, vector-weighted RRF, and semantic vs fusion reranker

> Fusion is not a semantic reranker. It combines rankings produced independently by BM25 and vector search. The ablation tests with and without a semantic ranker were too small to translate into a meaningful difference in search quality. The results are in the readme.
>
> Amazon Rerank receives the question and the fused candidate chunks together, jointly scores each query-chunk pair, and returns the best evidence for generation. The configured path reranks up to 50 candidates before selecting the final sources.
>
> The reranker adds roughly one second, so its value must be measured. In the 103-paper evaluation, the production BM25-plus-vector path reached 68 percent hit at rank one with BM25 alone and 55 percent with vector alone. Hybrid plus reranking reached 82 percent hit at one and 95 percent hit at five. 
>
> The project still documents one missing ablation: BM25 plus the same reranker. Without that condition, we should not claim that fusion alone causes the complete gain.

### 5:35–6:20 — Turn on cited generation

**On screen**

- Enable **Generate answer** while keeping Hybrid and Reranker on.
- Run the same question.
- Show the grounded answer, evidence chunks, pages, and timings.

**Narration**

> Only after inspecting retrieval do I turn on generation. Nova Lite receives the numbered sources and is instructed to answer from those sources with citations.
>
> The timing panel separates embedding, keyword search, vector search, reranking, and generation. A warm content request is typically dominated by reranking and answer generation rather than database retrieval.
>
> The answer is the final layer. The retrieved chunks remain visible so a reviewer can verify that the stated value is actually supported.

### 6:20–8:15 — Paper Chat: routing, citations, and follow-ups

**On screen**

- Switch to `/chat`.
- Ask: **What is Orca?**
- Expand or scroll through the cited sources and timing line.
- Follow with: **How was it evaluated?**
- Then ask: **Which papers are by Kaiming He?**

**Narration**

> Paper Chat searches across the full corpus rather than one selected document.
>
> Every turn first goes through a small router. Content questions go through retrieval, reranking, and cited generation. A follow-up such as “How was it evaluated?” is rewritten into a standalone search query using the conversation history.
>
> Questions about the library itself take a different path. “Which papers are by Kaiming He?” is answered from document metadata with SQL. The result is built deterministically instead of asking an LLM to reproduce a long catalog from memory.
>
> This is an important solution-architecture pattern: use generation for synthesis, but use structured queries for authoritative lists, counts, authors, years, categories, and identifiers.

**On-screen callout**

```text
Router
├── list/find → SQL metadata answer
└── content   → BM25 + vector → RRF → rerank → cited generation
```

### 8:15–9:15 — Figure-aware answer with source thumbnail

**On screen**

- Ask: **According to the YOLO error analysis chart, what percentage of YOLO's top detections are correct?**
- Show the answer `65.5%` and the figure thumbnail beneath the cited source.
- Click the thumbnail to show the full-size presigned image.

**Narration**

> Text retrieval alone cannot answer a value that appears only inside a chart. The figure-aware path extracts each figure image, asks Nova Lite to transcribe visible labels and numbers before summarizing it, and indexes that description as a figure chunk.
>
> When a selected source has an image key, the API returns a one-hour presigned S3 URL and the chat displays the figure under the answer.
>
> On the nine figure-only evaluation questions, the text-only system answered zero. Figure chunks increased answer accuracy to seven of nine, with the correct page at rank one for all nine. The remaining misses are useful evidence: plotted relationships without printed values and poorly rendered vector figures are still difficult.

### 9:15–10:10 — Compare Postgres and Weaviate

**On screen**

- Switch to `/backends`.
- Use a suggested query such as **how does dropout prevent overfitting**.
- Run the side-by-side comparison.
- Point to overlapping and unique chunks and the timing badges.

**Narration**

> The same chunks and Titan vectors are also copied into Weaviate for a controlled backend comparison.
>
> Postgres runs BM25 over `rag_terms`, vector nearest-neighbor search through pgvector, and reciprocal-rank fusion in application code. Weaviate performs native hybrid search and exposes the keyword-versus-vector balance through alpha.
>
> This comparison is about retrieval behavior, not brand preference. At 103 papers, Postgres hybrid plus rerank and Weaviate hybrid plus rerank produced the same 82 percent hit at one, 95 percent hit at five, and 0.88 MRR at ten. The identical vectors help isolate search and fusion differences.

**Qualification to say aloud**

> The Weaviate sandbox uses HFresh while Postgres uses HNSW, and new papers are not copied automatically, so the comparison is valid only when the mirror is current.

### 10:10–11:00 — Show Langfuse observability

**On screen**

- Open the Langfuse trace for the Orca turn.
- Show the route, retrieval, query embedding, rerank, and answer observations.
- Show token usage and timings without exposing sensitive values.

**Narration**

> Each lab query and chat turn can be traced in Langfuse. The trace records routing, retrieval, embedding, reranking, answer generation, chunk IDs, scores, token usage, and latency.
>
> Thumbs-up or thumbs-down feedback in the chat is stored as a score on the trace. Because Lambda can freeze immediately after a response, traces are flushed at the end of each request.
>
> Public papers are appropriate for this demonstration. Sensitive member questions and passages would require a BAA or self-hosted observability, explicit retention rules, and a different security review.

### 11:00–12:05 — Evaluation evidence, not anecdotes

**On screen**

- Open `evals/results.md` or a prepared results slide.
- Highlight the 62-question mixed suite and the 202-paper scaling results.

**Narration**

> A few successful demo questions are not evidence of system quality. The repository stores the questions, expected evidence, rankings, answer checks, and Markdown summaries.
>
> The mixed evaluation contains fact, paraphrase, table, and figure questions. Across 203 papers, the current reranked hybrid path records 77 percent hit at one, 95 percent hit at five, and 0.85 MRR at ten. Table-aware Docling extraction answered 11 of 13 table questions. Figure-aware chunks answered seven of nine figure-only questions.
>
> These are configuration-bound measurements, not universal claims. The table and figure results come from separate rollout phases, and generated fact questions may preserve source wording, which can favor keyword retrieval.
>
> A scheduled GitHub Actions quality gate runs the production retrieval path without reranking and checks recall, MRR, nDCG, and latency. Keeping the non-reranked gate controls cost while still detecting index or retrieval regressions.

### 12:05–13:35 — Andrew Ng-style error analysis: inspect, categorize, and prioritize

**On screen**

- Open the complete Langfuse traces for `q41` and `t03`.
- Put the retrieved candidates, reranked context, generated answer, and expected answer side by side.
- Fill in an error-analysis worksheet rather than changing the system immediately.

| Query ID | Expected evidence | Correct evidence retrieved? | Reranker kept it? | Required facts reached the prompt? | Answer supported? | First failing stage | Primary error category | Candidate fix |
|---|---|---|---|---|---|---|---|---|
| `q41` | Transformer optimizer schedule | No | Cannot rescue an absent candidate | No | No | Retrieval | Document scope / retrieval miss | Add title-aware filtering or contextual indexing, then rerun |
| `t03` | ConvNet E, multi-crop, top-1 = 24.6% | Inspect trace | Inspect trace | Inspect trace | No; returned top-5 = 7.1% | Determined from trace | Table representation, context assembly, or generation selection | Preserve row/column structure or verify the selected cell |

**Narration**

> Andrew Ng's error-analysis method starts with a working baseline, then manually examines failed development examples before choosing a fix. For an agentic or RAG workflow, DeepLearning.AI extends that idea: read the complete trace and find the step that performed materially worse than a human could have performed with the same inputs.
>
> I record the **first failing stage**, because downstream failures are often symptoms. If the correct chunk never enters the candidate set, the reranker and generator cannot recover it. If the complete table reaches the prompt and the model chooses the wrong cell, retrieval succeeded and the failure belongs to generation or answer verification.
>
> `q41` is initially a retrieval and document-scope failure. The system retrieves evidence from Scaling Laws and SGDR rather than the Transformer optimizer section. A larger language model would not repair missing evidence; the candidate fixes are title-aware filtering, metadata constraints, or contextual indexing.
>
> `t03` returned 7.1 percent, the top-5 value, instead of the expected 24.6 percent top-1 value. I do not label that from the final answer alone. If extraction or context assembly lost the row-and-column relationship, it is a representation failure. If the complete table was present, it is a generation-selection failure and should trigger structured verification or deterministic cell lookup.

**Use one mutually exclusive primary category for counting**

1. Gold answer or evaluation-data defect
2. Ingestion or representation loss, including damaged tables and figures
3. Router, metadata-filter, or document-scope error
4. BM25 candidate miss
5. Vector candidate miss
6. Fusion or reranker error
7. Context-assembly omission or distracting noise
8. Generation error: omitted fact, wrong selection, or incorrect synthesis
9. Unsupported claim or citation failure
10. Guardrail, timeout, dependency, or other operational failure

Secondary tags are useful, but one primary root cause keeps the totals interpretable.

**Narration**

> After labeling the failures, I count them. If a category appears in `n` of 62 evaluation questions, fixing it perfectly can improve this suite by at most `n / 62`. That ceiling is not a promise; it is a way to compare potential payoff. I prioritize categories that are frequent, important to users, actionable, and unlikely to create regressions.
>
> Andrew Ng recommends manually reviewing roughly one hundred errors when the development set is large. This suite has only 62 questions, so I can inspect every failure. I keep the cases used for diagnosis in an **eyeball set** and reserve an untouched **blackbox holdout** to test whether the fix generalizes instead of merely fitting the examples I studied.
>
> The loop is: establish a baseline, inspect traces, categorize the first failure, count categories, fix the highest-value bottleneck, and rerun both the inspected cases and the untouched holdout. Error analysis turns two embarrassing misses into evidence about where engineering effort should go next.

### 13:35–14:30 — Reliability and cost controls

**On screen**

- Show the CloudFormation/SAM resources or CloudWatch alarm list.
- Point to SQS queues and their DLQs.
- Show the query Lambda concurrency setting and budget configuration.

**Narration**

> The operational controls are part of the architecture, not an appendix.
>
> Failed ingestion messages retry and then move to dead-letter queues. CloudWatch alarms cover unhandled query errors, throttling, slow requests, chunker and embedder failures, and messages arriving in either DLQ.
>
> Query Lambda reserved concurrency caps parallel requests and limits Bedrock exposure if the shared API key leaks. The stack also defines an account-wide monthly budget, 30-day log retention, and an SNS alert topic.
>
> When the demo is not in use, setting reserved concurrency to zero stops chat traffic without deleting the Function URL, database, or indexed documents.

### 14:30–15:10 — Production boundary and close

**On screen**

- Return to the architecture diagram or the cited figure answer.
- Display the repository path `aws_rag/`.

**Narration**

> This is a technically complete demo, but it is not yet a production member-facing service.
>
> The shared API key should become per-user authentication through API Gateway with Cognito or another OIDC provider, plus rate limits and WAF controls. Sensitive tracing needs an approved data boundary. Deployment should move from laptops to staged CI/CD with retrieval and safety evaluations as gates and automatic rollback.
>
> The main lesson is architectural: preserve document structure, combine exact and semantic retrieval, inspect rankings before generation, use reranking only when the evaluation justifies its latency, and operate the system with the same discipline as any other cloud service.

## Optional ingestion segment: add an arXiv paper

Use this as an additional 90-second chapter only when you are comfortable incurring ingestion and embedding calls.

**On screen**

- In Paper Chat, paste an arXiv ID into **Add an arXiv paper**.
- Show the status until the paper appears in the library.
- In a terminal, show the raw and chunks buckets and tail the two Lambda logs.

```bash
cd /Users/dc/geha/aws_rag

STACK=sam-app
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
RAW=$STACK-raw-$ACCOUNT
CHUNKS=$STACK-chunks-$ACCOUNT

aws s3 ls "s3://$RAW/arxiv/"
aws s3 ls "s3://$CHUNKS/chunks/"
sam logs --stack-name "$STACK" --name Chunker --tail
sam logs --stack-name "$STACK" --name Embedder --tail
```

**Narration**

> Adding an arXiv paper writes the PDF and its metadata sidecar to the raw S3 bucket. S3 notifies the chunk queue, the chunker writes deterministic JSONL, the chunks bucket notifies the embed queue, and the embedder replaces that document's rows in one transaction.
>
> This live add-paper feature uses the Lambda flat-text chunker. It does not automatically perform the richer local Docling table extraction or figure-description workflow. Those representations are separate preprocessing paths and should not be claimed for a newly added paper unless they were actually run.

## Optional 90-second version

> This AWS RAG system separates each stage so retrieval quality is visible before generation.
>
> PDFs and metadata enter S3, SQS buffers the work, Lambda creates page-aware JSONL, Titan produces 1,024-dimensional embeddings, and Neon Postgres stores document metadata, chunks, pgvector embeddings, and a BM25 inverted index.
>
> In the retrieval lab I can hold one document and question constant, then switch among vector, BM25, and hybrid search. Hybrid uses reciprocal-rank fusion because cosine and BM25 scores are not directly comparable. Amazon Rerank then jointly scores the question and up to 50 candidates before Nova Lite writes a cited answer.
>
> Table-aware Docling chunks preserve rows, columns, and captions. Figure chunks describe the visible image and return a source thumbnail with the answer. On the recorded mixed evaluation, the current 203-paper system achieved 95 percent hit at five and 0.85 MRR at ten; table questions were answered 11 of 13 times and figure-only questions seven of nine.
>
> Known misses are replayed as error-analysis cases: inspect the full trace, label the first failing stage, count failure categories, and prioritize the fix with the greatest measurable payoff.
>
> Langfuse traces routing, retrieval, reranking, generation, tokens, and latency. SQS dead-letter queues, CloudWatch alarms, a budget, log retention, and Lambda concurrency limits provide operational controls.
>
> The result is not “vector search plus an LLM.” It is an observable retrieval and evidence system whose architecture can be tested one component at a time.

## Suggested YouTube chapters

```text
00:00 Inspect retrieval before generation
00:40 AWS architecture
01:45 Flat, table-aware, figure-aware, and validated ingestion
02:30 Vector versus BM25 versus hybrid
04:35 Amazon Bedrock reranking
05:35 Cited answer generation
06:20 Chat routing and follow-up questions
08:15 Figure-aware answers and thumbnails
09:15 Postgres versus Weaviate
10:10 Langfuse traces
11:00 Offline retrieval and answer evaluation
12:05 Andrew Ng-style trace and error analysis
13:35 Reliability and cost controls
14:30 Production boundary and summary
```

## Error-analysis sources

- Andrew Ng, DeepLearning.AI, *Agentic AI — Evaluations (evals)*: the course lesson referenced for this demo's workflow-level evaluation framing.  
  <https://learn.deeplearning.ai/courses/agentic-ai/lesson/pu5xbl/evaluations-(evals)>
- Andrew Ng, *Machine Learning Yearning*: build a baseline quickly, manually inspect development-set errors, count categories, estimate their potential payoff, and separate an inspected eyeball set from an untouched blackbox set.  
  <https://home-wordpress.deeplearning.ai/wp-content/uploads/2022/03/andrew-ng-machine-learning-yearning.pdf>
- Andrew Ng, DeepLearning.AI, *Improve Agentic Performance with Evals and Error Analysis — Part 1*: prototype first, inspect outputs, and iteratively define objective and subjective evaluations.  
  <https://www.deeplearning.ai/the-batch/improve-agentic-performance-with-evals-and-error-analysis-part-1>
- Andrew Ng, DeepLearning.AI, *Improve Agentic Performance with Evals and Error Analysis — Part 2*: inspect complete traces for subpar outputs and identify the workflow step that most needs improvement.  
  <https://www.deeplearning.ai/the-batch/improve-agentic-performance-with-evals-and-error-analysis-part-2/>

## Accuracy and recording notes

- The deployed stack name in `samconfig.toml` is `sam-app` in `us-west-2`.
- The browser pages are public, but `/api/*` except health requires the shared `X-API-Key`.
- Do not display the API key, AWS account ID, database URL, SSM values, or Langfuse secrets.
- The Function URL uses `AuthType: NONE`; the shared key is application-layer demo protection, not production identity.
- Do not call reciprocal-rank fusion a reranker. It fuses ranked lists without jointly evaluating query-document pairs.
- The default learned reranker is Amazon Rerank 1.0 through Bedrock.
- New arXiv papers added through the UI use the Lambda flat-text path. The richer Docling table and figure workflow is separate.
- The current figure-aware corpus contains generated descriptions. Preserve figure images as the authoritative visual evidence.
- Retrieval hit at five measures whether a gold page appears in the first five results. It does not prove answer correctness.
- The 103-paper and 203-paper results use different corpus sizes; state which one you are quoting.
- The 62-question mixed suite combines fact, paraphrase, table, and figure questions. Table and figure improvements were evaluated on their own subsets.
- The README identifies a missing `BM25 → same reranker` ablation. Do not attribute the whole gain specifically to hybrid fusion until that condition is run.
- Warm and cold Lambda latencies differ. The first request after idle may include database wake-up and Lambda cold-start time.
- Weaviate is a comparison copy, not the system of record, and must be refreshed after new papers are indexed.
- Langfuse receives questions, retrieved passages, and answers. Use only public data in this demo.
- The monthly budget is account-wide, not isolated to this stack.
- Pausing QueryApi with reserved concurrency zero intentionally produces throttling; restore concurrency before the demo.

## Suggested links for the video description

```text
AWS RAG implementation:
aws_rag/

Architecture diagram:
aws_rag/docs/architecture.svg

Retrieval and answer evaluations:
aws_rag/evals/

AWS SAM infrastructure:
aws_rag/template.yaml
```
