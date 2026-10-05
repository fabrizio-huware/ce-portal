"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-05 09:33:01.086820
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Estensione per la ricerca parziale (ILIKE) su codice, progetto e cliente.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table('clients',
    sa.Column('name', sa.String(length=300), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('external_ref', sa.String(length=100), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_clients'))
    )
    op.create_index('ix_clients_name_trgm', 'clients', ['name'], unique=False, postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('uq_clients_name_lower', 'clients', [sa.literal_column('lower(name)')], unique=True)
    op.create_table('email_outbox',
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('recipient', sa.String(length=320), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=10), server_default='pending', nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name=op.f('ck_email_outbox_status_valid')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_email_outbox'))
    )
    op.create_index(op.f('ix_email_outbox_status'), 'email_outbox', ['status'], unique=False)
    op.create_table('non_working_days',
    sa.Column('day', sa.Date(), nullable=False),
    sa.Column('kind', sa.String(length=20), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("kind IN ('holiday', 'company_closure')", name=op.f('ck_non_working_days_kind_valid')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_non_working_days')),
    sa.UniqueConstraint('day', name=op.f('uq_non_working_days_day'))
    )
    op.create_table('profiles',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('band', sa.String(length=10), nullable=True),
    sa.Column('billability_target', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('billability_target IS NULL OR (billability_target BETWEEN 0 AND 100)', name=op.f('ck_profiles_billability_range')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_profiles')),
    sa.UniqueConstraint('name', name=op.f('uq_profiles_name'))
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('full_name', sa.String(length=200), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('google_sub', sa.String(length=255), nullable=True),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('admin', 'presale', 'viewer')", name=op.f('ck_users_role_valid')),
    sa.CheckConstraint('email = lower(email)', name=op.f('ck_users_email_lowercase')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email')),
    sa.UniqueConstraint('google_sub', name=op.f('uq_users_google_sub'))
    )
    op.create_table('audit_log',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=True),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_audit_log_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_log'))
    )
    op.create_index('ix_audit_log_entity', 'audit_log', ['entity_type', 'entity_id'], unique=False)
    op.create_index(op.f('ix_audit_log_occurred_at'), 'audit_log', ['occurred_at'], unique=False)
    op.create_table('ce',
    sa.Column('code', sa.String(length=100), nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_ce_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['deleted_by'], ['users.id'], name=op.f('fk_ce_deleted_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ce'))
    )
    op.create_index('ix_ce_code_trgm', 'ce', ['code'], unique=False, postgresql_using='gin', postgresql_ops={'code': 'gin_trgm_ops'})
    op.create_index('uq_ce_code_lower', 'ce', [sa.literal_column('lower(code)')], unique=True)
    op.create_table('employees',
    sa.Column('first_name', sa.String(length=100), nullable=False),
    sa.Column('last_name', sa.String(length=100), nullable=False),
    sa.Column('default_profile_id', sa.UUID(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('netsuite_id', sa.String(length=100), nullable=True),
    sa.Column('jira_account_id', sa.String(length=100), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['default_profile_id'], ['profiles.id'], name=op.f('fk_employees_default_profile_id_profiles'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_employees'))
    )
    op.create_index(op.f('ix_employees_default_profile_id'), 'employees', ['default_profile_id'], unique=False)
    op.create_table('profile_rates',
    sa.Column('profile_id', sa.UUID(), nullable=False),
    sa.Column('year', sa.Integer(), nullable=False),
    sa.Column('daily_price', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('daily_cost', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('daily_cost >= 0', name=op.f('ck_profile_rates_cost_non_negative')),
    sa.CheckConstraint('daily_price >= 0', name=op.f('ck_profile_rates_price_non_negative')),
    sa.CheckConstraint('year BETWEEN 2000 AND 2100', name=op.f('ck_profile_rates_year_range')),
    sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], name=op.f('fk_profile_rates_profile_id_profiles'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('profile_id', 'year', name=op.f('pk_profile_rates'))
    )
    op.create_table('ce_versions',
    sa.Column('ce_id', sa.UUID(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
    sa.Column('client_id', sa.UUID(), nullable=False),
    sa.Column('project_name', sa.String(length=300), nullable=False),
    sa.Column('sf_opportunity', sa.String(length=100), nullable=True),
    sa.Column('business_unit', sa.String(length=100), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=False),
    sa.Column('end_date', sa.Date(), nullable=False),
    sa.Column('planning_mode', sa.String(length=10), nullable=False),
    sa.Column('rate_year', sa.Integer(), nullable=False),
    sa.Column('signed_price', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('approved_by', sa.UUID(), nullable=True),
    sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejected_by', sa.UUID(), nullable=True),
    sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejection_reason', sa.Text(), nullable=True),
    sa.Column('approved_totals', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("planning_mode IN ('hours', 'percent')", name=op.f('ck_ce_versions_planning_mode_valid')),
    sa.CheckConstraint("status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL AND approved_totals IS NOT NULL)", name=op.f('ck_ce_versions_approved_fields')),
    sa.CheckConstraint("status <> 'rejected' OR (rejected_by IS NOT NULL AND rejected_at IS NOT NULL)", name=op.f('ck_ce_versions_rejected_fields')),
    sa.CheckConstraint("status IN ('draft', 'submitted', 'approved', 'rejected')", name=op.f('ck_ce_versions_status_valid')),
    sa.CheckConstraint('end_date >= start_date', name=op.f('ck_ce_versions_dates_ordered')),
    sa.CheckConstraint('rate_year BETWEEN 2000 AND 2100', name=op.f('ck_ce_versions_rate_year_range')),
    sa.CheckConstraint('signed_price IS NULL OR signed_price >= 0', name=op.f('ck_ce_versions_signed_price_positive')),
    sa.CheckConstraint('version_number >= 1', name=op.f('ck_ce_versions_version_number_positive')),
    sa.ForeignKeyConstraint(['approved_by'], ['users.id'], name=op.f('fk_ce_versions_approved_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['ce_id'], ['ce.id'], name=op.f('fk_ce_versions_ce_id_ce'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['client_id'], ['clients.id'], name=op.f('fk_ce_versions_client_id_clients'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], name=op.f('fk_ce_versions_created_by_users'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['rejected_by'], ['users.id'], name=op.f('fk_ce_versions_rejected_by_users'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ce_versions')),
    sa.UniqueConstraint('ce_id', 'version_number', name=op.f('uq_ce_versions_ce_id'))
    )
    op.create_index(op.f('ix_ce_versions_client_id'), 'ce_versions', ['client_id'], unique=False)
    op.create_index('ix_ce_versions_dates', 'ce_versions', ['start_date', 'end_date'], unique=False)
    op.create_index('ix_ce_versions_project_name_trgm', 'ce_versions', ['project_name'], unique=False, postgresql_using='gin', postgresql_ops={'project_name': 'gin_trgm_ops'})
    op.create_index('ix_ce_versions_status', 'ce_versions', ['status'], unique=False)
    op.create_index('uq_ce_versions_one_open', 'ce_versions', ['ce_id'], unique=True, postgresql_where=sa.text("status IN ('draft', 'submitted', 'rejected')"))
    op.create_table('ce_milestones',
    sa.Column('version_id', sa.UUID(), nullable=False),
    sa.Column('month', sa.Date(), nullable=False),
    sa.Column('label', sa.String(length=200), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('EXTRACT(DAY FROM month) = 1', name=op.f('ck_ce_milestones_month_first_day')),
    sa.ForeignKeyConstraint(['version_id'], ['ce_versions.id'], name=op.f('fk_ce_milestones_version_id_ce_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ce_milestones')),
    sa.UniqueConstraint('version_id', 'month', 'label', name=op.f('uq_ce_milestones_version_id'))
    )
    op.create_index(op.f('ix_ce_milestones_version_id'), 'ce_milestones', ['version_id'], unique=False)
    op.create_table('ce_phases',
    sa.Column('version_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('contingency_pct', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('contingency_pct BETWEEN 0 AND 100', name=op.f('ck_ce_phases_contingency_range')),
    sa.ForeignKeyConstraint(['version_id'], ['ce_versions.id'], name=op.f('fk_ce_phases_version_id_ce_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ce_phases'))
    )
    op.create_index(op.f('ix_ce_phases_version_id'), 'ce_phases', ['version_id'], unique=False)
    op.create_table('ce_version_rates',
    sa.Column('version_id', sa.UUID(), nullable=False),
    sa.Column('profile_id', sa.UUID(), nullable=False),
    sa.Column('daily_price', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('daily_cost', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('daily_cost >= 0', name=op.f('ck_ce_version_rates_cost_non_negative')),
    sa.CheckConstraint('daily_price >= 0', name=op.f('ck_ce_version_rates_price_non_negative')),
    sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], name=op.f('fk_ce_version_rates_profile_id_profiles'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['version_id'], ['ce_versions.id'], name=op.f('fk_ce_version_rates_version_id_ce_versions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('version_id', 'profile_id', name=op.f('pk_ce_version_rates'))
    )
    op.create_table('ce_lines',
    sa.Column('phase_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('line_type', sa.String(length=10), nullable=False),
    sa.Column('activity', sa.String(length=300), nullable=False),
    sa.Column('profile_id', sa.UUID(), nullable=True),
    sa.Column('employee_id', sa.UUID(), nullable=True),
    sa.Column('is_project_management', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('hours', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('external_cost', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('external_revenue', sa.Numeric(precision=14, scale=2), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(line_type = 'internal' AND profile_id IS NOT NULL AND external_cost IS NULL AND external_revenue IS NULL) OR (line_type = 'external' AND profile_id IS NULL AND employee_id IS NULL AND hours IS NULL AND NOT is_project_management AND external_cost IS NOT NULL AND external_revenue IS NOT NULL)", name=op.f('ck_ce_lines_line_shape')),
    sa.CheckConstraint("line_type IN ('internal', 'external')", name=op.f('ck_ce_lines_line_type_valid')),
    sa.CheckConstraint('external_cost IS NULL OR external_cost >= 0', name=op.f('ck_ce_lines_external_cost_non_negative')),
    sa.CheckConstraint('external_revenue IS NULL OR external_revenue >= 0', name=op.f('ck_ce_lines_external_revenue_non_negative')),
    sa.CheckConstraint('hours IS NULL OR hours >= 0', name=op.f('ck_ce_lines_hours_non_negative')),
    sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], name=op.f('fk_ce_lines_employee_id_employees'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['phase_id'], ['ce_phases.id'], name=op.f('fk_ce_lines_phase_id_ce_phases'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['profile_id'], ['profiles.id'], name=op.f('fk_ce_lines_profile_id_profiles'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ce_lines'))
    )
    op.create_index(op.f('ix_ce_lines_employee_id'), 'ce_lines', ['employee_id'], unique=False)
    op.create_index(op.f('ix_ce_lines_phase_id'), 'ce_lines', ['phase_id'], unique=False)
    op.create_index(op.f('ix_ce_lines_profile_id'), 'ce_lines', ['profile_id'], unique=False)
    op.create_table('ce_line_allocations',
    sa.Column('line_id', sa.UUID(), nullable=False),
    sa.Column('month', sa.Date(), nullable=False),
    sa.Column('allocation_pct', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('EXTRACT(DAY FROM month) = 1', name=op.f('ck_ce_line_allocations_month_first_day')),
    sa.CheckConstraint('allocation_pct BETWEEN 0 AND 100', name=op.f('ck_ce_line_allocations_allocation_pct_range')),
    sa.ForeignKeyConstraint(['line_id'], ['ce_lines.id'], name=op.f('fk_ce_line_allocations_line_id_ce_lines'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('line_id', 'month', name=op.f('pk_ce_line_allocations'))
    )


def downgrade() -> None:
    op.drop_table('ce_line_allocations')
    op.drop_index(op.f('ix_ce_lines_profile_id'), table_name='ce_lines')
    op.drop_index(op.f('ix_ce_lines_phase_id'), table_name='ce_lines')
    op.drop_index(op.f('ix_ce_lines_employee_id'), table_name='ce_lines')
    op.drop_table('ce_lines')
    op.drop_table('ce_version_rates')
    op.drop_index(op.f('ix_ce_phases_version_id'), table_name='ce_phases')
    op.drop_table('ce_phases')
    op.drop_index(op.f('ix_ce_milestones_version_id'), table_name='ce_milestones')
    op.drop_table('ce_milestones')
    op.drop_index('uq_ce_versions_one_open', table_name='ce_versions', postgresql_where=sa.text("status IN ('draft', 'submitted', 'rejected')"))
    op.drop_index('ix_ce_versions_status', table_name='ce_versions')
    op.drop_index('ix_ce_versions_project_name_trgm', table_name='ce_versions', postgresql_using='gin', postgresql_ops={'project_name': 'gin_trgm_ops'})
    op.drop_index('ix_ce_versions_dates', table_name='ce_versions')
    op.drop_index(op.f('ix_ce_versions_client_id'), table_name='ce_versions')
    op.drop_table('ce_versions')
    op.drop_table('profile_rates')
    op.drop_index(op.f('ix_employees_default_profile_id'), table_name='employees')
    op.drop_table('employees')
    op.drop_index('uq_ce_code_lower', table_name='ce')
    op.drop_index('ix_ce_code_trgm', table_name='ce', postgresql_using='gin', postgresql_ops={'code': 'gin_trgm_ops'})
    op.drop_table('ce')
    op.drop_index(op.f('ix_audit_log_occurred_at'), table_name='audit_log')
    op.drop_index('ix_audit_log_entity', table_name='audit_log')
    op.drop_table('audit_log')
    op.drop_table('users')
    op.drop_table('profiles')
    op.drop_table('non_working_days')
    op.drop_index(op.f('ix_email_outbox_status'), table_name='email_outbox')
    op.drop_table('email_outbox')
    op.drop_index('uq_clients_name_lower', table_name='clients')
    op.drop_index('ix_clients_name_trgm', table_name='clients', postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.drop_table('clients')
