# Test del modulo con provider simulati (nessun accesso a Google Cloud): controllano che
# i valori pianificati siano quelli voluti. Si lanciano con:  terraform test   (oppure: tofu test)

mock_provider "google" {
  mock_data "google_project" {
    defaults = {
      number = "123456789012"
    }
  }

  # I valori inventati dal simulatore non rispettano i formati che Google richiede: se ne indicano di realistici.
  mock_resource "google_service_account" {
    defaults = {
      name  = "projects/demo-progetto/serviceAccounts/esempio@demo-progetto.iam.gserviceaccount.com"
      email = "esempio@demo-progetto.iam.gserviceaccount.com"
    }
  }

  mock_resource "google_iam_workload_identity_pool" {
    defaults = {
      name = "projects/123456789012/locations/global/workloadIdentityPools/ce-portal-test-github"
    }
  }

  mock_resource "google_iam_workload_identity_pool_provider" {
    defaults = {
      name = "projects/123456789012/locations/global/workloadIdentityPools/ce-portal-test-github/providers/github"
    }
  }
}

mock_provider "random" {}

variables {
  project_id        = "demo-progetto"
  environment       = "test"
  github_repository = "huware/ce-portal"
}

run "indirizzo_e_nomi" {
  command = plan

  assert {
    condition     = output.service_url == "https://ce-portal-test-123456789012.europe-west8.run.app"
    error_message = "L'indirizzo pubblico deve essere quello deterministico di Cloud Run"
  }
  assert {
    condition     = output.image_repository == "europe-west8-docker.pkg.dev/demo-progetto/ce-portal"
    error_message = "Il registro delle immagini ha un percorso inatteso"
  }
  assert {
    condition     = google_cloud_run_v2_service.app.name == "ce-portal-test"
    error_message = "Nome del servizio inatteso"
  }
  assert {
    condition     = google_cloud_run_v2_service.app.location == "europe-west8"
    error_message = "La regione predefinita deve essere Milano"
  }
}

run "dominio_proprio" {
  command = plan

  variables {
    public_url_override = "https://ce.example.com"
  }

  assert {
    condition     = output.service_url == "https://ce.example.com"
    error_message = "Con un dominio proprio, i link devono usare quello"
  }
  assert {
    condition     = local.env["PUBLIC_BASE_URL"] == "https://ce.example.com" && local.env["CORS_ORIGINS"] == "https://ce.example.com"
    error_message = "PUBLIC_BASE_URL e CORS_ORIGINS devono seguire il dominio proprio"
  }
}

run "variabili_dambiente_del_servizio" {
  command = plan

  variables {
    environment            = "prod"
    google_oauth_client_id = "123-abc.apps.googleusercontent.com"
    bootstrap_admin_email  = "admin@huware.com"
    allowed_email_domains  = ["huware.com", "huware.it"]
  }

  assert {
    condition     = local.env["APP_ENV"] == "prod" && local.env["DB_USER"] == "ceportal" && local.env["DB_NAME"] == "ceportal"
    error_message = "APP_ENV, DB_USER e DB_NAME inattesi"
  }
  assert {
    condition     = local.env["GOOGLE_OAUTH_CLIENT_ID"] == "123-abc.apps.googleusercontent.com" && local.env["BOOTSTRAP_ADMIN_EMAIL"] == "admin@huware.com"
    error_message = "Client ID e amministratore iniziale devono arrivare al servizio"
  }
  assert {
    condition     = local.env["ALLOWED_EMAIL_DOMAINS"] == "huware.com,huware.it"
    error_message = "I domini ammessi devono essere separati da virgola"
  }
  assert {
    condition     = contains(keys(local.env), "CLOUDSQL_INSTANCE") && !contains(keys(local.env), "DB_PASSWORD") && !contains(keys(local.env), "JWT_SECRET")
    error_message = "Nessun segreto deve stare tra le variabili in chiaro"
  }
}

run "senza_client_id_e_admin_le_variabili_non_ci_sono" {
  command = plan

  assert {
    condition     = !contains(keys(local.env), "GOOGLE_OAUTH_CLIENT_ID") && !contains(keys(local.env), "BOOTSTRAP_ADMIN_EMAIL")
    error_message = "Variabili vuote non devono essere passate al servizio"
  }
}

run "i_segreti_stanno_in_secret_manager" {
  command = plan

  assert {
    condition     = toset(keys(local.secret_env)) == toset(["JWT_SECRET", "DB_PASSWORD", "MAILJET_API_KEY", "MAILJET_API_SECRET"])
    error_message = "I quattro segreti devono arrivare da Secret Manager"
  }
  assert {
    condition     = length(google_secret_manager_secret.all) == 4
    error_message = "Devono esistere quattro segreti"
  }
  assert {
    condition     = alltrue([for s in google_secret_manager_secret.all : length(s.replication[0].auto) == 1])
    error_message = "Replica automatica dei segreti"
  }
  assert {
    condition     = length(google_secret_manager_secret_iam_member.runtime_reads) == 4
    error_message = "L'account di esecuzione deve poter leggere solo i quattro segreti"
  }
  assert {
    condition     = alltrue([for k, v in google_secret_manager_secret_version.mailjet_placeholder : v.secret_data == "DA-IMPOSTARE"])
    error_message = "Le chiavi di Mailjet non devono passare da Terraform"
  }
}

run "protezioni_in_produzione" {
  command = plan

  variables {
    environment         = "prod"
    deletion_protection = true
  }

  assert {
    condition     = google_sql_database_instance.db.deletion_protection && google_sql_database_instance.db.settings[0].deletion_protection_enabled
    error_message = "Il database di produzione deve essere protetto dall'eliminazione"
  }
  assert {
    condition     = google_cloud_run_v2_service.app.deletion_protection && alltrue([for j in google_cloud_run_v2_job.jobs : j.deletion_protection])
    error_message = "Servizio e lavori devono essere protetti"
  }
  assert {
    condition     = google_sql_database_instance.db.settings[0].backup_configuration[0].enabled
    error_message = "I backup devono essere attivi"
  }
}

run "database_sicuro_e_postgres_16" {
  command = plan

  variables {
    db_point_in_time_recovery = true
  }

  assert {
    condition     = google_sql_database_instance.db.database_version == "POSTGRES_16"
    error_message = "Versione del database"
  }
  assert {
    condition     = google_sql_database_instance.db.settings[0].ip_configuration[0].ssl_mode == "ENCRYPTED_ONLY"
    error_message = "Solo connessioni cifrate"
  }
  assert {
    condition     = length(google_sql_database_instance.db.settings[0].ip_configuration[0].authorized_networks) == 0
    error_message = "Nessuna rete autorizzata: ci si arriva solo da Cloud Run"
  }
  assert {
    condition     = google_sql_database_instance.db.settings[0].backup_configuration[0].point_in_time_recovery_enabled
    error_message = "Il recupero a un istante preciso deve seguire la variabile"
  }
}

run "lavori_e_pianificazione" {
  command = plan

  assert {
    condition     = toset(keys(google_cloud_run_v2_job.jobs)) == toset(["migrate", "seed", "mail"])
    error_message = "Servono i lavori migrate, seed e mail"
  }
  assert {
    condition     = local.jobs["migrate"].command == ["alembic"] && local.jobs["migrate"].args == ["upgrade", "head"]
    error_message = "La migrazione esegue alembic upgrade head"
  }
  assert {
    condition     = local.jobs["mail"].args == ["-m", "app.notifications", "dispatch"]
    error_message = "L'invio email esegue app.notifications dispatch"
  }
  assert {
    condition     = google_cloud_scheduler_job.mail.schedule == "*/5 * * * *" && google_cloud_scheduler_job.mail.time_zone == "Europe/Rome"
    error_message = "L'invio delle email parte ogni 5 minuti"
  }
  assert {
    condition     = endswith(google_cloud_scheduler_job.mail.http_target[0].uri, "/jobs/ce-portal-test-mail:run")
    error_message = "La pianificazione deve lanciare il lavoro delle email"
  }
}

run "accesso_pubblico_configurabile" {
  command = plan

  assert {
    condition     = length(google_cloud_run_v2_service_iam_member.public) == 1
    error_message = "Per impostazione predefinita il servizio è raggiungibile (l'accesso è protetto dal login)"
  }
}

run "accesso_non_pubblico" {
  command = plan

  variables {
    allow_unauthenticated = false
  }

  assert {
    condition     = length(google_cloud_run_v2_service_iam_member.public) == 0
    error_message = "Senza allow_unauthenticated nessuno può invocare il servizio senza permessi"
  }
}

run "github_solo_il_repository_indicato" {
  command = plan

  assert {
    condition     = google_iam_workload_identity_pool_provider.github.attribute_condition == "assertion.repository == \"huware/ce-portal\""
    error_message = "Solo il repository indicato può ottenere un'identità"
  }
  assert {
    condition     = google_iam_workload_identity_pool_provider.github.oidc[0].issuer_uri == "https://token.actions.githubusercontent.com"
    error_message = "Emittente OIDC di GitHub"
  }
}

run "avvisi_solo_con_un_indirizzo" {
  command = plan

  assert {
    condition     = length(google_monitoring_notification_channel.email) == 0 && length(local.channels) == 0
    error_message = "Senza indirizzo non si crea nessun canale di avviso"
  }
}

run "avvisi_con_indirizzo" {
  command = plan

  variables {
    alert_email = "teamdata@huware.com"
  }

  assert {
    condition     = length(google_monitoring_notification_channel.email) == 1
    error_message = "Con un indirizzo si crea il canale di avviso"
  }
}

run "ambiente_non_valido" {
  command = plan

  variables {
    environment = "staging"
  }

  expect_failures = [var.environment]
}

run "repository_non_valido" {
  command = plan

  variables {
    github_repository = "solo-il-nome"
  }

  expect_failures = [var.github_repository]
}

run "mail_backend_non_valido" {
  command = plan

  variables {
    mail_backend = "sendgrid"
  }

  expect_failures = [var.mail_backend]
}
