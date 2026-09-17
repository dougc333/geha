# Table-Aware Coverage Policy RAG

This project retrieves information from tables extracted from synthetic coverage-policy PDFs. The PDFs contain embedded text, so ingestion explicitly disables OCR and does not use Tesseract. It uses a parent-child retrieval design:

- Each table row is embedded as a searchable child record.
- The complete table is stored as its parent record.
- A matching row causes the entire table to be returned.
- The `search` command works locally without an LLM.
- The `ask` command sends the retrieved table to OpenAI and generates a cited answer.

![Table-aware parent-child RAG architecture](table_rag_architecture.svg)

```text
Question
   |
   v
Local embedding model (BAAI/bge-small-en-v1.5)
   |
   v
pgvector row similarity search
   |
   v
Complete parent table
   |
   +--> search: print locally
   |
   +--> ask: OpenAI answer with source and table citation
```

## Semantic search implementation

Semantic search is implemented locally with Sentence Transformers and PostgreSQL `pgvector`; it does not require an LLM. During ingestion, explicit condition headings are extracted from each policy's `.docling.md` section between `Indication Specific Criteria` and `Universal Approval Criteria`. Every normalized table row is then converted into text containing those conditions, its source filename, inferred table title, column names, and nonempty cell values. `BAAI/bge-small-en-v1.5` encodes that text as a normalized 384-dimensional vector, which is stored in `policy_table_vectors` and linked to the complete table in `policy_tables`.

The extracted condition list and the original indication-section text are stored on each parent table as `conditions_json` and `indication_context`. Policies that do not explicitly enumerate an indication retain an empty list; the pipeline does not guess conditions from the drug name or outside knowledge.

At query time, the same model encodes and normalizes the user's question. PostgreSQL uses the `pgvector` cosine-distance operator to rank child rows:

```sql
1 - (embedding <=> query_embedding) AS similarity
```

An HNSW index using `vector_cosine_ops` accelerates this search. The nearest `--candidate-rows` are grouped by `table_id`; each parent table receives the maximum similarity of any matching child row. The highest-ranked `--top-tables` parent records are then returned with their complete CSV, structured rows, source filename, table number, and title.

```text
Table row + headers + source metadata
               |
               v
      normalized row embedding
               |
Question --> normalized query embedding
               |
               v
       cosine similarity search
               |
               v
 best child rows grouped by table_id
               |
               v
        complete parent tables
```

The current retriever is semantic-only: it does not yet combine vector similarity with PostgreSQL full-text search, BM25, exact procedure-code matching, or a separate reranker. The optional `ask` command runs only after retrieval and does not affect which tables are selected.

## Requirements

- macOS or Linux
- Docker with Compose
- [`uv`](https://docs.astral.sh/uv/)
- An OpenAI API key for the optional `ask` command
- Text-layer PDFs and extracted table files named `*_table_openai.csv`

The CSV extractor places multiple tables in one file and separates them with two blank rows.

## Setup

Run commands from the repository root:

```bash
cd /Users/dc/geha
uv sync
```

Create the local configuration:

```bash
cp chunking_benchmarks_RAG/.env.example chunking_benchmarks_RAG/.env
```

Edit `chunking_benchmarks_RAG/.env`:

```dotenv
GEHA_RAG_DATABASE_URL=postgresql://geha:geha-local@127.0.0.1:5433/geha_rag
OPENAI_API_KEY=sk-your-key
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_INPUT_COST_PER_1M_USD=
OPENAI_OUTPUT_COST_PER_1M_USD=

# Optional tracing to Langfuse Cloud or a self-hosted instance
LANGFUSE_BASE_URL=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
```

The program loads this project file with `override=True`, so its values replace stale variables exported by an earlier shell session. The `.env` file is ignored by Git. Never put a real key in `.env.example`.

## Quick start: database and Medical Claims Advisor

Run both commands from the repository root. First, create or start the pgvector
database container:

```bash
cd /Users/dc/geha
docker compose -f chunking_benchmarks_RAG/docker-compose.pgvector.yml up -d pgvector
```

Confirm that the database is running and healthy:

```bash
docker compose -f chunking_benchmarks_RAG/docker-compose.pgvector.yml ps
```

Then start the Medical Claims Advisor Streamlit application:

```bash
uv run streamlit run chunking_benchmarks_RAG/medical_claims_advisor_ui.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`.
Keep the database container running while using the application. Stop it later
without deleting its persistent data volume:

```bash
docker compose -f chunking_benchmarks_RAG/docker-compose.pgvector.yml stop pgvector
```

## Start PostgreSQL and pgvector

```bash
docker compose -f chunking_benchmarks_RAG/docker-compose.pgvector.yml up -d
```

Check its status:

```bash
docker compose -f chunking_benchmarks_RAG/docker-compose.pgvector.yml ps
```

The database listens on `127.0.0.1:5433` and stores its data in the `geha_pgvector_data` Docker volume.

## Initialize the schema

```bash
uv run python chunking_benchmarks_RAG/table_rag.py init-db
```

This creates:

- `policy_tables`: complete parent tables, source metadata, structured conditions, and the supporting indication section
- `policy_table_vectors`: embedded child rows
- `policy_chunks`: numbered Docling chunks labeled as indication, universal, or non-criteria sections
- `policy_source_terms`: policy-name and drug-name terms for direct source lookup
- An HNSW cosine-similarity index over the 384-dimensional embeddings

## Ingest extracted tables

### Review-only extraction tools for a new PDF

Three LangChain tools can stage a single policy for the data-cleaning workflow:

```python
from chunking_benchmarks_RAG.policy_extraction_tools import (
    docling_extract,
    html_table_extract,
    pdf_page_screenshots,
)

source = "geha-coverage-policy-nplate.pdf"
docling_result = docling_extract.invoke({"pdf_filename": source})
html_result = html_table_extract.invoke({"pdf_filename": source})
page_result = pdf_page_screenshots.invoke({"pdf_filename": source, "dpi": 180})
print(docling_result)  # Markdown and numbered chunk paths
print(html_result)     # HTML table paths, headings, and excluded revisions
print(page_result)     # One PNG path and page number per source PDF page
```

The tools accept a PDF filename in `downloads/coverage-policies`, not an
arbitrary path. They write new files under
`downloads/coverage-policies/extraction_review/<policy-name>/` and never
overwrite the existing `.docling.md`, `.docling_chunks.md`, or published HTML
tables. The HTML tool reuses the existing closest-heading, embedded-CSS, and
revision-history filtering logic. When Docling gives a table numeric columns
(`0`, `1`, `2`, ...), the HTML extractor promotes the first row only if it has
recognizable, unique policy-table column labels; the extraction result records
`header_promoted: true` for review. Existing published HTML files are not
changed by this rule until they are explicitly regenerated. None of the tools writes
to PostgreSQL; validate the staged outputs against the PDF before promoting or
ingesting them. The `pdf_page_screenshots` tool uses Poppler (`pdfinfo` and
`pdftoppm`) to render the original PDF at 100-300 DPI. It returns a numbered
PNG path for each requested page, stored in a source-hash-specific review
directory, but does not send images to an LLM or compare them automatically.
Because the Docling and HTML tools are independent, calling both converts the
PDF twice.

For a table that continues onto the next page without repeating its column
labels, the HTML extractor inherits the preceding table's headers only when the
pages are adjacent, the section heading and column count match, and the prior
headers are recognizable. It retains every continuation row and records
`header_inherited_from_table` in the extraction result. A numeric-column table
without that evidence is left unchanged for manual review; `0`, `1`, `2` are not
silently hidden. Run the batch extractor with `--output-dir` pointing to a new
directory to compare results without replacing previously published HTML.

Reusable extraction functions now live in `policy_table_html_lib.py`; the
`extract_pdf_tables_html.py` command remains a compatible batch wrapper. The
continuation check also handles a Docling fragment that puts its first billing
data row in the DataFrame column names: with adjacent pages, matching headings,
and a recognizable HCPCS code, it restores that row before rendering. The two
small PDFs in `test_fixtures/` exercise numeric headers and page continuation
through real Docling conversion. Run the focused suite with
`uv run python -m unittest -v chunking_benchmarks_RAG.test_extract_pdf_tables_html`.

### Local LangGraph review loop

The review-only graph stages HTML tables, renders their source PDF pages, runs
structural checks, and uses a conditional edge to repair a recognizable
`0`/`1`/`2` header artifact once. It then rechecks the staged table. Other
issues go directly to human review. Even when structural checks pass, the
status is `awaiting_visual_review`: this workflow **does not** establish that
the extracted values match the PDF. Compare each HTML table with its PNG
before publishing or ingesting anything.

```bash
cd /Users/dc/geha
uv sync --frozen
uv run python -m chunking_benchmarks_RAG.policy_review_graph \
  geha-coverage-policy-ziihera.pdf
```

The command prints the status and path to `qc_report.json`. Its run-specific
HTML and report are under `downloads/coverage-policies/extraction_review/`;
the page PNGs are source-hash-specific. There are no database writes and no
external model calls in the default mode.

For the synthetic policy documents, opt in to the OpenAI visual-QC pass:
Set a valid `OPENAI_API_KEY` in the process environment first; the review
command does not load a `.env` file automatically. Never put the key in a
source file or share it in chat.

```bash
cd /Users/dc/geha
uv run python -m chunking_benchmarks_RAG.policy_review_graph \
  geha-coverage-policy-ziihera.pdf --vision-model gpt-4.1-mini
```

This converts the PDF to Docling chunks with assigned headings and page
provenance, renders the relevant source pages to PNGs, and renders every
extracted HTML table into a full-height comparison PNG. For each chunk the
model checks heading/section association against its source page; for each
table it checks heading, columns, rows, and values against the PDF image. The
table PNG is a deterministic rendering of the HTML cells, not a pixel-exact
browser screenshot. The OpenAI Responses API receives the relevant PNGs and
chunk text; it does not receive the database or full repository. Requests use
`store=False`. Findings are model-generated QC suggestions, not policy facts.

The graph prints and saves one summary per pass: `table_error_count`,
`chunk_heading_error_count`, `chunk_other_error_count`, `total_error_count`,
`uncertain_count`, and `structural_error_count`. Error counts are individual
reported issues, not the number of files. API/render failures count as
**uncertain**, never as a successful comparison. When it detects the known
numeric-header artifact, the graph applies only the deterministic header-row
repair to staged HTML and runs one more comparison; all other discrepancies
go to human review. It never promotes an extract or writes to PostgreSQL.

Regenerate the CSV inputs directly from the PDFs' embedded text layer when needed:

```bash
uv run python chunking_benchmarks_RAG/extract_pdf_tables.py \
  /Users/dc/geha/downloads/coverage-policies \
  --overwrite \
  --summary /Users/dc/geha/chunking_benchmarks_RAG/table_extraction_summary.json
```

The extractor configures Docling with `do_ocr = False`. An image-only PDF is
reported as an error instead of invoking Tesseract or another OCR engine. The
historical `_table_openai.csv` suffix is retained for compatibility with the
existing index and evaluation data; extraction itself does not call OpenAI.

Then load the extracted tables:

```bash
uv run python chunking_benchmarks_RAG/table_rag.py ingest \
  /Users/dc/geha/downloads/coverage-policies
```

Ingestion is repeatable. Existing tables with the same source filename and table number are updated, and their condition-aware child vectors are rebuilt. Run `init-db` once after upgrading an existing database so the condition metadata columns are added before re-ingestion.

The same `ingest` command also loads all 35 `*.docling_chunks.md` files into
`policy_chunks`, including the nested medical-necessity-review document. Chunk
labels come from indication headings in the matching `.docling.md`; billing,
references, disclaimers, and revision history are retained for traceability
but are not returned as approval criteria. Universal approval criteria remain
linked to their own source policy. These chunks are not embedded in pgvector.

To add only the new policy-section tables to an existing database without
rebuilding table-row embeddings, run:

```bash
uv run python chunking_benchmarks_RAG/table_rag.py ingest-sections \
  /Users/dc/geha/downloads/coverage-policies
```

`ingest-sections` creates the new tables if necessary and reloads each source's
chunk records and direct-lookup terms in a transaction. Restart Streamlit after
loading them. A drug-name lookup such as `nplate` or `romiplostim` then displays
both Nplate indication sections, followed by its policy-specific universal
criteria in an expandable section. A query naming one documented condition
displays that indication section instead. Preferred and non-preferred lists
still come only from extracted preference tables, not from criteria text.

The current sample corpus produces 103 parent tables and 691 searchable child rows from 35 extracted CSV files.

## Retrieve a complete table locally

```bash
uv run python chunking_benchmarks_RAG/table_rag.py search \
  "Which bendamustine products are non-preferred?"
```

Useful retrieval controls:

```bash
uv run python chunking_benchmarks_RAG/table_rag.py search \
  "Which bendamustine products are non-preferred?" \
  --top-tables 3 \
  --candidate-rows 30
```

`--candidate-rows` controls how many row matches are considered before grouping them by parent table. `--top-tables` controls how many complete tables are returned.

## Generate an answer

The policy documents in this demo are synthetic. The `ask` command transmits the retrieved table content and its structured condition list to the configured OpenAI model:

```bash
uv run python chunking_benchmarks_RAG/table_rag.py ask \
  "Which bendamustine products are non-preferred?"
```

Expected answer:

```text
The non-preferred bendamustine products are Bendeka, Belrapzo, and Vivimusta.
(Source: geha-coverage-policy-bendamustine.pdf,
Table: Drug preference and prior authorization)
```

Override the configured model for one request:

```bash
uv run python chunking_benchmarks_RAG/table_rag.py ask \
  "Which bendamustine products are non-preferred?" \
  --model gpt-3.5-turbo
```

## Medical claims policy advisor

The medical claims advisor uses the same pgvector parent-child table retriever,
then formats the retrieved GEHA records with deterministic Python code. The
Streamlit search displays GEHA evidence and exact retrieved tables without
calling OpenAI. The CLI retains an optional, separately labeled OpenAI
typo/OCR-correction pass; use `--no-openai` to suppress it.

The advisor distinguishes policies with explicit condition metadata from
policies whose extracted tables do not enumerate conditions. An empty condition
list is treated as unknown, never as evidence that a condition is excluded.
Queries that name an explicitly indexed condition or its documented
parenthetical abbreviation bypass semantic top-K ranking and return every parent
table associated with that condition. For example, `MM` resolves to `Multiple
Myeloma (MM)` and returns the Elrexfio, Talvey, and Tecvayli tables, with billing
tables ordered before revision-history tables.

Use `--no-openai` with the CLI to suppress the final correction pass, or
`--evidence-only` to print retrieved evidence as JSON.

Run the chat interface:

```bash
uv run streamlit run chunking_benchmarks_RAG/medical_claims_advisor_ui.py
```

To review policy-name search results, click **Start 3-second search cycle** in
the sidebar. The app reads the 34 `geha-coverage-policy-*.docling_chunks.md`
files directly under `downloads/coverage-policies`, removes the filename prefix
and `.docling_chunks.md` suffix, and submits each resulting term through the
normal search path. It shows one result at a time, waits 3 seconds after each
search, then advances. Click **Stop search cycle** to end the run. The file
count is determined from the directory at start and may change as files are
added or removed.

### Reproduce the chemotherapy-induced anemia answer

From the repository root, install/synchronize the project environment and start
the pgvector database:

```bash
cd /Users/dc/geha
uv sync
docker compose -f chunking_benchmarks_RAG/docker-compose.pgvector.yml up -d pgvector
docker compose -f chunking_benchmarks_RAG/docker-compose.pgvector.yml ps
```

If this is a new or empty database, initialize it and ingest the extracted
coverage-policy tables:

```bash
uv run python chunking_benchmarks_RAG/table_rag.py init-db
uv run python chunking_benchmarks_RAG/table_rag.py ingest \
  /Users/dc/geha/downloads/coverage-policies
```

Start the Streamlit application:

```bash
uv run streamlit run chunking_benchmarks_RAG/medical_claims_advisor_ui.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`, and
submit this query:

```text
Which policies discuss anemia caused by cancer treatment?
```

The structured result should identify the **Erythropoietin Stimulating Agents**
policy and its **Chemotherapy Induced Anemia** section. It should show Retacrit
and Aranesp as preferred, Epogen and Procrit as non-preferred, prior
authorization as Yes for all four, the extracted condition criteria, source-file
download buttons, and the complete retrieved TableRAG evidence. The Streamlit
search does not generate or display an OpenAI correction result.

Inspect retrieval as JSON:

```bash
uv run python chunking_benchmarks_RAG/medical_claims_advisor.py \
  "Does Ziihera require prior authorization for biliary tract cancer?" \
  --evidence-only
```

The advisor explains policy evidence but does not adjudicate claims, determine
medical necessity, or guarantee coverage or payment. Do not enter member or
patient identifiers.

### LangChain Preferred-table tool

`preferred_table_tool.py` exports `search_preferred_policy_tables`, a LangChain
tool that looks up a policy, drug, or documented condition in PostgreSQL and
returns only tables with an explicit `Preferred` row. Each result includes the
source PDF, preferred product names, documented conditions, and the complete
extracted CSV table. It does not call OpenAI or infer coverage from a missing
Preferred row. Set `GEHA_RAG_DATABASE_URL` if the database is not at the local
default URL.

```python
from chunking_benchmarks_RAG.preferred_table_tool import search_preferred_policy_tables

result = search_preferred_policy_tables.invoke({"query": "bendamustine"})
print(result["tables"])

# To make it available to a LangChain agent, register it in that agent's tool list.
tools = [search_preferred_policy_tables]
```

After loading pgvector, compare the LangChain tool with all 17 source CSVs
containing explicit Preferred rows:

```bash
GEHA_RUN_DB_TESTS=1 uv run python -m unittest \
  chunking_benchmarks_RAG.test_preferred_table_integration
```

The test checks each source PDF, its Preferred product names, and the returned
complete table. It is skipped in the ordinary unit-test run unless
`GEHA_RUN_DB_TESTS=1` is set.

## Langfuse trace and A/B evaluation UI

The comparison UI runs deterministic table interpretation and LLM table
interpretation against the same top retrieved parent table. This holds retrieval
constant for each case and compares objective product-list accuracy, error rate,
latency, token usage, and cost. Each case is emitted as a Langfuse trace with
`retriever`, `evaluator`, and `generation` observations.

Start the existing Langfuse instance, create a project, and place its public and
secret keys in `chunking_benchmarks_RAG/.env`. Then run:

```bash
cd /Users/dc/geha
uv sync
uv run streamlit run chunking_benchmarks_RAG/table_rag_ui.py
```

Open the Streamlit URL printed by the command. The UI links each result to its
trace in the Langfuse UI configured by `LANGFUSE_BASE_URL`.

The batch action is deliberately guarded because it makes one paid LLM call per
case. The deterministic method makes no LLM calls. Langfuse infers model cost
from recorded usage when its model definition has current pricing. To also show
a local cost estimate, set the current input and output prices per million tokens
in `.env` or enter them in the UI; do not treat the example configuration as a
pricing source.

For a small CLI comparison without Streamlit:

```bash
uv run python chunking_benchmarks_RAG/table_rag_comparison.py --limit 3
```

This evaluation compares the two interpretation methods end to end using the
same top retrieved table. `expected_table_retrieved` is reported separately so
retrieval failures are not mistaken for LLM interpretation failures.

## Run tests

```bash
uv run python -m unittest -v chunking_benchmarks_RAG/test_table_rag.py
uv run python -m unittest -v chunking_benchmarks_RAG/test_table_rag_comparison.py
uv run python -m py_compile chunking_benchmarks_RAG/table_rag.py
```

The unit tests cover table separation, uneven-row normalization, and inferred table titles.

## Preference evaluation set

[`table_preference_evals.json`](table_preference_evals.json) contains one preferred query and one non-preferred query for every qualifying policy. Each case records the expected source, table title, preference class, and all expected drug-name phrases.

[`tables.md`](tables.md) lists the qualifying PDFs and row counts. The current suite contains 34 cases across 17 policy documents. Detailed per-query rankings and product comparisons are in [`table_preference_eval_results.md`](table_preference_eval_results.md).

| Measurement | Correct | Accuracy | Error rate |
| --- | ---: | ---: | ---: |
| Expected source at top 1 | 31/34 | 91.2% | 8.8% |
| Expected source within top 3 | 33/34 | 97.1% | 2.9% |
| Expected source within top 5 | 34/34 | 100.0% | 0.0% |
| Exact table at top 1 | 28/34 | 82.4% | 17.6% |
| Exact table within top 3 | 32/34 | 94.1% | 5.9% |
| Exact table within top 5 | 33/34 | 97.1% | 2.9% |
| Exact product-list match from the top table | 28/34 | 82.4% | 17.6% |

Error rate is `1 - accuracy`. Product answers are extracted deterministically from the top retrieved table, without an LLM, so the table reports retrieval and table-interpretation errors rather than generation or hallucination errors.

Run the complete local comparison:

```bash
cd /Users/dc/geha/chunking_benchmarks_RAG
uv run python evaluate_table_preferences.py
```

The evaluator records the top-five tables and similarity scores for every query, compares the expected and retrieved table, and extracts the requested products from the top result without calling an LLM. It writes:

- `table_preference_eval_results.md`: readable comparison of all 34 cases
- `table_preference_eval_results.json`: complete machine-readable results

## Secondary-condition policy evals

[`secondary_condition_evals.json`](secondary_condition_evals.json) tests the ten
manually verified secondary conditions in [`qc3.txt`](qc3.txt). It contains
three natural-language query variants per condition (30 cases total), including
questions such as `Is anemia covered when undergoing chemotherapy?`.

[`condition_aliases.json`](condition_aliases.json) stores the corresponding
human-approved canonical conditions, aliases, required concept groups, and
source-policy relationships. The advisor checks this versioned metadata before
falling back to extracted-condition matching or semantic TableRAG. These aliases
are not OpenAI output and are not embedded in pgvector.

Each case declares the expected source policy, normalized condition label,
answer terms, maximum source rank, and whether revision-history tables must be
excluded. The evaluator uses the same deterministic condition-metadata routing,
semantic TableRAG fallback, and policy-summary formatter as the Streamlit app.
It does not call OpenAI.

With the pgvector database running, execute:

```bash
cd /Users/dc/geha
uv run python chunking_benchmarks_RAG/evaluate_secondary_conditions.py \
  --output chunking_benchmarks_RAG/secondary_condition_eval_results.json
```

The report separates four checks:

- expected policy source ranks first;
- expected condition is returned;
- required grounded answer terms are present; and
- revision-history tables are not displayed as evidence.

A case passes end to end only when all four checks pass. This distinction makes
it clear whether a failure came from retrieval, condition metadata, or response
formatting.

| Measurement | Before approved aliases | After approved aliases |
| --- | ---: | ---: |
| Expected policy source at rank one | 19/30 (63.3%) | 30/30 (100.0%) |
| Complete response passed | 12/30 (40.0%) | 30/30 (100.0%) |
| Revision-history filtering passed | 30/30 (100.0%) | 30/30 (100.0%) |

The after-alias measurement is stored in
[`secondary_condition_eval_results.json`](secondary_condition_eval_results.json).

## Combined Streamlit-backend condition evals

The combined runner executes both condition fixture sets through the same
condition routing, semantic TableRAG fallback, and policy-summary functions used
by the Streamlit application:

```bash
cd /Users/dc/geha
uv run python chunking_benchmarks_RAG/evaluate_streamlit_backend.py
```

It evaluates 56 queries: 26 indication-specific condition-to-policy cases from
`indication_specific_criteria_evals.json` and 30 secondary-condition semantic
queries from `secondary_condition_evals.json`. It does not call OpenAI or write
to PostgreSQL. Results are written to `streamlit_backend_eval_results.json`.

## Parent-child table retrieval evals

The Docling-grounded cases in `parent_child_retrieval_evals.json` test semantic
row retrieval while treating the complete policy table as the returned evidence
unit. Each case checks the cited Docling row, the indexed child-row hit, the
linked parent table, and a distinct sibling row in that parent. Run against the
loaded pgvector database:

```bash
cd /Users/dc/geha
.venv/bin/python chunking_benchmarks_RAG/evaluate_parent_child_retrieval.py \
  --output chunking_benchmarks_RAG/parent_child_retrieval_eval_results.json
```

The runner reports both parent-table rank and child-row rank using the app's
default retrieval settings (3 parent tables, 30 candidate rows). It does not
call OpenAI or adjudicate coverage.

To test whether Streamlit itself reaches that semantic fallback, run the
name-free, code-free cases in `semantic_fallback_evals.json`:

```bash
cd /Users/dc/geha
.venv/bin/python chunking_benchmarks_RAG/evaluate_semantic_fallback.py \
  --output chunking_benchmarks_RAG/semantic_fallback_eval_results.json
```

The runner verifies that direct source/condition lookup and billing-code lookup
do not intercept each query, then checks the displayed parent table against a
Docling source line. It deliberately includes known misses as regression cases
and exits nonzero while any expected table is absent.

## Policy-section retrieval evals

The separate section suite tests the new direct drug-name and indication paths
without calling OpenAI or creating embeddings. Start and load the database as
above, then run:

```bash
cd /Users/dc/geha
uv run python chunking_benchmarks_RAG/evaluate_policy_sections.py \
  --output chunking_benchmarks_RAG/policy_section_eval_results.json
```

The runner executes 46 query cases: 12 focused cases in
`policy_section_evals.json` and one filename-derived name lookup for each of
the 34 root policy chunk files in `policy_name_section_evals.json`. The focused
cases cover Nplate and romiplostim, condition-specific narrowing,
policy-specific universal wording, and Datroway/Trodelvy source precedence.
The filename cases check the exact source and indication/universal chunk list
for every root policy, including policies with no such sections. The 35th file
is a nested general medical-necessity review document rather than a treatment
policy; the runner verifies its stored chunks separately and confirms it has
no treatment table. It also verifies the complete 35-file, 409-chunk inventory.
The command exits nonzero if any check fails. This suite is additive to the
existing 56 condition evals; it does not replace or alter them.

## Stop the database

```bash
docker compose -f chunking_benchmarks_RAG/docker-compose.pgvector.yml down
```

This keeps the database volume. To delete the stored database as well, explicitly remove the `geha_pgvector_data` Docker volume.

## Files

- `table_rag.py`: schema creation, ingestion, retrieval, and answer generation
- `test_table_rag.py`: local unit tests
- `docker-compose.pgvector.yml`: PostgreSQL 17 with pgvector
- `.env.example`: safe configuration template
- `table_preference_evals.json`: preferred and non-preferred retrieval/answer cases
- `evaluate_table_preferences.py`: repeatable local evaluation runner
- `secondary_condition_evals.json`: 30 secondary-condition policy eval cases
- `secondary_condition_eval_results.json`: latest machine-readable eval results
- `condition_aliases.json`: approved condition aliases and source-policy mappings
- `evaluate_secondary_conditions.py`: deterministic Streamlit-path eval runner
- `evaluate_streamlit_backend.py`: combined 56-case Streamlit-backend runner
- `streamlit_backend_eval_results.json`: latest combined backend results
- `policy_section_evals.json`: 12 focused policy-section retrieval cases
- `policy_name_section_evals.json`: 34 filename-derived policy-name query cases and the nested general-review document check
- `evaluate_policy_sections.py`: deterministic section-eval runner
- `policy_section_eval_results.json`: latest section-eval results
- `table_rag_comparison.py`: deterministic-versus-LLM evaluation and Langfuse tracing
- `table_rag_ui.py`: Streamlit comparison dashboard with Langfuse trace links
- `medical_claims_advisor.py`: grounded claims-advisor retrieval and generation core
- `medical_claims_advisor_ui.py`: Streamlit claims chat interface
- `test_medical_claims_advisor.py`: condition-handling and grounding tests
- `test_table_rag_comparison.py`: contract, scoring, token, and cost unit tests
- `table_preference_eval_results.md`: complete readable evaluation report
- `table_preference_eval_results.json`: machine-readable evaluation report
- `tables.md`: qualifying policy inventory and retrieval baseline
- `table_rag_architecture.svg`: editable architecture figure
- `table_rag_architecture.png`: rendered architecture figure
- `*_table_openai.csv`: extracted table inputs in the coverage-policy directory
