# Unstructured managed API extraction comparison

This project displays one source PDF page beside the structured elements returned by the
Unstructured managed Partition API. The React browser application never receives the API key;
the local FastAPI server reads it from `.env`, uploads the configured PDF, and returns only the
extraction result.

## Install

```bash
cd /Users/dc/geha/test_unstructured_cloudapi
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cd ui
npm install
npm run build
cd ..

cp .env.example .env
```

Edit `.env` and set `UNSTRUCTURED_API_KEY`. Replace `UNSTRUCTURED_API_URL` too if the account
provides a workspace-specific endpoint.

## Run

```bash
source .venv/bin/activate
unstructured-cloud-ui
```

Open <http://127.0.0.1:8512> and select **Extract this page**.

The first request calls the managed API and stores its JSON under `results/`. Later requests with
the same document and options reuse that result, preventing a browser refresh from incurring
another API call. Select **Call API again** when a fresh response is intentional.

## React development

```bash
# Terminal 1
source .venv/bin/activate
uvicorn unstructured_cloud_test.server:app --reload --port 8512

# Terminal 2
cd ui
npm run dev
```

Open <http://127.0.0.1:5175>. Vite proxies `/api` to the Python server.

## Validate

```bash
pytest
cd ui && npm run build
```

Do not use protected health information unless the Unstructured account, contract, BAA, region,
retention configuration, and data-processing terms have been approved for that data.
