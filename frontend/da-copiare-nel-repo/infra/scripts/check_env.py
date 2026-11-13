#!/usr/bin/env python3
"""Controlla lo stato di un ambiente del Portale CE su Google Cloud e dice cosa manca.

    python3 infra/scripts/check_env.py --project ID-PROGETTO --env test|prod [--region europe-west8]

Serve gcloud già autenticato (gcloud auth login) con almeno il ruolo «Visualizzatore» sul progetto.
Legge soltanto: non modifica nulla. Non stampa mai il valore dei segreti, solo se esistono.
Esce con 0 se non ci sono errori (✘); gli avvisi (⚠) non bloccano.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

OK, WARN, FAIL = "✔", "⚠", "✘"
results: list[tuple[str, str]] = []


def say(level: str, text: str) -> None:
    results.append((level, text))
    print(f"  {level} {text}")


def section(title: str) -> None:
    print(f"\n{title}")


def run(*args: str, timeout: int = 90, merge: bool = False) -> tuple[int, str]:
    """Esegue un comando; con merge=True l'uscita include anche i messaggi di errore (dove gli script scrivono il motivo)."""
    try:
        p = subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout + (p.stderr if merge else "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)


def gcloud_json(*args: str):
    """Esegue gcloud con --format=json; restituisce (dati, None) oppure (None, motivo)."""
    code, out = run("gcloud", *args, "--format=json", "--quiet")
    if code != 0:
        return (
            None,
            "comando non riuscito (permessi mancanti, risorsa assente o gcloud non autenticato)",
        )
    try:
        return json.loads(out or "null"), None
    except json.JSONDecodeError:
        return None, "risposta non leggibile"


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age(value: str | None) -> timedelta | None:
    t = parse_time(value)
    return datetime.now(timezone.utc) - t if t else None


def human(delta: timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    if minutes < 90:
        return f"{minutes} minuti fa"
    if minutes < 60 * 48:
        return f"{minutes // 60} ore fa"
    return f"{minutes // 1440} giorni fa"


def unreadable(what: str, reason: str) -> None:
    say(WARN, f"{what}: non verificabile — {reason}")


# ------------------------------------------------------------------------------------------------ controlli
def check_service(a) -> str | None:
    section(f"1. Servizio Cloud Run «{a.service}»")
    data, err = gcloud_json(
        "run", "services", "describe", a.service, f"--project={a.project}", f"--region={a.region}"
    )
    if err:
        say(
            FAIL,
            f"servizio non leggibile ({err}). Hai lanciato «terraform apply» su questo progetto?",
        )
        return None
    status, spec = data.get("status", {}), data.get("spec", {}).get("template", {}).get("spec", {})
    ready = next((c for c in status.get("conditions", []) if c.get("type") == "Ready"), {})
    if ready.get("status") == "True":
        say(OK, "il servizio è pronto (Ready)")
    else:
        say(
            FAIL,
            f"il servizio non è pronto: {ready.get('message') or ready.get('reason') or 'motivo non indicato'}",
        )
    container = (spec.get("containers") or [{}])[0]
    image = container.get("image", "")
    if "cloudrun/container/hello" in image or not image:
        say(
            FAIL,
            "gira ancora l'immagine di esempio di Google: nessun rilascio è ancora arrivato (lancia il flusso Deploy)",
        )
    else:
        say(OK, f"immagine pubblicata: …/{image.rsplit('/', 1)[-1]}")
    latest_ready, latest_created = (
        status.get("latestReadyRevisionName"),
        status.get("latestCreatedRevisionName"),
    )
    if latest_ready and latest_ready == latest_created:
        say(OK, f"revisione attuale pronta: {latest_ready}")
    else:
        say(
            WARN,
            f"l'ultima revisione creata ({latest_created}) non è quella pronta ({latest_ready}): un rilascio è in corso o è fallito",
        )
    traffic = status.get("traffic", [])
    on_latest = sum(
        t.get("percent", 0)
        for t in traffic
        if t.get("latestRevision") or t.get("revisionName") == latest_ready
    )
    if on_latest == 100:
        say(OK, "il 100% del traffico va alla revisione più recente")
    else:
        say(
            WARN,
            f"solo il {on_latest}% del traffico va alla revisione più recente (dopo un ripristino manuale o automatico è normale)",
        )

    env = {e["name"]: e for e in container.get("env", []) if "name" in e}
    expect = "prod" if a.env == "prod" else "test"
    if env.get("APP_ENV", {}).get("value") == expect:
        say(OK, f"APP_ENV = {expect}")
    else:
        say(FAIL, f"APP_ENV vale «{env.get('APP_ENV', {}).get('value')}», deve essere «{expect}»")
    for name in ("CLOUDSQL_INSTANCE", "DB_USER", "DB_NAME", "PUBLIC_BASE_URL"):
        if name not in env:
            say(FAIL, f"manca la variabile {name}")
    if "GOOGLE_OAUTH_CLIENT_ID" in env:
        say(OK, "il Client ID di Google è impostato")
    else:
        say(
            FAIL,
            "manca GOOGLE_OAUTH_CLIENT_ID: l'accesso con Google non può funzionare (google_oauth_client_id in terraform.tfvars)",
        )
    if "BOOTSTRAP_ADMIN_EMAIL" in env:
        say(OK, "è impostato l'amministratore iniziale")
    else:
        say(
            WARN,
            "BOOTSTRAP_ADMIN_EMAIL non impostato: nessun amministratore verrà creato da un database vuoto",
        )
    audiences = [
        x.strip() for x in env.get("S2S_AUDIENCES", {}).get("value", "").split(",") if x.strip()
    ]
    if not audiences:
        say(
            WARN,
            "manca S2S_AUDIENCES: i programmi esterni (account di servizio) non possono accedere",
        )
    elif any(not x.startswith("https://") for x in audiences):
        say(
            FAIL,
            "S2S_AUDIENCES contiene indirizzi che non iniziano con https://: i token non corrisponderebbero",
        )
    else:
        say(OK, f"accesso per i programmi esterni: {len(audiences)} indirizzo/i come audience")
    backend = env.get("MAIL_BACKEND", {}).get("value")
    if backend == "mailjet":
        say(OK, "le email sono inviate con Mailjet")
    elif a.env == "prod":
        say(FAIL, f"in produzione MAIL_BACKEND vale «{backend}»: le email non verrebbero inviate")
    else:
        say(
            WARN,
            f'MAIL_BACKEND vale «{backend}»: nel test le email NON vengono inviate (si scrivono solo nel log). Per provarle: mail_backend = "mailjet"',
        )
    for name in ("JWT_SECRET", "DB_PASSWORD", "MAILJET_API_KEY", "MAILJET_API_SECRET"):
        ref = env.get(name, {}).get("valueFrom", {}).get("secretKeyRef")
        if ref:
            continue
        say(
            FAIL,
            f"{name} non arriva da Secret Manager" if name in env else f"manca il segreto {name}",
        )
    return (status.get("url") or "").rstrip("/") or None


def check_database(a) -> None:
    section(f"2. Database Cloud SQL «{a.sql}»")
    data, err = gcloud_json("sql", "instances", "describe", a.sql, f"--project={a.project}")
    if err:
        say(FAIL, f"istanza non leggibile ({err})")
        return
    say(OK if data.get("state") == "RUNNABLE" else FAIL, f"stato: {data.get('state')}")
    say(
        OK if data.get("databaseVersion") == "POSTGRES_16" else WARN,
        f"versione: {data.get('databaseVersion')}",
    )
    settings = data.get("settings", {})
    if settings.get("backupConfiguration", {}).get("enabled"):
        say(OK, "i backup automatici sono attivi")
    else:
        say(FAIL, "i backup automatici NON sono attivi")
    if a.env == "prod":
        say(
            OK
            if settings.get("backupConfiguration", {}).get("pointInTimeRecoveryEnabled")
            else WARN,
            "recupero a un istante preciso "
            + (
                "attivo"
                if settings.get("backupConfiguration", {}).get("pointInTimeRecoveryEnabled")
                else "NON attivo"
            ),
        )
        say(
            OK if settings.get("deletionProtectionEnabled") else FAIL,
            "protezione dall'eliminazione "
            + (
                "attiva"
                if settings.get("deletionProtectionEnabled")
                else "NON attiva in produzione"
            ),
        )
    backups, err = gcloud_json(
        "sql", "backups", "list", f"--instance={a.sql}", f"--project={a.project}"
    )
    if err:
        unreadable("elenco dei backup", err)
        return
    done = sorted(
        (b for b in backups if b.get("status") == "SUCCESSFUL"),
        key=lambda b: b.get("endTime", ""),
        reverse=True,
    )
    if not done:
        say(
            WARN,
            "nessun backup riuscito finora (normale solo nel primo giorno: i backup partono di notte)",
        )
    else:
        last = age(done[0].get("endTime"))
        if last and last < timedelta(hours=36):
            say(OK, f"ultimo backup riuscito: {human(last)}")
        else:
            say(
                WARN,
                f"l'ultimo backup riuscito è vecchio ({human(last) if last else 'data sconosciuta'})",
            )


def latest_execution(a, job: str):
    data, err = gcloud_json(
        "run",
        "jobs",
        "executions",
        "list",
        f"--job={job}",
        f"--project={a.project}",
        f"--region={a.region}",
    )
    if err:
        return None, err
    items = sorted(
        data or [], key=lambda e: e.get("metadata", {}).get("creationTimestamp", ""), reverse=True
    )
    return items, None


def succeeded(execution: dict) -> bool:
    status = execution.get("status", {})
    return (status.get("succeededCount") or 0) >= 1 and not status.get("failedCount")


def check_jobs(a) -> None:
    section("3. Lavori (migrazioni, dati iniziali, invio email)")
    for kind, text in (
        ("migrate", "migrazioni del database"),
        ("seed", "dati iniziali (listino e festività)"),
        ("mail", "invio delle email"),
    ):
        name = f"{a.prefix}-{kind}"
        data, err = gcloud_json(
            "run", "jobs", "describe", name, f"--project={a.project}", f"--region={a.region}"
        )
        if err:
            say(FAIL, f"lavoro «{name}» non leggibile ({err})")
            continue
        image = (
            data.get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("template", {})
            .get("spec", {})
            .get("containers")
            or [{}]
        )[0].get("image", "")
        if "cloudrun/container/hello" in image:
            say(WARN, f"«{kind}»: ha ancora l'immagine di esempio (si aggiorna al primo rilascio)")
        executions, err = latest_execution(a, name)
        if err:
            unreadable(f"esecuzioni di «{kind}»", err)
            continue
        if not executions:
            say(
                WARN if kind != "migrate" else FAIL,
                f"«{kind}» ({text}): mai eseguito"
                + (
                    " — lancia i dati iniziali una volta, vedi docs/deploy.md"
                    if kind == "seed"
                    else ""
                ),
            )
            continue
        ok_any = any(succeeded(e) for e in executions)
        last = executions[0]
        when = age(last.get("metadata", {}).get("creationTimestamp"))
        when_text = f" ({human(when)})" if when else ""
        if kind == "seed":
            say(
                OK if ok_any else FAIL,
                f"«seed»: "
                + (
                    "eseguito con successo almeno una volta"
                    if ok_any
                    else "tutte le esecuzioni sono fallite"
                ),
            )
        elif succeeded(last):
            if kind == "mail" and when and when > timedelta(minutes=15):
                say(
                    WARN,
                    f"«mail»: ultima esecuzione riuscita{when_text}, ma lo scheduler dovrebbe lanciarla ogni 5 minuti",
                )
            else:
                say(OK, f"«{kind}»: ultima esecuzione riuscita{when_text}")
        else:
            say(
                FAIL,
                f"«{kind}»: l'ultima esecuzione{when_text} NON è riuscita (log: Cloud Run → Lavori → {name} → Esecuzioni)",
            )


def check_scheduler(a) -> None:
    section("4. Pianificazione delle email")
    name = f"{a.prefix}-mail"
    data, err = gcloud_json(
        "scheduler", "jobs", "describe", name, f"--location={a.region}", f"--project={a.project}"
    )
    if err:
        say(FAIL, f"pianificazione «{name}» non leggibile ({err})")
        return
    say(OK if data.get("state") == "ENABLED" else FAIL, f"stato: {data.get('state')}")
    last = age(data.get("lastAttemptTime"))
    if last is None:
        say(WARN, "non ha ancora mai eseguito (attendi 5 minuti dopo l'apply)")
    elif last > timedelta(minutes=15):
        say(WARN, f"ultimo tentativo {human(last)}: dovrebbe essere ogni 5 minuti")
    else:
        code = (data.get("status") or {}).get("code", 0)
        say(
            OK if not code else FAIL,
            f"ultimo tentativo {human(last)}"
            + (
                ""
                if not code
                else f" con errore (codice {code}: {(data.get('status') or {}).get('message', '')})"
            ),
        )


def check_secrets(a) -> None:
    section("5. Segreti (solo esistenza, i valori non vengono letti)")
    for key, label in (
        ("jwt-secret", "chiave delle sessioni"),
        ("db-password", "password del database"),
        ("mailjet-api-key", "chiave Mailjet"),
        ("mailjet-api-secret", "segreto Mailjet"),
    ):
        name = f"{a.prefix}-{key}"
        versions, err = gcloud_json("secrets", "versions", "list", name, f"--project={a.project}")
        if err:
            say(FAIL, f"segreto «{name}» non leggibile ({err})")
            continue
        enabled = [v for v in versions if v.get("state") == "ENABLED"]
        if not enabled:
            say(FAIL, f"«{name}» ({label}): nessuna versione attiva")
        elif key.startswith("mailjet") and len(enabled) == 1:
            say(
                WARN,
                f"«{name}» ({label}): c'è una sola versione, probabilmente ancora il segnaposto «DA-IMPOSTARE» (vedi docs/deploy.md, passo 5)",
            )
        else:
            say(OK, f"«{name}» ({label}): {len(enabled)} versione/i attive")


def check_registry(a) -> None:
    section("6. Registro delle immagini")
    path = f"{a.region}-docker.pkg.dev/{a.project}/ce-portal"
    images, err = gcloud_json(
        "artifacts", "docker", "images", "list", path, "--include-tags", f"--project={a.project}"
    )
    if err:
        say(FAIL, f"registro «{path}» non leggibile ({err})")
        return
    tags = sorted({t for i in images for t in (i.get("tags") or [])})
    say(
        OK if images else WARN,
        f"{len(images)} immagini"
        + (
            f", etichette recenti: {', '.join(tags[-3:])}"
            if tags
            else " (nessuna: il primo rilascio le crea)"
        ),
    )


def api_get(url: str):
    code, token = run("gcloud", "auth", "print-access-token", "--quiet")
    if code != 0:
        return None, "token non ottenibile"
    code, out = run("curl", "-sS", "-m", "30", "-H", f"Authorization: Bearer {token.strip()}", url)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None, "risposta non leggibile"
    if isinstance(data, dict) and data.get("error"):
        return None, data["error"].get("message", "errore dell'API")
    return data, None


def check_monitoring(a) -> None:
    section("7. Monitoraggio e avvisi")
    base = f"https://monitoring.googleapis.com/v3/projects/{a.project}"
    uptime, err = api_get(f"{base}/uptimeCheckConfigs")
    if err:
        unreadable("controllo di raggiungibilità", err)
    else:
        say(
            OK if uptime.get("uptimeCheckConfigs") else FAIL,
            "controllo di raggiungibilità "
            + ("presente" if uptime.get("uptimeCheckConfigs") else "ASSENTE"),
        )
    policies, err = api_get(f"{base}/alertPolicies")
    if err:
        unreadable("avvisi", err)
        return
    items = [p for p in policies.get("alertPolicies", []) if p.get("enabled", True)]
    say(
        OK if len(items) >= 3 else WARN,
        f"{len(items)} avvisi attivi (attesi 3: non raggiungibile, errori 5xx, lavoro fallito)",
    )
    if items and not any(p.get("notificationChannels") for p in items):
        say(
            WARN,
            "gli avvisi non hanno nessun destinatario (alert_email in terraform.tfvars): scatterebbero senza avvisare nessuno",
        )


def check_smoke(a, url: str | None) -> None:
    section("8. Prova di fumo sul servizio pubblicato")
    if a.no_smoke:
        say(WARN, "saltata (--no-smoke)")
        return
    if not url:
        say(WARN, "saltata: l'indirizzo del servizio non è noto")
        return
    cmd = ["bash", a.smoke_script, url] + (["--prod"] if a.env == "prod" else [])
    code, out = run(*cmd, timeout=240, merge=True)
    last = [line for line in out.strip().splitlines() if line.strip()][-1:] or [""]
    if code == 0:
        say(
            OK,
            f"{url}: tutti i controlli superati (frontend, intestazioni di sicurezza, API protetta)",
        )
    else:
        say(FAIL, f"{url}: {last[0].strip()}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--project", required=True, help="ID del progetto Google Cloud")
    ap.add_argument("--env", required=True, choices=["test", "prod"])
    ap.add_argument("--region", default="europe-west8")
    ap.add_argument(
        "--no-smoke", action="store_true", help="salta la prova sul servizio pubblicato"
    )
    ap.add_argument("--smoke-script", default=str(Path(__file__).with_name("smoke.sh")))
    a = ap.parse_args()
    a.prefix = f"ce-portal-{a.env}"
    a.service = a.prefix
    a.sql = f"{a.prefix}-db"

    print(f"Collaudo dell'ambiente «{a.env}» · progetto {a.project} · regione {a.region}")
    url = check_service(a)
    check_database(a)
    check_jobs(a)
    check_scheduler(a)
    check_secrets(a)
    check_registry(a)
    check_monitoring(a)
    check_smoke(a, url)

    counts = {level: sum(1 for lv, _ in results if lv == level) for level in (OK, WARN, FAIL)}
    print(f"\nRiepilogo: {counts[OK]} {OK} · {counts[WARN]} {WARN} · {counts[FAIL]} {FAIL}")
    if counts[FAIL]:
        print("Da correggere (✘):")
        for level, text in results:
            if level == FAIL:
                print(f"  - {text}")
    return 1 if counts[FAIL] else 0


if __name__ == "__main__":
    sys.exit(main())
