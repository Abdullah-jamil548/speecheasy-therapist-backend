"""
SpeakEasy for Therapists API entrypoint.

Layers:
  api/           → HTTP routes + branded HTML pages
  schemas/       → request/response DTOs
  services/      → email and domain helpers
  repositories/  → Supabase REST data access
  core/          → config, security, logging, middleware
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.middleware import RequestLogMiddleware

setup_logging()
settings = get_settings()
log = get_logger("app")

app = FastAPI(title=settings.app_name, debug=settings.debug)

# Bearer-token API: do not combine allow_origins=["*"] with credentials=True
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)

api_prefix = settings.api_prefix.rstrip("/") or "/api"
app.include_router(api_router, prefix=api_prefix)

log.info("%s started | docs=http://localhost:8000/docs", settings.app_name)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}
