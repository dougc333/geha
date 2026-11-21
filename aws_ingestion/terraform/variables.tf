variable "aws_region" {
  type    = string
  default = "us-west-2"
}

variable "project_name" {
  type    = string
  default = "geha-aws-ingestion"
}

variable "image_tag" {
  type        = string
  description = "Image tag already pushed to the ECR repository."
}

variable "allowed_cidrs" {
  type        = list(string)
  description = "Client IP ranges allowed to reach the demo ALB. Supply a narrow CIDR; the API has no login."
  validation {
    condition     = length(var.allowed_cidrs) > 0 && alltrue([for cidr in var.allowed_cidrs : can(cidrhost(cidr, 0)) && cidr != "0.0.0.0/0" && cidr != "::/0"])
    error_message = "Supply at least one valid narrow CIDR; unrestricted Internet access is not allowed."
  }
}

variable "model_secrets_enabled" {
  type        = bool
  description = "Manage three model API key records in Secrets Manager. Disable to schedule deletion and avoid recreation."
  default     = false
}

variable "model_secret_arns" {
  type        = map(string)
  description = "Optional existing Secrets Manager ARNs overriding the three Terraform-managed secret records."
  default     = {}
  validation {
    condition     = alltrue([for key in keys(var.model_secret_arns) : contains(["ANTHROPIC_API_KEY", "NOUS_API_KEY", "OPENAI_API_KEY"], key)])
    error_message = "Only model API key environment names are supported."
  }
}

variable "api_cpu" {
  type    = number
  default = 1024
}
variable "api_memory" {
  type    = number
  default = 2048
}
variable "worker_cpu" {
  type    = number
  default = 4096
}
variable "worker_memory" {
  type    = number
  default = 16384
}
variable "worker_ephemeral_gib" {
  type    = number
  default = 40
}
variable "runtime_enabled" {
  type        = bool
  description = "Create the ALB and ECS services. Disable to retain data while removing billable app runtime."
  default     = false
}

variable "api_desired_count" {
  type    = number
  default = 1
}
variable "worker_desired_count" {
  type    = number
  default = 1
}
variable "container_architecture" {
  type    = string
  default = "ARM64"
  validation {
    condition     = contains(["ARM64", "X86_64"], var.container_architecture)
    error_message = "Use ARM64 or X86_64."
  }
}
