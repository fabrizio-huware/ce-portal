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
    event,
    false,
    func,
    insert,
    select,
    true,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin, in_list

ROLES = ("admin", "presale", "viewer")
NON_WORKING_KINDS = ("holiday", "company_closure")
# Practice di sistema: la ricevono i collaboratori finché non se ne indica una.
# Non si rinomina né si disattiva.
DEFAULT_PRACTICE = "Da assegnare"


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


class Practice(UUIDPkMixin, TimestampMixin, Base):
    """Practice (area di competenza): ogni collaboratore ne ha una sola.

    Non si elimina: si disattiva.
    """

    __tablename__ = "practices"

    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())


# Unicità del nome senza distinzione tra maiuscole e minuscole.
Index("uq_practices_name_lower", func.lower(Practice.name), unique=True)


class Employee(UUIDPkMixin, TimestampMixin, Base):
    """Collaboratore aziendale (anagrafica separata dagli utenti dell'applicazione)."""

    __tablename__ = "employees"

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    default_profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), index=True
    )
    # Obbligatoria: a chi non ne ha una indicata si assegna «Da assegnare» (vedi sotto).
    practice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practices.id", ondelete="RESTRICT"), index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    netsuite_id: Mapped[str | None] = mapped_column(String(100))
    jira_account_id: Mapped[str | None] = mapped_column(String(100))


@event.listens_for(Employee, "before_insert")
def _default_practice(mapper, connection, employee: Employee) -> None:
    """Un collaboratore nasce sempre con una practice.

    Senza indicazione si usa «Da assegnare», creata se manca.
    """
    if employee.practice_id is not None:
        return
    found = connection.execute(
        select(Practice.id).where(func.lower(Practice.name) == DEFAULT_PRACTICE.lower())
    ).scalar()
    if found is None:
        found = connection.execute(
            insert(Practice).values(name=DEFAULT_PRACTICE).returning(Practice.id)
        ).scalar_one()
    employee.practice_id = found


class NonWorkingDay(UUIDPkMixin, TimestampMixin, Base):
    """Festività e chiusure aziendali (i weekend si calcolano nel codice)."""

    __tablename__ = "non_working_days"
    __table_args__ = (CheckConstraint(in_list("kind", NON_WORKING_KINDS), name="kind_valid"),)

    day: Mapped[date] = mapped_column(Date, unique=True)
    kind: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(200))
