import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

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
