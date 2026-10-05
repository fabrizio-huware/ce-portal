import uuid

from app.schemas.common import InputModel, OutputModel, short_text


class EmployeeOut(OutputModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    default_profile_id: uuid.UUID
    profile_name: str
    is_active: bool
    netsuite_id: str | None
    jira_account_id: str | None


class EmployeeCreate(InputModel):
    first_name: short_text(100)
    last_name: short_text(100)
    default_profile_id: uuid.UUID
    is_active: bool = True
    netsuite_id: short_text(100) | None = None
    jira_account_id: short_text(100) | None = None


class EmployeeUpdate(InputModel):
    first_name: short_text(100) | None = None
    last_name: short_text(100) | None = None
    default_profile_id: uuid.UUID | None = None
    is_active: bool | None = None
    netsuite_id: short_text(100) | None = None
    jira_account_id: short_text(100) | None = None
