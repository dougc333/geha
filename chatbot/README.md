# chatbot

A RAG system feeding a chatbot, tried out on arXiv papers. It's a chat page on
top of the serverless RAG stack in [`../aws_rag`](../aws_rag): same index, same
models, no extra infrastructure.

**Open it:** the `ChatUrl` output of the `sam-app` stack, i.e. the query
Lambda's URL plus `/chat`:

```bash
aws cloudformation describe-stacks --stack-name sam-app --region us-west-2 \
  --query "Stacks[0].Outputs[?OutputKey=='ChatUrl'].OutputValue" --output text
```

## What it does

- **Multi-turn chat across every indexed paper.** Follow-ups work: "what is
  QLoRA?" then "what hardware did they fine-tune on?"
- **Cited answers.** Each answer cites numbered sources `[1]`; the sources
  (paper, page, chunk, rerank score, snippet) are listed under the answer.
- **Traced in Langfuse.** Each message is a trace (route → retrieve →
  rerank → answer, with prompts, chunks, tokens and timings), each page load a
  session, and 👍/👎 under an answer becomes a score. Setup is in
  [`../aws_rag/README.md`](../aws_rag/README.md#tracing-with-langfuse).
- **Add papers by arXiv ID or link** from the page, or with `add_arxiv.py`.
  A new paper is searchable about 10 seconds later.

## How a turn works

```
browser (chat.html, keeps the conversation)
  │  POST /api/chat {messages: [...last 20]}
  ▼
QueryApi Lambda (aws_rag/query/chat.py)
  1. route     library question or content? + standalone query   Nova Lite
              library (list/count/authors/topics) → SQL on rag_documents, done
  2. retrieve  BM25 over all chunks + pgvector top 25  Titan Text Embeddings v2, Neon
               fused with reciprocal-rank fusion
  3. rerank    up to 50 candidates → top 6            Amazon Rerank 1.0
  4. answer    history + numbered sources             Nova Lite, cite-only-sources prompt
  ▼
{answer, standalone_question, sources[], timings}
```

Adding a paper:

```
POST /api/arxiv {paper: "2305.14314"}
  → arXiv API for the title → download PDF (≤25 MB) → s3://<raw>/arxiv/<id>.pdf
    (title stored as S3 metadata) → chunker → embedder → Neon
```

The chatbot searches every turn, rather than letting the model decide when to
search, which keeps it predictable with a small model. It calls the search code
directly, so the RAG stack doesn't need to be an MCP server. An MCP endpoint
could be added later to use the same papers from Claude Desktop or Claude Code.

## Adding papers from the command line

```bash
python add_arxiv.py 2305.14314 https://arxiv.org/abs/2310.11511
```

It uses only the standard library. It finds the API URL from the stack (needs
the AWS CLI), or pass `--url` / set `CHATBOT_URL`. It waits until each paper is
indexed; `--no-wait` returns right away.

## Cost and speed

About 3.5–5 s per content message (library answers ~1.5–2.5 s): roughly 0.4 s route, 0.5 s BM25, 0.25 s vector,
0.8 s rerank and 0.5–2 s generation. Per message, about $0.0015 in Bedrock
(rerank $0.001, two Nova Lite calls, one embedding). Adding a 15-page paper
costs about $0.0002 to embed. Lambda, SQS and logs are within the free tier.

## Limits

- **The page's URL is public.** Anyone with it can chat (Bedrock cost) and
  add papers (only from arXiv, ≤25 MB each). Add auth before sharing widely.
- **BM25 scans every chunk on each turn.** Fine for hundreds of papers; beyond
  that, move BM25 into Postgres full-text search.
- **Comparisons can lean on one paper.** "Compare Orca and Self-RAG" may
  retrieve mostly one paper's chunks, because the top 6 aren't balanced across
  papers.
- **The conversation isn't saved.** It lives in the browser tab.
- **Papers added before the chatbot** are titled by file name (e.g.
  `2306.02707`); papers added by arXiv ID get their real titles.
