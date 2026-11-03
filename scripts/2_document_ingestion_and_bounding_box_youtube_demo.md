# YouTube Demo Script: Auditable Document Ingestion and Figure Reconstruction

**Target length:** 9–11 minutes  
**Audience:** AI context engineering, solution architecture, and document-processing teams  
**Applications:** `bounding_box` and `document_ingestion_workflow`  
**Demo message:** Reliable document ingestion is not one generic OCR call. The system classifies the document, selects a layout-specific workflow, preserves source evidence, and makes every extraction and correction step inspectable.

## Video title

**Beyond OCR: An Auditable Workflow for Tables, Charts, Forms, and Policy PDFs**

## Thumbnail text

**PDF → Evidence → Verified Context**

## Before recording

1. Start Docker Desktop.
2. Confirm the public demo documents exist under `crawl_dir/raw`.
3. Export `ANTHROPIC_API_KEY`. Export `OPENAI_API_KEY` only if demonstrating the Bill of Lading live.
4. Start the ingestion application:

   ```bash
   cd /Users/dc/geha/document_ingestion_workflow
   ./docker-up.sh --build
   ```

   Open <http://127.0.0.1:8510>.

5. Build and start the bounding-box application in a second terminal:

   ```bash
   cd /Users/dc/geha/bounding_box/figure_bbox_app/ui
   npm install
   npm run build

   cd /Users/dc/geha
   source .venv/bin/activate
   python -m bounding_box.figure_bbox_app.backend --port 8511
   ```

   Open <http://127.0.0.1:8511>.

6. In the ingestion app, confirm that a previous Datroway or EY/LIMRA run loads. This gives the recording a reliable fallback if a live model call is slow.
7. In the bounding-box app, open a page with saved boxes and prompts. Page 4 of the default EY/LIMRA report is a strong visual example.
8. Hide API keys, terminal history containing secrets, local usernames if desired, and unrelated browser tabs.
9. Record at 1440p or higher so the source document, semantic HTML, and trace remain legible.

## Recording script

### 0:00–0:35 — Hook

**On screen**

- Begin with the ingestion app showing a source PDF and reconstructed semantic HTML side by side.
- Briefly scroll the pipeline trace.

**Narration**

> Most document-ingestion demos stop when OCR returns text. That is not enough for a policy, a dense form, or a research report containing charts. Text can be present while the structure—the relationship among a title, legend, bars, percentages, and footnotes—is lost.
>
> This demo shows an auditable alternative. I will identify visual regions, ground them in source evidence, create structured figure specifications, route each document to the appropriate extraction workflow, and compare the final semantic output directly with the source page.

**On-screen callout**

`Source evidence → layout-specific tools → rendered verification → immutable candidate`

### 0:35–1:15 — Explain the two applications

**On screen**

- Show a simple two-stage title card or switch between the two browser tabs.
- First highlight the bounding-box app, then the ingestion app.

**Narration**

> These are two connected applications.
>
> The bounding-box workbench is the authoring stage. It records where figures, charts, tables, and images live on a page using resolution-independent coordinates. It can then build evidence-grounded figure specifications.
>
> The document-ingestion workflow is the execution and review stage. It classifies the document, selects the extraction route, renders the source and candidate output, streams every tool decision, and saves the artifacts and quality-control report.
>
> The orchestration is deterministic. Models can assist with selected extraction tasks, but they do not get to skip required rendering or verification steps.

### 1:15–2:30 — Show layout-aware routing

**On screen**

- Open the document selector in the ingestion app.
- Point to Datroway, Elrexfio, Bendamustine, Bill of Lading, and EY workforce benefits.
- Select two or three documents without starting a run yet so the audience sees the available profiles.

**Narration**

> A major design decision is that these documents do not all go through the same parser.
>
> Datroway and Elrexfio are mixed-layout coverage policies, so their route can use whole-page semantic HTML generation and visual review. Bendamustine has usable native PDF text and structure, so the workflow avoids an unnecessary generation call. The synthetic Bill of Lading uses a versioned schema and named-cell OCR. The EY workforce-benefits report combines ordinary text with designed figures, so it uses native pages plus authored figure specifications.
>
> The principle is simple: use the least expensive deterministic method that preserves the document's meaning, and escalate only the pages or regions that require more capable tools.

**On-screen callout**

`One catalog · multiple extraction contracts`

### 2:30–4:15 — Run or replay the ingestion trace

**On screen**

- Select Datroway for a model-assisted example, or EY workforce benefits for the authored-spec route.
- If recording a live run, click **Start live run**.
- If latency is unpredictable, select **Previous run** and say explicitly that this is an immutable saved run.
- Keep the extraction-tool router and pipeline trace visible.

**Narration**

> I will use [Datroway / EY workforce benefits] for this pass. The interface first records the source and the document profile. Then the screenshot router selects PyMuPDF to render exact source-page pixels. The extraction router considers the available strategies and records both the selected tool and the reason.
>
> The trace is not decorative. Each event has an order, a page or segment, the selected renderer, an iteration number, latency, and the artifact path. When visual review is required, candidate HTML must be rendered in Playwright Chromium before it can be compared with the source.
>
> A mismatch enters a bounded correction loop. A match can proceed to candidate assembly. The loop has an explicit iteration limit, so failure produces inspectable evidence instead of an endless autonomous process.

**Pause on these trace events when available**

- `Screenshot tool selected`
- `Extraction tools considered`
- `Extraction tool selected`
- `HTML render tool called`
- `Vision review returned`
- `Corrected HTML ready`
- `Candidate assembled`

### 4:15–5:15 — Compare source evidence with semantic output

**On screen**

- Use the page arrows.
- Toggle between the source view and verified HTML.
- If available, switch between current and previous runs.
- End on the summary metrics.

**Narration**

> This comparison is the center of the demo. On one side is the authoritative PDF page. On the other is the candidate semantic HTML that downstream retrieval and accessibility systems can use.
>
> I can navigate completed pages and inspect a previous immutable run. The summary reports page count, scanned pages, visual reviews, verified pages, and the final quality-control outcome.
>
> This separates three questions that are often collapsed into one: Did we extract text? Did we preserve the relationships on the page? And did the rendered candidate actually satisfy the review contract?

### 5:15–6:00 — Transition to the upstream bounding-box workbench

**On screen**

- Switch to <http://127.0.0.1:8511>.
- Show the default EY/LIMRA document.
- Navigate to a page containing a chart or table.

**Narration**

> Now I will show where the authored figure specifications come from.
>
> A generic PDF parser may recover the words and percentages inside this chart while losing which percentage belongs to which series or year. The bounding-box workbench isolates the non-running-text region without modifying the source PDF.

### 6:00–7:15 — Draw and classify a region

**On screen**

- If the page already contains a reviewed region, select it first and show its label, type, and coordinates.
- Optionally draw one temporary tight rectangle around a figure.
- Set the type to **Chart** or **Table** and add a short label.
- Show **All changes saved**, the page counter, and the region count.
- Delete the temporary region afterward if it is not intended to become part of the curated annotations.

**Narration**

> I draw a tight box around the complete visual unit, including the elements needed to interpret it. The region gets a semantic type and a human-readable label.
>
> The coordinates are normalized from zero to one thousand rather than stored as screenshot pixels. That makes the annotation independent of rendering resolution. Edits autosave to JSON, and the backend validates page numbers, unique IDs, coordinate bounds, minimum box size, and region count before performing an atomic write.
>
> Annotation and reconstruction are deliberately separate. Drawing a box says where the evidence is; it does not claim that the system already understands the figure.

**On-screen callout**

`Locate first · interpret second`

### 7:15–8:35 — Generate and inspect an evidence-grounded specification

**On screen**

- Select a saved region with an existing reconstruction prompt.
- Point to the evidence chips: years, geometry mapping, or “Needs visual mapping.”
- Click **Generate specs** only if you want a live demonstration; otherwise show an existing saved spec and describe the recorded stages.
- Highlight the progress stages:
  `Boxed → Crawl data loaded → Spec assembled → Validating → Spec saved`

**Narration**

> The next step is evidence-grounded specification generation. The workflow loads the newest passed crawl artifact for the document, assembles a structured chart or diagram specification, and validates it against the source evidence.
>
> Notice that uncertainty is preserved. If geometry can map labels to marks, the interface records that mapping. If the relationship is ambiguous, it says “Needs visual mapping” rather than inventing one.
>
> The saved specification is versionable JSON. Existing reviewed specs are skipped by default, which prevents a batch run from silently replacing curated work. For this saved-spec route, report content is not sent to an external model during specification generation.

### 8:35–9:35 — Connect the specification back to ingestion

**On screen**

- Return to the ingestion app.
- Select **EY workforce benefits**.
- Show a completed page containing a reconstructed figure and adjacent data table.
- Point to the selected extraction route and final artifacts.

**Narration**

> Back in the ingestion workflow, the authored specification becomes an explicit extraction contract. The system verifies printed labels and values against native PDF text inside the figure region, renders accessible semantic HTML deterministically, and adds a data table so the chart's relationships are available to retrieval—not just the visible strings.
>
> This is the practical connection between document engineering and RAG quality. Better chunking cannot recover a relationship that ingestion already destroyed. By preserving structure here, downstream BM25, vector, hybrid, or structured retrieval receives evidence with clearer semantics and provenance.

### 9:35–10:20 — Architecture and reliability summary

**On screen**

- Show the final comparison and pipeline trace together.
- Optionally overlay the architecture text below.

```text
Public PDF
   ↓
Layout classification
   ↓
Native extraction | figure specs | bounded vision | schema + named-cell OCR
   ↓
Source rendering + candidate browser rendering
   ↓
Bounded review/correction
   ↓
Semantic HTML + Markdown + manifests + QC report
```

**Narration**

> The key ideas are layout-aware routing, evidence before generation, mandatory rendering for visually reviewed routes, bounded correction, immutable artifacts, and human-reviewable promotion.
>
> This is a public-document demonstration, not a production or HIPAA-ready system. Candidates are not automatically promoted. But it demonstrates the controls needed to turn document extraction from a black-box model call into an observable engineering workflow.

### 10:20–10:40 — Close

**On screen**

- End on the side-by-side verified page.
- Display the repository name and the two component paths.

**Narration**

> The result is not simply more text. It is structured, traceable context whose relationship to the source can be inspected page by page. The code for both applications is in the GEHA demo repository under `bounding_box` and `document_ingestion_workflow`.

## Optional 60-second short version

> OCR can recover words from a PDF and still destroy the meaning of a chart or form. This workflow first classifies the document, then chooses among native extraction, authored figure specs, bounded vision correction, or schema-based named-cell OCR.
>
> In the bounding-box workbench, I isolate a complete visual region, label its type, and save resolution-independent coordinates. The system then loads source evidence, assembles a structured specification, validates it, and preserves ambiguity instead of guessing.
>
> In the ingestion application, every routing and rendering decision appears in a live trace. The authoritative PDF page sits beside the semantic HTML candidate. Visually reviewed routes must render in Chromium, compare against the source, and either pass or enter a bounded correction loop.
>
> The output is semantic HTML, Markdown, manifests, and a QC report—better evidence for downstream retrieval than flattened OCR text.

## Suggested chapter markers

```text
00:00 Why OCR is not enough
00:35 Two connected applications
01:15 Layout-aware routing
02:30 Live ingestion trace
04:15 Source versus semantic output
05:15 Bounding-box workbench
06:00 Resolution-independent annotations
07:15 Evidence-grounded figure specs
08:35 From figure specs to retrievable context
09:35 Reliability controls and architecture
10:20 Summary
```

## Recording safety and accuracy notes

- Call the browser application “Document Ingestion Pipeline” when referring to the UI label; call its repository directory `document_ingestion_workflow`.
- Do not describe the workflow as fully autonomous. Routing and control flow are deterministic.
- Do not claim every route uses an LLM. Native-text and saved figure-spec routes can avoid generation calls.
- Do not call generated output production data. It is an immutable candidate pending review or promotion.
- Do not claim HIPAA readiness. The repository explicitly describes the application as a public-document demonstration.
- If replaying an existing result, call it a saved immutable run rather than a live run.
- If **Generate specs** skips a page, explain that reviewed specs are preserved by default.
- Keep API keys and local secrets out of the recording.
