#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="$ROOT_DIR/infra/terraform"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-west-2}}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$ROOT_DIR" rev-parse --short HEAD)-$(date -u +%Y%m%dT%H%M%SZ)}"
PREBUILT_RUNTIME_DIR="${PREBUILT_RUNTIME_DIR:-$ROOT_DIR/runtime/documents}"

for command_name in aws curl docker terraform; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required command is missing: $command_name" >&2
    exit 1
  fi
done

if [ -z "${TYPESAFE_API_KEY:-}" ]; then
  echo "TYPESAFE_API_KEY must be exported before deployment." >&2
  exit 1
fi

INDEX_FILES=()
while IFS= read -r index_file; do
  INDEX_FILES+=("$index_file")
done < <(find "$PREBUILT_RUNTIME_DIR" -type f -path '*/contextual-retrieval/whole-document-context.jsonl' | sort)
if [ "${#INDEX_FILES[@]}" -eq 0 ]; then
  echo "No prebuilt whole-document contextual embedding files found under: $PREBUILT_RUNTIME_DIR" >&2
  echo "Set PREBUILT_RUNTIME_DIR to the Mac runtime/documents directory." >&2
  exit 1
fi

aws sts get-caller-identity >/dev/null
docker info >/dev/null
DEPLOYER_CIDR="${ALLOWED_CIDR:-$(curl --fail --silent https://checkip.amazonaws.com)/32}"
CLOUDFRONT_ALLOWED_IPS="${CLOUDFRONT_ALLOWED_IPS:-[\"${DEPLOYER_CIDR%/32}\"]}"

terraform -chdir="$TF_DIR" init
terraform -chdir="$TF_DIR" apply -auto-approve \
  -target=aws_ecr_repository.app \
  -target=aws_s3_bucket.artifacts \
  -target=aws_secretsmanager_secret.jev \
  -var="allowed_cidrs=[\"$DEPLOYER_CIDR\"]" \
  -var="cloudfront_allowed_ips=$CLOUDFRONT_ALLOWED_IPS" \
  -var="aws_region=$AWS_REGION" \
  -var="image_tag=$IMAGE_TAG"

ECR_REPOSITORY="$(terraform -chdir="$TF_DIR" output -raw ecr_repository_url)"
ARTIFACT_BUCKET="$(terraform -chdir="$TF_DIR" output -raw artifact_bucket)"
JEV_SECRET_ARN="$(terraform -chdir="$TF_DIR" output -raw jev_secret_arn)"
ECR_REGISTRY="${ECR_REPOSITORY%%/*}"

printf '%s' "$TYPESAFE_API_KEY" | aws secretsmanager put-secret-value \
  --region "$AWS_REGION" \
  --secret-id "$JEV_SECRET_ARN" \
  --secret-string file:///dev/stdin >/dev/null

for index_file in "${INDEX_FILES[@]}"; do
  document_id="$(basename "$(dirname "$(dirname "$index_file")")")"
  aws s3 cp "$index_file" "s3://$ARTIFACT_BUCKET/indexes/$document_id.jsonl" \
    --region "$AWS_REGION" \
    --sse AES256
done

aws ecr get-login-password --region "$AWS_REGION" | \
  docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker buildx build \
  --platform linux/amd64 \
  --file "$ROOT_DIR/Dockerfile.runtime" \
  --tag "$ECR_REPOSITORY:$IMAGE_TAG" \
  --push \
  "$ROOT_DIR"

terraform -chdir="$TF_DIR" apply -auto-approve \
  -var="allowed_cidrs=[\"$DEPLOYER_CIDR\"]" \
  -var="cloudfront_allowed_ips=$CLOUDFRONT_ALLOWED_IPS" \
  -var="aws_region=$AWS_REGION" \
  -var="image_tag=$IMAGE_TAG"

ECS_CLUSTER="$(terraform -chdir="$TF_DIR" output -raw ecs_cluster)"
ECS_SERVICE="$(terraform -chdir="$TF_DIR" output -raw ecs_service)"
APPLICATION_URL="$(terraform -chdir="$TF_DIR" output -raw application_url)"

aws ecs wait services-stable \
  --region "$AWS_REGION" \
  --cluster "$ECS_CLUSTER" \
  --services "$ECS_SERVICE"

curl --fail --retry 12 --retry-delay 10 "$APPLICATION_URL/api/health"
printf '\nDeployed: %s\n' "$APPLICATION_URL"
