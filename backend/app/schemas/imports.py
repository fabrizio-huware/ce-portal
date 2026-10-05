from app.schemas.common import OutputModel


class ImportErrorItem(OutputModel):
    line: int | None = None
    message: str


class ImportResult(OutputModel):
    dry_run: bool
    applied: bool
    total_rows: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    extra: dict[str, int] = {}
    errors: list[ImportErrorItem] = []
