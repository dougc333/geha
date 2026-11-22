# EY page-004 figure benchmark

This directory contains its own copy of the source PDF, authored figure spec, and the production pipeline modules used by the benchmark. Runtime code reads no project paths outside this directory. Python packages and, for the HTML mode, Claude's API are external dependencies. The browser executable installs in `.browsers/` here.

## Inputs

- `inputs/page-004-source.pdf` is copied from the requested run's `pages/page-004/source.pdf` (a one-page PDF).
- `inputs/page-004-spec.json` is copied from `bounding_box/annotations/research/ey-limra-workforce-benefits-study-final-2025/figure-specs/page-004.json`.
- `crawl_dir/src/pipeline/` and `geha_processing/` are copies of the production code. The benchmark imports these local copies only.

## Setup

```bash
cd /Users/dc/geha/benchmarks
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
PLAYWRIGHT_BROWSERS_PATH="$PWD/.browsers" .venv/bin/python -m playwright install chromium
```

Set `ANTHROPIC_API_KEY` in your shell to run the live HTML path. Do not store it in this directory.

## Run

```bash
.venv/bin/python src/benchmark.py spec
.venv/bin/python src/benchmark.py html --model claude-sonnet-5-5 --max-iterations 6
.venv/bin/python src/benchmark.py both --model claude-sonnet-5-5 --max-iterations 6
```

Each invocation prints the total time, timed function calls, and extracted table rows. It writes `results/<run-id>/timings.json`, HTML, tables, and review artifacts. `html` uses the spec **only for the figure's coordinates**; it does not pass the authored chart labels or values to the model. It renders the source crop, generates HTML, renders HTML to PNG, asks the model to review/correct it, then extracts the table from the resulting HTML. `spec` verifies the authored values and labels against native PDF text, deterministically renders the spec to semantic HTML, then uses the **same** HTML table extraction function. It makes no model call or browser screenshot.

The benchmark excludes the historical time and cost of authoring the existing spec. If the HTML review fails within the iteration limit, its timing is reported but the output is not a validated match. Nested call times appear inside the `generate_page_html_with_corrected_figures` parent time, so do not add the rows together. Results from one page are not a general throughput estimate.

## React dashboard

The React 18, TypeScript, Zod, and Tailwind app lives in `benchmark/`. It reads this directory's `results/` through its local Vite server and shows timing, extracted tables, and images side by side. It does not launch or modify benchmark runs.

```bash
cd /Users/dc/geha/benchmarks/benchmark
npm install
npm run dev
```

Open `http://127.0.0.1:8530/`. Run `npm run build` to typecheck and build the app. Refresh the dashboard after running `src/benchmark.py` to see new results.

## Recorded comparison

`results/page004-comparison/timings.json` records one live run on the copied inputs. The HTML+PNG path passed in two iterations after one correction and took 33,969.95 ms. The existing-spec path passed native PDF verification and table extraction in 21.20 ms, a 1,602.4× timing ratio. Both produced the same three categories and four shared data columns; the HTML path additionally put the printed change-from-2023 callouts in a fifth table column. This ratio measures reuse of an already authored spec and excludes the work to create that spec.

## Bendamustine table-spec experiment

`inputs/bendamustine-page-001.pdf` is a copied one-page PDF with extractable text. `inputs/bendamustine-table-001-reference.json` is a copied prior table output used only for comparison after a spec is generated; its `review_status` is pending. The local PyMuPDF step finds the table, trims a following bullet list that PyMuPDF included in its raw grid, and writes a table crop and coordinate evidence:

```bash
.venv/bin/python src/table_spec_poc.py
```

Outputs are under `results/bendamustine-table-spec-poc/`. The optional `--call-model` flag sends the PNG crop and extracted text/coordinates to Claude, writes `table-spec.json`, then compares cells with the copied reference. Use it only when that document transfer is authorized. `--verify-existing` repeats the local checks without another model call.

One authorized Claude Sonnet 5.5 call generated five rows and five columns. All 25 generated cells matched the copied reference and the PyMuPDF text/grid checks. The call took 4,279.57 ms; total extraction, call, and verification took 4,386.72 ms. The reference itself is marked `pending`, so this agreement is useful evidence but not an approved gold standard. This is a single-page experiment, not a production table-spec generator.

The table HTML/PNG comparison script is `src/table_html_loop_poc.py`. It uses the same copied PDF and model, records PyMuPDF preparation, model generation, browser rendering, table extraction, visual review, and any model correction separately. It sends the table crop and evidence to Claude and should be run only when that transfer is authorized:

```bash
.venv/bin/python src/table_html_loop_poc.py
```

The React app has a **Bendamustine table** view at `http://127.0.0.1:8530/?view=table`. It reads the saved spec result and, when available, the HTML/PNG loop result.

In the recorded table comparison, the HTML/PNG path took 25,578.35 ms: PyMuPDF evidence 126.78 ms, Claude HTML generation 20,710.52 ms, browser PNG render 973.87 ms, table extraction/comparison 3.43 ms, and Claude visual review 3,762.32 ms. The first HTML candidate passed review and matched all 25 reference cells, so no correction call occurred. Against the earlier 4,386.72 ms spec-creation run, this is 5.83× slower. These are separate model calls, and the reference table is still marked pending; the ratio is a one-document observation, not a general throughput estimate.
