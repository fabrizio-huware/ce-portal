"""Conto economico: identità, versioni, tariffe congelate, fasi, righe, allocazioni, milestone."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPkMixin, in_list

CE_STATUSES = ("draft", "submitted", "approved", "rejected")
OPEN_STATUSES = ("draft", "submitted", "rejected")  # versioni non ancora approvate
PLANNING_MODES = ("hours", "percent")
LINE_TYPES = ("internal", "external")


def _fk(target: str, *, ondelete: str, nullable: bool = False, index: bool = False):
    return mapped_column(
        UUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        index=index,
    )


class CE(UUIDPkMixin, TimestampMixin, Base):
    """Identità del conto economico (il codice progetto). I dati variabili sono nelle versioni."""

    __tablename__ = "ce"

    code: Mapped[str] = mapped_column(String(100))
    created_by: Mapped[uuid.UUID] = _fk("users.id", ondelete="RESTRICT")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_by: Mapped[uuid.UUID | None] = _fk("users.id", ondelete="RESTRICT", nullable=True)

    versions: Mapped[list["CEVersion"]] = relationship(
        back_populates="ce", order_by="CEVersion.version_number", passive_deletes=True
    )


# Codice progetto univoco senza distinzione tra maiuscole e minuscole + ricerca parziale.
Index("uq_ce_code_lower", func.lower(CE.code), unique=True)
Index("ix_ce_code_trgm", CE.code, postgresql_using="gin", postgresql_ops={"code": "gin_trgm_ops"})


class CEVersion(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "ce_versions"
    __table_args__ = (
        UniqueConstraint("ce_id", "version_number"),
        CheckConstraint("version_number >= 1", name="version_number_positive"),
        CheckConstraint(in_list("status", CE_STATUSES), name="status_valid"),
        CheckConstraint(in_list("planning_mode", PLANNING_MODES), name="planning_mode_valid"),
        CheckConstraint("end_date >= start_date", name="dates_ordered"),
        CheckConstraint("rate_year BETWEEN 2000 AND 2100", name="rate_year_range"),
        CheckConstraint("signed_price IS NULL OR signed_price >= 0", name="signed_price_positive"),
        CheckConstraint(
            "status <> 'approved' OR (approved_by IS NOT NULL AND approved_at IS NOT NULL "
            "AND approved_totals IS NOT NULL)",
            name="approved_fields",
        ),
        CheckConstraint(
            "status <> 'rejected' OR (rejected_by IS NOT NULL AND rejected_at IS NOT NULL)",
            name="rejected_fields",
        ),
    )

    ce_id: Mapped[uuid.UUID] = _fk("ce.id", ondelete="RESTRICT")
    version_number: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), server_default="draft")

    client_id: Mapped[uuid.UUID] = _fk("clients.id", ondelete="RESTRICT", index=True)
    project_name: Mapped[str] = mapped_column(String(300))
    sf_opportunity: Mapped[str | None] = mapped_column(String(100))
    business_unit: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)

    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    planning_mode: Mapped[str] = mapped_column(String(10))
    rate_year: Mapped[int] = mapped_column(Integer)  # anno del listino usato per le tariffe
    signed_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    created_by: Mapped[uuid.UUID] = _fk("users.id", ondelete="RESTRICT")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[uuid.UUID | None] = _fk("users.id", ondelete="RESTRICT", nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejected_by: Mapped[uuid.UUID | None] = _fk("users.id", ondelete="RESTRICT", nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    # Fotografia dei totali al momento dell'approvazione (ricavi, costi, margine, giornate).
    approved_totals: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    ce: Mapped[CE] = relationship(back_populates="versions")
    phases: Mapped[list["CEPhase"]] = relationship(
        back_populates="version",
        order_by="CEPhase.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    rates: Mapped[list["CEVersionRate"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    milestones: Mapped[list["CEMilestone"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


# Per ogni CE può esistere una sola versione non ancora approvata.
Index(
    "uq_ce_versions_one_open",
    CEVersion.ce_id,
    unique=True,
    postgresql_where=text("status IN ('draft', 'submitted', 'rejected')"),
)
Index("ix_ce_versions_status", CEVersion.status)
Index("ix_ce_versions_dates", CEVersion.start_date, CEVersion.end_date)
Index(
    "ix_ce_versions_project_name_trgm",
    CEVersion.project_name,
    postgresql_using="gin",
    postgresql_ops={"project_name": "gin_trgm_ops"},
)


class CEVersionRate(TimestampMixin, Base):
    """Tariffe giornaliere dei profili congelate nella versione del CE."""

    __tablename__ = "ce_version_rates"
    __table_args__ = (
        CheckConstraint("daily_price >= 0", name="price_non_negative"),
        CheckConstraint("daily_cost >= 0", name="cost_non_negative"),
    )

    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ce_versions.id", ondelete="CASCADE"), primary_key=True
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), primary_key=True
    )
    daily_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    daily_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class CEPhase(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "ce_phases"
    __table_args__ = (
        CheckConstraint("contingency_pct BETWEEN 0 AND 100", name="contingency_range"),
    )

    version_id: Mapped[uuid.UUID] = _fk("ce_versions.id", ondelete="CASCADE", index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(200))
    contingency_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default="0")

    version: Mapped[CEVersion] = relationship(back_populates="phases")
    lines: Mapped[list["CELine"]] = relationship(
        back_populates="phase",
        order_by="CELine.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class CELine(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "ce_lines"
    __table_args__ = (
        CheckConstraint(in_list("line_type", LINE_TYPES), name="line_type_valid"),
        CheckConstraint("hours IS NULL OR hours >= 0", name="hours_non_negative"),
        CheckConstraint(
            "external_cost IS NULL OR external_cost >= 0", name="external_cost_non_negative"
        ),
        CheckConstraint(
            "external_revenue IS NULL OR external_revenue >= 0",
            name="external_revenue_non_negative",
        ),
        # Riga interna: profilo obbligatorio, nessun costo/ricavo esterno.
        # Riga esterna: nessun profilo/collaboratore/ore/flag PM, costo e ricavo obbligatori.
        CheckConstraint(
            "(line_type = 'internal' AND profile_id IS NOT NULL "
            "AND external_cost IS NULL AND external_revenue IS NULL) "
            "OR (line_type = 'external' AND profile_id IS NULL AND employee_id IS NULL "
            "AND hours IS NULL AND NOT is_project_management "
            "AND external_cost IS NOT NULL AND external_revenue IS NOT NULL)",
            name="line_shape",
        ),
    )

    phase_id: Mapped[uuid.UUID] = _fk("ce_phases.id", ondelete="CASCADE", index=True)
    position: Mapped[int] = mapped_column(Integer)
    line_type: Mapped[str] = mapped_column(String(10))
    activity: Mapped[str] = mapped_column(String(300))
    profile_id: Mapped[uuid.UUID | None] = _fk(
        "profiles.id", ondelete="RESTRICT", nullable=True, index=True
    )
    employee_id: Mapped[uuid.UUID | None] = _fk(
        "employees.id", ondelete="RESTRICT", nullable=True, index=True
    )
    is_project_management: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))  # solo modalità "ore"
    external_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    external_revenue: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))

    phase: Mapped[CEPhase] = relationship(back_populates="lines")
    allocations: Mapped[list["CELineAllocation"]] = relationship(
        order_by="CELineAllocation.month", cascade="all, delete-orphan", passive_deletes=True
    )


class CELineAllocation(TimestampMixin, Base):
    """% di occupazione di una riga in un mese (solo modalità "percentuale")."""

    __tablename__ = "ce_line_allocations"
    __table_args__ = (
        CheckConstraint("allocation_pct BETWEEN 0 AND 100", name="allocation_pct_range"),
        CheckConstraint("EXTRACT(DAY FROM month) = 1", name="month_first_day"),
    )

    line_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ce_lines.id", ondelete="CASCADE"), primary_key=True
    )
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    allocation_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))


class CEMilestone(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "ce_milestones"
    __table_args__ = (
        UniqueConstraint("version_id", "month", "label"),
        CheckConstraint("EXTRACT(DAY FROM month) = 1", name="month_first_day"),
    )

    version_id: Mapped[uuid.UUID] = _fk("ce_versions.id", ondelete="CASCADE", index=True)
    month: Mapped[date] = mapped_column(Date)
    label: Mapped[str] = mapped_column(String(200))


class AuditLog(Base):
    """Registro delle modifiche: chi ha fatto cosa e quando."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    user_id: Mapped[uuid.UUID | None] = _fk("users.id", ondelete="SET NULL", nullable=True)
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(50))
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


Index("ix_audit_log_entity", AuditLog.entity_type, AuditLog.entity_id)


class EmailOutbox(UUIDPkMixin, TimestampMixin, Base):
    """Coda di invio email: un errore di Mailjet non blocca il workflow e si può ritentare."""

    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint(in_list("status", ("pending", "sent", "failed")), name="status_valid"),
    )

    type: Mapped[str] = mapped_column(String(50))
    recipient: Mapped[str] = mapped_column(String(320))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(10), server_default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
