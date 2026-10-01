# e2e_RAG

This project includes PDF loading, chunking, Chroma retrieval, optional query
expansion and reranking, answer generation, and an optional offline Ragas
evaluation command.

## Install

```bash
cd /Users/dc/geha/e2e_RAG
uv pip install -r requirements.txt
```

Set `OPENAI_API_KEY` in the environment before using OpenAI generation or
evaluation models.

## Run the Ragas evaluation

Copy `evals/questions.example.jsonl` and replace its sample content with
approved questions and reference answers. Each JSONL record requires
`user_input` and `reference`; `reference_contexts` is optional.

```bash
cd /Users/dc/geha/e2e_RAG/src
python evaluate_ragas.py \
  --pdf ../data/2306.02707.pdf \
  --dataset ../evals/questions.example.jsonl \
  --output ../evals/results.json \
  --reranker-model none
```

The report contains per-question and mean scores for:

- `faithfulness`: whether claims in the answer are supported by retrieved text.
- `answer_relevancy`: whether the answer addresses the question.
- `context_precision`: whether useful passages are ranked ahead of noise.
- `context_recall`: whether the retrieved passages contain the reference facts.

Ragas is kept out of the normal CLI and Streamlit answer path. Evaluation makes
additional evaluator-model and embedding API calls, so run it deliberately on
a versioned test set rather than on every user request.

The project pins Ragas 0.4.3. That release imports a LangChain Vertex AI
compatibility module that modern `langchain-community` removed, so the local
adapter supplies the optional import only for Ragas. This evaluation uses
OpenAI and does not install or invoke Vertex AI.

## Test

```bash
cd /Users/dc/geha/e2e_RAG/src
python -m unittest test_class_refactor test_ragas_evaluator
```

## Retrieval benchmark

The retrieval-only benchmark exercises the actual dense parent-document path:
PDF extraction, token-aware parent/child chunking, BGE embeddings, Chroma
maximum-inner-product retrieval, and parent lookup. It does **not** call an
answer-generation model or Ragas, so its metrics isolate retrieval behavior.

The versioned fixture contains 14 grounded questions over seven tracked PDFs.
Gold labels are source filenames. Because several parent chunks can come from
one PDF, retrieved chunks are deduplicated by source before calculating:

| Metric | Meaning |
|---|---|
| Recall@5 | Fraction of relevant source PDFs found in the first five unique sources |
| MRR@10 | Reciprocal rank of the first relevant source, capped at rank 10 |
| nDCG@10 | Position-discounted ranking quality for all relevant sources through rank 10 |
| Latency | Median and p95 retriever query time; model loading and indexing are excluded |

Run the production BGE profile used in CI:

```bash
cd /Users/dc/geha
PYTHONPATH=e2e_RAG/src \
  .venv/bin/python e2e_RAG/evals/retrieval_benchmark.py \
  --embedding-model BAAI/bge-large-en-v1.5 \
  --out e2e_RAG/evals/retrieval_results

.venv/bin/python e2e_RAG/evals/check_retrieval_thresholds.py \
  e2e_RAG/evals/retrieval_results.json
```

For a faster development-only comparison, replace the model argument with
`BAAI/bge-small-en-v1.5`. Do not compare its latency directly with the large
model's CI baseline.

Observed local baseline on the 14-question fixture (2026-09-30):

| Embedding profile | Recall@5 | MRR@10 | nDCG@10 | Median latency |
|---|---:|---:|---:|---:|
| `BAAI/bge-large-en-v1.5` | 1.0000 | 1.0000 | 1.0000 | 86.9 ms |
| `BAAI/bge-small-en-v1.5` | 1.0000 | 0.9643 | 0.9736 | 14.8 ms |

CI gates are intentionally below that baseline: Recall@5 ≥ 0.90, MRR@10 ≥
0.80, nDCG@10 ≥ 0.82, and median latency ≤ 2,000 ms. The broad latency budget
allows for shared GitHub CPU runners while still catching severe regressions.
The workflow publishes both JSON evidence and a Markdown summary as artifacts.
