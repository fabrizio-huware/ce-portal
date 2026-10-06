from fastapi import APIRouter

from app.api.v1 import (
    auth,
    calendar,
    ce,
    clients,
    dashboard,
    employees,
    exports,
    health,
    notifications,
    profiles,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(clients.router)
api_router.include_router(employees.router)
api_router.include_router(profiles.router)
api_router.include_router(calendar.router)
api_router.include_router(
    exports.router
)  # prima di ce: /ce/export e /ce/summaries/export sono percorsi fissi
api_router.include_router(ce.router)
api_router.include_router(dashboard.router)
api_router.include_router(notifications.router)
