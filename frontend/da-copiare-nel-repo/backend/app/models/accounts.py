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
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPkMixin, in_list

ROLES = ("admin", "presale", "bu_manager", "viewer")
# Chi vede costi e margini e lavora sui CE: admin e presale, più il responsabile di business unit.
EDITOR_ROLES = ("admin", "presale", "bu_manager")
# Chi può essere autore di un CE (modifica i propri).
AUTHOR_ROLES = ("presale", "bu_manager")
NON_WORKING_KINDS = ("holiday", "company_closure")
# Practice di sistema: la ricevono i collaboratori finché non se ne indica una.
# Non si rinomina né si disattiva.
DEFAULT_PRACTICE = "Da assegnare"
DEFAULT_BUSINESS_UNIT = "Da assegnare"  # business unit di sistema: accoglie i dati esistenti
# Cosa può fare un'integrazione (programma esterno con un account di servizio Google).
INTEGRATION_PERMISSIONS = ("create", "edit", "read", "export")


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
    # Utente di servizio collegato a un'integrazione: è l'autore dei CE creati dal programma
    # esterno. Non accede mai con il login: si identifica solo con il token Google del suo
    # account di servizio.
    is_service: Mapped[bool] = mapped_column(Boolean, server_default=false())
    # Business unit di un presale o di un responsabile (vede i CE che la coinvolgono).
    business_unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="RESTRICT"), index=True
    )


class Integration(UUIDPkMixin, TimestampMixin, Base):
    """Programma esterno autorizzato ad agire con un account di servizio Google.

    L'amministratore registra l'email dell'account di servizio e i permessi; ogni chiamata porta
    un ID token Google che il portale verifica a ogni richiesta (nessun segreto è conservato qui).
    Non si elimina: si disattiva.
    """

    __tablename__ = "integrations"
    __table_args__ = (
        CheckConstraint(
            "service_account_email = lower(service_account_email)", name="sa_email_lowercase"
        ),
        CheckConstraint(
            "permissions <@ ARRAY['create','edit','read','export']::varchar[]",
            name="permissions_valid",
        ),
    )

    name: Mapped[str] = mapped_column(String(100))
    service_account_email: Mapped[str] = mapped_column(String(320), unique=True)
    # Identificativo univoco dell'account di servizio: si lega alla prima chiamata, come
    # google_sub per le persone.
    service_account_sub: Mapped[str | None] = mapped_column(String(255), unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), unique=True
    )
    permissions: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    # Ultimo utilizzo; serve anche al limite di una richiesta al secondo.
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )


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


class BusinessUnit(UUIDPkMixin, TimestampMixin, Base):
    """Business unit: sta sopra le practice (business unit → practice → collaboratori).

    Decide anche chi vede un CE. Non si elimina: si disattiva.
    """

    __tablename__ = "business_units"

    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())


# Unicità del nome senza distinzione tra maiuscole e minuscole.
Index("uq_business_units_name_lower", func.lower(BusinessUnit.name), unique=True)


def _default_business_unit_id(connection) -> uuid.UUID:
    """Id di «Da assegnare», creata se manca."""
    found = connection.execute(
        select(BusinessUnit.id).where(
            func.lower(BusinessUnit.name) == DEFAULT_BUSINESS_UNIT.lower()
        )
    ).scalar()
    if found is None:
        found = connection.execute(
            insert(BusinessUnit).values(name=DEFAULT_BUSINESS_UNIT).returning(BusinessUnit.id)
        ).scalar_one()
    return found


class Practice(UUIDPkMixin, TimestampMixin, Base):
    """Practice (area di competenza): ogni collaboratore ne ha una, e sta in una sola business unit.

    Non si elimina: si disattiva.
    """

    __tablename__ = "practices"

    name: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
    business_unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("business_units.id", ondelete="RESTRICT"), index=True
    )


# Unicità del nome senza distinzione tra maiuscole e minuscole.
Index("uq_practices_name_lower", func.lower(Practice.name), unique=True)


@event.listens_for(Practice, "before_insert")
def _default_business_unit(mapper, connection, practice: Practice) -> None:
    """Una practice nasce sempre in una business unit: senza indicazione, in «Da assegnare»."""
    if practice.business_unit_id is None:
        practice.business_unit_id = _default_business_unit_id(connection)


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
            insert(Practice)
            .values(name=DEFAULT_PRACTICE, business_unit_id=_default_business_unit_id(connection))
            .returning(Practice.id)
        ).scalar_one()
    employee.practice_id = found


class NonWorkingDay(UUIDPkMixin, TimestampMixin, Base):
    """Festività e chiusure aziendali (i weekend si calcolano nel codice)."""

    __tablename__ = "non_working_days"
    __table_args__ = (CheckConstraint(in_list("kind", NON_WORKING_KINDS), name="kind_valid"),)

    day: Mapped[date] = mapped_column(Date, unique=True)
    kind: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(String(200))
