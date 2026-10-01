#!/usr/bin/env bash
# One-time setup so the weekly GitHub Actions retrieval benchmark can log into AWS.
#
#   aws login                              # first, if your session has expired
#   bash aws_rag/scripts/setup_ci_role.sh
#
# Creates (or reuses) the GitHub OIDC provider and an IAM role that only the main branch of
# dougc333/geha can assume, gives it read access to three /rag-demo/ SSM parameters and Titan
# embeddings, and stores the role ARN as the GitHub secret AWS_RAG_CI_ROLE_ARN. Safe to rerun.
set -euo pipefail

REPO="dougc333/geha"
REGION="us-west-2"
ROLE="geha-ci-aws-rag-benchmark"
OIDC_HOST="token.actions.githubusercontent.com"

step() { printf '\n== %s\n' "$1"; }

step "1/5 Check AWS login"
if ! ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null); then
  echo "Not logged in to AWS. Run: aws login   (then rerun this script)"
  exit 1
fi
echo "Logged in to account $ACCOUNT"
if ! gh auth status >/dev/null 2>&1; then
  echo "Not logged in to GitHub. Run: gh auth login   (then rerun this script)"
  exit 1
fi

step "2/5 GitHub OIDC provider (lets AWS trust GitHub Actions)"
PROVIDER_ARN="arn:aws:iam::${ACCOUNT}:oidc-provider/${OIDC_HOST}"
if aws iam get-open-id-connect-provider --open-id-connect-provider-arn "$PROVIDER_ARN" >/dev/null 2>&1; then
  echo "Already exists: $PROVIDER_ARN"
else
  aws iam create-open-id-connect-provider --url "https://${OIDC_HOST}" \
    --client-id-list sts.amazonaws.com --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
  echo "Created: $PROVIDER_ARN"
fi

step "3/5 IAM role $ROLE (only $REPO on main can use it)"
TRUST=$(cat <<EOF
{"Version": "2012-10-17",
 "Statement": [{"Effect": "Allow",
   "Principal": {"Federated": "${PROVIDER_ARN}"},
   "Action": "sts:AssumeRoleWithWebIdentity",
   "Condition": {"StringEquals": {"${OIDC_HOST}:aud": "sts.amazonaws.com",
                                  "${OIDC_HOST}:sub": "repo:${REPO}:ref:refs/heads/main"}}}]}
EOF
)
if aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "$ROLE" --policy-document "$TRUST"
  echo "Already exists; trust policy refreshed"
else
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document "$TRUST" \
    --description "Weekly aws_rag retrieval benchmark in GitHub Actions" >/dev/null
  echo "Created"
fi
ROLE_ARN=$(aws iam get-role --role-name "$ROLE" --query Role.Arn --output text)
echo "Role ARN: $ROLE_ARN"

step "4/5 Permissions: read 3 SSM parameters, call Titan embeddings"
POLICY=$(cat <<EOF
{"Version": "2012-10-17",
 "Statement": [
  {"Effect": "Allow", "Action": "ssm:GetParameter",
   "Resource": ["arn:aws:ssm:${REGION}:${ACCOUNT}:parameter/rag-demo/database-url",
                "arn:aws:ssm:${REGION}:${ACCOUNT}:parameter/rag-demo/weaviate-url",
                "arn:aws:ssm:${REGION}:${ACCOUNT}:parameter/rag-demo/weaviate-api-key"]},
  {"Effect": "Allow", "Action": "bedrock:InvokeModel",
   "Resource": "arn:aws:bedrock:${REGION}::foundation-model/amazon.titan-embed-text-v2:0"}]}
EOF
)
aws iam put-role-policy --role-name "$ROLE" --policy-name aws-rag-benchmark --policy-document "$POLICY"
echo "Policy set"

step "5/5 GitHub secret AWS_RAG_CI_ROLE_ARN"
gh secret set AWS_RAG_CI_ROLE_ARN --repo "$REPO" --body "$ROLE_ARN"
echo "Secret set on $REPO"

printf '\nDone. After the CI change is merged to main, test it with:\n  gh workflow run ci.yml --repo %s\n' "$REPO"
