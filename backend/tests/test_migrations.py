import pytest
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
    "ce_version_months",
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


# ------------------------------------------------------------------ migrazione 0002 con dati veri
def _insert_legacy_ce(conn, *, external_line: bool) -> dict:
    """Un CE come lo avrebbe salvato lo schema 0001 (prima dei servizi esterni come profilo)."""
    q = lambda sql, **p: conn.execute(text(sql), p).scalar()  # noqa: E731
    user = q(
        "INSERT INTO users (email, full_name, role) VALUES ('legacy@huware.com', 'L', 'admin') RETURNING id"
    )
    client = q("INSERT INTO clients (name) VALUES ('Legacy') RETURNING id")
    profile = q("INSERT INTO profiles (name) VALUES ('Senior') RETURNING id")
    ce = q("INSERT INTO ce (code, created_by) VALUES ('LEG-1', :u) RETURNING id", u=user)
    version = q(
        "INSERT INTO ce_versions (ce_id, version_number, status, client_id, project_name, start_date, "
        "end_date, planning_mode, rate_year, created_by) VALUES (:ce, 1, 'draft', :c, 'P', "
        "'2026-01-01', '2026-03-31', 'hours', 2026, :u) RETURNING id",
        ce=ce,
        c=client,
        u=user,
    )
    phase = q(
        "INSERT INTO ce_phases (version_id, position, name) VALUES (:v, 0, 'F') RETURNING id",
        v=version,
    )
    q(
        "INSERT INTO ce_lines (phase_id, position, line_type, activity, profile_id, hours) "
        "VALUES (:p, 0, 'internal', 'Analisi', :pr, 16) RETURNING id",
        p=phase,
        pr=profile,
    )
    if external_line:
        q(
            "INSERT INTO ce_lines (phase_id, position, line_type, activity, external_cost, external_revenue) "
            "VALUES (:p, 1, 'external', 'Licenze', 100, 150) RETURNING id",
            p=phase,
        )
    return {"version": version}


def _purge_legacy(engine) -> None:
    with engine.begin() as conn:
        for table in ("ce_lines", "ce_phases", "ce_versions", "ce", "profiles", "clients", "users"):
            conn.execute(text(f"DELETE FROM {table}"))


def test_upgrade_0002_preserves_existing_data_and_sets_defaults(engine):
    cfg = alembic_config()
    command.downgrade(cfg, "0001")
    try:
        with engine.begin() as conn:
            _insert_legacy_ce(conn, external_line=False)
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    "SELECT v.max_discount_pct, v.revision, v.summary, l.hours, l.profile_id, p.is_external "
                    "FROM ce_versions v JOIN ce_phases ph ON ph.version_id = v.id "
                    "JOIN ce_lines l ON l.phase_id = ph.id JOIN profiles p ON p.id = l.profile_id"
                )
            ).one()
        assert (row.max_discount_pct, row.revision, row.summary, row.is_external) == (
            0,
            1,
            None,
            False,
        )
        assert row.hours == 16 and row.profile_id is not None  # i dati esistenti sono intatti
    finally:
        command.upgrade(cfg, "head")
        _purge_legacy(engine)


def test_upgrade_0002_refuses_to_delete_free_cost_external_lines(engine):
    cfg = alembic_config()
    command.downgrade(cfg, "0001")
    try:
        with engine.begin() as conn:
            _insert_legacy_ce(conn, external_line=True)
        with pytest.raises(Exception) as exc:
            command.upgrade(cfg, "head")
        assert "profilo Esterni" in str(exc.value)
        with engine.connect() as conn:  # la migrazione è stata annullata per intero
            assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0001"
            assert (
                conn.execute(text("SELECT count(*) FROM ce_lines")).scalar() == 2
            )  # niente cancellato
    finally:
        _purge_legacy(engine)
        command.upgrade(cfg, "head")


def test_downgrade_0002_restores_the_old_shape(engine):
    cfg = alembic_config()
    command.downgrade(cfg, "0001")
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("ce_lines")}
        assert {"line_type", "external_cost", "external_revenue"} <= cols
        assert "ce_version_months" not in inspect(engine).get_table_names()
        assert "is_external" not in {c["name"] for c in inspect(engine).get_columns("profiles")}
    finally:
        command.upgrade(cfg, "head")


# ------------------------------------------------------------------ migrazione 0003 (coda email)
def test_upgrade_0003_keeps_waiting_emails_due_and_adds_the_new_rules(engine):
    cfg = alembic_config()
    command.downgrade(cfg, "0002")
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO email_outbox (type, recipient, payload, status, attempts) "
                    "VALUES ('ce_submitted', 'a@huware.com', '{}', 'pending', 2), "
                    "('ce_approved', 'b@huware.com', '{}', 'sent', 1)"
                )
            )
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT recipient, status, attempts, dedupe_key, last_attempt_at, provider_message_id, "
                    "next_attempt_at <= now() AS due FROM email_outbox ORDER BY recipient"
                )
            ).all()
            assert [(r.recipient, r.status, r.attempts) for r in rows] == [
                ("a@huware.com", "pending", 2),
                ("b@huware.com", "sent", 1),
            ]
            assert all(
                r.due and r.dedupe_key is None and r.provider_message_id is None for r in rows
            )
            # chiave anti-doppione unica; più email senza chiave sono consentite
            conn.execute(
                text(
                    "INSERT INTO email_outbox (type, recipient, payload, dedupe_key) VALUES ('t', 'c@h.it', '{}', 'k1')"
                )
            )
            with pytest.raises(Exception, match="uq_email_outbox_dedupe_key"):
                with conn.begin_nested():
                    conn.execute(
                        text(
                            "INSERT INTO email_outbox (type, recipient, payload, dedupe_key) VALUES ('t', 'd@h.it', '{}', 'k1')"
                        )
                    )
            with pytest.raises(Exception, match="ck_email_outbox_attempts_non_negative"):
                with conn.begin_nested():
                    conn.execute(
                        text(
                            "INSERT INTO email_outbox (type, recipient, payload, attempts) VALUES ('t', 'e@h.it', '{}', -1)"
                        )
                    )
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM email_outbox"))
        command.upgrade(cfg, "head")


def test_downgrade_0003_removes_the_delivery_columns(engine):
    cfg = alembic_config()
    command.downgrade(cfg, "0002")
    try:
        cols = {c["name"] for c in inspect(engine).get_columns("email_outbox")}
        assert cols.isdisjoint(
            {"dedupe_key", "next_attempt_at", "last_attempt_at", "provider_message_id"}
        )
    finally:
        command.upgrade(cfg, "head")
