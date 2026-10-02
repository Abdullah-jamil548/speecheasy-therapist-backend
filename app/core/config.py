import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SpeakEasy for Therapists API"
    debug: bool = False
    api_prefix: str = "/api"

    # JWT
    jwt_secret: str = "change-me-to-a-long-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # Supabase (service role bypasses RLS — keep secret on server only)
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Public API URL (email verification / reset links)
    app_public_url: str = "http://localhost:8000"
    # Doctor web/app URL shown on success pages after verify/reset
    doctor_app_url: str = "http://localhost:5050"
    frontend_deep_link: str = "speakeasyDoctor://auth"

    # Google Sign-In (OAuth Web client ID). Comma-separate multiple client IDs.
    google_client_ids: str = (
        "26703591720-pt9vo0tdkudsqfd3dteeqi1kf1l7dluv.apps.googleusercontent.com"
    )

    # SMTP (works locally; Render Free blocks SMTP ports)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "SpeakEasy for Therapists"
    smtp_use_tls: bool = True

    # Resend (HTTPS email — required on Render Free)
    # https://resend.com → API Keys. Free: onboarding@resend.dev or verified domain.
    resend_api_key: str = ""
    resend_from_email: str = "SpeakEasy for Therapists <onboarding@resend.dev>"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def public_site_origin(settings: Settings | None = None) -> str:
    """Base URL for email links (verify / reset). Uses Vercel/Render env if APP_PUBLIC_URL is still localhost."""
    s = settings or get_settings()
    raw = (s.app_public_url or "").strip().rstrip("/")
    lower = raw.lower()
    if raw and "localhost" not in lower and not lower.startswith("http://127."):
        return raw

    vercel = os.environ.get("VERCEL_URL", "").strip()
    if vercel:
        host = vercel if vercel.startswith("http") else f"https://{vercel}"
        return host.rstrip("/")

    render = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    if render:
        return render.rstrip("/")

    return raw or "http://localhost:8000"
