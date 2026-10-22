"""business unit sopra le practice

Revision ID: 0006
Revises: 0005

Nuova anagrafica `business_units` (business unit → practice → collaboratori), colonna obbligatoria
`practices.business_unit_id`, colonna facoltativa `users.business_unit_id` e nuovo ruolo `bu_manager`
(responsabile di business unit). Le practice già presenti ricevono la business unit di sistema «Da assegnare»
(creata qui), che l'amministrazione riassegna poi. Nessun altro dato cambia.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "business_units",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_business_units")),
    )
    op.create_index(
        "uq_business_units_name_lower",
        "business_units",
        [sa.literal_column("lower(name)")],
        unique=True,
    )
    op.execute("INSERT INTO business_units (name) VALUES ('Da assegnare')")
    # la colonna nasce vuota, si riempie per le practice esistenti e solo dopo diventa obbligatoria
    op.add_column("practices", sa.Column("business_unit_id", sa.UUID(), nullable=True))
    op.execute(
        "UPDATE practices SET business_unit_id = (SELECT id FROM business_units WHERE lower(name) = 'da assegnare')"
    )
    op.alter_column("practices", "business_unit_id", nullable=False)
    op.create_index(
        op.f("ix_practices_business_unit_id"), "practices", ["business_unit_id"], unique=False
    )
    op.create_foreign_key(
        op.f("fk_practices_business_unit_id_business_units"),
        "practices",
        "business_units",
        ["business_unit_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("users", sa.Column("business_unit_id", sa.UUID(), nullable=True))
    op.create_index(op.f("ix_users_business_unit_id"), "users", ["business_unit_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_users_business_unit_id_business_units"),
        "users",
        "business_units",
        ["business_unit_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(op.f("ck_users_role_valid"), "users", type_="check")
    op.create_check_constraint(
        op.f("ck_users_role_valid"), "users", "role IN ('admin', 'presale', 'bu_manager', 'viewer')"
    )


def downgrade() -> None:
    # i responsabili di business unit tornano presale: il ruolo non esiste più nel vincolo
    op.execute("UPDATE users SET role = 'presale' WHERE role = 'bu_manager'")
    op.drop_constraint(op.f("ck_users_role_valid"), "users", type_="check")
    op.create_check_constraint(
        op.f("ck_users_role_valid"), "users", "role IN ('admin', 'presale', 'viewer')"
    )
    op.drop_constraint(
        op.f("fk_users_business_unit_id_business_units"), "users", type_="foreignkey"
    )
    op.drop_index(op.f("ix_users_business_unit_id"), table_name="users")
    op.drop_column("users", "business_unit_id")
    op.drop_constraint(
        op.f("fk_practices_business_unit_id_business_units"), "practices", type_="foreignkey"
    )
    op.drop_index(op.f("ix_practices_business_unit_id"), table_name="practices")
    op.drop_column("practices", "business_unit_id")
    op.drop_index("uq_business_units_name_lower", table_name="business_units")
    op.drop_table("business_units")
