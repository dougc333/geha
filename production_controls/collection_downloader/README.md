# GEHA S3 collection downloader

This is an AWS-ready React/API application for the 141-document GEHA catalog.
It uses the existing catalog snapshot at
`/Users/dc/geha/collections/inventory-snapshot.json` as the initial manifest.

## Architecture

- React/Vite frontend: lists every catalog asset and starts one-document or
  all-document downloads.
- API Gateway + Python Lambda: reads the catalog from S3 and queues work.
- Step Functions Map: downloads all catalog assets with bounded concurrency.
- Downloader Lambda: validates GEHA HTTPS PDF URLs, downloads the PDF, computes
  SHA-256, and stores it in a private, KMS-encrypted S3 bucket.
- DynamoDB: stores per-asset status, checksum, S3 key, byte count, and errors.

No MacBook crawl directory is used by the deployed service. The local snapshot
is only the initial catalog seed; all runtime state and PDFs live in AWS.

## Deploy backend

From this directory, with AWS credentials configured:

```bash
./deploy.sh
```

The script runs `sam build`, deploys the stack, and uploads the 141-asset catalog
to the created S3 bucket. It prints the bucket name; the API URL is available in
the CloudFormation outputs.

## Run the frontend

```bash
cd frontend
npm install
VITE_API_BASE_URL=https://YOUR_API_ID.execute-api.us-west-2.amazonaws.com npm run dev
```

Build it for S3/CloudFront with:

```bash
npm run build
aws s3 sync dist/ s3://YOUR_FRONTEND_BUCKET/ --delete
```

The frontend calls `GET /api/inventory`, `POST /api/download`, and
`POST /api/download-all`.
