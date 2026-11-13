"""allegato nella coda delle email

Revision ID: 0012
Revises: 0011

Il report di un CE inviato per email viaggia come allegato: la coda ne conserva il contenuto
finché l'email non parte (poi viene cancellato), con nome e tipo del file. Nessun dato esistente cambia.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("email_outbox", sa.Column("attachment", sa.LargeBinary(), nullable=True))
    op.add_column("email_outbox", sa.Column("attachment_name", sa.String(200), nullable=True))
    op.add_column("email_outbox", sa.Column("attachment_mime", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("email_outbox", "attachment_mime")
    op.drop_column("email_outbox", "attachment_name")
    op.drop_column("email_outbox", "attachment")
