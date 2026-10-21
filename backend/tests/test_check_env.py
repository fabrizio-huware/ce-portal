"""Lo strumento di collaudo (infra/scripts/check_env.py) provato con gcloud e curl simulati."""

import copy
import json
import os
import stat
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "infra" / "scripts" / "check_env.py"

FAKE_GCLOUD = """#!{python}
import json, os, sys
fixtures = json.load(open(os.environ["FAKE_FIXTURES"]))
args = sys.argv[1:]
sig = " ".join([a for a in args if not a.startswith("--")] + [a.split("=", 1)[1] for a in args if a.startswith(("--job=", "--instance="))])
if sig == "auth print-access-token":
    print("token-finto"); sys.exit(0)
if sig not in fixtures or fixtures[sig] is None:
    print("ERROR: (gcloud) simulato: non disponibile", file=sys.stderr); sys.exit(1)
print(json.dumps(fixtures[sig]))
"""
FAKE_CURL = """#!{python}
import json, os, sys
fixtures = json.load(open(os.environ["FAKE_FIXTURES"]))
url = sys.argv[-1]
for key in ("uptimeCheckConfigs", "alertPolicies"):
    if key in url:
        value = fixtures.get("curl " + key)
        print(json.dumps(value if value is not None else {"error": {"message": "permesso negato"}}))
        sys.exit(0)
print("{}")
"""


def iso(minutes_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes_ago)).isoformat().replace("+00:00", "Z")


def healthy(env: str = "test") -> dict:
    prefix = f"ce-portal-{env}"
    secret_env = [
        {"name": n, "valueFrom": {"secretKeyRef": {"name": f"{prefix}-{k}", "key": "latest"}}}
        for n, k in (
            ("JWT_SECRET", "jwt-secret"),
            ("DB_PASSWORD", "db-password"),
            ("MAILJET_API_KEY", "mailjet-api-key"),
            ("MAILJET_API_SECRET", "mailjet-api-secret"),
        )
    ]
    plain = {
        "APP_ENV": env,
        "CLOUDSQL_INSTANCE": "p:europe-west8:db",
        "DB_USER": "ceportal",
        "DB_NAME": "ceportal",
        "PUBLIC_BASE_URL": "https://x.run.app",
        "MAIL_BACKEND": "mailjet",
        "GOOGLE_OAUTH_CLIENT_ID": "1-a.apps.googleusercontent.com",
        "BOOTSTRAP_ADMIN_EMAIL": "admin@huware.com",
        "S2S_AUDIENCES": "https://x.run.app",
    }
    image = "europe-west8-docker.pkg.dev/p/ce-portal/ce-portal:abc123def456"
    run_ok = [{"metadata": {"creationTimestamp": iso(3)}, "status": {"succeededCount": 1}}]
    f = {
        f"run services describe {prefix}": {
            "status": {
                "conditions": [{"type": "Ready", "status": "True"}],
                "latestReadyRevisionName": "r-2",
                "latestCreatedRevisionName": "r-2",
                "url": "https://x.run.app",
                "traffic": [{"latestRevision": True, "percent": 100}],
            },
            "spec": {
                "template": {
                    "spec": {
                        "containers": [
                            {
                                "image": image,
                                "env": [{"name": k, "value": v} for k, v in plain.items()]
                                + secret_env,
                            }
                        ]
                    }
                }
            },
        },
        f"sql instances describe {prefix}-db": {
            "state": "RUNNABLE",
            "databaseVersion": "POSTGRES_16",
            "settings": {
                "backupConfiguration": {"enabled": True, "pointInTimeRecoveryEnabled": True},
                "deletionProtectionEnabled": True,
            },
        },
        f"sql backups list {prefix}-db": [{"status": "SUCCESSFUL", "endTime": iso(60 * 5)}],
        f"scheduler jobs describe {prefix}-mail": {
            "state": "ENABLED",
            "lastAttemptTime": iso(2),
            "status": {},
        },
        "artifacts docker images list europe-west8-docker.pkg.dev/p/ce-portal": [
            {"tags": ["abc123def456"]}
        ],
        "curl uptimeCheckConfigs": {"uptimeCheckConfigs": [{"name": "u"}]},
        "curl alertPolicies": {
            "alertPolicies": [{"enabled": True, "notificationChannels": ["c"]}] * 3
        },
    }
    for kind in ("migrate", "seed", "mail"):
        f[f"run jobs describe {prefix}-{kind}"] = {
            "spec": {
                "template": {"spec": {"template": {"spec": {"containers": [{"image": image}]}}}}
            }
        }
        f[f"run jobs executions list {prefix}-{kind}"] = run_ok
    for key in ("jwt-secret", "db-password", "mailjet-api-key", "mailjet-api-secret"):
        f[f"secrets versions list {prefix}-{key}"] = [
            {"state": "ENABLED", "name": "v1"},
            {"state": "ENABLED", "name": "v2"},
        ]
    return f


def set_env(f: dict, env: str, name: str, value):
    key = f"run services describe ce-portal-{env}"
    containers = f[key]["spec"]["template"]["spec"]["containers"][0]
    containers["env"] = [e for e in containers["env"] if e["name"] != name]
    if value is not None:
        containers["env"].append({"name": name, "value": value})


@pytest.fixture
def run_check(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("gcloud", FAKE_GCLOUD), ("curl", FAKE_CURL)):
        path = bin_dir / name
        path.write_text(body.replace("{python}", sys.executable))
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    ok = tmp_path / "smoke_ok.sh"
    ok.write_text("#!/usr/bin/env bash\necho 'Tutti i controlli superati su '$1\n")
    bad = tmp_path / "smoke_bad.sh"
    bad.write_text(
        "#!/usr/bin/env bash\necho 'ERRORE: l accesso simulato è attivo in produzione' >&2\nexit 1\n"
    )

    def go(fixtures: dict, env: str = "test", smoke: str = "ok", extra: tuple[str, ...] = ()):
        (tmp_path / "fx.json").write_text(json.dumps(fixtures))
        smoke_path = {"ok": ok, "bad": bad}[smoke]
        p = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--project",
                "p",
                "--env",
                env,
                "--smoke-script",
                str(smoke_path),
                *extra,
            ],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "FAKE_FIXTURES": str(tmp_path / "fx.json"),
            },
        )
        return p.returncode, p.stdout, p.stderr

    return go


def fails(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.strip().startswith("✘")]


def warns(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.strip().startswith("⚠")]


class TestHealthy:
    @pytest.mark.parametrize("env", ["test", "prod"])
    def test_a_correct_environment_has_no_errors(self, run_check, env):
        code, out, err = run_check(healthy(env), env)
        assert code == 0 and not fails(out) and not err, out
        assert "Riepilogo:" in out and "✔" in out
        for section in (
            "1. Servizio",
            "2. Database",
            "3. Lavori",
            "4. Pianificazione",
            "5. Segreti",
            "6. Registro",
            "7. Monitoraggio",
            "8. Prova di fumo",
        ):
            assert section in out

    def test_secret_values_are_never_printed(self, run_check):
        f = healthy()
        f["secrets versions list ce-portal-test-jwt-secret"] = [
            {"state": "ENABLED", "payload": {"data": "SEGRETO-DA-NON-STAMPARE"}}
        ]
        _, out, _ = run_check(f)
        assert "SEGRETO-DA-NON-STAMPARE" not in out


class TestJustAfterTerraformApply:
    def fresh(self):
        f = healthy()
        f["run services describe ce-portal-test"]["spec"]["template"]["spec"]["containers"][0][
            "image"
        ] = "us-docker.pkg.dev/cloudrun/container/hello"
        for kind in ("migrate", "seed", "mail"):
            f[f"run jobs executions list ce-portal-test-{kind}"] = []
        f["sql backups list ce-portal-test-db"] = []
        f["artifacts docker images list europe-west8-docker.pkg.dev/p/ce-portal"] = []
        for key in ("mailjet-api-key", "mailjet-api-secret"):
            f[f"secrets versions list ce-portal-test-{key}"] = [{"state": "ENABLED"}]
        return f

    def test_it_says_what_is_missing_in_plain_words(self, run_check):
        code, out, _ = run_check(self.fresh(), smoke="bad")
        assert code == 1
        text = "\n".join(fails(out))
        assert "immagine di esempio" in text and "migrate" in text
        warn_text = "\n".join(warns(out))
        assert "seed" in warn_text and "docs/deploy.md" in warn_text
        assert "segnaposto" in warn_text and "backup" in warn_text.lower()


class TestServiceConfiguration:
    def test_missing_google_client_id_is_an_error(self, run_check):
        f = healthy()
        set_env(f, "test", "GOOGLE_OAUTH_CLIENT_ID", None)
        code, out, _ = run_check(f)
        assert code == 1 and any("GOOGLE_OAUTH_CLIENT_ID" in line for line in fails(out))

    def test_missing_s2s_audiences_is_only_a_warning(self, run_check):
        f = healthy()
        set_env(f, "test", "S2S_AUDIENCES", None)
        code, out, _ = run_check(f)
        assert code == 0 and any("S2S_AUDIENCES" in line for line in warns(out))

    def test_non_https_s2s_audience_is_an_error(self, run_check):
        f = healthy()
        set_env(f, "test", "S2S_AUDIENCES", "https://x.run.app,http://x.run.app")
        code, out, _ = run_check(f)
        assert code == 1 and any("S2S_AUDIENCES" in line for line in fails(out))

    def test_console_mail_is_only_a_warning_in_test_but_an_error_in_production(self, run_check):
        f = healthy()
        set_env(f, "test", "MAIL_BACKEND", "console")
        code, out, _ = run_check(f)
        assert code == 0 and any("NON vengono inviate" in w for w in warns(out))
        g = healthy("prod")
        set_env(g, "prod", "MAIL_BACKEND", "console")
        code, out, _ = run_check(g, "prod")
        assert code == 1 and any("non verrebbero inviate" in line for line in fails(out))

    def test_wrong_app_env_is_an_error(self, run_check):
        f = healthy("prod")
        set_env(f, "prod", "APP_ENV", "test")
        code, out, _ = run_check(f, "prod")
        assert code == 1 and any("APP_ENV" in line for line in fails(out))

    def test_a_secret_set_as_plain_text_is_an_error(self, run_check):
        f = healthy()
        containers = f["run services describe ce-portal-test"]["spec"]["template"]["spec"][
            "containers"
        ][0]
        containers["env"] = [e for e in containers["env"] if e["name"] != "JWT_SECRET"] + [
            {"name": "JWT_SECRET", "value": "in-chiaro"}
        ]
        code, out, _ = run_check(f)
        assert code == 1 and any(
            "JWT_SECRET non arriva da Secret Manager" in line for line in fails(out)
        )

    def test_a_service_that_is_not_ready_is_an_error_with_the_reason(self, run_check):
        f = healthy()
        f["run services describe ce-portal-test"]["status"]["conditions"] = [
            {"type": "Ready", "status": "False", "message": "Container failed to start"}
        ]
        code, out, _ = run_check(f)
        assert code == 1 and any(
            "non è pronto" in line and "Container failed to start" in line for line in fails(out)
        )

    def test_traffic_not_on_the_latest_revision_is_a_warning(self, run_check):
        f = healthy()
        f["run services describe ce-portal-test"]["status"]["traffic"] = [
            {"revisionName": "r-1", "percent": 100}
        ]
        code, out, _ = run_check(f)
        assert code == 0 and any("traffico" in w for w in warns(out))

    def test_a_failed_rollout_is_flagged(self, run_check):
        f = healthy()
        f["run services describe ce-portal-test"]["status"]["latestCreatedRevisionName"] = "r-3"
        _, out, _ = run_check(f)
        assert any("r-3" in w for w in warns(out))


class TestResilience:
    def test_a_missing_service_does_not_stop_the_other_checks(self, run_check):
        f = healthy()
        del f["run services describe ce-portal-test"]
        code, out, err = run_check(f)
        assert code == 1 and "Traceback" not in err
        assert any("terraform apply" in line for line in fails(out))
        assert "2. Database" in out and "5. Segreti" in out and "saltata: l'indirizzo" in out

    def test_missing_permissions_give_a_message_not_a_crash(self, run_check):
        f = healthy()
        f["sql instances describe ce-portal-test-db"] = None
        f["curl alertPolicies"] = None
        code, out, err = run_check(f)
        assert code == 1 and "Traceback" not in err
        assert any("istanza non leggibile" in line for line in fails(out))
        assert any("avvisi: non verificabile" in w for w in warns(out))


class TestDatabase:
    def test_backups_off_is_an_error_and_an_old_backup_a_warning(self, run_check):
        f = healthy()
        f["sql instances describe ce-portal-test-db"]["settings"]["backupConfiguration"][
            "enabled"
        ] = False
        code, out, _ = run_check(f)
        assert code == 1 and any("backup automatici NON sono attivi" in line for line in fails(out))
        g = healthy()
        g["sql backups list ce-portal-test-db"] = [
            {"status": "SUCCESSFUL", "endTime": iso(60 * 24 * 3)}
        ]
        code, out, _ = run_check(g)
        assert code == 0 and any("vecchio" in w for w in warns(out))

    def test_production_without_deletion_protection_is_an_error(self, run_check):
        f = healthy("prod")
        f["sql instances describe ce-portal-prod-db"]["settings"]["deletionProtectionEnabled"] = (
            False
        )
        code, out, _ = run_check(f, "prod")
        assert code == 1 and any("protezione dall'eliminazione" in line for line in fails(out))

    def test_stopped_database_is_an_error(self, run_check):
        f = healthy()
        f["sql instances describe ce-portal-test-db"]["state"] = "SUSPENDED"
        code, out, _ = run_check(f)
        assert code == 1 and any("SUSPENDED" in line for line in fails(out))


class TestJobsAndScheduler:
    def test_failed_migration_is_an_error(self, run_check):
        f = healthy()
        f["run jobs executions list ce-portal-test-migrate"] = [
            {"metadata": {"creationTimestamp": iso(5)}, "status": {"failedCount": 1}}
        ]
        code, out, _ = run_check(f)
        assert code == 1 and any(
            "migrate" in line and "NON è riuscita" in line for line in fails(out)
        )

    def test_seed_that_failed_once_but_succeeded_later_is_fine(self, run_check):
        f = healthy()
        f["run jobs executions list ce-portal-test-seed"] = [
            {"metadata": {"creationTimestamp": iso(10)}, "status": {"succeededCount": 1}},
            {"metadata": {"creationTimestamp": iso(60)}, "status": {"failedCount": 1}},
        ]
        code, out, _ = run_check(f)
        assert code == 0 and not fails(out)

    def test_stale_mail_job_and_paused_scheduler(self, run_check):
        f = healthy()
        f["run jobs executions list ce-portal-test-mail"] = [
            {"metadata": {"creationTimestamp": iso(120)}, "status": {"succeededCount": 1}}
        ]
        _, out, _ = run_check(f)
        assert any("ogni 5 minuti" in w for w in warns(out))
        g = healthy()
        g["scheduler jobs describe ce-portal-test-mail"]["state"] = "PAUSED"
        code, out, _ = run_check(g)
        assert code == 1 and any("PAUSED" in line for line in fails(out))

    def test_scheduler_error_code_is_reported(self, run_check):
        f = healthy()
        f["scheduler jobs describe ce-portal-test-mail"]["status"] = {
            "code": 7,
            "message": "PERMISSION_DENIED",
        }
        code, out, _ = run_check(f)
        assert code == 1 and any("PERMISSION_DENIED" in line for line in fails(out))


class TestMonitoringAndSmoke:
    def test_alerts_without_recipients_are_a_warning(self, run_check):
        f = healthy()
        f["curl alertPolicies"] = {
            "alertPolicies": [{"enabled": True, "notificationChannels": []}] * 3
        }
        code, out, _ = run_check(f)
        assert code == 0 and any("nessun destinatario" in w for w in warns(out))

    def test_missing_uptime_check_is_an_error(self, run_check):
        f = healthy()
        f["curl uptimeCheckConfigs"] = {}
        code, out, _ = run_check(f)
        assert code == 1 and any("ASSENTE" in line for line in fails(out))

    def test_failed_smoke_is_an_error_with_the_reason(self, run_check):
        code, out, _ = run_check(healthy("prod"), "prod", smoke="bad")
        assert code == 1 and any("accesso simulato" in line for line in fails(out))

    def test_smoke_can_be_skipped(self, run_check):
        code, out, _ = run_check(healthy(), extra=("--no-smoke",))
        assert code == 0 and any("saltata" in w for w in warns(out))


def test_the_input_is_never_modified_and_runs_are_independent(run_check):
    f = healthy()
    snapshot = copy.deepcopy(f)
    run_check(f)
    assert f == snapshot
