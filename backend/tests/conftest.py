import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.google import GoogleIdentity, InvalidGoogleTokenError, get_google_verifier
from app.db.session import get_session
from app.main import create_app
from tests.helpers import TEST_SETTINGS

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://ceportal:ceportal@localhost:5432/ceportal_test"
)


def alembic_config(url: str = TEST_DATABASE_URL) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """Database PostgreSQL di test, ricreato da zero applicando le migrazioni."""
    eng = create_engine(TEST_DATABASE_URL)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except OperationalError:
        pytest.skip("PostgreSQL di test non raggiungibile (imposta TEST_DATABASE_URL)")
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(), "head")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    """Sessione che annulla tutto a fine test (rollback)."""
    connection = engine.connect()
    transaction = connection.begin()
    sess = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield sess
    sess.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def app(session: Session):
    """Applicazione con database di test (rollback a fine test) e impostazioni di test."""
    application = create_app(TEST_SETTINGS)

    def fresh_session():
        # In produzione ogni richiesta ha una sessione propria. Qui la sessione è condivisa, quindi:
        # prima della richiesta lo stato preparato dal test diventa "salvato" e la cache si svuota;
        # dopo, tutto ciò che la richiesta non ha confermato viene annullato (come alla chiusura).
        session.commit()
        session.expire_all()
        try:
            yield session
        finally:
            session.rollback()

    application.dependency_overrides[get_session] = fresh_session
    application.dependency_overrides[get_settings] = lambda: TEST_SETTINGS
    return application


@pytest.fixture
def api(app) -> TestClient:
    return TestClient(app)


class FakeGoogle:
    """Verificatore Google simulato: imposta `identity` oppure `fail = True`."""

    def __init__(self) -> None:
        self.identity: GoogleIdentity | None = None
        self.fail = False

    def __call__(self, token: str) -> GoogleIdentity:
        if self.fail or self.identity is None:
            raise InvalidGoogleTokenError("token non valido")
        return self.identity


@pytest.fixture
def google(app) -> FakeGoogle:
    fake = FakeGoogle()
    app.dependency_overrides[get_google_verifier] = lambda: fake
    return fake


@pytest.fixture
def env(session):
    """Utenti dei tre ruoli, un cliente e il listino 2026 del foglio reale."""
    from tests.ce_helpers import make_env

    return make_env(session)


# ------------------------------------------------------------------ email
class RecordingMailer:
    """Registra le email "inviate". `behavior` permette di simulare errori (temporanei o definitivi)."""

    def __init__(self) -> None:
        self.calls: list[list] = []
        self.behavior = None  # funzione (emails) -> list[SendOutcome] oppure solleva un'eccezione

    @property
    def sent(self) -> list:
        return [email for call in self.calls for email in call]

    def send(self, emails):
        from app.notifications.mailer import SendOutcome

        self.calls.append(list(emails))
        if self.behavior:
            return self.behavior(emails)
        return [SendOutcome(ok=True, provider_id=f"rec-{len(self.sent)}") for _ in emails]


@pytest.fixture
def mailer(app) -> RecordingMailer:
    """Sostituisce Mailjet: tutte le email del test finiscono qui."""
    from app.notifications.deps import get_mailer

    recorder = RecordingMailer()
    app.dependency_overrides[get_mailer] = lambda: recorder
    return recorder


@pytest.fixture
def mailjet():
    """Un finto Mailjet in ascolto su una porta locale."""
    from tests.fake_mailjet import FakeMailjet

    server = FakeMailjet().start()
    yield server
    server.stop()
