output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.id
}
output "ecr_repository_url" {
  value = aws_ecr_repository.ingestion.repository_url
}
output "api_url" {
  value = var.runtime_enabled ? "http://${aws_lb.api[0].dns_name}" : null
}
output "job_queue_url" {
  value = aws_sqs_queue.jobs.url
}
output "state_table_name" {
  value = aws_dynamodb_table.run_state.name
}
output "aws_region" {
  value = var.aws_region
}
