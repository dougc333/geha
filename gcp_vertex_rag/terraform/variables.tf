variable "project_id" {
  type        = string
  description = "Google Cloud project ID."
}

variable "region" {
  type        = string
  default     = "us-central1"
  description = "Region shared by Cloud Run and Vertex AI RAG Engine."
}

variable "image" {
  type        = string
  description = "Immutable Artifact Registry image reference for the API."
}

variable "rag_corpus_name" {
  type        = string
  description = "Full Vertex AI RAG corpus resource name."
}

variable "invoker_members" {
  type        = set(string)
  default     = []
  description = "IAM principals allowed to invoke the private service, such as user:name@example.com."
}

