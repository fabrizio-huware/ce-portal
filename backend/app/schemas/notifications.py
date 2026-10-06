import uuid
from datetime import datetime
from typing import Literal

from app.schemas.common import OutputModel

NotificationStatus = Literal["pending", "sent", "failed"]


class NotificationOut(OutputModel):
    id: uuid.UUID
    type: str
    recipient: str
    subject: str | None  # oggetto dell'email, ricostruito dal contenuto salvato
    status: NotificationStatus
    attempts: int
    next_attempt_at: datetime
    last_attempt_at: datetime | None
    sent_at: datetime | None
    error: str | None
    created_at: datetime


class DispatchOut(OutputModel):
    processed: int
    sent: int
    deferred: int
    failed: int
    remaining: int
