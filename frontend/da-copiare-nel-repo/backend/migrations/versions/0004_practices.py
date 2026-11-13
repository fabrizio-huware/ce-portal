"""practice dei collaboratori

Revision ID: 0004
Revises: 0003

Nuova anagrafica `practices` e colonna obbligatoria `employees.practice_id`. I collaboratori già presenti
ricevono la practice di sistema «Da assegnare» (creata qui), che l'amministrazione riassegna poi.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('practices',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_practices'))
    )
    op.create_index('uq_practices_name_lower', 'practices', [sa.literal_column('lower(name)')], unique=True)
    # la colonna nasce vuota, si riempie per i collaboratori esistenti e solo dopo diventa obbligatoria
    op.add_column('employees', sa.Column('practice_id', sa.UUID(), nullable=True))
    op.execute("INSERT INTO practices (name) VALUES ('Da assegnare')")
    op.execute("UPDATE employees SET practice_id = (SELECT id FROM practices WHERE lower(name) = 'da assegnare')")
    op.alter_column('employees', 'practice_id', nullable=False)
    op.create_index(op.f('ix_employees_practice_id'), 'employees', ['practice_id'], unique=False)
    op.create_foreign_key(op.f('fk_employees_practice_id_practices'), 'employees', 'practices', ['practice_id'], ['id'], ondelete='RESTRICT')


def downgrade() -> None:
    op.drop_constraint(op.f('fk_employees_practice_id_practices'), 'employees', type_='foreignkey')
    op.drop_index(op.f('ix_employees_practice_id'), table_name='employees')
    op.drop_column('employees', 'practice_id')
    op.drop_index('uq_practices_name_lower', table_name='practices')
    op.drop_table('practices')
