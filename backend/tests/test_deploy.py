"""Esecuzione su Cloud Run: database via socket, frontend servito dal backend, intestazioni di sicurezza,
log strutturati, configurazione pubblica."""

import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.logging_config import JsonFormatter, configure_logging
from app.main import create_app
from tests.helpers import TEST_SETTINGS


def settings(**over) -> Settings:
    base = dict(_env_file=None, app_env="local", mail_backend="console")
    base.update(over)
    return Settings(**base)


PROD = dict(
    app_env="prod", jwt_secret="p" * 48, google_oauth_client_id="abc.apps.googleusercontent.com"
)


# ------------------------------------------------------------------ indirizzo del database
class TestDatabaseUrl:
    def test_without_cloud_sql_the_configured_url_is_used(self):
        s = settings(database_url="postgresql+psycopg://a:b@host:5432/db")
        assert s.effective_database_url == "postgresql+psycopg://a:b@host:5432/db"

    def test_cloud_sql_is_reached_through_the_socket(self):
        s = settings(
            cloudsql_instance="prog:europe-west8:ist",
            db_user="ceportal",
            db_password="segreto",
            db_name="ceportal",
        )
        url = make_url(s.effective_database_url)
        assert (url.drivername, url.username, url.password, url.database) == (
            "postgresql+psycopg",
            "ceportal",
            "segreto",
            "ceportal",
        )
        assert url.host is None and url.query["host"] == "/cloudsql/prog:europe-west8:ist"

    @pytest.mark.parametrize(
        "password", ["p@ss:w/ord", "100%#?&=", "con spazi e àccènti", "a" * 64]
    )
    def test_special_characters_in_the_password_survive(self, password):
        s = settings(cloudsql_instance="p:r:i", db_user="u", db_password=password)
        assert make_url(s.effective_database_url).password == password

    @pytest.mark.parametrize("missing", [{"db_user": "u"}, {"db_password": "x"}, {}])
    def test_cloud_sql_requires_user_and_password(self, missing):
        with pytest.raises(ValidationError, match="DB_USER e DB_PASSWORD"):
            settings(cloudsql_instance="p:r:i", **missing)

    def test_the_engine_and_migrations_use_the_effective_url(self):
        import inspect

        import app.db.session as session_module

        assert "effective_database_url" in inspect.getsource(session_module)
        env = (
            __import__("pathlib").Path(__file__).resolve().parents[1] / "migrations" / "env.py"
        ).read_text()
        assert "effective_database_url" in env


# ------------------------------------------------------------------ configurazione pubblica
class TestPublicConfig:
    def test_local_offers_the_simulated_login(self):
        body = TestClient(create_app(settings())).get("/api/v1/config").json()
        assert body == {"google_client_id": None, "dev_login": True}

    def test_production_never_offers_it_and_exposes_only_the_public_client_id(self):
        client = TestClient(create_app(settings(**PROD, mail_backend="console")))
        assert client.get("/api/v1/config").json() == {
            "google_client_id": "abc.apps.googleusercontent.com",
            "dev_login": False,
        }
        assert (
            client.post("/api/v1/auth/dev-login", json={"email": "a@huware.com"}).status_code == 404
        )

    @pytest.mark.parametrize("env", ["test", "prod"])
    def test_the_simulated_login_exists_only_in_local(self, env):
        extra = {**PROD, "app_env": env}
        assert (
            TestClient(create_app(settings(**extra))).get("/api/v1/config").json()["dev_login"]
            is False
        )

    def test_it_needs_no_token_and_leaks_no_secrets(self):
        text = TestClient(create_app(settings(**PROD))).get("/api/v1/config").text
        for secret in ("p" * 48, "jwt", "mailjet", "database"):
            assert secret not in text


# ------------------------------------------------------------------ frontend servito dal backend
@pytest.fixture
def site(tmp_path):
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "brand").mkdir()
    (root / "index.html").write_text(
        '<!doctype html><div id="root"></div><script type="module" src="/assets/app-abc123.js"></script>'
    )
    (root / "assets" / "app-abc123.js").write_text("console.log('ok')")
    (root / "assets" / "font-abc.woff2").write_bytes(b"wOF2")
    (root / "brand" / "logo.png").write_bytes(b"\x89PNG")
    (tmp_path / "segreto.txt").write_text("NON DEVE USCIRE")
    return TestClient(create_app(settings(static_dir=str(root))))


class TestFrontend:
    def test_the_home_and_every_application_page_return_index_html_without_cache(self, site):
        for path in ("/", "/login", "/ce/123", "/admin/utenti", "/dashboard/portfolio"):
            r = site.get(path)
            assert r.status_code == 200 and '<div id="root">' in r.text, path
            assert r.headers["cache-control"] == "no-cache"
            assert r.headers["content-type"].startswith("text/html")

    def test_hashed_assets_are_cached_for_a_year(self, site):
        r = site.get("/assets/app-abc123.js")
        assert (
            r.status_code == 200
            and r.headers["cache-control"] == "public, max-age=31536000, immutable"
        )
        assert "javascript" in r.headers["content-type"]
        assert site.get("/assets/font-abc.woff2").headers["content-type"] == "font/woff2"

    def test_other_files_get_a_short_cache(self, site):
        r = site.get("/brand/logo.png")
        assert r.status_code == 200 and r.headers["cache-control"] == "public, max-age=3600"

    def test_a_missing_file_is_a_404_not_the_application_page(self, site):
        for path in ("/assets/nope.js", "/brand/nope.png", "/favicon.ico"):
            r = site.get(path)
            assert r.status_code == 404 and r.headers["content-type"].startswith(
                "application/json"
            ), path

    def test_the_api_stays_json_and_unknown_api_paths_are_json_404(self, site):
        assert site.get("/api/v1/health").json() == {"status": "ok"}
        for path in ("/api/v1/inesistente", "/api", "/api/"):
            r = site.get(path)
            assert r.status_code == 404 and r.json() == {"detail": "Non trovato"}, path

    @pytest.mark.parametrize(
        "path",
        [
            "/../segreto.txt",
            "/%2e%2e/segreto.txt",
            "/..%2fsegreto.txt",
            "/assets/../../segreto.txt",
            "/%2e%2e%2fsegreto.txt",
            "//etc/passwd",
            "/assets/..%5c..%5csegreto.txt",
        ],
    )
    def test_files_outside_the_folder_are_never_served(self, site, path):
        r = site.get(path)
        assert "NON DEVE USCIRE" not in r.text and "root:" not in r.text
        assert r.status_code in (200, 404)  # 200 = la pagina dell'applicazione, mai il file

    def test_head_requests_work(self, site):
        assert site.head("/").status_code == 200
        assert site.head("/assets/app-abc123.js").status_code == 200

    def test_a_folder_without_the_frontend_stops_the_start(self, tmp_path):
        with pytest.raises(RuntimeError, match="manca"):
            create_app(settings(static_dir=str(tmp_path)))

    def test_without_static_dir_nothing_changes(self):
        client = TestClient(create_app(settings()))
        assert (
            client.get("/").status_code == 404 and client.get("/api/v1/health").status_code == 200
        )

    def test_production_does_not_publish_the_interactive_docs(self, tmp_path):
        client = TestClient(create_app(settings(**PROD)))
        assert (
            client.get("/docs").status_code == 404
            and client.get("/api/v1/openapi.json").status_code == 404
        )
        assert TestClient(create_app(settings())).get("/docs").status_code == 200  # in sviluppo sì


# ------------------------------------------------------------------ intestazioni di sicurezza
class TestSecurityHeaders:
    def test_every_response_gets_the_basic_headers(self, site):
        for path in ("/", "/api/v1/health", "/assets/app-abc123.js", "/inesistente.png"):
            h = site.get(path).headers
            assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY", path
            assert h["referrer-policy"] == "strict-origin-when-cross-origin"
            assert "camera=()" in h["permissions-policy"]

    def test_the_content_security_policy_allows_only_self_and_google_sign_in(self, site):
        csp = site.get("/").headers["content-security-policy"]
        assert (
            "default-src 'self'" in csp
            and "frame-ancestors 'none'" in csp
            and "object-src 'none'" in csp
        )
        assert "script-src 'self' https://accounts.google.com/gsi/client" in csp
        assert "'unsafe-eval'" not in csp and "script-src 'self' 'unsafe-inline'" not in csp
        assert "http://" not in csp and "*" not in csp.replace(
            "https://*.googleusercontent.com", ""
        )
        assert "fonts.googleapis.com" not in csp  # il font è incluso nel portale

    def test_api_responses_are_never_cached_but_explicit_choices_are_respected(self, site):
        assert site.get("/api/v1/health").headers["cache-control"] == "no-store"
        assert site.get("/").headers["cache-control"] == "no-cache"  # non toccato dal middleware

    def test_hsts_only_outside_local_development(self):
        assert (
            "strict-transport-security"
            not in TestClient(create_app(settings())).get("/api/v1/health").headers
        )
        prod = TestClient(create_app(settings(**PROD))).get("/api/v1/health").headers
        assert prod["strict-transport-security"] == "max-age=31536000; includeSubDomains"

    def test_the_api_docs_page_keeps_working_in_development(self):
        r = TestClient(create_app(settings())).get("/docs")
        assert (
            r.status_code == 200 and "content-security-policy" not in r.headers
        )  # carica script da un CDN


# ------------------------------------------------------------------ log
class TestLogging:
    def record(self, msg="ciao %s", args=("mondo",), level=logging.WARNING, exc_info=None):
        return logging.LogRecord("ce_portal", level, __file__, 1, msg, args, exc_info)

    def test_each_line_is_json_with_severity_and_message(self):
        out = json.loads(JsonFormatter().format(self.record()))
        assert out == {"severity": "WARNING", "message": "ciao mondo", "logger": "ce_portal"}

    def test_accents_stay_readable_and_exceptions_are_included(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys

            line = JsonFormatter().format(
                self.record("Errore è àccentato", (), logging.ERROR, sys.exc_info())
            )
        out = json.loads(line)
        assert (
            "è àccentato" in line
            and out["severity"] == "ERROR"
            and "ValueError: boom" in out["exception"]
        )

    def test_production_logs_through_one_json_handler_and_development_is_untouched(self):
        root, saved = (
            logging.getLogger(),
            (logging.getLogger().handlers[:], logging.getLogger().level),
        )
        uvicorn_saved = {
            n: (logging.getLogger(n).handlers[:], logging.getLogger(n).propagate)
            for n in ("uvicorn", "uvicorn.access")
        }
        try:
            configure_logging(settings())  # locale: non cambia nulla
            assert root.handlers == saved[0]
            configure_logging(settings(**PROD))
            assert len(root.handlers) == 1 and isinstance(root.handlers[0].formatter, JsonFormatter)
            assert (
                logging.getLogger("uvicorn.access").propagate
                and logging.getLogger("uvicorn.access").handlers == []
            )
        finally:
            root.handlers, root.level = saved
            for n, (h, p) in uvicorn_saved.items():
                logging.getLogger(n).handlers, logging.getLogger(n).propagate = h, p


def test_the_shared_test_settings_still_build_a_working_app():
    assert TestClient(create_app(TEST_SETTINGS)).get("/api/v1/health").status_code == 200
