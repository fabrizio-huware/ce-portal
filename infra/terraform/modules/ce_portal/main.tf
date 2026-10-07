data "google_project" "this" {
  project_id = var.project_id
}

locals {
  prefix       = "ce-portal-${var.environment}"
  service_name = local.prefix
  runtime_user = "ceportal"
  db_name      = "ceportal"

  # Indirizzo che Cloud Run assegna al servizio (è deterministico: nome, numero del progetto e regione).
  run_url         = "https://${local.service_name}-${data.google_project.this.number}.${var.region}.run.app"
  public_base_url = var.public_url_override != "" ? var.public_url_override : local.run_url

  apis = [
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
    "sts.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each = toset(local.apis)

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

# ============================================================== registro delle immagini
resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "ce-portal"
  format        = "DOCKER"
  description   = "Immagini del Portale Conti Economici"

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 20
    }
  }
  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      tag_state  = "ANY"
      older_than = "2592000s" # 30 giorni
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_artifact_registry_repository_iam_member" "readers" {
  for_each = toset(var.registry_reader_members)

  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.images.repository_id
  role       = "roles/artifactregistry.reader"
  member     = each.value
}

# ============================================================== account di servizio
resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "${local.prefix}-run"
  display_name = "Portale CE (${var.environment}): esecuzione"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "runtime_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "${local.prefix}-sched"
  display_name = "Portale CE (${var.environment}): pianificazione dei lavori"

  depends_on = [google_project_service.apis]
}

resource "google_service_account" "deploy" {
  project      = var.project_id
  account_id   = "${local.prefix}-deploy"
  display_name = "Portale CE (${var.environment}): pubblicazione da GitHub"

  depends_on = [google_project_service.apis]
}

# La pubblicazione può: aggiornare servizio e lavori, scrivere nel registro, "agire come" l'account di esecuzione.
resource "google_project_iam_member" "deploy_run" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_artifact_registry_repository_iam_member" "deploy_writer" {
  project    = var.project_id
  location   = var.region
  repository = google_artifact_registry_repository.images.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "deploy_acts_as_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

# ============================================================== GitHub senza chiavi (Workload Identity Federation)
resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "${local.prefix}-github"
  display_name              = "GitHub Actions (${var.environment})"

  depends_on = [google_project_service.apis]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  # Solo questo repository può ottenere un'identità: nessun altro repository GitHub.
  attribute_condition = "assertion.repository == \"${var.github_repository}\""

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "deploy_from_github" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}

# ============================================================== segreti
resource "random_password" "jwt" {
  length  = 64
  special = false
}

resource "random_password" "db" {
  length  = 32
  special = false
}

locals {
  secrets = {
    jwt_secret         = "${local.prefix}-jwt-secret"
    db_password        = "${local.prefix}-db-password"
    mailjet_api_key    = "${local.prefix}-mailjet-api-key"
    mailjet_api_secret = "${local.prefix}-mailjet-api-secret"
  }
}

resource "google_secret_manager_secret" "all" {
  for_each = local.secrets

  project   = var.project_id
  secret_id = each.value

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "jwt" {
  secret      = google_secret_manager_secret.all["jwt_secret"].id
  secret_data = random_password.jwt.result
}

resource "google_secret_manager_secret_version" "db" {
  secret      = google_secret_manager_secret.all["db_password"].id
  secret_data = random_password.db.result
}

# Le chiavi di Mailjet non passano da Terraform (finirebbero nello stato): qui c'è solo un segnaposto.
# Il valore vero si aggiunge come nuova versione del segreto (docs/deploy.md) e Terraform non lo tocca più.
resource "google_secret_manager_secret_version" "mailjet_placeholder" {
  for_each = toset(["mailjet_api_key", "mailjet_api_secret"])

  secret      = google_secret_manager_secret.all[each.key].id
  secret_data = "DA-IMPOSTARE"

  lifecycle {
    ignore_changes = [secret_data]
  }
}

resource "google_secret_manager_secret_iam_member" "runtime_reads" {
  for_each = google_secret_manager_secret.all

  project   = var.project_id
  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# ============================================================== database
resource "google_sql_database_instance" "db" {
  project             = var.project_id
  name                = "${local.prefix}-db"
  region              = var.region
  database_version    = "POSTGRES_16"
  deletion_protection = var.deletion_protection

  settings {
    tier                        = var.db_tier
    edition                     = "ENTERPRISE"
    availability_type           = var.db_availability_type
    disk_type                   = "PD_SSD"
    disk_size                   = var.db_disk_size_gb
    disk_autoresize             = true
    deletion_protection_enabled = var.deletion_protection

    backup_configuration {
      enabled                        = true
      start_time                     = "02:00"
      point_in_time_recovery_enabled = var.db_point_in_time_recovery
      backup_retention_settings {
        retained_backups = var.db_backup_retention_days
      }
    }

    # Indirizzo pubblico ma senza reti autorizzate: ci si arriva solo da Cloud Run con il connettore
    # integrato (autenticato dai permessi del progetto), sempre cifrato.
    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    maintenance_window {
      day          = 7 # domenica
      hour         = 3
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled = true
    }

    database_flags {
      name  = "log_min_duration_statement"
      value = "1000" # registra le query più lente di 1 secondo
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_sql_database" "app" {
  project  = var.project_id
  instance = google_sql_database_instance.db.name
  name     = local.db_name
}

resource "google_sql_user" "app" {
  project  = var.project_id
  instance = google_sql_database_instance.db.name
  name     = local.runtime_user
  password = random_password.db.result
}

# ============================================================== servizio e lavori di Cloud Run
locals {
  env = merge(
    {
      APP_ENV               = var.environment
      CLOUDSQL_INSTANCE     = google_sql_database_instance.db.connection_name
      DB_USER               = local.runtime_user
      DB_NAME               = local.db_name
      PUBLIC_BASE_URL       = local.public_base_url
      CORS_ORIGINS          = local.public_base_url
      MAIL_BACKEND          = var.mail_backend
      MAIL_FROM             = var.mail_from
      ALLOWED_EMAIL_DOMAINS = join(",", var.allowed_email_domains)
    },
    var.google_oauth_client_id != "" ? { GOOGLE_OAUTH_CLIENT_ID = var.google_oauth_client_id } : {},
    var.bootstrap_admin_email != "" ? { BOOTSTRAP_ADMIN_EMAIL = var.bootstrap_admin_email } : {},
  )

  secret_env = {
    JWT_SECRET         = google_secret_manager_secret.all["jwt_secret"].secret_id
    DB_PASSWORD        = google_secret_manager_secret.all["db_password"].secret_id
    MAILJET_API_KEY    = google_secret_manager_secret.all["mailjet_api_key"].secret_id
    MAILJET_API_SECRET = google_secret_manager_secret.all["mailjet_api_secret"].secret_id
  }

  # Lavori eseguiti con la stessa immagine del servizio, ma con un altro comando.
  jobs = {
    migrate = { command = ["alembic"], args = ["upgrade", "head"], timeout = "600s" }
    seed    = { command = ["python"], args = ["-m", "app.db.seed"], timeout = "300s" }
    mail    = { command = ["python"], args = ["-m", "app.notifications", "dispatch"], timeout = "180s" }
  }
}

resource "google_cloud_run_v2_service" "app" {
  project             = var.project_id
  name                = local.service_name
  location            = var.region
  ingress             = "INGRESS_TRAFFIC_ALL"
  deletion_protection = var.deletion_protection

  template {
    service_account                  = google_service_account.runtime.email
    timeout                          = "${var.request_timeout_seconds}s"
    max_instance_request_concurrency = var.concurrency

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.db.connection_name]
      }
    }

    containers {
      image = var.initial_image

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle          = true # CPU assegnata solo mentre elabora richieste
        startup_cpu_boost = true
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      dynamic "env" {
        for_each = local.env
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = local.secret_env
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      # Controllo semplice di avvio: va bene anche per l'immagine segnaposto della prima creazione.
      startup_probe {
        tcp_socket {
          port = 8080
        }
        period_seconds    = 3
        timeout_seconds   = 3
        failure_threshold = 30
      }
    }
  }

  lifecycle {
    # L'immagine la aggiorna la pubblicazione automatica: Terraform non deve riportarla indietro.
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [
    google_secret_manager_secret_version.jwt,
    google_secret_manager_secret_version.db,
    google_secret_manager_secret_version.mailjet_placeholder,
    google_secret_manager_secret_iam_member.runtime_reads,
    google_project_iam_member.runtime_cloudsql,
    google_sql_user.app,
    google_sql_database.app,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "public" {
  count = var.allow_unauthenticated ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_job" "jobs" {
  for_each = local.jobs

  project             = var.project_id
  name                = "${local.prefix}-${each.key}"
  location            = var.region
  deletion_protection = var.deletion_protection

  template {
    template {
      service_account = google_service_account.runtime.email
      timeout         = each.value.timeout
      max_retries     = 0

      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.db.connection_name]
        }
      }

      containers {
        image   = var.initial_image
        command = each.value.command
        args    = each.value.args

        resources {
          limits = {
            cpu    = "1"
            memory = "512Mi"
          }
        }

        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }

        dynamic "env" {
          for_each = local.env
          content {
            name  = env.key
            value = env.value
          }
        }

        dynamic "env" {
          for_each = local.secret_env
          content {
            name = env.key
            value_source {
              secret_key_ref {
                secret  = env.value
                version = "latest"
              }
            }
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  depends_on = [
    google_secret_manager_secret_version.jwt,
    google_secret_manager_secret_version.db,
    google_secret_manager_secret_version.mailjet_placeholder,
    google_secret_manager_secret_iam_member.runtime_reads,
    google_project_iam_member.runtime_cloudsql,
  ]
}

# Invio delle email in coda ogni 5 minuti (ritentativi di quelle fallite e recupero dei guasti).
resource "google_cloud_run_v2_job_iam_member" "scheduler_runs_mail" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_job.jobs["mail"].name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "mail" {
  project          = var.project_id
  region           = var.region
  name             = "${local.prefix}-mail"
  description      = "Invia le email in coda del Portale CE"
  schedule         = "*/5 * * * *"
  time_zone        = "Europe/Rome"
  attempt_deadline = "180s"

  retry_config {
    retry_count = 1
  }

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.jobs["mail"].name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_runs_mail]
}

# ============================================================== avvisi
locals {
  channels = var.alert_email != "" ? [google_monitoring_notification_channel.email[0].id] : []
  host     = replace(local.public_base_url, "https://", "")
}

resource "google_monitoring_notification_channel" "email" {
  count = var.alert_email != "" ? 1 : 0

  project      = var.project_id
  display_name = "Portale CE (${var.environment}): avvisi"
  type         = "email"
  labels = {
    email_address = var.alert_email
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_uptime_check_config" "health" {
  project      = var.project_id
  display_name = "Portale CE (${var.environment}): raggiungibile"
  period       = "300s"
  timeout      = "10s"

  http_check {
    path           = "/api/v1/health"
    port           = 443
    use_ssl        = true
    validate_ssl   = true
    request_method = "GET"
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      project_id = var.project_id
      host       = local.host
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_monitoring_alert_policy" "unreachable" {
  project               = var.project_id
  display_name          = "Portale CE (${var.environment}): non raggiungibile"
  combiner              = "OR"
  notification_channels = local.channels

  conditions {
    display_name = "Il controllo di raggiungibilità fallisce"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.health.uptime_check_id}\" AND resource.type=\"uptime_url\""
      comparison      = "COMPARISON_GT"
      threshold_value = 1
      duration        = "300s"
      aggregations {
        alignment_period     = "1200s"
        per_series_aligner   = "ALIGN_NEXT_OLDER"
        cross_series_reducer = "REDUCE_COUNT_FALSE"
        group_by_fields      = ["resource.label.*"]
      }
      trigger {
        count = 1
      }
    }
  }

  documentation {
    content   = "Il portale non risponde al controllo /api/v1/health. Vedi docs/deploy.md, sezione «Se qualcosa non va»."
    mime_type = "text/markdown"
  }
}

resource "google_monitoring_alert_policy" "server_errors" {
  project               = var.project_id
  display_name          = "Portale CE (${var.environment}): errori del server"
  combiner              = "OR"
  notification_channels = local.channels

  conditions {
    display_name = "Più di 5 risposte 5xx in 5 minuti"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_revision\" AND resource.label.service_name=\"${local.service_name}\" AND metric.type=\"run.googleapis.com/request_count\" AND metric.label.response_code_class=\"5xx\""
      comparison      = "COMPARISON_GT"
      threshold_value = 5
      duration        = "0s"
      aggregations {
        alignment_period     = "300s"
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
      }
      trigger {
        count = 1
      }
    }
  }
}

resource "google_monitoring_alert_policy" "job_failed" {
  project               = var.project_id
  display_name          = "Portale CE (${var.environment}): lavoro fallito"
  combiner              = "OR"
  notification_channels = local.channels

  conditions {
    display_name = "Un'esecuzione di migrazione, dati iniziali o invio email è fallita"
    condition_threshold {
      filter          = "resource.type=\"cloud_run_job\" AND metric.type=\"run.googleapis.com/job/completed_execution_count\" AND metric.label.result=\"failed\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "0s"
      aggregations {
        alignment_period   = "300s"
        per_series_aligner = "ALIGN_DELTA"
      }
      trigger {
        count = 1
      }
    }
  }
}
