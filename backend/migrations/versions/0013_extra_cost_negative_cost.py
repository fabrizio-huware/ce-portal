"""costo negativo sui costi vari

Revision ID: 0013
Revises: 0012

Il costo di una riga di costi vari può essere negativo (storni, note di credito, abbuoni): il
vincolo `cost_non_negative` (cost >= 0) diventa `cost_min` (cost >= -9999999999.99, simmetrico al
massimo). Nessun dato cambia. La discesa è rifiutata se esistono righe con costo negativo.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ce_extra_costs_cost_non_negative"), "ce_extra_costs", type_="check")
    op.create_check_constraint("cost_min", "ce_extra_costs", "cost >= -9999999999.99")


def downgrade() -> None:
    negatives = op.get_bind().execute(
        sa.text("SELECT count(*) FROM ce_extra_costs WHERE cost < 0")
    ).scalar_one()
    if negatives:
        raise RuntimeError(
            f"Discesa impossibile: {negatives} righe di costi vari hanno un costo negativo. "
            "Modificale (o eliminale) prima di tornare indietro."
        )
    op.drop_constraint(op.f("ck_ce_extra_costs_cost_min"), "ce_extra_costs", type_="check")
    op.create_check_constraint("cost_non_negative", "ce_extra_costs", "cost >= 0")
