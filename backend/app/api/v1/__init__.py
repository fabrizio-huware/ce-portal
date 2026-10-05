from fastapi import APIRouter

from app.api.v1 import auth, calendar, clients, employees, health, profiles, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(clients.router)
api_router.include_router(employees.router)
api_router.include_router(profiles.router)
api_router.include_router(calendar.router)
