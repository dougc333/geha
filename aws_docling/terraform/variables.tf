variable "aws_region" {
  type = string
}

variable "image_uri" {
  type        = string
  description = "Pinned Docling Serve CPU image URI, preferably mirrored into ECR."
}

variable "project_name" {
  type    = string
  default = "aws-docling"
}
