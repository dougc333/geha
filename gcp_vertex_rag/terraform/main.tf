provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  services = toset([
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com",
  ])
}

resource "google_project_service" "required" {
  for_each           = local.services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "documents" {
  name                        = "${var.project_id}-vertex-rag-documents"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false

  versioning { enabled = true }

  lifecycle_rule {
    condition { num_newer_versions = 3 }
    action { type = "Delete" }
  }
}

resource "google_artifact_registry_repository" "app" {
  location      = var.region
  repository_id = "vertex-rag"
  format        = "DOCKER"
  depends_on    = [google_project_service.required]
}

resource "google_service_account" "runtime" {
  account_id   = "vertex-rag-runtime"
  display_name = "Vertex RAG Cloud Run runtime"
}

resource "google_service_account" "ingest" {
  account_id   = "vertex-rag-ingest"
  display_name = "Vertex RAG document ingestion"
}

resource "google_project_iam_member" "runtime_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = google_service_account.runtime.member
}

resource "google_project_iam_member" "runtime_logs" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = google_service_account.runtime.member
}

resource "google_project_iam_member" "ingest_vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = google_service_account.ingest.member
}

resource "google_storage_bucket_iam_member" "ingest_documents" {
  bucket = google_storage_bucket.documents.name
  role   = "roles/storage.objectAdmin"
  member = google_service_account.ingest.member
}

resource "google_cloud_run_v2_service" "api" {
  name                = "geha-vertex-rag"
  location            = var.region
  deletion_protection = true
  ingress             = "INGRESS_TRAFFIC_ALL"

  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "120s"
    max_instance_request_concurrency = 20

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = var.image
      resources {
        limits = { cpu = "1", memory = "1Gi" }
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "VERTEX_RAG_CORPUS"
        value = var.rag_corpus_name
      }
      env {
        name  = "GEMINI_MODEL"
        value = "gemini-2.5-flash"
      }
      env {
        name  = "RAG_TOP_K"
        value = "6"
      }

      startup_probe {
        failure_threshold = 3
        period_seconds    = 10
        timeout_seconds   = 3
        http_get {
          path = "/healthz"
        }
      }
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_service_iam_member" "invoker" {
  for_each = var.invoker_members
  project  = var.project_id
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = each.value
}
