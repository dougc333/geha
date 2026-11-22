output "bucket_name" {
  value = aws_s3_bucket.runs.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.worker.repository_url
}

output "worker_image_uri" {
  value = local.image_uri
}

output "source_sha256" {
  value = var.source_sha256
}

output "ecs_cluster_arn" {
  value = aws_ecs_cluster.forms.arn
}

output "task_definition_arn" {
  value = aws_ecs_task_definition.worker.arn
}

output "task_execution_role_arn" {
  value = aws_iam_role.execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "task_security_group_id" {
  value = aws_security_group.worker.id
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.worker.name
}
