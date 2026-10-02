"""
Aggregate all API routers under /api.
"""

from fastapi import APIRouter

from app.api.routes import auth, patients, profile, schedule
from app.core.config import get_settings

settings = get_settings()
api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(patients.router)
api_router.include_router(schedule.router)
