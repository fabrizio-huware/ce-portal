"""esito «Close Won» / «Close Lost» sui CE

Revision ID: 0009
Revises: 0008

Quattro colonne sul CE: `outcome` (`won` o `lost`), `outcome_at`, `outcome_by` e la nota facoltativa
`outcome_note`. L'esito sta sul **CE** (uno solo), non sulla versione, e si imposta solo quando l'ultima
versione è approvata (regola dell'applicazione). Il flusso di approvazione e gli stati non cambiano.
Due vincoli: il valore è `won` o `lost`; valore, data e autore ci sono tutti o non c'è nessuno
(la nota non esiste senza esito). Nessun CE ha un esito all'inizio: nessun dato esistente cambia.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ce", sa.Column("outcome", sa.String(length=10), nullable=True))
    op.add_column("ce", sa.Column("outcome_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ce", sa.Column("outcome_by", sa.UUID(), nullable=True))
    op.add_column("ce", sa.Column("outcome_note", sa.String(length=1000), nullable=True))
    op.create_foreign_key(
        op.f("fk_ce_outcome_by_users"), "ce", "users", ["outcome_by"], ["id"], ondelete="RESTRICT"
    )
    op.create_check_constraint(op.f("ck_ce_outcome_valid"), "ce", "outcome IN ('won', 'lost')")
    op.create_check_constraint(
        op.f("ck_ce_outcome_complete"),
        "ce",
        "(outcome IS NULL AND outcome_at IS NULL AND outcome_by IS NULL AND outcome_note IS NULL)"
        " OR (outcome IS NOT NULL AND outcome_at IS NOT NULL AND outcome_by IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_ce_outcome_complete"), "ce", type_="check")
    op.drop_constraint(op.f("ck_ce_outcome_valid"), "ce", type_="check")
    op.drop_constraint(op.f("fk_ce_outcome_by_users"), "ce", type_="foreignkey")
    op.drop_column("ce", "outcome_note")
    op.drop_column("ce", "outcome_by")
    op.drop_column("ce", "outcome_at")
    op.drop_column("ce", "outcome")
