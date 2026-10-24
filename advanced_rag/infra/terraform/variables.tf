variable "aws_region" {
  description = "AWS region for the complete deployment."
  type        = string
  default     = "us-west-2"
}

variable "name" {
  description = "Resource name prefix."
  type        = string
  default     = "geha-advanced-rag"
}

variable "image_tag" {
  description = "Immutable container image tag pushed by deploy.sh."
  type        = string
  default     = "latest"
}

variable "task_cpu" {
  description = "Fargate task CPU units for Jev routing and BGE query embeddings."
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 2048
}

variable "allowed_cidrs" {
  description = "IPv4 CIDRs allowed to reach the public ALB. Restrict this for non-demo use."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "cloudfront_allowed_ips" {
  description = "Exact IPv4 or IPv6 viewer addresses allowed by CloudFront. Defaults to the first ALB IPv4 CIDR address."
  type        = list(string)
  default     = []
}
