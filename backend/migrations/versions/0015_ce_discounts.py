"""righe di sconti sul CE

Revision ID: 0015
Revises: 0014

Nuova tabella `ce_discounts`: per ogni versione, righe con descrizione, tipo (importo in euro o
percentuale sul prezzo prima degli sconti) e valore. Le righe tolgono dal prezzo progetto e non
cambiano i costi. Solo aggiunta: nessuna versione esistente ha righe, quindi nessun CE cambia i
propri numeri.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ce_discounts",
        sa.Column("version_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("value", sa.Numeric(precision=14, scale=2), nullable=False),
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
        sa.CheckConstraint("kind IN ('amount', 'percent')", name=op.f("ck_ce_discounts_kind_valid")),
        sa.CheckConstraint("value >= 0", name=op.f("ck_ce_discounts_value_non_negative")),
        sa.CheckConstraint(
            "kind <> 'percent' OR value <= 100", name=op.f("ck_ce_discounts_percent_range")
        ),
        sa.ForeignKeyConstraint(
            ["version_id"],
            ["ce_versions.id"],
            name=op.f("fk_ce_discounts_version_id_ce_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ce_discounts")),
    )
    op.create_index(
        op.f("ix_ce_discounts_version_id"), "ce_discounts", ["version_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_ce_discounts_version_id"), table_name="ce_discounts")
    op.drop_table("ce_discounts")
