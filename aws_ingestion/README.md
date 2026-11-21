
# AWS ingestion 
Replicate the code from document_ingestion=_workflow do not make any calls to any folders outside this. Replicate the crawl_dir/raw source and runs structure for traking and promotion of results. 





## Run locally

From `/Users/dc/geha/aws_ingestion`:

```bash
docker compose up --build -d ingestion-workflow ingestion-worker
```

Open <http://localhost:8513>. The queue emulator uses host port 9325. Runs are written under `crawl_dir/runs`; the SQLite run state is in the Compose volume `aws_ingestion_ingestion-state`. The copied PDFs retain their relative paths under `crawl_dir/raw`.

The UI can display documents and saved runs without API credentials. Starting an ingestion run may send document content to a selected model provider. Set the relevant API key only when you intend to run that provider's pipeline.

## Local verification

```bash
docker compose ps
docker compose exec -T ingestion-workflow python -m unittest \
  document_ingestion_workflow.test_backend \
  document_ingestion_workflow.test_run_store
```

Local Compose retains ElasticMQ and SQLite. The AWS configuration below uses S3, SQS, DynamoDB, ECS/Fargate, and an ALB.

The design drafts remain in `docs/` and `specs/`.

## AWS deployment

The AWS app uses S3 for source PDFs and run artifacts, DynamoDB for run status and event traces, SQS for jobs, and ECS/Fargate for the API and worker. Terraform is in `terraform/`. The application load balancer serves HTTP to the narrow IP ranges in `allowed_cidrs`; the API has no login.

To launch the app, set `runtime_enabled = true` and provide an ECR `image_tag`. Model-backed runs also require provider API keys. Set `model_secrets_enabled = true` to create three Secrets Manager records, then populate their values separately. Alternatively, leave it false and supply existing secret ARNs through `model_secret_arns`. Secret values do not belong in Terraform variables or state.

From `/Users/dc/geha/aws_ingestion/terraform`:

```bash
AWS_PROFILE=geha-terraform terraform init
AWS_PROFILE=geha-terraform terraform plan
AWS_PROFILE=geha-terraform terraform apply
```

The image must already exist in ECR under the configured tag. The S3 bucket retains the `raw/` and `runs/` directory structure. The deployed app reads saved-run artifacts from S3.

## Pause AWS app runtime

Set `runtime_enabled = false` and apply Terraform to remove the load balancer and both ECS services. Terraform also removes their unused task definitions. S3 artifacts, ECR images, DynamoDB run state, and SQS queues remain.

Set `model_secrets_enabled = false` to schedule deletion of the three Terraform-managed API key secrets. AWS applies a seven-day recovery window. The local Docker API keys are unaffected. Model-backed runs cannot start on AWS again until provider secrets are configured.

The current stack is paused: the load balancer, ECS services, task definitions, and Secrets Manager records have been removed or scheduled for deletion. S3, ECR, DynamoDB, and SQS remain. Terraform reports no pending changes with both flags set to `false`.
