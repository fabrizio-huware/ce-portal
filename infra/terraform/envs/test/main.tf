terraform {
  required_version = ">= 1.6"

  backend "gcs" {} # il bucket si indica con: terraform init -backend-config=backend.hcl
}

provider "google" {
  project = var.project_id
  region  = var.region
}

variable "project_id" {
  description = "ID del progetto Google Cloud di test."
  type        = string
}

variable "region" {
  type    = string
  default = "europe-west8"
}

variable "github_repository" {
  description = "organizzazione/repository GitHub."
  type        = string
}

variable "google_oauth_client_id" {
  type    = string
  default = ""
}

variable "bootstrap_admin_email" {
  type    = string
  default = ""
}

variable "alert_email" {
  type    = string
  default = ""
}

variable "mail_backend" {
  type    = string
  default = "console"
}

variable "public_url_override" {
  type    = string
  default = ""
}

variable "public_access_method" {
  description = "iam_binding (predefinito) oppure disable_iam_check se l'organizzazione vieta allUsers."
  type        = string
  default     = "iam_binding"
}

variable "registry_reader_members" {
  type    = list(string)
  default = []
}

variable "min_instances" {
  type    = number
  default = 0
}

module "ce_portal" {
  source = "../../modules/ce_portal"

  project_id        = var.project_id
  region            = var.region
  environment       = "test"
  github_repository = var.github_repository

  google_oauth_client_id  = var.google_oauth_client_id
  bootstrap_admin_email   = var.bootstrap_admin_email
  alert_email             = var.alert_email
  mail_backend            = var.mail_backend
  public_url_override     = var.public_url_override
  registry_reader_members = var.registry_reader_members
  public_access_method    = var.public_access_method

  db_tier                   = "db-f1-micro"
  db_availability_type      = "ZONAL"
  db_disk_size_gb           = 10
  db_backup_retention_days  = 7
  db_point_in_time_recovery = false
  deletion_protection       = false

  min_instances = var.min_instances
  max_instances = 3
}

output "service_url" {
  value = module.ce_portal.service_url
}

output "image_repository" {
  value = module.ce_portal.image_repository
}

output "workload_identity_provider" {
  value = module.ce_portal.workload_identity_provider
}

output "deploy_service_account" {
  value = module.ce_portal.deploy_service_account
}

output "cloud_run_service_agent" {
  value = module.ce_portal.cloud_run_service_agent
}

output "database_connection_name" {
  value = module.ce_portal.database_connection_name
}

output "secrets_to_fill" {
  value = module.ce_portal.secrets_to_fill
}

output "github_variables" {
  value = module.ce_portal.github_variables
}

output "github_variable_commands" {
  value = module.ce_portal.github_variable_commands
}
