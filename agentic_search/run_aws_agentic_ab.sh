#!/usr/bin/env bash
# Compare one-shot and one-correction RAG over the deployed AWS paper corpus.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PROJECT_DIR}/../.venv/bin/python"

export AWS_PROFILE="${AWS_PROFILE:-geha-user}"
export AWS_REGION="${AWS_REGION:-us-west-2}"

if ! aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "AWS session is missing or expired." >&2
  echo "Run: aws login --profile $AWS_PROFILE" >&2
  exit 1
fi

export AWS_RAG_URL="${AWS_RAG_URL:-$(
  aws cloudformation describe-stacks \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" --stack-name sam-app \
    --query "Stacks[0].Outputs[?OutputKey=='QueryUrl'].OutputValue" --output text
)}"
export CHATBOT_API_KEY="${CHATBOT_API_KEY:-$(
  aws ssm get-parameter \
    --profile "$AWS_PROFILE" --region "$AWS_REGION" --name /rag-demo/api-key \
    --with-decryption --query Parameter.Value --output text
)}"

exec "$PYTHON" "$PROJECT_DIR/evals/aws_agentic_ab.py" "$@"
