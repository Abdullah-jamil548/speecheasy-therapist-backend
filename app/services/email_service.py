from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import get_settings

# SpeakEasy brand (same tokens as Flutter AppColors.light)
_BRAND = "#2F6B5F"       # primaryIndigo / tealPrimary
_BRAND_DARK = "#0F3D32"  # navyDark / headerNavy
_BG = "#FAFAF8"          # background
_CREAM = "#F5F4F0"       # cream
_TEXT = "#1C1C1A"        # textPrimary
_MUTED = "#6F6F6A"       # textSecondary
_BORDER = "#E6E4DF"      # inputBorder
_OK_BG = "#E8F3EF"       # statFill


def _escape(text: str) -> str:
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def branded_email_html(
    *,
    preheader: str,
    title: str,
    greeting: str,
    body_html: str,
    cta_label: str | None = None,
    cta_url: str | None = None,
    code: str | None = None,
    code_label: str = "Or enter this code in the app",
    footer_note: str = "",
) -> str:
    """Table-based HTML that renders cleanly in Gmail."""
    safe_pre = _escape(preheader)
    safe_title = _escape(title)
    safe_greeting = _escape(greeting)
    safe_footer = _escape(footer_note)

    cta_block = ""
    if cta_label and cta_url:
        cta_block = f"""
          <tr>
            <td align="center" style="padding:8px 0 22px;">
              <a href="{_escape(cta_url)}"
                 style="display:inline-block;background:{_BRAND_DARK};color:#ffffff;text-decoration:none;
                        font-family:Segoe UI,Arial,sans-serif;font-size:15px;font-weight:700;
                        padding:14px 28px;border-radius:12px;letter-spacing:0.2px;">
                {_escape(cta_label)}
              </a>
            </td>
          </tr>"""

    code_block = ""
    if code:
        code_block = f"""
          <tr>
            <td style="padding:4px 0 8px;">
              <p style="margin:0 0 10px;font-family:Segoe UI,Arial,sans-serif;font-size:13px;
                         color:{_MUTED};text-align:center;">{_escape(code_label)}</p>
              <div style="margin:0 auto;max-width:280px;background:{_CREAM};border:1px solid {_BORDER};
                          border-radius:14px;padding:16px 12px;text-align:center;">
                <span style="font-family:Consolas,Monaco,monospace;font-size:28px;font-weight:700;
                             letter-spacing:8px;color:{_BRAND_DARK};">{_escape(code)}</span>
              </div>
            </td>
          </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
</head>
<body style="margin:0;padding:0;background:{_BG};">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{safe_pre}</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background:{_BG};padding:28px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="max-width:560px;background:#ffffff;border:1px solid {_BORDER};border-radius:20px;
                      overflow:hidden;">
          <tr>
            <td style="background:linear-gradient(135deg,{_BRAND_DARK},{_BRAND});padding:22px 28px;text-align:center;">
              <p style="margin:0;font-family:Segoe UI,Arial,sans-serif;font-size:11px;font-weight:600;
                         color:rgba(255,255,255,0.78);letter-spacing:1.4px;text-transform:uppercase;">
                Therapist Portal
              </p>
              <p style="margin:6px 0 0;font-family:Segoe UI,Arial,sans-serif;font-size:18px;font-weight:700;
                         color:#ffffff;letter-spacing:0.2px;">SpeakEasy</p>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 8px;">
              <h1 style="margin:0 0 12px;font-family:Segoe UI,Arial,sans-serif;font-size:22px;
                          font-weight:700;color:{_TEXT};letter-spacing:-0.3px;">{safe_title}</h1>
              <p style="margin:0 0 14px;font-family:Segoe UI,Arial,sans-serif;font-size:15px;
                         color:{_TEXT};line-height:1.5;">{safe_greeting}</p>
              <div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:{_MUTED};
                          line-height:1.55;">{body_html}</div>
            </td>
          </tr>
          {cta_block}
          {code_block}
          <tr>
            <td style="padding:18px 28px 28px;">
              <p style="margin:0;font-family:Segoe UI,Arial,sans-serif;font-size:12.5px;color:{_MUTED};
                         line-height:1.5;text-align:center;">{safe_footer}</p>
            </td>
          </tr>
        </table>
        <p style="margin:16px 0 0;font-family:Segoe UI,Arial,sans-serif;font-size:11px;color:#9A9A94;
                   text-align:center;">© SpeakEasy · Therapist Portal</p>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    text_body: str | None = None,
) -> None:
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password:
        raise RuntimeError("SMTP is not configured. Set SMTP_USER and SMTP_PASSWORD in .env")

    from_addr = settings.smtp_from_email or settings.smtp_user
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings.smtp_from_name} <{from_addr}>"
    msg["To"] = to_email
    msg.set_content(text_body or "Open this email in an HTML-capable client.")
    msg.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(msg)


def send_verification_email(
    *,
    to_email: str,
    token: str,
    doctor_name: str,
    code: str,
) -> None:
    settings = get_settings()
    link = f"{settings.app_public_url.rstrip('/')}/api/auth/verify-email?token={token}"
    name = doctor_name.strip() or "Doctor"
    html = branded_email_html(
        preheader=f"Your SpeakEasy verification code is {code}",
        title="Verify your email",
        greeting=f"Hi {name},",
        body_html=(
            "<p style='margin:0 0 12px;'>Welcome to SpeakEasy for Therapists. Confirm your email to activate "
            "your therapist account — use the button below, or enter the code in the app.</p>"
        ),
        cta_label="Verify email",
        cta_url=link,
        code=code,
        code_label="Or enter this 6-digit code in the app",
        footer_note="This link and code expire in 24 hours. If you did not create an account, you can ignore this email.",
    )
    send_email(
        to_email=to_email,
        subject="Verify your SpeakEasy for Therapists email",
        html_body=html,
        text_body=(
            f"Hi {name},\n\n"
            "Welcome to SpeakEasy for Therapists. Verify your email to activate your account.\n\n"
            f"Verification code: {code}\n\n"
            f"Or open this link:\n{link}\n\n"
            "This link and code expire in 24 hours."
        ),
    )


def send_password_reset_email(*, to_email: str, token: str, doctor_name: str = "") -> None:
    settings = get_settings()
    link = f"{settings.app_public_url.rstrip('/')}/api/auth/reset-password-page?token={token}"
    name = (doctor_name or "").strip() or "Doctor"
    html = branded_email_html(
        preheader="Secure link to update your Therapist Portal password",
        title="Reset your password",
        greeting=f"Hi {name},",
        body_html=(
            "<p style='margin:0 0 12px;'>We received a request to reset the password for your "
            "<strong style='color:#1C1C1A;'>SpeakEasy Therapist Portal</strong> account.</p>"
            "<p style='margin:0 0 12px;'>Use the secure button below to choose a new password. "
            "For your protection, this link works only once and expires in <strong style='color:#1C1C1A;'>1 hour</strong>.</p>"
            "<p style='margin:0;'>If you did not request this change, you can ignore this email — "
            "your password will stay the same.</p>"
        ),
        cta_label="Reset password securely",
        cta_url=link,
        code=None,
        footer_note=(
            "This email was sent by SpeakEasy Therapist Portal. "
            "Never share this link with anyone."
        ),
    )
    send_email(
        to_email=to_email,
        subject="Reset your Therapist Portal password — SpeakEasy",
        html_body=html,
        text_body=(
            f"Hi {name},\n\n"
            "We received a request to reset the password for your SpeakEasy Therapist Portal account.\n\n"
            f"Reset your password securely:\n{link}\n\n"
            "This link works once and expires in 1 hour.\n"
            "If you did not request this, ignore this email — your password will stay the same.\n\n"
            "— SpeakEasy Therapist Portal"
        ),
    )


def send_simple_notice(*, to_email: str, subject: str, message: str) -> None:
    html = branded_email_html(
        preheader=subject,
        title=subject,
        greeting="Hello,",
        body_html=f"<p style='margin:0;'>{_escape(message)}</p>",
        footer_note="This is an automated message from SpeakEasy for Therapists.",
    )
    send_email(
        to_email=to_email,
        subject=subject,
        html_body=html,
        text_body=message,
    )
