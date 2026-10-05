"""Un CE completo si salva e si rilegge correttamente attraverso le relazioni dei modelli."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.models import CE, CELine, CELineAllocation, CEMilestone, CEPhase, CEVersion, CEVersionRate
from tests.factories import make_client, make_profile, make_user


def test_full_ce_can_be_saved_and_reloaded(session):
    user, client, profile = make_user(session), make_client(session), make_profile(session)

    ce = CE(code="PS-MENAR-AI-GECX", created_by=user.id)
    version = CEVersion(
        version_number=1,
        client_id=client.id,
        project_name="Menarini - Virtual Assistant",
        sf_opportunity="006XX0000012345",
        business_unit="AI",
        start_date=date(2026, 1, 20),
        end_date=date(2026, 4, 20),
        planning_mode="percent",
        rate_year=2026,
        created_by=user.id,
        rates=[CEVersionRate(profile_id=profile.id, daily_price=850, daily_cost=330)],
        milestones=[CEMilestone(month=date(2026, 4, 1), label="GoLive")],
        phases=[
            CEPhase(
                position=2,
                name="Delivery",
                contingency_pct=Decimal("10"),
                lines=[
                    CELine(
                        position=1,
                        activity="Sviluppo",
                        profile_id=profile.id,
                        allocations=[
                            CELineAllocation(month=date(2026, 2, 1), allocation_pct=50),
                            CELineAllocation(month=date(2026, 1, 1), allocation_pct=25),
                        ],
                    ),
                    CELine(position=2, activity="Licenze", profile_id=profile.id, hours=8),
                ],
            ),
            CEPhase(position=1, name="Analisi", contingency_pct=0),
        ],
    )
    ce.versions.append(version)
    session.add(ce)
    session.flush()
    session.expire_all()

    loaded = session.scalars(select(CE).where(CE.code == "PS-MENAR-AI-GECX")).one()
    v = loaded.versions[0]
    assert [p.name for p in v.phases] == ["Analisi", "Delivery"]  # ordinate per position
    delivery = v.phases[1]
    assert delivery.contingency_pct == Decimal("10.00")
    assert [line.activity for line in delivery.lines] == ["Sviluppo", "Licenze"]
    months = [a.month for a in delivery.lines[0].allocations]
    assert months == [date(2026, 1, 1), date(2026, 2, 1)]  # ordinate per mese
    assert delivery.lines[1].hours == Decimal("8.00")
    assert v.rates[0].daily_cost == Decimal("330.00")
    assert v.milestones[0].label == "GoLive"
