#!/usr/bin/env bash
# Run bounded corrective search against the deployed AWS paper corpus.
# Usage: ./run_aws_agentic.sh "Compare RAG, ReAct, and Self-RAG."

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PROJECT_DIR}/../.venv/bin/python"

export AWS_PROFILE="${AWS_PROFILE:-geha-user}"
export AWS_REGION="${AWS_REGION:-us-west-2}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"question about the paper corpus\"" >&2
  exit 2
fi

if ! aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "AWS session is missing or expired." >&2
  echo "Run: aws login --profile $AWS_PROFILE --region $AWS_REGION" >&2
  exit 1
fi

if [[ -z "${AWS_RAG_URL:-}" ]]; then
  export AWS_RAG_URL="$(
    aws cloudformation describe-stacks \
      --profile "$AWS_PROFILE" \
      --region "$AWS_REGION" \
      --stack-name sam-app \
      --query "Stacks[0].Outputs[?OutputKey=='QueryUrl'].OutputValue" \
      --output text
  )"
fi

if [[ -z "${CHATBOT_API_KEY:-}" ]]; then
  export CHATBOT_API_KEY="$(
    aws ssm get-parameter \
      --profile "$AWS_PROFILE" \
      --region "$AWS_REGION" \
      --name /rag-demo/api-key \
      --with-decryption \
      --query Parameter.Value \
      --output text
  )"
fi

exec "$PYTHON" "$PROJECT_DIR/src/agentic_rag.py" --aws "$@"
