output "document_bucket" {
  value = google_storage_bucket.documents.name
}

output "artifact_repository" {
  value = google_artifact_registry_repository.app.name
}

output "service_url" {
  value = google_cloud_run_v2_service.api.uri
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "ingest_service_account" {
  value = google_service_account.ingest.email
}

