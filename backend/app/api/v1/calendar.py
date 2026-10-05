import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.api.deps import AdminUser, EditorUser, SessionDep, get_or_404
from app.db.calendar import holidays_for_year
from app.models import NonWorkingDay
from app.schemas.calendar import (
    GenerateHolidaysRequest,
    GenerateHolidaysResponse,
    NonWorkingDayCreate,
    NonWorkingDayOut,
    NonWorkingDayUpdate,
)
from app.schemas.imports import ImportResult
from app.services import audit
from app.services.imports import import_closures, read_upload

router = APIRouter(prefix="/calendar", tags=["Calendario"])


@router.get("", response_model=list[NonWorkingDayOut], summary="Festività e chiusure aziendali")
def list_days(
    user: EditorUser,
    session: SessionDep,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> list[NonWorkingDay]:
    stmt = select(NonWorkingDay).order_by(NonWorkingDay.day)
    if year:
        stmt = stmt.where(
            NonWorkingDay.day >= date(year, 1, 1), NonWorkingDay.day <= date(year, 12, 31)
        )
    return list(session.scalars(stmt).all())


@router.post("", response_model=NonWorkingDayOut, status_code=201, summary="Aggiunge un giorno")
def create_day(body: NonWorkingDayCreate, admin: AdminUser, session: SessionDep) -> NonWorkingDay:
    if not 2000 <= body.day.year <= 2100:
        raise HTTPException(422, "Anno fuori intervallo")
    if session.scalar(select(NonWorkingDay.id).where(NonWorkingDay.day == body.day)):
        raise HTTPException(409, "Questa data è già presente nel calendario")
    day = NonWorkingDay(**body.model_dump())
    session.add(day)
    session.flush()
    audit.record(session, admin, "non_working_day", day.id, "create", body.model_dump())
    session.commit()
    return day


@router.post(
    "/import",
    response_model=ImportResult,
    summary="Importa le chiusure aziendali da CSV",
    responses={
        422: {"model": ImportResult, "description": "File non valido: nulla è stato importato"}
    },
)
def import_closures_csv(
    file: UploadFile,
    admin: AdminUser,
    session: SessionDep,
    dry_run: Annotated[bool, Query(description="Se true (default) mostra solo l'anteprima")] = True,
):
    """Colonne: data; descrizione (facoltativa). Le date già presenti restano invariate."""
    result = import_closures(session, read_upload(file), actor=admin, dry_run=dry_run)
    if result.errors and not dry_run:
        return JSONResponse(status_code=422, content=result.model_dump(mode="json"))
    if result.applied:
        session.commit()
    return result


@router.post(
    "/generate-holidays",
    response_model=GenerateHolidaysResponse,
    summary="Genera le festività nazionali di un anno",
)
def generate_holidays(
    body: GenerateHolidaysRequest, admin: AdminUser, session: SessionDep
) -> GenerateHolidaysResponse:
    """Aggiunge le festività mancanti (include Pasqua, Lunedì dell'Angelo e Sant'Ambrogio)."""
    existing = set(session.scalars(select(NonWorkingDay.day)))
    created = 0
    for day, description in holidays_for_year(body.year):
        if day not in existing:
            session.add(NonWorkingDay(day=day, kind="holiday", description=description))
            created += 1
    audit.record(
        session,
        admin,
        "non_working_day",
        None,
        "generate_holidays",
        {"year": body.year, "created": created},
    )
    session.commit()
    return GenerateHolidaysResponse(year=body.year, created=created)


@router.patch("/{day_id}", response_model=NonWorkingDayOut, summary="Modifica un giorno")
def update_day(
    day_id: uuid.UUID, body: NonWorkingDayUpdate, admin: AdminUser, session: SessionDep
) -> NonWorkingDay:
    day = get_or_404(session, NonWorkingDay, day_id, "Giorno")
    values = body.model_dump(exclude_unset=True)
    if any(v is None for v in values.values()):
        raise HTTPException(422, "I campi indicati non possono essere nulli")
    changes = audit.apply_changes(day, values)
    if changes:
        audit.record(session, admin, "non_working_day", day.id, "update", changes)
        session.commit()
    return day


@router.delete("/{day_id}", status_code=204, summary="Elimina un giorno dal calendario")
def delete_day(day_id: uuid.UUID, admin: AdminUser, session: SessionDep) -> Response:
    day = get_or_404(session, NonWorkingDay, day_id, "Giorno")
    audit.record(
        session,
        admin,
        "non_working_day",
        day.id,
        "delete",
        {"day": day.day, "kind": day.kind, "description": day.description},
    )
    session.delete(day)
    session.commit()
    return Response(status_code=204)
