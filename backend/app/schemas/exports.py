from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.schemas.common import Email, OutputModel


class ExportEmailIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient: Email
    format: Literal["xlsx", "pdf"] = "pdf"
    variant: Literal["full", "summary"] = "summary"
    version: int | None = Field(
        default=None, ge=1, description="Numero di versione (default: l'ultima)"
    )
    message: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


class ExportEmailOut(OutputModel):
    recipient: str
    filename: str
    # sent = partita; queued = in coda, il portale riprova da solo; failed = rifiutata (vedi error)
    status: Literal["sent", "queued", "failed"]
    error: str | None = None
