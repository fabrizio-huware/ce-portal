"""costo dei costi vari di nuovo non negativo (annulla la 0013)

Revision ID: 0014
Revises: 0013

La modifica CL-049 (costo negativo nei costi vari) è stata annullata. La migrazione `0013` resta
nella catena (può essere già stata applicata): questa ripristina il vincolo `cost_non_negative`
(cost >= 0). La salita è rifiutata se esistono righe con costo negativo, per non perdere dati in
silenzio: vanno modificate o eliminate prima.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    negatives = op.get_bind().execute(
        sa.text("SELECT count(*) FROM ce_extra_costs WHERE cost < 0")
    ).scalar_one()
    if negatives:
        raise RuntimeError(
            f"Migrazione impossibile: {negatives} righe di costi vari hanno un costo negativo. "
            "Modificale (o eliminale) prima di aggiornare."
        )
    op.drop_constraint(op.f("ck_ce_extra_costs_cost_min"), "ce_extra_costs", type_="check")
    op.create_check_constraint("cost_non_negative", "ce_extra_costs", "cost >= 0")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_ce_extra_costs_cost_non_negative"), "ce_extra_costs", type_="check")
    op.create_check_constraint("cost_min", "ce_extra_costs", "cost >= -9999999999.99")
