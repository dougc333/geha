variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "project_name" {
  type    = string
  default = "aws-forms"
}

variable "image_tag" {
  type        = string
  description = "Immutable ECR image tag for the forms worker. Change it for each build."
  default     = "v1"
}

variable "source_sha256" {
  type        = string
  description = "SHA-256 of the reviewed alt-2 PDF; this first task rejects other documents."
  default     = "583531c29e7d97d6754dbe6b8c2debfcf7382ca6a2965a4a9c2d1aaff7ddd2d8"
}

variable "anthropic_secret_arn" {
  type        = string
  description = "ARN of an existing Secrets Manager secret containing ANTHROPIC_API_KEY."
}

variable "openai_secret_arn" {
  type        = string
  description = "ARN of an existing Secrets Manager secret containing OPENAI_API_KEY."
}

variable "task_cpu" {
  type        = number
  description = "Fargate CPU units for a single extraction task."
  default     = 4096
}

variable "task_memory" {
  type        = number
  description = "Fargate memory in MiB for a single extraction task."
  default     = 16384
}
