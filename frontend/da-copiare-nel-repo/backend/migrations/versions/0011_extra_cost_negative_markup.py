"""ricarico negativo sui costi vari

Revision ID: 0011
Revises: 0010

Il ricarico di una riga di costi vari può essere negativo, fino a -100% (totale di riga zero):
il vincolo `markup_range` passa da 0..1000 a -100..1000. Nessun dato cambia. La discesa è
rifiutata se esistono righe con ricarico negativo: riportarle a zero ne cambierebbe i numeri.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT = "markup_range"


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ce_extra_costs_markup_range"), "ce_extra_costs", type_="check")
    op.create_check_constraint(CONSTRAINT, "ce_extra_costs", "markup_pct >= -100 AND markup_pct <= 1000")


def downgrade() -> None:
    negatives = op.get_bind().execute(
        sa.text("SELECT count(*) FROM ce_extra_costs WHERE markup_pct < 0")
    ).scalar_one()
    if negatives:
        raise RuntimeError(
            f"Discesa impossibile: {negatives} righe di costi vari hanno un ricarico negativo. "
            "Modificale (o eliminale) prima di tornare indietro."
        )
    op.drop_constraint(op.f("ck_ce_extra_costs_markup_range"), "ce_extra_costs", type_="check")
    op.create_check_constraint(CONSTRAINT, "ce_extra_costs", "markup_pct >= 0 AND markup_pct <= 1000")
