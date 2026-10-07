variable "project_id" {
  description = "ID del progetto Google Cloud di questo ambiente."
  type        = string
}

variable "region" {
  description = "Regione di Cloud Run, Cloud SQL e Artifact Registry."
  type        = string
  default     = "europe-west8" # Milano
}

variable "environment" {
  description = "Ambiente: test oppure prod."
  type        = string

  validation {
    condition     = contains(["test", "prod"], var.environment)
    error_message = "environment deve essere \"test\" oppure \"prod\"."
  }
}

variable "github_repository" {
  description = "Repository GitHub autorizzato a pubblicare, nella forma organizzazione/repository."
  type        = string

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository deve avere la forma organizzazione/repository."
  }
}

# ---------------------------------------------------------------- applicazione
variable "google_oauth_client_id" {
  description = "Client ID OAuth di Google per l'accesso (si crea a mano nella console: vedi docs/deploy.md)."
  type        = string
  default     = ""
}

variable "allowed_email_domains" {
  description = "Domini email ammessi all'accesso."
  type        = list(string)
  default     = ["huware.com"]
}

variable "bootstrap_admin_email" {
  description = "Email del primo amministratore (si crea al primo avvio se il database non ha utenti)."
  type        = string
  default     = ""
}

variable "mail_backend" {
  description = "mailjet (email vere) oppure console (le email si scrivono solo nel log: utile all'inizio)."
  type        = string
  default     = "mailjet"

  validation {
    condition     = contains(["mailjet", "console"], var.mail_backend)
    error_message = "mail_backend deve essere \"mailjet\" oppure \"console\"."
  }
}

variable "mail_from" {
  description = "Mittente delle email (deve essere validato in Mailjet)."
  type        = string
  default     = "teamdata@huware.com"
}

variable "public_url_override" {
  description = "Indirizzo pubblico se si usa un dominio proprio (https://...); vuoto = indirizzo run.app."
  type        = string
  default     = ""
}

variable "allow_unauthenticated" {
  description = "Il servizio è raggiungibile da Internet (l'accesso è protetto dal login dell'applicazione)."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------- database
variable "db_tier" {
  description = "Taglia di Cloud SQL (db-f1-micro per test, db-custom-1-3840 o più per produzione)."
  type        = string
  default     = "db-f1-micro"
}

variable "db_availability_type" {
  description = "ZONAL oppure REGIONAL (alta disponibilità: costa il doppio)."
  type        = string
  default     = "ZONAL"
}

variable "db_disk_size_gb" {
  type    = number
  default = 10
}

variable "db_backup_retention_days" {
  type    = number
  default = 7
}

variable "db_point_in_time_recovery" {
  description = "Recupero a un istante preciso (conserva i log del database)."
  type        = bool
  default     = false
}

variable "deletion_protection" {
  description = "Impedisce di eliminare per errore database e servizi con Terraform."
  type        = bool
  default     = true
}

# ---------------------------------------------------------------- Cloud Run
variable "min_instances" {
  description = "Istanze sempre accese: 0 = si spegne quando non serve (primo caricamento più lento), 1 = sempre pronto."
  type        = number
  default     = 0
}

variable "max_instances" {
  type    = number
  default = 3
}

variable "cpu" {
  type    = string
  default = "1"
}

variable "memory" {
  type    = string
  default = "1Gi"
}

variable "concurrency" {
  type    = number
  default = 40
}

variable "request_timeout_seconds" {
  type    = number
  default = 300
}

variable "initial_image" {
  description = "Immagine usata solo alla prima creazione; poi la sostituisce la pubblicazione automatica."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "registry_reader_members" {
  description = "Chi può leggere le immagini di questo registro (per esempio l'agente di servizio Cloud Run di un altro progetto)."
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------- monitoraggio
variable "alert_email" {
  description = "Indirizzo che riceve gli avvisi (servizio non raggiungibile, errori, lavori falliti). Vuoto = nessun avviso."
  type        = string
  default     = ""
}
