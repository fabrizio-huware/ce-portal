"""Copia delle tariffe di un anno su altri anni (con adeguamento facoltativo in %).

Per ogni profilo con una tariffa nell'anno di partenza si crea o si **sovrascrive** quella degli
anni di arrivo; i profili senza tariffa nell'anno di partenza non si toccano. I CE già creati non
cambiano: hanno le tariffe congelate (si aggiornano con «Riallinea»).
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Profile, ProfileRate, User
from app.schemas.profiles import CopyRatesIn, CopyRatesItem, CopyRatesResult
from app.services import audit

CENT = Decimal("0.01")


class CopyRatesError(ValueError):
    pass


def _adjusted(value: Decimal, pct: Decimal) -> Decimal:
    return (value * (Decimal(100) + pct) / Decimal(100)).quantize(CENT, rounding=ROUND_HALF_UP)


def copy_rates(
    session: Session, body: CopyRatesIn, *, actor: User, dry_run: bool
) -> CopyRatesResult:
    years = sorted(set(body.to_years))
    if len(years) != len(body.to_years):
        raise CopyRatesError("Un anno di arrivo compare più di una volta")
    if body.from_year in years:
        raise CopyRatesError("L'anno di arrivo non può essere quello di partenza")
    if any(not 2000 <= y <= 2100 for y in years):
        raise CopyRatesError("Anno di arrivo fuori intervallo (2000-2100)")

    sources = session.execute(
        select(ProfileRate, Profile)
        .join(Profile, Profile.id == ProfileRate.profile_id)
        .where(ProfileRate.year == body.from_year)
        .order_by(Profile.sort_order, Profile.name)
    ).all()
    if not sources:
        raise CopyRatesError(f"Nessun profilo ha una tariffa nel {body.from_year}")

    result = CopyRatesResult(
        dry_run=dry_run, applied=not dry_run, from_year=body.from_year, to_years=years
    )
    for year in years:
        for source, profile in sources:
            price = _adjusted(source.daily_price, body.price_adjust_pct)
            cost = _adjusted(source.daily_cost, body.cost_adjust_pct)
            existing = session.get(ProfileRate, (profile.id, year))
            old_price = existing.daily_price if existing else None
            old_cost = existing.daily_cost if existing else None
            if existing is None:
                action = "created"
                if not dry_run:
                    session.add(
                        ProfileRate(
                            profile_id=profile.id, year=year, daily_price=price, daily_cost=cost
                        )
                    )
                    audit.record(
                        session,
                        actor,
                        "profile",
                        profile.id,
                        "create_rate",
                        {
                            "year": year,
                            "daily_price": price,
                            "daily_cost": cost,
                            "copied_from": body.from_year,
                        },
                    )
            elif existing.daily_price == price and existing.daily_cost == cost:
                action = "unchanged"
            else:
                action = "updated"
                if not dry_run:
                    changes = audit.apply_changes(
                        existing, {"daily_price": price, "daily_cost": cost}
                    )
                    audit.record(
                        session,
                        actor,
                        "profile",
                        profile.id,
                        "update_rate",
                        {"year": year, **changes, "copied_from": body.from_year},
                    )
            setattr(result, action, getattr(result, action) + 1)
            result.items.append(
                CopyRatesItem(
                    profile_id=profile.id,
                    profile_name=profile.name,
                    year=year,
                    action=action,
                    old_price=old_price,
                    old_cost=old_cost,
                    new_price=price,
                    new_cost=cost,
                )
            )
    if not dry_run:
        session.flush()
    return result
