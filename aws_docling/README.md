# On-demand AWS Docling and PDF review viewer

S3 receives PDFs at `incoming/`. An S3 event invokes a short Lambda, which starts one Fargate task per PDF. The task runs Docling, writes Markdown to `extracted/`, and exits. The React viewer can upload a PDF, show processing status, and compare the source PDF with Markdown. There is no always-on Docling service, load balancer, NAT gateway, or VPC endpoint.

The worker now enables page and picture images. Its Markdown embeds the figure crops at their original positions, and it writes a separate `extracted/<name>.figures.zip` with PNGs and a page/box manifest. It also writes `extracted/<name>.models.json` with the Hugging Face model directories found in that task's container cache. The `do_chart_extraction` option remains off by default; it needs a compatible Granite Vision runtime and its numeric output must be checked against the PDF before enabling it in AWS. See [the Georgetown local verification](verification/georgetown/README.md).

For a no-AWS server test, use the pinned image and client in [docker/](docker/README.md). The 30-page Georgetown paper completed locally in 64 seconds (about 28 pages/minute for that one CPU run); the server's Markdown matched the deployed AWS Markdown after replacing embedded images with placeholders. This is one measured document, not a throughput guarantee.

## Start and verify

Terraform creates a VPC and two public subnets in `us-west-2`. Fargate gets a public IP for outbound image pulls and S3 access. Its security group has no inbound rules. **Nothing is deployed until you apply Terraform.** Applying creates AWS resources, and each upload incurs Fargate and public IPv4 usage. The Docling CPU image is large, so the first image pull may take time.

### 1. Deploy the stack

```bash
cd /Users/dc/geha/aws_docling/terraform
AWS_PROFILE=geha-terraform terraform init
AWS_PROFILE=geha-terraform terraform plan
AWS_PROFILE=geha-terraform terraform apply
```

Review the plan before entering `yes`. The plan should create the VPC, S3 bucket, Lambda launcher, and ECS task definition; it should not create an always-on ECS service, load balancer, or NAT gateway.

### 2. Start the React viewer

Open another terminal:

```bash
cd /Users/dc/geha/aws_docling/viewer
export PATH=/Users/dc/.nvm/versions/node/v22.23.5/bin:$PATH
npm ci
AWS_PROFILE=geha-terraform AWS_REGION=us-west-2 \
  AWS_DOCLING_BUCKET=$(cd ../terraform && terraform output -raw bucket_name) \
  npm run dev
```

Open the local URL Vite prints. Click **Upload PDF and process** and select a PDF under 25 MB. The viewer gives it a unique S3 name, shows *processing*, and polls every five seconds for the matching Markdown. The status panel shows a four-stage completion bar, ECS startup, conversion, failure, the most recent worker heartbeat, and recent CloudWatch container logs. The bar tracks stages rather than pages or elapsed time. The worker emits a heartbeat every 15 seconds while processing; ECS `RUNNING` alone only confirms the container started. When conversion finishes, the viewer shows the Markdown beside the PDF.

### 3. Verify the result or diagnose a failure

From `/Users/dc/geha/aws_docling/terraform`:

```bash
AWS_PROFILE=geha-terraform aws logs tail /ecs/aws-docling \
  --region us-west-2 --since 1h

AWS_PROFILE=geha-terraform aws s3 ls \
  "s3://$(terraform output -raw bucket_name)/extracted/" --recursive
```

A matching `.md` under `extracted/` confirms output was written. If the task fails, the status panel shows *failed* and the container traceback; the document selector may still say *processing* because no Markdown was written. S3 can deliver an event more than once, so duplicate tasks are possible. Presigned S3 URLs expire after six hours. The local AWS profile needs S3 list/get/put, ECS list/describe, and CloudWatch Logs read permissions.

After `terraform apply`, an EventBridge rule invokes `aws-docling-archive-logs` when a Docling ECS task stops. It copies that task's `/ecs/aws-docling` CloudWatch stream and stop metadata to `s3://<bucket>/jobs/logs/<task-id>.log`, including failed tasks. The live status panel continues reading CloudWatch; the S3 copy is a per-run record. This rule and Lambda are triggered only when a task stops, and existing runs are not backfilled. Check an archived log with `aws s3 ls "s3://$(cd terraform && terraform output -raw bucket_name)/jobs/logs/" --profile geha-user`.

For command-line upload, run this from the Terraform directory:

```bash
AWS_PROFILE=geha-terraform aws s3 cp report.pdf \
  "s3://$(terraform output -raw bucket_name)/incoming/report.pdf"
```

The worker uses the pinned Docling Serve CPU image but runs one Python conversion instead of starting the HTTP server. `worker/worker.py` is embedded as the ECS container command by Terraform. This keeps the example free of a custom image build; changes to the worker create a new task definition revision.

## React viewer

Open the URL printed by Vite and click **Load AWS outputs** or **Upload PDF and process**. The local Vite server uses the AWS SDK and your profile to list `extracted/*.md`; it pairs each file with `incoming/*.pdf`, serves Markdown through a localhost endpoint, and provides a 15-minute presigned PDF URL for the browser's PDF viewer. **S3 bucket files** lists the bucket by prefix and previews PDFs, Markdown, JSON, CSV, and images. **Docling models** lists the Mac's downloaded Hugging Face models separately from any per-run Fargate model inventory. Existing runs predate that inventory and show no run models. The IAM identity used by the local profile also needs access to list and describe ECS tasks and read the Docling CloudWatch log stream for the status panel. Reload AWS outputs if a PDF URL expires. This local development server binds to `127.0.0.1`; the static production build does not provide an AWS backend.

You can also use **Add PDFs and Markdown** for a local pair, or **Open run folder** for several local pairs. The viewer matches `report.pdf` with `report.md` by basename, shows the entire multipage PDF in the left pane, and renders Markdown tables and text in the right pane. Local files stay in browser memory. Duplicate basenames from different local folders should be renamed before loading.

## References

- [Docling Serve deployment](https://docling-project.github.io/docling/usage/api_server/deployment/)
- [Docling Serve REST API](https://docling-project.github.io/docling/usage/api_server/rest_api/)
