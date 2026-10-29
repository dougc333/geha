#!/usr/bin/env bash
# Source this file for local database administration only:
#   source /Users/dc/geha/aws_rag/scripts/load_local_aws_env.sh

export AWS_PROFILE="${AWS_PROFILE:-geha-user}"
export AWS_REGION="${AWS_REGION:-us-west-2}"

if ! aws sts get-caller-identity --profile "$AWS_PROFILE" --region "$AWS_REGION" >/dev/null 2>&1; then
  echo "AWS session is missing or expired." >&2
  echo "Run: aws login --profile $AWS_PROFILE --region $AWS_REGION" >&2
  return 1 2>/dev/null || exit 1
fi

export DATABASE_URL="$(
  aws ssm get-parameter \
    --profile "$AWS_PROFILE" \
    --region "$AWS_REGION" \
    --name /rag-demo/database-url \
    --with-decryption \
    --query Parameter.Value \
    --output text
)"

echo "AWS admin environment loaded for $AWS_PROFILE in $AWS_REGION; DATABASE_URL is set."
