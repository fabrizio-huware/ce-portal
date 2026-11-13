import uuid
from datetime import datetime

from app.schemas.common import InputModel, OutputModel, short_text


class BusinessUnitOut(OutputModel):
    id: uuid.UUID
    name: str
    is_active: bool
    practices_count: int  # practice attive di questa business unit
    employees_count: int  # collaboratori attivi delle sue practice
    users_count: int  # presale e responsabili attivi assegnati
    created_at: datetime
    updated_at: datetime


class BusinessUnitRef(OutputModel):
    """Vista minima per filtri e menu a tendina."""

    id: uuid.UUID
    name: str
    is_active: bool


class BusinessUnitCreate(InputModel):
    name: short_text(100)


class CERefOut(OutputModel):
    ce_id: uuid.UUID
    code: str


class ApplyToCEsResult(OutputModel):
    updated: int  # CE a cui sono state assegnate le business unit
    without_business_units: list[CERefOut]  # CE che restano senza: visibili solo ad autore e admin


class BusinessUnitUpdate(InputModel):
    name: short_text(100) | None = None
    is_active: bool | None = None


class VisibilityReport(OutputModel):
    """Che cosa manca prima di accendere la visibilità per business unit."""

    ces_without_business_units: int  # visibili solo ad autore e admin finché non ne hanno
    ces_without_examples: list[CERefOut]  # i primi 20
    people_without_business_unit: list[
        str
    ]  # presale senza business unit: vedrebbero solo i propri CE
    practices_unassigned: int  # practice attive ancora in «Da assegnare»


class VisibilityOut(OutputModel):
    enabled: bool
    report: VisibilityReport


class VisibilityIn(InputModel):
    enabled: bool
