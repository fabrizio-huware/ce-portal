from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

import app.models  # noqa: F401
from app.db.base import Base
from tests.conftest import alembic_config

EXPECTED_TABLES = {
    "audit_log",
    "ce",
    "ce_line_allocations",
    "ce_lines",
    "ce_milestones",
    "ce_phases",
    "ce_version_rates",
    "ce_versions",
    "clients",
    "email_outbox",
    "employees",
    "non_working_days",
    "profile_rates",
    "profiles",
    "users",
}


def test_upgrade_creates_all_tables(engine):
    tables = set(inspect(engine).get_table_names())
    assert tables == EXPECTED_TABLES | {"alembic_version"}


def test_trigram_extension_installed(engine):
    with engine.connect() as conn:
        found = conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")).scalar()
    assert found == 1


def test_models_and_migration_are_in_sync(engine):
    """Se i modelli cambiano senza una migrazione, questo test fallisce."""
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == []


def test_downgrade_then_upgrade_roundtrip(engine):
    cfg = alembic_config()
    command.downgrade(cfg, "base")
    assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    command.upgrade(cfg, "head")
    assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES | {"alembic_version"}
