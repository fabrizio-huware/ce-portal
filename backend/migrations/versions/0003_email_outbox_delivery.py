"""email outbox delivery

Revision ID: 0003
Revises: 0002

Campi per un invio affidabile: chiave anti-doppione (una sola email per evento), ora del prossimo
tentativo (ritentativi con attesa crescente), ultimo tentativo e identificativo del messaggio Mailjet.
Le email già presenti in coda risultano subito "da inviare".
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('email_outbox', sa.Column('dedupe_key', sa.String(length=200), nullable=True))
    op.add_column('email_outbox', sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('email_outbox', sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('email_outbox', sa.Column('provider_message_id', sa.String(length=100), nullable=True))
    op.create_unique_constraint(op.f('uq_email_outbox_dedupe_key'), 'email_outbox', ['dedupe_key'])
    op.create_check_constraint(op.f('ck_email_outbox_attempts_non_negative'), 'email_outbox', 'attempts >= 0')
    op.create_index('ix_email_outbox_due', 'email_outbox', ['next_attempt_at'], unique=False, postgresql_where=sa.text("status = 'pending'"))


def downgrade() -> None:
    op.drop_index('ix_email_outbox_due', table_name='email_outbox', postgresql_where=sa.text("status = 'pending'"))
    op.drop_constraint(op.f('ck_email_outbox_attempts_non_negative'), 'email_outbox', type_='check')
    op.drop_constraint(op.f('uq_email_outbox_dedupe_key'), 'email_outbox', type_='unique')
    op.drop_column('email_outbox', 'provider_message_id')
    op.drop_column('email_outbox', 'last_attempt_at')
    op.drop_column('email_outbox', 'next_attempt_at')
    op.drop_column('email_outbox', 'dedupe_key')
