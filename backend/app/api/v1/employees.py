import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select

from app.api.deps import (
    AdminUser,
    EditorUser,
    PageDep,
    SessionDep,
    get_or_404,
    like_pattern,
    paginate,
)
from app.models import Employee, Profile
from app.schemas.common import Page
from app.schemas.employees import EmployeeCreate, EmployeeOut, EmployeeUpdate
from app.schemas.imports import ImportResult
from app.services import audit
from app.services.imports import import_employees, read_upload

router = APIRouter(prefix="/employees", tags=["Collaboratori"])


def _to_out(session, employees: list[Employee]) -> list[EmployeeOut]:
    ids = {e.default_profile_id for e in employees}
    names = (
        dict(session.execute(select(Profile.id, Profile.name).where(Profile.id.in_(ids))).all())
        if ids
        else {}
    )
    return [
        EmployeeOut(
            id=e.id,
            first_name=e.first_name,
            last_name=e.last_name,
            default_profile_id=e.default_profile_id,
            profile_name=names[e.default_profile_id],
            is_active=e.is_active,
            netsuite_id=e.netsuite_id,
            jira_account_id=e.jira_account_id,
        )
        for e in employees
    ]


def _require_active_profile(session, profile_id: uuid.UUID) -> None:
    profile = session.get(Profile, profile_id)
    if profile is None:
        raise HTTPException(422, "Profilo non trovato")
    if not profile.is_active:
        raise HTTPException(422, "Il profilo selezionato non è attivo")


def _name_taken(session, first: str, last: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(Employee.id).where(
        func.lower(Employee.first_name) == first.lower(),
        func.lower(Employee.last_name) == last.lower(),
    )
    if exclude_id:
        stmt = stmt.where(Employee.id != exclude_id)
    return session.scalar(stmt) is not None


@router.get("", response_model=Page[EmployeeOut], summary="Elenco collaboratori")
def list_employees(
    user: EditorUser,
    session: SessionDep,
    params: PageDep,
    q: str | None = None,
    is_active: bool | None = None,
    profile_id: uuid.UUID | None = None,
) -> Page[EmployeeOut]:
    stmt = select(Employee).order_by(
        func.lower(Employee.last_name), func.lower(Employee.first_name)
    )
    if q:
        p = like_pattern(q)
        full = func.concat(Employee.first_name, " ", Employee.last_name)
        stmt = stmt.where(
            or_(
                Employee.first_name.ilike(p, escape="\\"),
                Employee.last_name.ilike(p, escape="\\"),
                full.ilike(p, escape="\\"),
            )
        )
    if is_active is not None:
        stmt = stmt.where(Employee.is_active == is_active)
    if profile_id:
        stmt = stmt.where(Employee.default_profile_id == profile_id)
    rows, total = paginate(session, stmt, params)
    return Page(items=_to_out(session, rows), total=total, limit=params.limit, offset=params.offset)


@router.post("", response_model=EmployeeOut, status_code=201, summary="Crea un collaboratore")
def create_employee(body: EmployeeCreate, admin: AdminUser, session: SessionDep) -> EmployeeOut:
    _require_active_profile(session, body.default_profile_id)
    if _name_taken(session, body.first_name, body.last_name):
        raise HTTPException(409, "Esiste già un collaboratore con questo nome e cognome")
    employee = Employee(**body.model_dump())
    session.add(employee)
    session.flush()
    audit.record(session, admin, "employee", employee.id, "create", body.model_dump())
    session.commit()
    return _to_out(session, [employee])[0]


@router.post(
    "/import",
    response_model=ImportResult,
    summary="Importa collaboratori da CSV",
    responses={
        422: {"model": ImportResult, "description": "File non valido: nulla è stato importato"}
    },
)
def import_employees_csv(
    file: UploadFile,
    admin: AdminUser,
    session: SessionDep,
    dry_run: Annotated[bool, Query(description="Se true (default) mostra solo l'anteprima")] = True,
):
    """Colonne: nome; cognome; profilo; attivo (facoltative: netsuite_id, jira_account_id)."""
    result = import_employees(session, read_upload(file), actor=admin, dry_run=dry_run)
    if result.errors and not dry_run:
        return JSONResponse(status_code=422, content=result.model_dump(mode="json"))
    if result.applied:
        session.commit()
    return result


@router.get("/{employee_id}", response_model=EmployeeOut, summary="Dettaglio collaboratore")
def get_employee(employee_id: uuid.UUID, user: EditorUser, session: SessionDep) -> EmployeeOut:
    return _to_out(session, [get_or_404(session, Employee, employee_id, "Collaboratore")])[0]


@router.patch("/{employee_id}", response_model=EmployeeOut, summary="Modifica un collaboratore")
def update_employee(
    employee_id: uuid.UUID, body: EmployeeUpdate, admin: AdminUser, session: SessionDep
) -> EmployeeOut:
    employee = get_or_404(session, Employee, employee_id, "Collaboratore")
    values = body.model_dump(exclude_unset=True)
    for required in ("first_name", "last_name", "default_profile_id", "is_active"):
        if required in values and values[required] is None:
            raise HTTPException(422, f"Il campo {required} non può essere nullo")
    if (
        "default_profile_id" in values
        and values["default_profile_id"] != employee.default_profile_id
    ):
        _require_active_profile(session, values["default_profile_id"])
    first = values.get("first_name", employee.first_name)
    last = values.get("last_name", employee.last_name)
    if ("first_name" in values or "last_name" in values) and _name_taken(
        session, first, last, exclude_id=employee.id
    ):
        raise HTTPException(409, "Esiste già un collaboratore con questo nome e cognome")
    changes = audit.apply_changes(employee, values)
    if changes:
        audit.record(session, admin, "employee", employee.id, "update", changes)
        session.commit()
    return _to_out(session, [employee])[0]
