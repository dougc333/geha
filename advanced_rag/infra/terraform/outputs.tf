output "application_url" {
  description = "IP-restricted HTTPS browser URL."
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "alb_origin_url" {
  description = "Direct HTTP origin URL for diagnostics."
  value       = "http://${aws_lb.app.dns_name}"
}

output "artifact_bucket" {
  value = aws_s3_bucket.artifacts.id
}

output "dynamodb_table" {
  value = aws_dynamodb_table.jobs.name
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "ecs_cluster" {
  value = aws_ecs_cluster.app.name
}

output "ecs_service" {
  value = aws_ecs_service.app.name
}

output "jev_secret_arn" {
  value = aws_secretsmanager_secret.jev.arn
}
