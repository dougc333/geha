data "aws_caller_identity" "current" {}

locals {
  bucket_name = "${var.project_name}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
  image_uri   = "${aws_ecr_repository.ingestion.repository_url}:${var.image_tag}"
}

resource "aws_s3_bucket" "artifacts" {
  bucket        = local.bucket_name
  force_destroy = false
  tags          = { Name = "${var.project_name}-artifacts" }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket                  = aws_s3_bucket.artifacts.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_ownership_controls" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_sqs_queue" "dlq" {
  name                      = "${var.project_name}-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "jobs" {
  name                       = "${var.project_name}-jobs"
  visibility_timeout_seconds = 900
  receive_wait_time_seconds  = 10
  message_retention_seconds  = 1209600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 3
  })
}

resource "aws_dynamodb_table" "run_state" {
  name         = "${var.project_name}-run-state"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "run_id"
  range_key    = "record_key"
  attribute {
    name = "run_id"
    type = "S"
  }
  attribute {
    name = "record_key"
    type = "S"
  }
  server_side_encryption {
    enabled = true
  }
  point_in_time_recovery {
    enabled = true
  }
  tags = { Name = "${var.project_name}-run-state" }
}

resource "aws_ecr_repository" "ingestion" {
  name                 = var.project_name
  image_tag_mutability = "IMMUTABLE"
  force_delete         = false
  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.project_name}/api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}/worker"
  retention_in_days = 14
}
