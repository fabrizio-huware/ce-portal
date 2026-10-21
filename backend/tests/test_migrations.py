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
    "integrations",
    "non_working_days",
    "practices",
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


# ------------------------------------------------------------------ migrazione 0004 con dati veri
def test_upgrade_0004_gives_existing_employees_the_default_practice(engine):
    """I collaboratori già presenti ricevono «Da assegnare», e da lì la practice è obbligatoria."""
    cfg = alembic_config()
    command.downgrade(cfg, "0003")
    try:
        with engine.begin() as conn:
            profile = conn.execute(
                text("INSERT INTO profiles (name) VALUES ('Senior') RETURNING id")
            ).scalar()
            for first in ("Ada", "Bruno", "Carla"):
                conn.execute(
                    text(
                        "INSERT INTO employees (first_name, last_name, default_profile_id) VALUES (:f, 'Test', :p)"
                    ),
                    {"f": first, "p": profile},
                )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            names = (
                conn.execute(
                    text("SELECT p.name FROM employees e JOIN practices p ON p.id = e.practice_id")
                )
                .scalars()
                .all()
            )
            assert names == ["Da assegnare"] * 3
            assert conn.execute(text("SELECT count(*) FROM practices")).scalar() == 1
            nullable = conn.execute(
                text(
                    "SELECT is_nullable FROM information_schema.columns "
                    "WHERE table_name = 'employees' AND column_name = 'practice_id'"
                )
            ).scalar()
            assert nullable == "NO"
    finally:
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            for table in ("employees", "profiles", "practices"):
                conn.execute(text(f"DELETE FROM {table}"))


def test_upgrade_0004_on_an_empty_employee_table_still_creates_the_default_practice(engine):
    cfg = alembic_config()
    command.downgrade(cfg, "0003")
    try:
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT name FROM practices")).scalars().all() == [
                "Da assegnare"
            ]
    finally:
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM practices"))


def test_upgrade_0005_keeps_existing_data_and_the_new_constraints_hold(engine):
    """Utenti e CE già presenti restano com'erano; l'identificativo esterno è unico per integrazione."""
    from sqlalchemy.exc import IntegrityError

    cfg = alembic_config()
    command.downgrade(cfg, "0004")
    try:
        with engine.begin() as conn:
            person = conn.execute(
                text(
                    "INSERT INTO users (email, full_name, role) VALUES ('x@huware.com', 'X', 'presale') RETURNING id"
                )
            ).scalar()
            conn.execute(
                text("INSERT INTO ce (code, created_by) VALUES ('PS-OLD-001', :u)"), {"u": person}
            )
        command.upgrade(cfg, "head")
        with engine.connect() as conn:
            assert (
                conn.execute(
                    text("SELECT is_service FROM users WHERE email = 'x@huware.com'")
                ).scalar()
                is False
            )
            row = conn.execute(
                text(
                    "SELECT integration_id, external_ref, requested_by FROM ce WHERE code = 'PS-OLD-001'"
                )
            ).one()
            assert tuple(row) == (None, None, None)
            assert conn.execute(text("SELECT count(*) FROM integrations")).scalar() == 0

        with engine.begin() as conn:
            service_user = conn.execute(
                text(
                    "INSERT INTO users (email, full_name, role, is_service) "
                    "VALUES ('s@p.iam.gserviceaccount.com', 'S (servizio)', 'presale', true) RETURNING id"
                )
            ).scalar()
            integration = conn.execute(
                text(
                    "INSERT INTO integrations (name, service_account_email, user_id, permissions, created_by) "
                    "VALUES ('S', 's@p.iam.gserviceaccount.com', :s, ARRAY['read'], :p) RETURNING id"
                ),
                {"s": service_user, "p": person},
            ).scalar()
        insert_ce = text(
            "INSERT INTO ce (code, created_by, integration_id, external_ref) VALUES (:c, :u, :i, :r)"
        )
        with engine.begin() as conn:
            conn.execute(
                insert_ce, {"c": "PS-EXT-A", "u": service_user, "i": integration, "r": "R-1"}
            )
            conn.execute(
                insert_ce, {"c": "PS-EXT-B", "u": service_user, "i": integration, "r": None}
            )
            conn.execute(
                insert_ce, {"c": "PS-EXT-C", "u": service_user, "i": integration, "r": None}
            )  # senza identificativo: ammessi
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                insert_ce, {"c": "PS-EXT-D", "u": person, "i": integration, "r": "R-1"}
            )  # stesso identificativo
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO integrations (name, service_account_email, user_id, permissions, created_by) "
                    "VALUES ('M', 'Maiuscole@p.iam.gserviceaccount.com', :s, ARRAY['read'], :p)"
                ),
                {"s": person, "p": person},
            )  # l'indirizzo si conserva minuscolo
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO integrations (name, service_account_email, user_id, permissions, created_by) "
                    "VALUES ('P', 'p@p.iam.gserviceaccount.com', :s, ARRAY['delete'], :p)"
                ),
                {"s": person, "p": person},
            )  # permesso inesistente
    finally:
        command.upgrade(cfg, "head")
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM ce WHERE code LIKE 'PS-OLD-%' OR code LIKE 'PS-EXT-%'"))
            conn.execute(text("DELETE FROM integrations"))
            conn.execute(
                text(
                    "DELETE FROM users WHERE email IN ('x@huware.com', 's@p.iam.gserviceaccount.com')"
                )
            )


def test_downgrade_0005_removes_the_integration_structures(engine):
    cfg = alembic_config()
    command.downgrade(cfg, "0004")
    try:
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            assert "integrations" not in tables
            assert not {"integration_id", "external_ref", "requested_by"} & {
                c["name"] for c in inspect(conn).get_columns("ce")
            }
            assert "is_service" not in {c["name"] for c in inspect(conn).get_columns("users")}
    finally:
        command.upgrade(cfg, "head")
