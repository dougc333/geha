# AWS forms extraction

This directory is the on-demand AWS port of the existing bill-of-lading React workflow. It is separate from `aws_docling`: the alt-2 path uses PyMuPDF, reviewed named-cell geometry, Claude OCR, HTML construction, OpenAI segment review, and field verification. It does not run a Docling server.

The React UI stays on the Mac. Terraform creates an ECR repository, an S3 bucket, an ECS cluster and Fargate task definition, IAM roles, a CloudWatch log group, and outbound-only networking. It does **not** create an ECS service, load balancer, NAT gateway, queue, or continuously running task. The local app will submit one task per run and read its S3 artifacts. Terraform alone does not start extraction.

## Artifact contract

- Input: `s3://<bucket>/incoming/<run-id>/source.pdf`
- Claim against duplicate paid work: `runs/<run-id>/claim`
- Task status: `runs/<run-id>/status.json`
- Extraction output: `runs/<run-id>/artifacts/...`, including `pages/page-001/final.html`, `pages/page-001/segments/structured-ocr.json`, `candidate/bill_of_lading_fields.json`, and `qc-report.json`
- Container logs: `/ecs/aws-forms` in CloudWatch Logs

The first worker is scoped to the reviewed `bill_of_lading_alt_2.pdf` fixture. It checks the uploaded file's SHA-256 before any paid OCR call. Its named-cell boxes should not be applied to an unrelated form; template matching and additional template definitions are separate work.

## Terraform

Set the ARNs of two **existing** AWS Secrets Manager secrets in `terraform/terraform.tfvars`, using `terraform/terraform.tfvars.example` as a guide. The secret *values* are the raw API keys; Terraform receives only their ARNs. Use an AWS profile permitted to create the resources.

```bash
cd /Users/dc/geha/aws_forms/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit the two secret ARNs and the image_tag.
AWS_PROFILE=geha-user terraform init
AWS_PROFILE=geha-user terraform plan
AWS_PROFILE=geha-user terraform apply
```

Applying Terraform creates cloud resources and can incur storage, logging, and task charges. The Fargate task gets a public IP while running so it can reach ECR, S3, Anthropic, and OpenAI without a NAT gateway. It has no inbound security-group rule.

## Container image

The task definition references the immutable ECR tag in `image_tag`. After Terraform creates the repository, build the existing ingestion Dockerfile for Linux/AMD64 and push that tag:

```bash
cd /Users/dc/geha
AWS_PROFILE=geha-user aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin "$(AWS_PROFILE=geha-user aws sts get-caller-identity --query Account --output text).dkr.ecr.us-west-2.amazonaws.com"
IMAGE_URI=$(cd aws_forms/terraform && terraform output -raw worker_image_uri)
docker buildx build --platform linux/amd64 \
  -f document_ingestion_workflow/Dockerfile \
  -t "$IMAGE_URI" --push .
```

For a changed image, set a new `image_tag`, apply Terraform to create a new task-definition revision, then push the matching image before starting a task. The execution role pulls ECR images and injects API keys; the task role can read `incoming/` and write `runs/` in this bucket.

The local React AWS run button and status/artifact proxy are the next integration step; the Terraform stack and worker are deliberately not deployed or invoked by this repository change.

Until that UI wiring is complete, the local launcher starts one task using the same AWS profile as Terraform:

```bash
cd /Users/dc/geha
/Users/dc/geha/.venv/bin/python -m aws_forms.launch \
  crawl_dir/raw/forms/bill_of_lading_alt_2.pdf --profile geha-user
```

It prints the run ID, ECS task ARN, and S3 status key. The profile needs `s3:PutObject` under `incoming/`, `ecs:RunTask` for the task definition, and `iam:PassRole` for both task roles. A successful task writes the full run under `runs/<run-id>/artifacts/`. The worker's `status.json` remains `needs_visual_review` until a human reviews the new run.
