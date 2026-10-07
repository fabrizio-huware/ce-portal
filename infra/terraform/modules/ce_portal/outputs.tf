output "service_url" {
  description = "Indirizzo del portale."
  value       = local.public_base_url
}

output "service_name" {
  value = google_cloud_run_v2_service.app.name
}

output "job_names" {
  description = "Lavori di Cloud Run: migrazioni, dati iniziali, invio email."
  value       = { for k, j in google_cloud_run_v2_job.jobs : k => j.name }
}

output "image_repository" {
  description = "Dove si pubblicano le immagini."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "workload_identity_provider" {
  description = "Da copiare nella variabile GCP_WORKLOAD_IDENTITY_PROVIDER dell'ambiente GitHub."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "Da copiare nella variabile GCP_DEPLOY_SERVICE_ACCOUNT dell'ambiente GitHub."
  value       = google_service_account.deploy.email
}

output "runtime_service_account" {
  value = google_service_account.runtime.email
}

output "cloud_run_service_agent" {
  description = "Agente di servizio di Cloud Run di questo progetto (serve per far leggere le immagini da un altro registro)."
  value       = "serviceAccount:service-${data.google_project.this.number}@serverless-robot-prod.iam.gserviceaccount.com"
}

output "database_connection_name" {
  value = google_sql_database_instance.db.connection_name
}

output "secrets_to_fill" {
  description = "Segreti da aggiornare a mano con i valori veri (non passano da Terraform)."
  value = [
    google_secret_manager_secret.all["mailjet_api_key"].secret_id,
    google_secret_manager_secret.all["mailjet_api_secret"].secret_id,
  ]
}
