# GEHA batch ingestion

This is an independent copy of the ingestion processing code and a new React batch app. It does not import code from `aws_ingestion` or other GEHA directories. Its PDF snapshot is under `crawl_dir/raw` and its run artifacts are under `runs`.

## Local app

```bash
cd /Users/dc/geha/aws_batch
docker compose up --build -d
```

Open <http://localhost:8520>. Select one or more PDFs, then choose **Run selected**. The app writes `batch.json`, per-document manifests, page Markdown and HTML, source-faithful figure crops, `figure-bounding-boxes.json`, and provisional `figure-specs/page-NNN.json` to `runs/batch-*/`. It uses two local worker threads by default; set `BATCH_WORKERS` to change that. It does not submit to AWS or call model providers.

The copied `bounding_box.figure_bbox_app.source_evidence_specs` module converts detected crop coordinates to the bounding-box annotation schema and writes a provisional spec for every page. Each figure has `status: needs_review`, `chart: null`, and `semantic_render_ready: false`. These files preserve the PDF crop and native text evidence; they are not authored chart specs. A reviewer must correct the boxes and verify values, labels, and geometry before semantic rendering. The older `generate_figure_specs.py` only assembles numbered findings from passed crawl artifacts, so it does not apply to arbitrary GEHA charts or forms. Pages with insufficient native text are sent through local Tesseract OCR; OCR text is marked for review.

## Public GEHA catalog

The [GEHA forms and documents page](https://www.geha.com/en/resource-center/forms-and-documents) currently lists 141 PDF links. The catalog sync checked filenames across every subdirectory of `/Users/dc/geha/crawl_dir/raw` before downloading. It found 97 existing filenames, downloaded 43 files into `/Users/dc/geha/crawl_dir/raw/geha_misc`, and recorded one GEHA link that returns HTTP 404. The 140 available PDFs were copied into this independent workspace with their relative raw paths retained. `catalog.json` records titles, URLs, source status, and SHA-256 hashes.

To refresh the catalog, first run a dry inventory. Pass the shared raw directory explicitly; the script does not import or call code outside this workspace:

```bash
python scripts/sync_geha_catalog.py \
  --raw-root /Users/dc/geha/crawl_dir/raw \
  --manifest geha_catalog_manifest.json
```

Download missing public PDFs into `geha_misc`, then refresh the independent copy and catalog:

```bash
python scripts/sync_geha_catalog.py \
  --raw-root /Users/dc/geha/crawl_dir/raw \
  --manifest geha_catalog_manifest.json \
  --execute
python scripts/build_snapshot.py \
  --raw-root /Users/dc/geha/crawl_dir/raw \
  --manifest geha_catalog_manifest.json
```

Run `python scripts/check_boundary.py` to check that copied Python files remain inside `aws_batch` and parse successfully before rebuilding the app.

## Next AWS stage

The current app is a local batch prototype. Before deployment, replace its in-process thread pool and local run directory with an SQS worker service and S3 artifacts, and store batch status in DynamoDB. Keep its Terraform state and resources separate from the existing demo.
