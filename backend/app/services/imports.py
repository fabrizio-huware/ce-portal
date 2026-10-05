"""Import CSV a due fasi (anteprima / conferma) con regola "tutto o niente"."""

from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Employee, NonWorkingDay, Profile, ProfileRate, User
from app.schemas.imports import ImportErrorItem, ImportResult
from app.services import audit
from app.services.csv_utils import (
    CsvFileError,
    CsvRow,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_int,
    read_csv,
)


def read_upload(file: UploadFile) -> bytes:
    """Legge il file caricato, rifiutando quelli troppo grandi senza caricarli in memoria."""
    content = file.file.read(1_000_001)
    return content


@dataclass
class Tally:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    extra: dict[str, int] = field(default_factory=dict)


@dataclass
class Plan:
    """Righe validate e pronte da applicare, più gli errori trovati."""

    rows: list = field(default_factory=list)
    errors: list[ImportErrorItem] = field(default_factory=list)

    def error(self, line: int | None, message: str) -> None:
        self.errors.append(ImportErrorItem(line=line, message=message))


def _clean(text: str) -> str:
    return " ".join(text.split())


def _run(
    session: Session,
    content: bytes,
    *,
    entity: str,
    columns: dict[str, tuple[str, ...]],
    required: set[str],
    validate: Callable[[list[CsvRow], Plan], None],
    apply: Callable[[Session, Plan], Tally],
    actor: User,
    dry_run: bool,
) -> ImportResult:
    try:
        rows = read_csv(content, columns, required)
    except CsvFileError as exc:
        return ImportResult(
            dry_run=dry_run, applied=False, errors=[ImportErrorItem(message=str(exc))]
        )

    plan = Plan()
    validate(rows, plan)
    if plan.errors:
        return ImportResult(
            dry_run=dry_run, applied=False, total_rows=len(rows), errors=plan.errors
        )

    # Le modifiche avvengono in un savepoint: in anteprima vengono annullate, così i conteggi
    # mostrati sono esattamente quelli che si otterranno confermando.
    savepoint = session.begin_nested()
    try:
        tally = apply(session, plan)
    except Exception:
        savepoint.rollback()
        raise
    if dry_run:
        savepoint.rollback()
    else:
        savepoint.commit()
        audit.record(
            session,
            actor,
            entity,
            None,
            "import",
            {
                "rows": len(rows),
                "created": tally.created,
                "updated": tally.updated,
                "unchanged": tally.unchanged,
                **tally.extra,
            },
        )
    return ImportResult(
        dry_run=dry_run,
        applied=not dry_run,
        total_rows=len(rows),
        created=tally.created,
        updated=tally.updated,
        unchanged=tally.unchanged,
        extra=tally.extra,
    )


# ---------------------------------------------------------------- collaboratori
def import_employees(
    session: Session, content: bytes, *, actor: User, dry_run: bool
) -> ImportResult:
    profiles = {p.name.lower(): p for p in session.scalars(select(Profile))}

    def validate(rows: list[CsvRow], plan: Plan) -> None:
        seen: dict[tuple[str, str], int] = {}
        for row in rows:
            v = row.values
            first, last = _clean(v["nome"]), _clean(v["cognome"])
            if not first or not last:
                plan.error(row.line, "Nome e cognome sono obbligatori")
                continue
            key = (first.lower(), last.lower())
            if key in seen:
                plan.error(row.line, f"{first} {last} compare già alla riga {seen[key]}")
                continue
            seen[key] = row.line
            profile = profiles.get(_clean(v["profilo"]).lower())
            if profile is None:
                plan.error(row.line, f"Profilo sconosciuto: '{v['profilo']}'")
                continue
            if not profile.is_active:
                plan.error(row.line, f"Il profilo '{profile.name}' non è attivo")
                continue
            try:
                active = parse_bool(v.get("attivo", ""), default=True) if "attivo" in v else None
            except ValueError as exc:
                plan.error(row.line, str(exc))
                continue
            plan.rows.append(
                {
                    "first": first,
                    "last": last,
                    "profile_id": profile.id,
                    "is_active": active,
                    "netsuite_id": v.get("netsuite_id") or None if "netsuite_id" in v else ...,
                    "jira_account_id": (
                        v.get("jira_account_id") or None if "jira_account_id" in v else ...
                    ),
                }
            )

    def apply(session: Session, plan: Plan) -> Tally:
        existing = {
            (e.first_name.lower(), e.last_name.lower()): e
            for e in session.scalars(select(Employee))
        }
        tally = Tally()
        for r in plan.rows:
            employee = existing.get((r["first"].lower(), r["last"].lower()))
            if employee is None:
                session.add(
                    Employee(
                        first_name=r["first"],
                        last_name=r["last"],
                        default_profile_id=r["profile_id"],
                        is_active=True if r["is_active"] is None else r["is_active"],
                        netsuite_id=None if r["netsuite_id"] is ... else r["netsuite_id"],
                        jira_account_id=None
                        if r["jira_account_id"] is ...
                        else r["jira_account_id"],
                    )
                )
                tally.created += 1
                continue
            new = {"default_profile_id": r["profile_id"]}
            if r["is_active"] is not None:
                new["is_active"] = r["is_active"]
            if r["netsuite_id"] is not ...:
                new["netsuite_id"] = r["netsuite_id"]
            if r["jira_account_id"] is not ...:
                new["jira_account_id"] = r["jira_account_id"]
            if audit.apply_changes(employee, new):
                tally.updated += 1
            else:
                tally.unchanged += 1
        session.flush()
        return tally

    return _run(
        session,
        content,
        entity="employees",
        columns={
            "nome": ("first_name", "name"),
            "cognome": ("last_name", "surname"),
            "profilo": ("profile", "ruolo"),
            "attivo": ("active", "is_active"),
            "netsuite_id": ("netsuite",),
            "jira_account_id": ("jira", "jira_id"),
        },
        required={"nome", "cognome", "profilo"},
        validate=validate,
        apply=apply,
        actor=actor,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------- listino
def import_rates(session: Session, content: bytes, *, actor: User, dry_run: bool) -> ImportResult:
    def validate(rows: list[CsvRow], plan: Plan) -> None:
        seen: dict[tuple[str, int], int] = {}
        for row in rows:
            v = row.values
            name = _clean(v["profilo"])
            if not name:
                plan.error(row.line, "Il profilo è obbligatorio")
                continue
            try:
                year = parse_int(v["anno"])
                price = parse_decimal(v["prezzo_giorno"])
                cost = parse_decimal(v["costo_giorno"])
            except ValueError as exc:
                plan.error(row.line, str(exc))
                continue
            if not 2000 <= year <= 2100:
                plan.error(row.line, f"Anno fuori intervallo: {year}")
                continue
            if price < 0 or cost < 0:
                plan.error(row.line, "Prezzo e costo non possono essere negativi")
                continue
            key = (name.lower(), year)
            if key in seen:
                plan.error(row.line, f"{name} {year} compare già alla riga {seen[key]}")
                continue
            seen[key] = row.line
            external = None
            if "esterno" in v and v["esterno"].strip():
                try:
                    external = parse_bool(v["esterno"], default=False)
                except ValueError as exc:
                    plan.error(row.line, str(exc))
                    continue
            plan.rows.append(
                {"name": name, "year": year, "price": price, "cost": cost, "external": external}
            )

    def apply(session: Session, plan: Plan) -> Tally:
        profiles = {p.name.lower(): p for p in session.scalars(select(Profile))}
        next_order = (session.scalar(select(func.max(Profile.sort_order))) or 0) + 10
        tally = Tally(extra={"profili_creati": 0, "profili_aggiornati": 0})
        for r in plan.rows:
            profile = profiles.get(r["name"].lower())
            if profile is None:
                # Senza la colonna "esterno", un profilo chiamato "Esterni" è esterno.
                external = (
                    r["external"] if r["external"] is not None else r["name"].lower() == "esterni"
                )
                profile = Profile(name=r["name"], sort_order=next_order, is_external=external)
                next_order += 10
                session.add(profile)
                session.flush()
                profiles[r["name"].lower()] = profile
                tally.extra["profili_creati"] += 1
            elif r["external"] is not None and profile.is_external != r["external"]:
                profile.is_external = r["external"]
                tally.extra["profili_aggiornati"] += 1
            rate = session.get(ProfileRate, (profile.id, r["year"]))
            if rate is None:
                session.add(
                    ProfileRate(
                        profile_id=profile.id,
                        year=r["year"],
                        daily_price=r["price"],
                        daily_cost=r["cost"],
                    )
                )
                tally.created += 1
            elif audit.apply_changes(rate, {"daily_price": r["price"], "daily_cost": r["cost"]}):
                tally.updated += 1
            else:
                tally.unchanged += 1
        session.flush()
        return tally

    return _run(
        session,
        content,
        entity="profile_rates",
        columns={
            "profilo": ("profile", "ruolo"),
            "anno": ("year",),
            "prezzo_giorno": ("prezzo", "fee", "price_per_day", "tariffa_vendita"),
            "costo_giorno": ("costo", "cost_per_day", "tariffa_interna"),
            "esterno": ("external", "is_external"),
        },
        required={"profilo", "anno", "prezzo_giorno", "costo_giorno"},
        validate=validate,
        apply=apply,
        actor=actor,
        dry_run=dry_run,
    )


# ---------------------------------------------------------------- chiusure aziendali
def import_closures(
    session: Session, content: bytes, *, actor: User, dry_run: bool
) -> ImportResult:
    def validate(rows: list[CsvRow], plan: Plan) -> None:
        seen: dict = {}
        for row in rows:
            v = row.values
            try:
                day = parse_date(v["data"])
            except ValueError as exc:
                plan.error(row.line, str(exc))
                continue
            if not 2000 <= day.year <= 2100:
                plan.error(row.line, f"Anno fuori intervallo: {day.year}")
                continue
            if day in seen:
                plan.error(row.line, f"La data {day:%d/%m/%Y} compare già alla riga {seen[day]}")
                continue
            seen[day] = row.line
            plan.rows.append(
                {
                    "day": day,
                    "description": _clean(v.get("descrizione", "")) or "Chiusura aziendale",
                }
            )

    def apply(session: Session, plan: Plan) -> Tally:
        existing = set(session.scalars(select(NonWorkingDay.day)))
        tally = Tally()
        for r in plan.rows:
            if r["day"] in existing:  # già non lavorativo (festività o chiusura): nessuna modifica
                tally.unchanged += 1
                continue
            session.add(
                NonWorkingDay(
                    day=r["day"], kind="company_closure", description=r["description"][:200]
                )
            )
            tally.created += 1
        session.flush()
        return tally

    return _run(
        session,
        content,
        entity="non_working_days",
        columns={"data": ("date", "giorno"), "descrizione": ("description", "note")},
        required={"data"},
        validate=validate,
        apply=apply,
        actor=actor,
        dry_run=dry_run,
    )
