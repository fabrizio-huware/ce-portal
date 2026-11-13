"""righe di costi vari sul CE

Revision ID: 0010
Revises: 0009

Nuova tabella `ce_extra_costs`: per ogni versione, righe con descrizione, costo e ricarico % sul
costo (ricavo di riga = costo x (1 + ricarico)). Le righe non hanno giornate, mese né profilo.
Vincoli: costo >= 0 e ricarico tra 0 e 1000. Solo aggiunta: nessuna versione esistente ha righe,
quindi nessun CE cambia i propri numeri.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ce_extra_costs",
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("cost", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column(
            "markup_pct", sa.Numeric(precision=7, scale=2), server_default="0", nullable=False
        ),
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
        sa.CheckConstraint("cost >= 0", name=op.f("ck_ce_extra_costs_cost_non_negative")),
        sa.CheckConstraint(
            "markup_pct >= 0 AND markup_pct <= 1000", name=op.f("ck_ce_extra_costs_markup_range")
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["ce_versions.id"],
            name=op.f("fk_ce_extra_costs_version_id_ce_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ce_extra_costs")),
    )
    op.create_index(
        op.f("ix_ce_extra_costs_version_id"), "ce_extra_costs", ["version_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ce_extra_costs_version_id"), table_name="ce_extra_costs")
    op.drop_table("ce_extra_costs")
