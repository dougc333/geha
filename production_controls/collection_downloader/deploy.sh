#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
STACK_NAME="${STACK_NAME:-geha-context-downloader}"
REGION="${AWS_REGION:-us-west-2}"
CATALOG="${GEHA_CATALOG:-/Users/dc/geha/collections/inventory-snapshot.json}"

if [[ ! -f "$CATALOG" ]]; then
  echo "Catalog not found: $CATALOG" >&2
  exit 1
fi

sam build --template-file "$ROOT/template.yaml" --build-dir "$ROOT/.aws-sam/build"
sam deploy --guided --template-file "$ROOT/.aws-sam/build/template.yaml" --stack-name "$STACK_NAME" --region "$REGION" --capabilities CAPABILITY_IAM

BUCKET="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`BucketName`].OutputValue' --output text)"
aws s3 cp "$CATALOG" "s3://$BUCKET/catalog/inventory-snapshot.json" --region "$REGION" --content-type application/json
echo "Catalog uploaded to s3://$BUCKET/catalog/inventory-snapshot.json"
