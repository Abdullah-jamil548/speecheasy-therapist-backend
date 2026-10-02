from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.responses import HTMLResponse

from app.schemas.auth import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.core.security import (
    create_access_token,
    hash_password,
    new_doctor_id,
    new_otp_code,
    new_token_value,
    otp_token,
    public_therapist,
    verify_password,
)
from app.core.config import get_settings
from app.repositories.supabase_client import get_db
from app.core.logging import get_logger
from app.api.html.branded_pages import banner, branded_shell, error_body, success_body
from app.services.email_service import send_password_reset_email, send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger("auth")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_doctor_code() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(chars) for _ in range(6))


def _issue_email_challenge(
    db,
    *,
    doctor_id: str,
    purpose: str,
    hours: float,
    with_otp: bool = True,
) -> tuple[str, str | None]:
    """Create link token (+ optional OTP). Returns (link_token, code_or_none)."""
    link_token = new_token_value()
    expires = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()
    db.insert(
        "email_tokens",
        {
            "token": link_token,
            "doctor_id": doctor_id,
            "purpose": purpose,
            "expires_at": expires,
            "used": False,
        },
    )
    if not with_otp:
        return link_token, None

    code = new_otp_code(6)
    code_key = otp_token(purpose=purpose, doctor_id=doctor_id, code=code)
    db.insert(
        "email_tokens",
        {
            "token": code_key,
            "doctor_id": doctor_id,
            "purpose": purpose,
            "expires_at": expires,
            "used": False,
        },
    )
    return link_token, code


def _consume_token_row(db, row: dict) -> None:
    db.update("email_tokens", {"token": f"eq.{row['token']}"}, {"used": True})
    # Invalidate sibling unused tokens for same doctor + purpose
    siblings = db.select(
        "email_tokens",
        filters={
            "doctor_id": f"eq.{row['doctor_id']}",
            "purpose": f"eq.{row['purpose']}",
            "used": "eq.false",
        },
    )
    for sib in siblings:
        if sib.get("token") != row.get("token"):
            db.update("email_tokens", {"token": f"eq.{sib['token']}"}, {"used": True})


def _load_valid_token(db, *, token: str, purpose: str) -> dict:
    rows = db.select("email_tokens", filters={"token": f"eq.{token}"}, limit=1)
    if not rows:
        raise HTTPException(status_code=400, detail="Invalid or expired code/link")
    row = rows[0]
    if row.get("used"):
        raise HTTPException(status_code=400, detail="This code/link was already used")
    if row.get("purpose") != purpose:
        raise HTTPException(status_code=400, detail="Invalid token purpose")
    expires = datetime.fromisoformat(str(row["expires_at"]).replace("Z", "+00:00"))
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This code/link has expired")
    return row


def _resolve_challenge_token(
    db,
    *,
    purpose: str,
    token: str | None = None,
    email: str | None = None,
    code: str | None = None,
) -> dict:
    if token and token.strip():
        return _load_valid_token(db, token=token.strip(), purpose=purpose)
    if email and code:
        email_n = email.lower().strip()
        code_n = "".join(ch for ch in code.strip() if ch.isdigit())
        if len(code_n) != 6:
            raise HTTPException(status_code=400, detail="Enter the 6-digit code from your email")
        doctors = db.select("therapists", filters={"email": f"eq.{email_n}"}, limit=1)
        if not doctors:
            raise HTTPException(status_code=400, detail="Invalid email or code")
        doctor_id = doctors[0]["id"]
        key = otp_token(purpose=purpose, doctor_id=doctor_id, code=code_n)
        return _load_valid_token(db, token=key, purpose=purpose)
    raise HTTPException(status_code=400, detail="Provide a link token, or email + code")


def _verify_google_id_token(token: str) -> dict:
    """Validate Google ID token and return payload (email, name, sub, ...)."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    settings = get_settings()
    audiences = [a.strip() for a in settings.google_client_ids.split(",") if a.strip()]
    if not audiences:
        raise HTTPException(status_code=500, detail="Google Sign-In is not configured on the server.")

    last_error: Exception | None = None
    for audience in audiences:
        try:
            return google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                audience,
            )
        except Exception as exc:  # noqa: BLE001 — try next audience
            last_error = exc
    raise HTTPException(status_code=401, detail=f"Invalid Google token: {last_error}") from last_error


@router.post("/google", response_model=TokenResponse)
def google_login(body: GoogleLoginRequest) -> TokenResponse:
    info = _verify_google_id_token(body.id_token)
    email = (info.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email.")
    if not info.get("email_verified", False):
        raise HTTPException(status_code=400, detail="Google email is not verified.")

    full_name = (info.get("name") or email.split("@")[0]).strip()
    db = get_db()
    rows = db.select("therapists", filters={"email": f"eq.{email}"}, limit=1)
    is_new = not rows

    if rows:
        doctor = rows[0]
        if not doctor.get("email_verified"):
            updated = db.update(
                "therapists",
                {"id": f"eq.{doctor['id']}"},
                {"email_verified": True},
            )
            if updated:
                doctor = updated[0]
    else:
        doctor_id = new_doctor_id()
        doctor_code = _generate_doctor_code()
        for _ in range(5):
            clash = db.select("therapists", filters={"doctor_code": f"eq.{doctor_code}"}, limit=1)
            if not clash:
                break
            doctor_code = _generate_doctor_code()

        row = {
            "id": doctor_id,
            "email": email,
            "password_hash": None,
            "email_verified": True,
            "full_name": full_name,
            "phone": "",
            "qualification": "",
            "license_number": "",
            "years_of_experience": 0,
            "languages_spoken": "",
            "consultation_fee": 0,
            "status": "pending",
            "doctor_code": doctor_code,
            "rating": 0,
        }
        try:
            created = db.insert("therapists", row)
            doctor = created[0]
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not create account: {exc}") from exc

    token = create_access_token(doctor_id=doctor["id"], email=doctor["email"])
    log.info(
        "GOOGLE LOGIN | %s | %s | %s | id=%s",
        "NEW ACCOUNT" if is_new else "EXISTING",
        doctor.get("full_name") or full_name,
        doctor.get("email") or email,
        doctor["id"],
    )
    return TokenResponse(access_token=token, doctor=public_therapist(doctor))


@router.post("/register", response_model=MessageResponse)
def register(body: RegisterRequest) -> MessageResponse:
    db = get_db()
    email = body.email.lower().strip()

    existing = db.select("therapists", filters={"email": f"eq.{email}"}, limit=1)
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    doctor_id = new_doctor_id()
    doctor_code = _generate_doctor_code()
    for _ in range(5):
        clash = db.select("therapists", filters={"doctor_code": f"eq.{doctor_code}"}, limit=1)
        if not clash:
            break
        doctor_code = _generate_doctor_code()

    row = {
        "id": doctor_id,
        "email": email,
        "password_hash": hash_password(body.password),
        "email_verified": False,
        "full_name": body.full_name.strip(),
        "phone": body.phone.strip(),
        "qualification": body.qualification.strip(),
        "license_number": body.license_number.strip(),
        "years_of_experience": body.years_of_experience,
        "languages_spoken": (body.languages_spoken or "").strip(),
        "consultation_fee": body.consultation_fee,
        "status": "pending",
        "doctor_code": doctor_code,
        "rating": 0,
    }
    try:
        db.insert("therapists", row)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not create account: {exc}") from exc

    token, code = _issue_email_challenge(db, doctor_id=doctor_id, purpose="verify_email", hours=24)
    try:
        send_verification_email(
            to_email=email,
            token=token,
            doctor_name=body.full_name.strip(),
            code=code or "",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Account created but email failed. Configure SMTP. ({exc})",
        ) from exc

    log.info(
        "REGISTER | %s | %s | id=%s | verify email sent",
        body.full_name.strip(),
        email,
        doctor_id,
    )
    return MessageResponse(
        message="Account created. Check your email for a verification link or 6-digit code, then log in."
    )


def _verify_success_html() -> str:
    return branded_shell(
        title="Email verified",
        heading="All set",
        subtitle="Your therapist account email is confirmed.",
        body_html=success_body(
            title="Email verified",
            message="Your account is ready. Return to the app and sign in.",
        ),
    )


def _verify_error_html(message: str) -> str:
    return branded_shell(
        title="Verification failed",
        heading="Could not verify",
        subtitle="This link may be invalid or expired.",
        body_html=error_body(
            title="Verification failed",
            message=message,
        ),
    )


@router.get("/verify-email", response_class=HTMLResponse)
def verify_email_get(token: str = Query(default="")) -> HTMLResponse:
    if not token.strip():
        return HTMLResponse(
            _verify_error_html("Open the verification link from your SpeakEasy email again."),
            status_code=400,
        )
    try:
        db = get_db()
        row = _load_valid_token(db, token=token.strip(), purpose="verify_email")
        db.update("therapists", {"id": f"eq.{row['doctor_id']}"}, {"email_verified": True})
        _consume_token_row(db, row)
        log.info("EMAIL VERIFIED (link) | doctor_id=%s", row["doctor_id"])
    except HTTPException as exc:
        return HTMLResponse(_verify_error_html(str(exc.detail)), status_code=exc.status_code)
    return HTMLResponse(_verify_success_html())


@router.post("/verify-email", response_model=MessageResponse)
def verify_email_post(body: VerifyEmailRequest) -> MessageResponse:
    db = get_db()
    row = _resolve_challenge_token(
        db,
        purpose="verify_email",
        token=body.token,
        email=str(body.email) if body.email else None,
        code=body.code,
    )
    db.update("therapists", {"id": f"eq.{row['doctor_id']}"}, {"email_verified": True})
    _consume_token_row(db, row)
    log.info("EMAIL VERIFIED | doctor_id=%s", row["doctor_id"])
    return MessageResponse(message="Email verified successfully. You can log in now.")


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest) -> TokenResponse:
    db = get_db()
    email = body.email.lower().strip()
    rows = db.select("therapists", filters={"email": f"eq.{email}"}, limit=1)
    if not rows:
        log.warning("LOGIN FAILED | unknown email | %s", email)
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    doctor = rows[0]
    password_hash = doctor.get("password_hash") or ""
    if not password_hash or not verify_password(body.password, password_hash):
        log.warning("LOGIN FAILED | wrong password | %s", email)
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")
    if not doctor.get("email_verified"):
        log.warning("LOGIN BLOCKED | email not verified | %s", email)
        raise HTTPException(status_code=403, detail="Please verify your email before logging in.")

    token = create_access_token(doctor_id=doctor["id"], email=doctor["email"])
    log.info(
        "LOGIN OK | %s | %s | id=%s | status=%s",
        doctor.get("full_name") or "?",
        doctor.get("email"),
        doctor["id"],
        doctor.get("status"),
    )
    return TokenResponse(access_token=token, doctor=public_therapist(doctor))


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(body: ForgotPasswordRequest) -> MessageResponse:
    db = get_db()
    email = body.email.lower().strip()
    rows = db.select("therapists", filters={"email": f"eq.{email}"}, limit=1)
    # Always succeed to avoid email enumeration
    if not rows:
        return MessageResponse(message="If that email exists, a reset link was sent.")

    doctor = rows[0]
    token, _ = _issue_email_challenge(
        db,
        doctor_id=doctor["id"],
        purpose="reset_password",
        hours=1,
        with_otp=False,
    )
    try:
        send_password_reset_email(
            to_email=email,
            token=token,
            doctor_name=doctor.get("full_name") or "",
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not send email: {exc}") from exc
    log.info("FORGOT PASSWORD | reset email sent | %s | %s", doctor.get("full_name"), email)
    return MessageResponse(message="If that email exists, a reset link was sent.")


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(body: ResetPasswordRequest) -> MessageResponse:
    if not (body.token or "").strip():
        raise HTTPException(status_code=400, detail="Open the reset link from your email.")
    db = get_db()
    row = _resolve_challenge_token(
        db,
        purpose="reset_password",
        token=body.token,
    )
    db.update(
        "therapists",
        {"id": f"eq.{row['doctor_id']}"},
        {"password_hash": hash_password(body.new_password)},
    )
    _consume_token_row(db, row)
    log.info("PASSWORD RESET | doctor_id=%s", row["doctor_id"])
    return MessageResponse(message="Password updated. You can log in now.")


def _reset_page_html(
    *,
    token: str = "",
    message: str = "",
    error: str = "",
    done: bool = False,
) -> str:
    safe_token = escape(token or "", quote=True)
    banner_html = ""
    if error:
        banner_html = banner(kind="error", text=error)
    elif message:
        banner_html = banner(kind="ok", text=message)

    if done:
        body = success_body(
            title="Password updated",
            message=(
                "Your Therapist Portal password is ready. "
                "You can close this tab and sign in to SpeakEasy."
            ),
            cta_label="Open Therapist Portal",
        )
        heading = "You're all set"
        subtitle = "Your Therapist Portal account is secured with the new password."
    elif not token.strip() and error:
        body = error_body(
            title="Link unavailable",
            message=error,
            cta_label="Open Therapist Portal",
        )
        heading = "Reset unavailable"
        subtitle = "Open the secure Reset password button from your SpeakEasy email again."
    else:
        body = f"""
        <form method="post" action="/api/auth/reset-password-page" class="form" autocomplete="off">
          <input type="hidden" name="token" value="{safe_token}" />
          <label class="field">
            <span>New password</span>
            <span class="help">Use at least 6 characters</span>
            <input type="password" name="new_password" id="new_password" minlength="6" required
              placeholder="Enter new password" />
          </label>
          <label class="field">
            <span>Confirm password</span>
            <input type="password" name="confirm_password" id="confirm_password" minlength="6" required
              placeholder="Re-enter new password" />
          </label>
          <label class="check">
            <input type="checkbox" id="show_passwords" />
            <span>Show passwords</span>
          </label>
          <button type="submit" class="btn btn-primary">Update password</button>
          <div class="security-note">
            This secure link is for your Therapist Portal account only.
            It expires in 1 hour and can be used once.
          </div>
        </form>
        <script>
          const toggle = document.getElementById('show_passwords');
          if (toggle) {{
            toggle.addEventListener('change', () => {{
              const type = toggle.checked ? 'text' : 'password';
              document.getElementById('new_password').type = type;
              document.getElementById('confirm_password').type = type;
            }});
          }}
        </script>"""
        heading = "Choose a new password"
        subtitle = "Create a strong password to protect your Therapist Portal account."

    return branded_shell(
        title="Reset password",
        heading=heading,
        subtitle=subtitle,
        banner_html=banner_html if not (done or (not token.strip() and error)) else "",
        body_html=body,
    )


@router.get("/reset-password-page", response_class=HTMLResponse)
def reset_password_page_get(token: str = Query(default="")) -> HTMLResponse:
    if not token.strip():
        return HTMLResponse(
            _reset_page_html(
                token="",
                error="Missing reset link. Open the Reset password button from your email again.",
            ),
            status_code=400,
        )
    return HTMLResponse(_reset_page_html(token=token.strip()))


@router.post("/reset-password-page", response_class=HTMLResponse)
def reset_password_page_post(
    token: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
) -> HTMLResponse:
    token = (token or "").strip()
    if len(new_password) < 6:
        return HTMLResponse(
            _reset_page_html(token=token, error="Password must be at least 6 characters."),
            status_code=400,
        )
    if new_password != confirm_password:
        return HTMLResponse(
            _reset_page_html(token=token, error="Passwords do not match."),
            status_code=400,
        )
    try:
        reset_password(ResetPasswordRequest(token=token, new_password=new_password))
    except HTTPException as exc:
        return HTMLResponse(
            _reset_page_html(token=token, error=str(exc.detail)),
            status_code=exc.status_code,
        )
    return HTMLResponse(
        _reset_page_html(token="", message="Password updated. You can log in now.", done=True)
    )


@router.post("/resend-verification", response_model=MessageResponse)
def resend_verification(body: ForgotPasswordRequest) -> MessageResponse:
    db = get_db()
    email = body.email.lower().strip()
    rows = db.select("therapists", filters={"email": f"eq.{email}"}, limit=1)
    if not rows:
        return MessageResponse(message="If that email exists, a verification link and code were sent.")
    doctor = rows[0]
    if doctor.get("email_verified"):
        return MessageResponse(message="Email is already verified. You can log in.")

    token, code = _issue_email_challenge(db, doctor_id=doctor["id"], purpose="verify_email", hours=24)
    send_verification_email(
        to_email=email,
        token=token,
        doctor_name=doctor.get("full_name") or "Doctor",
        code=code or "",
    )
    return MessageResponse(message="If that email exists, a verification link and code were sent.")
