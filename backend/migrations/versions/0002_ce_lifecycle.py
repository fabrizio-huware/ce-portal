"""ce lifecycle: months, external profile, discount, revision

Revision ID: 0002
Revises: 0001

Decisioni dal confronto con il foglio reale:
* giorni non lavorativi inseriti a mano per mese (ce_version_months);
* i servizi esterni sono righe con il profilo "Esterni" (profiles.is_external), non più
  righe con costo e ricavo liberi;
* max sconto inserito da chi compila;
* contatore di revisione (salvataggio sicuro) e totali sempre pronti (summary).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Le righe esterne "libere" (senza profilo) non esistono più: non cancelliamo dati in silenzio.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM ce_lines WHERE profile_id IS NULL) THEN
                RAISE EXCEPTION 'Esistono righe senza profilo (servizi esterni a costo libero): '
                                'convertile al profilo Esterni prima di eseguire questa migrazione';
            END IF;
        END $$;
        """
    )

    op.add_column('profiles', sa.Column('is_external', sa.Boolean(), server_default=sa.text('false'), nullable=False))

    op.add_column('ce_versions', sa.Column('max_discount_pct', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False))
    op.add_column('ce_versions', sa.Column('revision', sa.Integer(), server_default='1', nullable=False))
    op.add_column('ce_versions', sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_check_constraint(op.f('ck_ce_versions_max_discount_range'), 'ce_versions', 'max_discount_pct BETWEEN 0 AND 100')
    op.create_check_constraint(op.f('ck_ce_versions_revision_positive'), 'ce_versions', 'revision >= 1')

    # Eliminare le colonne elimina anche i vincoli CHECK che le riguardano (line_shape, ecc.).
    op.drop_column('ce_lines', 'line_type')
    op.drop_column('ce_lines', 'external_cost')
    op.drop_column('ce_lines', 'external_revenue')
    op.alter_column('ce_lines', 'profile_id', existing_type=sa.UUID(), nullable=False)

    op.create_table('ce_version_months',
        sa.Column('version_id', sa.UUID(), nullable=False),
        sa.Column('month', sa.Date(), nullable=False),
        sa.Column('non_working_days', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('EXTRACT(DAY FROM month) = 1', name=op.f('ck_ce_version_months_month_first_day')),
        sa.CheckConstraint('non_working_days BETWEEN 0 AND 23', name=op.f('ck_ce_version_months_non_working_days_range')),
        sa.ForeignKeyConstraint(['version_id'], ['ce_versions.id'], name=op.f('fk_ce_version_months_version_id_ce_versions'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('version_id', 'month', name=op.f('pk_ce_version_months')),
    )


def downgrade() -> None:
    op.drop_table('ce_version_months')

    op.alter_column('ce_lines', 'profile_id', existing_type=sa.UUID(), nullable=True)
    op.add_column('ce_lines', sa.Column('external_revenue', sa.NUMERIC(precision=14, scale=2), nullable=True))
    op.add_column('ce_lines', sa.Column('external_cost', sa.NUMERIC(precision=14, scale=2), nullable=True))
    op.add_column('ce_lines', sa.Column('line_type', sa.VARCHAR(length=10), server_default='internal', nullable=False))
    op.alter_column('ce_lines', 'line_type', server_default=None)
    op.create_check_constraint(op.f('ck_ce_lines_line_type_valid'), 'ce_lines', "line_type IN ('internal', 'external')")
    op.create_check_constraint(op.f('ck_ce_lines_external_cost_non_negative'), 'ce_lines', 'external_cost IS NULL OR external_cost >= 0')
    op.create_check_constraint(op.f('ck_ce_lines_external_revenue_non_negative'), 'ce_lines', 'external_revenue IS NULL OR external_revenue >= 0')
    op.create_check_constraint(
        op.f('ck_ce_lines_line_shape'),
        'ce_lines',
        "(line_type = 'internal' AND profile_id IS NOT NULL AND external_cost IS NULL AND external_revenue IS NULL) "
        "OR (line_type = 'external' AND profile_id IS NULL AND employee_id IS NULL AND hours IS NULL "
        "AND NOT is_project_management AND external_cost IS NOT NULL AND external_revenue IS NOT NULL)",
    )

    op.drop_constraint(op.f('ck_ce_versions_revision_positive'), 'ce_versions', type_='check')
    op.drop_constraint(op.f('ck_ce_versions_max_discount_range'), 'ce_versions', type_='check')
    op.drop_column('ce_versions', 'summary')
    op.drop_column('ce_versions', 'revision')
    op.drop_column('ce_versions', 'max_discount_pct')

    op.drop_column('profiles', 'is_external')
