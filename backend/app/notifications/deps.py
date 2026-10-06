from typing import Annotated

from fastapi import Depends

from app.api.deps import SettingsDep
from app.notifications.mailer import Mailer, build_mailer
from app.notifications.outbox import Notifier


def get_mailer(settings: SettingsDep) -> Mailer:
    """Dependency FastAPI: nei test viene sostituita con un registratore di email."""
    return build_mailer(settings)


def get_notifier(settings: SettingsDep, mailer: Annotated[Mailer, Depends(get_mailer)]) -> Notifier:
    return Notifier(mailer, settings)


NotifierDep = Annotated[Notifier, Depends(get_notifier)]
