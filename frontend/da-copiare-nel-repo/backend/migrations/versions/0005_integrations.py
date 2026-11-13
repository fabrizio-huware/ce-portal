"""integrazioni: accesso da programma a programma con un account di servizio Google

Nuova tabella `integrations`, flag `users.is_service` (l'utente di servizio, autore dei CE creati dal programma esterno)
e i campi `ce.integration_id`, `ce.external_ref`, `ce.requested_by`. Nessun dato esistente cambia.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-20 16:41:14.496100
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "integrations",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("service_account_email", sa.String(length=320), nullable=False),
        sa.Column("service_account_sub", sa.String(length=255), nullable=True),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("permissions", postgresql.ARRAY(sa.String(length=20)), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "permissions <@ ARRAY['create','edit','read','export']::varchar[]",
            name=op.f("ck_integrations_permissions_valid"),
        ),
        sa.CheckConstraint(
            "service_account_email = lower(service_account_email)",
            name=op.f("ck_integrations_sa_email_lowercase"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_integrations_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_integrations_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integrations")),
        sa.UniqueConstraint(
            "service_account_email", name=op.f("uq_integrations_service_account_email")
        ),
        sa.UniqueConstraint(
            "service_account_sub", name=op.f("uq_integrations_service_account_sub")
        ),
        sa.UniqueConstraint("user_id", name=op.f("uq_integrations_user_id")),
    )
    op.add_column("ce", sa.Column("integration_id", sa.UUID(), nullable=True))
    op.add_column("ce", sa.Column("external_ref", sa.String(length=100), nullable=True))
    op.add_column("ce", sa.Column("requested_by", sa.String(length=320), nullable=True))
    op.create_index(
        "uq_ce_integration_external_ref",
        "ce",
        ["integration_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )
    op.create_foreign_key(
        op.f("fk_ce_integration_id_integrations"),
        "ce",
        "integrations",
        ["integration_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column(
        "users",
        sa.Column("is_service", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_service")
    op.drop_constraint(op.f("fk_ce_integration_id_integrations"), "ce", type_="foreignkey")
    op.drop_index(
        "uq_ce_integration_external_ref",
        table_name="ce",
        postgresql_where=sa.text("external_ref IS NOT NULL"),
    )
    op.drop_column("ce", "requested_by")
    op.drop_column("ce", "external_ref")
    op.drop_column("ce", "integration_id")
    op.drop_table("integrations")
