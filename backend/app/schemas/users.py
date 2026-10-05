import uuid
from datetime import datetime

from app.schemas.common import Email, InputModel, OutputModel, Role, short_text


class UserOut(OutputModel):
    id: uuid.UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime


class UserCreate(InputModel):
    email: Email
    full_name: short_text(200)
    role: Role


class UserUpdate(InputModel):
    full_name: short_text(200) | None = None
    role: Role | None = None
    is_active: bool | None = None


class GoogleLoginRequest(InputModel):
    id_token: str


class DevLoginRequest(InputModel):
    email: Email


class TokenResponse(OutputModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut
