# GEHA RAG demo

Standalone Streamlit + LangGraph + persistent Chroma demo over two GEHA policy PDFs.

## Start

```bash
cd /Users/dc/geha/RAG_demo
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

## Presentation chunk export and preference-row evaluation

```bash
cd /Users/dc/geha/RAG_demo
uv run python export_indexed_chunks.py
uv run python evaluate_preference_rows.py
```

`indexed_chunks.txt` contains the exact stored text of the 26 Chroma chunks from
the two PDFs, grouped by source, page, and chunk. `evals/preference_rows.json`
contains the same 13 questions used by the naive Chroma evaluation. The
evaluator updates the results below and writes a standalone Markdown report
and JSON report in `evals/`. It checks each source table row's drug, preference,
prior authorization, and code together before scoring retrieval.

<!-- PREFERENCE_ROW_EVAL_START -->
### RAG_demo preference-row retrieval evaluation

The 13 questions are copied verbatim from the naive_chroma gold question set.
This test searches both indexed PDFs using the same hybrid retriever as the Streamlit app.
Before scoring, it confirms that the drug, preference, prior authorization, and HCPCS code
occur together in one Markdown table row. A hit then means the complete table chunk was retrieved;
it does not measure generated-answer correctness.

- Indexed: **2 PDFs**, **26 chunks**.
- Verified gold table rows: **13/13**.
- Table hit@1: **12/13** (92.3%).
- Table hit@4: **13/13** (100.0%).

| Preference | Questions | Hit@1 | Hit@4 |
|---|---:|---:|---:|
| preferred | 3 | 3 | 3 |
| non-preferred | 10 | 9 | 10 |

| ID | Question | Gold answer | Gold table chunk | Top result | Gold rank | Top-1 diagnosis |
|---|---|---|---|---|---:|---|
| bendamustine_01 | In the bendamustine policy, is Treanda preferred? What is its HCPCS code and prior authorization requirement? | Treanda: preferred; HCPCS J9033; prior authorization Yes. | bendamustine-p1-001 | bendamustine-p1-001 | 1 | Exact gold row is in the first table chunk. |
| bendamustine_02 | In the bendamustine policy, is Bendamustine 505(b)(2) Dr Reddy's preferred? What is its HCPCS code and prior authorization requirement? | Bendamustine 505(b)(2) Dr Reddy's: preferred; HCPCS J9999; prior authorization Yes. | bendamustine-p1-001 | bendamustine-p1-001 | 1 | Exact gold row is in the first table chunk. |
| bendamustine_03 | In the bendamustine policy, is Bendeka preferred? What is its HCPCS code and prior authorization requirement? | Bendeka: non-preferred; HCPCS J9034; prior authorization Yes. | bendamustine-p1-001 | bendamustine-p1-001 | 1 | Exact gold row is in the first table chunk. |
| bendamustine_04 | In the bendamustine policy, is Belrapzo preferred? What is its HCPCS code and prior authorization requirement? | Belrapzo: non-preferred; HCPCS J9036; prior authorization Yes. | bendamustine-p1-001 | bendamustine-p1-001 | 1 | Exact gold row is in the first table chunk. |
| bendamustine_05 | In the bendamustine policy, is Vivimusta preferred? What is its HCPCS code and prior authorization requirement? | Vivimusta: non-preferred; HCPCS J9056; prior authorization Yes. | bendamustine-p1-001 | bendamustine-p1-001 | 1 | Exact gold row is in the first table chunk. |
| bevacizumab_01 | In the bevacizumab policy, is Bevacizumab-awwb (Mvasi) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab- awwb (Mvasi): non-preferred; HCPCS Q5107; prior authorization Yes. | bevacizumab-p1-012 | bevacizumab-p1-012 | 1 | Exact gold row is in the first table chunk. |
| bevacizumab_02 | In the bevacizumab policy, is Bevacizumab-bvzr (Zirabev) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab-bvzr (Zirabev): preferred; HCPCS Q5118; prior authorization Yes. | bevacizumab-p1-012 | bevacizumab-p1-012 | 1 | Exact gold row is in the first table chunk. |
| bevacizumab_03 | In the bevacizumab policy, is Bevacizumab (Avastin) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab (Avastin): non-preferred; HCPCS J9035; prior authorization Yes. | bevacizumab-p1-012 | bevacizumab-p1-012 | 1 | Exact gold row is in the first table chunk. |
| bevacizumab_04 | In the bevacizumab policy, is Bevacizumab-tnjn (Avzivi) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab-tnjn (Avzivi): non-preferred; HCPCS J9999; prior authorization Yes. | bevacizumab-p1-012 | bevacizumab-p1-012 | 1 | Exact gold row is in the first table chunk. |
| bevacizumab_05 | In the bevacizumab policy, is Bevacizumab-maly (Alymsys) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab- maly (Alymsys): non-preferred; HCPCS Q5126; prior authorization Yes. | bevacizumab-p1-012 | bevacizumab-p1-012 | 1 | Exact gold row is in the first table chunk. |
| bevacizumab_06 | In the bevacizumab policy, is Bevacizumab-adcd (Vegzelma) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab- adcd (Vegzelma): non-preferred; HCPCS Q5129; prior authorization Yes. | bevacizumab-p1-012 | bevacizumab-p3-020 | 2 | A billing table with the drug and code but no preference column ranked above the preference table. |
| bevacizumab_07 | In the bevacizumab policy, is Ziv-aflibercept (Zaltrap) preferred? What is its HCPCS code and prior authorization requirement? | Ziv-aflibercept (Zaltrap): non-preferred; HCPCS J9400; prior authorization Yes. | bevacizumab-p1-012 | bevacizumab-p1-012 | 1 | Exact gold row is in the first table chunk. |
| bevacizumab_08 | In the bevacizumab policy, is Bevacizumab - nwgd (Jobevne) preferred? What is its HCPCS code and prior authorization requirement? | Bevacizumab - nwgd (Jobevne): non-preferred; HCPCS Q5160; prior authorization Yes. | bevacizumab-p1-012 | bevacizumab-p1-012 | 1 | Exact gold row is in the first table chunk. |

#### Which retrieval ranked better, and why?

On these 13 questions, naive Chroma ranked its labeled chunk first **13/13** times,
while RAG_demo ranked the complete preference table first **12/13** times. Thus naive
Chroma had one more top-1 hit; both found the labeled evidence within four results for
all 13 questions. The RAG_demo miss was Vegzelma: its page-3 billing table mentions
Vegzelma and Q5129 but has no preference column, and ranked above the page-1 preference table.
That is the observed ranking error, not proof that whole-table chunks are inherently worse.

RAG_demo preserves each drug, preference, prior authorization, and code in one Markdown
table row under explicit column headers. The naive word chunk happened to contain those
rows, but it does not encode their row/column structure. This difference matters for
interpreting evidence, which these retrieval scores do not measure.

The naive run searched 32 PDFs with pure vector ranking. RAG_demo searched two PDFs
with combined vector and keyword ranking, so this is not a controlled chunking ablation.
Neither score tests generated-answer correctness.

<!-- PREFERENCE_ROW_EVAL_END -->
