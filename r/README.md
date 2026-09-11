# GEHA RAG demo

Standalone Streamlit + LangGraph + persistent Chroma demo over two GEHA policy PDFs.

## Start

```bash
cd /Users/dc/geha/r
uv sync
uv run streamlit run app.py
```

Open http://localhost:8501. Search and retrieval evaluation require no API key.
The first index build downloads Chroma's local MiniLM ONNX embedding model.

## Model answers

The sidebar accepts a chat-completions-compatible endpoint, model name and optional key.
For local Ollama, run `ollama pull llama3.2:3b`, start Ollama, and enable model answers.
Default endpoint: http://localhost:11434/v1. Default model: llama3.2:3b.
For another provider, supply its base URL (including /v1 if required), model and key.
Generation sends only the current question and retrieved excerpts. Keys are not written to files.
No conversation memory is used. Each question is independent.

## Documents and retrieval

`data/sources/`: original PDFs. `data/documents/`: extracted complete Markdown.
`ingest.py` extracts text and table boundaries without OCR. Character-center filtering avoids
clipped characters at table boundaries in the earlier extraction. Source spelling is retained.
`data/tables.json`: extracted rows with page provenance. A continued table repeats headers.
Tables remain whole chunks; long prose uses overlapping word windows. Table descriptions,
codes and preference fields are kept together. Hybrid retrieval fuses local vector similarity
with keyword matching. Fusion scores are ranks, not probabilities or confidence.
Document content fingerprints select persistent collections, preventing stale document reuse.
Old collections remain on disk; this demo does not automatically purge prior indexes.

## Evaluation

```bash
uv run python evaluate.py
uv run pytest -q
```

`evals/cases.json` is separate from the index: six answerable cases and two abstention cases.
Retrieval checks require expected source/page and terms in the retrieved evidence; this is a
smoke test, not a statistically representative benchmark or answer-correctness measure.
Abstention cases are not scored in retrieval-only mode.

Optional generation run (requires configured model server):

```bash
MODEL_BASE_URL=http://localhost:11434/v1 MODEL_NAME=llama3.2:3b uv run python evaluate.py --generate
```

Use MODEL_API_KEY if required. Results go to results/ with reference answers for review.
Generation checks enforce valid citation IDs and score declared abstention, but semantic answer
correctness still needs human review. A valid citation does not prove entailment.

To regenerate the project data and refresh its index: `uv run python ingest.py`, then restart
Streamlit. Evaluation answers are verified against the supplied policy version, not current coverage.
