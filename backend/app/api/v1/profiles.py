import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.api.deps import AdminUser, EditorUser, SessionDep, get_or_404
from app.models import Profile, ProfileRate
from app.schemas.imports import ImportResult
from app.schemas.profiles import (
    ProfileCreate,
    ProfileOut,
    ProfileUpdate,
    RateOut,
    RateUpsert,
)
from app.services import audit
from app.services.imports import import_rates, read_upload

router = APIRouter(prefix="/profiles", tags=["Profili e tariffe"])

Year = Annotated[int, Path(ge=2000, le=2100)]


def _to_out(session, profiles: list[Profile]) -> list[ProfileOut]:
    ids = [p.id for p in profiles]
    by_profile: dict[uuid.UUID, list[RateOut]] = {i: [] for i in ids}
    if ids:
        rates = session.scalars(
            select(ProfileRate).where(ProfileRate.profile_id.in_(ids)).order_by(ProfileRate.year)
        )
        for rate in rates:
            by_profile[rate.profile_id].append(RateOut.model_validate(rate))
    return [
        ProfileOut(
            id=p.id,
            name=p.name,
            is_active=p.is_active,
            sort_order=p.sort_order,
            band=p.band,
            billability_target=p.billability_target,
            rates=by_profile[p.id],
        )
        for p in profiles
    ]


def _name_taken(session, name: str, exclude_id: uuid.UUID | None = None) -> bool:
    stmt = select(Profile.id).where(func.lower(Profile.name) == name.lower())
    if exclude_id:
        stmt = stmt.where(Profile.id != exclude_id)
    return session.scalar(stmt) is not None


@router.get("", response_model=list[ProfileOut], summary="Listino: profili con tariffe per anno")
def list_profiles(
    user: EditorUser, session: SessionDep, is_active: bool | None = None
) -> list[ProfileOut]:
    stmt = select(Profile).order_by(Profile.sort_order, func.lower(Profile.name))
    if is_active is not None:
        stmt = stmt.where(Profile.is_active == is_active)
    return _to_out(session, list(session.scalars(stmt).all()))


@router.post("", response_model=ProfileOut, status_code=201, summary="Crea un profilo")
def create_profile(body: ProfileCreate, admin: AdminUser, session: SessionDep) -> ProfileOut:
    if _name_taken(session, body.name):
        raise HTTPException(409, "Esiste già un profilo con questo nome")
    profile = Profile(**body.model_dump())
    session.add(profile)
    session.flush()
    audit.record(session, admin, "profile", profile.id, "create", body.model_dump())
    session.commit()
    return _to_out(session, [profile])[0]


@router.post(
    "/import-rates",
    response_model=ImportResult,
    summary="Importa il listino da CSV",
    responses={
        422: {"model": ImportResult, "description": "File non valido: nulla è stato importato"}
    },
)
def import_rates_csv(
    file: UploadFile,
    admin: AdminUser,
    session: SessionDep,
    dry_run: Annotated[bool, Query(description="Se true (default) mostra solo l'anteprima")] = True,
):
    """Colonne: profilo; anno; prezzo_giorno; costo_giorno. Crea i profili mancanti."""
    result = import_rates(session, read_upload(file), actor=admin, dry_run=dry_run)
    if result.errors and not dry_run:
        return JSONResponse(status_code=422, content=result.model_dump(mode="json"))
    if result.applied:
        session.commit()
    return result


@router.get("/{profile_id}", response_model=ProfileOut, summary="Dettaglio profilo")
def get_profile(profile_id: uuid.UUID, user: EditorUser, session: SessionDep) -> ProfileOut:
    return _to_out(session, [get_or_404(session, Profile, profile_id, "Profilo")])[0]


@router.patch("/{profile_id}", response_model=ProfileOut, summary="Modifica un profilo")
def update_profile(
    profile_id: uuid.UUID, body: ProfileUpdate, admin: AdminUser, session: SessionDep
) -> ProfileOut:
    profile = get_or_404(session, Profile, profile_id, "Profilo")
    values = body.model_dump(exclude_unset=True)
    for required in ("name", "is_active", "sort_order"):
        if required in values and values[required] is None:
            raise HTTPException(422, f"Il campo {required} non può essere nullo")
    if "name" in values and _name_taken(session, values["name"], exclude_id=profile.id):
        raise HTTPException(409, "Esiste già un profilo con questo nome")
    changes = audit.apply_changes(profile, values)
    if changes:
        audit.record(session, admin, "profile", profile.id, "update", changes)
        session.commit()
    return _to_out(session, [profile])[0]


@router.put(
    "/{profile_id}/rates/{year}", response_model=RateOut, summary="Imposta la tariffa di un anno"
)
def upsert_rate(
    profile_id: uuid.UUID, year: Year, body: RateUpsert, admin: AdminUser, session: SessionDep
) -> ProfileRate:
    """Crea o aggiorna la tariffa. I CE esistenti non cambiano: hanno le tariffe congelate."""
    get_or_404(session, Profile, profile_id, "Profilo")
    rate = session.get(ProfileRate, (profile_id, year))
    if rate is None:
        rate = ProfileRate(profile_id=profile_id, year=year, **body.model_dump())
        session.add(rate)
        audit.record(
            session,
            admin,
            "profile",
            profile_id,
            "create_rate",
            {"year": year, **body.model_dump()},
        )
    else:
        changes = audit.apply_changes(rate, body.model_dump())
        if changes:
            audit.record(
                session, admin, "profile", profile_id, "update_rate", {"year": year, **changes}
            )
    session.commit()
    return rate


@router.delete(
    "/{profile_id}/rates/{year}", status_code=204, summary="Elimina la tariffa di un anno"
)
def delete_rate(
    profile_id: uuid.UUID, year: Year, admin: AdminUser, session: SessionDep
) -> Response:
    rate = session.get(ProfileRate, (profile_id, year))
    if rate is None:
        raise HTTPException(404, "Tariffa non trovata")
    audit.record(
        session,
        admin,
        "profile",
        profile_id,
        "delete_rate",
        {"year": year, "daily_price": rate.daily_price, "daily_cost": rate.daily_cost},
    )
    session.delete(rate)
    session.commit()
    return Response(status_code=204)
