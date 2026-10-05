"""Utenti, anagrafiche (clienti, collaboratori), listino profili e calendario."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
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
    false,
    func,
    true,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin, in_list

ROLES = ("admin", "presale", "viewer")
NON_WORKING_KINDS = ("holiday", "company_closure")


class User(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(in_list("role", ROLES), name="role_valid"),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Client(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "clients"

    name: Mapped[str] = mapped_column(String(300))
    address: Mapped[str | None] = mapped_column(Text)
    external_ref: Mapped[str | None] = mapped_column(String(100))  # predisposto per NetSuite
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())


# Unicità del nome cliente senza distinzione tra maiuscole e minuscole.
Index("uq_clients_name_lower", func.lower(Client.name), unique=True)
Index(
    "ix_clients_name_trgm",
    Client.name,
    postgresql_using="gin",
    postgresql_ops={"name": "gin_trgm_ops"},
)


class Profile(UUIDPkMixin, TimestampMixin, Base):
    """Profilo professionale del listino (Partner, Manager, ...)."""

    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            "billability_target IS NULL OR (billability_target BETWEEN 0 AND 100)",
            name="billability_range",
        ),
    )

    name: Mapped[str] = mapped_column(String(100), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    # Profilo "Esterni": le sue righe confluiscono in Servizi Esterni.
    is_external: Mapped[bool] = mapped_column(Boolean, server_default=false())
    sort_order: Mapped[int] = mapped_column(Integer, server_default="0")
    band: Mapped[str | None] = mapped_column(String(10))  # facoltativo, non usato nei calcoli
    billability_target: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # idem


class ProfileRate(TimestampMixin, Base):
    """Tariffe giornaliere di un profilo per anno di validità."""

    __tablename__ = "profile_rates"
    __table_args__ = (
        CheckConstraint("year BETWEEN 2000 AND 2100", name="year_range"),
        CheckConstraint("daily_price >= 0", name="price_non_negative"),
        CheckConstraint("daily_cost >= 0", name="cost_non_negative"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), primary_key=True
    )
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    daily_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # prezzo di vendita / giorno
    daily_cost: Mapped[Decimal] = mapped_column(Numeric(14, 2))  # costo interno / giorno


class Employee(UUIDPkMixin, TimestampMixin, Base):
    """Collaboratore aziendale (anagrafica separata dagli utenti dell'applicazione)."""

    __tablename__ = "employees"

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    default_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    netsuite_id: Mapped[str | None] = mapped_column(String(100))
    jira_account_id: Mapped[str | None] = mapped_column(String(100))


class NonWorkingDay(UUIDPkMixin, TimestampMixin, Base):
    """Festività e chiusure aziendali (i weekend si calcolano nel codice)."""

    __tablename__ = "non_working_days"
    __table_args__ = (CheckConstraint(in_list("kind", NON_WORKING_KINDS), name="kind_valid"),)

    day: Mapped[date] = mapped_column(Date, unique=True)
    kind: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(200))
