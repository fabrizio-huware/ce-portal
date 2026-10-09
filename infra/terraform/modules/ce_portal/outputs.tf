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
  description = "Valore della variabile <TEST|PROD>_WORKLOAD_IDENTITY_PROVIDER del repository GitHub (vedi github_variables)."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "Valore della variabile <TEST|PROD>_DEPLOY_SERVICE_ACCOUNT del repository GitHub (vedi github_variables)."
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

locals {
  # I nomi sono quelli che legge il flusso di pubblicazione (.github/workflows/deploy.yml).
  github_variables = {
    "GCP_REGION"                                           = var.region
    "${upper(var.environment)}_GCP_PROJECT"                = var.project_id
    "${upper(var.environment)}_WORKLOAD_IDENTITY_PROVIDER" = google_iam_workload_identity_pool_provider.github.name
    "${upper(var.environment)}_DEPLOY_SERVICE_ACCOUNT"     = google_service_account.deploy.email
  }
}

output "github_variables" {
  description = "Variabili da creare nel repository GitHub (Settings > Secrets and variables > Actions > Variables, scheda Variables, NON Secrets e non negli Environments)."
  value       = local.github_variables
}

output "github_variable_commands" {
  description = "Gli stessi valori come comandi per la GitHub CLI (gh), da incollare nel terminale dopo \"gh auth login\"."
  value       = [for k, v in local.github_variables : "gh variable set ${k} --repo ${var.github_repository} --body '${v}'"]
}
