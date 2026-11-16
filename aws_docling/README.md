# On-demand AWS Docling and PDF review viewer

S3 receives PDFs at `incoming/`. An S3 event invokes a short Lambda, which starts one Fargate task per PDF. The task runs Docling, writes Markdown to `extracted/`, and exits. The React viewer can upload a PDF, show processing status, and compare the source PDF with Markdown. There is no always-on Docling service, load balancer, NAT gateway, or VPC endpoint.

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

Open the local URL Vite prints. Click **Upload PDF and process** and select a PDF under 25 MB. The viewer gives it a unique S3 name, shows *processing*, and polls every five seconds for the matching Markdown. When conversion finishes, it shows the Markdown beside the PDF.

### 3. Verify the result or diagnose a failure

From `/Users/dc/geha/aws_docling/terraform`:

```bash
AWS_PROFILE=geha-terraform aws logs tail /ecs/aws-docling \
  --region us-west-2 --since 1h

AWS_PROFILE=geha-terraform aws s3 ls \
  "s3://$(terraform output -raw bucket_name)/extracted/" --recursive
```

A matching `.md` under `extracted/` confirms output was written. If the task fails, the viewer currently leaves the PDF marked *processing*; inspect the ECS task status and CloudWatch logs. S3 can deliver an event more than once, so duplicate tasks are possible. Presigned S3 URLs expire after six hours. The local AWS profile needs `s3:ListBucket`, `s3:GetObject`, and `s3:PutObject` permissions on the bucket.

For command-line upload, run this from the Terraform directory:

```bash
AWS_PROFILE=geha-terraform aws s3 cp report.pdf \
  "s3://$(terraform output -raw bucket_name)/incoming/report.pdf"
```

The worker uses the pinned Docling Serve CPU image but runs one Python conversion instead of starting the HTTP server. `worker/worker.py` is embedded as the ECS container command by Terraform. This keeps the example free of a custom image build; changes to the worker create a new task definition revision.

## React viewer

Open the URL printed by Vite and click **Load AWS outputs** or **Upload PDF and process**. The local Vite server uses the AWS SDK and your profile to list `extracted/*.md`; it pairs each file with `incoming/*.pdf`, serves Markdown through a localhost endpoint, and provides a 15-minute presigned PDF URL for the browser's PDF viewer. The IAM identity used by the local profile needs `s3:ListBucket`, `s3:GetObject`, and `s3:PutObject` on the bucket and relevant prefixes. Reload AWS outputs if a PDF URL expires. This local development server binds to `127.0.0.1`; the static production build does not provide an AWS backend.

You can also use **Add PDFs and Markdown** for a local pair, or **Open run folder** for several local pairs. The viewer matches `report.pdf` with `report.md` by basename, shows the entire multipage PDF in the left pane, and renders Markdown tables and text in the right pane. Local files stay in browser memory. Duplicate basenames from different local folders should be renamed before loading.

## References

- [Docling Serve deployment](https://docling-project.github.io/docling/usage/api_server/deployment/)
- [Docling Serve REST API](https://docling-project.github.io/docling/usage/api_server/rest_api/)
