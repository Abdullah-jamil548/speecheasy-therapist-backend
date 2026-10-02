from __future__ import annotations

from html import escape

from app.core.config import get_settings


def doctor_app_url() -> str:
    return get_settings().doctor_app_url.rstrip("/")


def branded_shell(
    *,
    title: str,
    heading: str,
    subtitle: str,
    body_html: str,
    banner_html: str = "",
) -> str:
    """Shared SpeakEasy Therapist Portal HTML shell for auth browser pages."""
    safe_title = escape(title)
    safe_heading = escape(heading)
    safe_subtitle = escape(subtitle)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title} — SpeakEasy Therapist Portal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --brand: #2F6B5F;
      --brand-dark: #0F3D32;
      --brand-light: #3D7F71;
      --bg: #FAFAF8;
      --cream: #F5F4F0;
      --card: #FFFFFF;
      --text: #1C1C1A;
      --muted: #6F6F6A;
      --border: #E6E4DF;
      --error: #B42318;
      --error-bg: #FEF3F2;
      --ok: #1E8E3E;
      --ok-bg: #E8F3EF;
      --shadow: 0 22px 60px rgba(15, 61, 50, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Poppins", "Segoe UI", system-ui, -apple-system, sans-serif;
      color: var(--text);
      background:
        radial-gradient(1000px 480px at 8% -8%, rgba(47,107,95,0.16), transparent 58%),
        radial-gradient(700px 360px at 100% 0%, rgba(15,61,50,0.08), transparent 50%),
        linear-gradient(180deg, var(--cream) 0%, var(--bg) 42%, var(--bg) 100%);
    }}
    .wrap {{
      min-height: 100vh;
      display: grid;
      place-items: center;
      padding: 28px 16px;
    }}
    .card {{
      width: 100%;
      max-width: 460px;
      background: var(--card);
      border: 1px solid rgba(230,228,223,0.95);
      border-radius: 24px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .top {{
      padding: 26px 28px 22px;
      background: linear-gradient(145deg, var(--brand-dark) 0%, var(--brand) 100%);
      color: #fff;
      text-align: center;
    }}
    .portal-badge {{
      display: inline-block;
      margin: 0 0 14px;
      padding: 5px 11px;
      border-radius: 999px;
      border: 1px solid rgba(255,255,255,0.22);
      background: rgba(255,255,255,0.10);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 1.2px;
      text-transform: uppercase;
      color: rgba(255,255,255,0.92);
    }}
    .brand-name {{
      margin: 0 0 14px;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: 0.2px;
    }}
    .top h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      letter-spacing: -0.4px;
      font-weight: 700;
    }}
    .top p.sub {{
      margin: 8px 0 0;
      font-size: 14px;
      line-height: 1.5;
      opacity: 0.88;
      font-weight: 400;
    }}
    .content {{ padding: 24px 28px 28px; }}
    .banner {{
      display: flex;
      gap: 10px;
      align-items: flex-start;
      padding: 12px 14px;
      border-radius: 12px;
      margin-bottom: 16px;
      font-size: 13.5px;
      line-height: 1.4;
    }}
    .banner p {{ margin: 0; }}
    .banner-dot {{
      width: 8px; height: 8px; border-radius: 50%;
      margin-top: 5px; flex: 0 0 auto;
    }}
    .banner-error {{ background: var(--error-bg); color: var(--error); }}
    .banner-error .banner-dot {{ background: var(--error); }}
    .banner-ok {{ background: var(--ok-bg); color: var(--brand-dark); }}
    .banner-ok .banner-dot {{ background: var(--ok); }}
    .form {{ display: grid; gap: 14px; }}
    .field {{ display: grid; gap: 7px; font-size: 13px; font-weight: 600; color: var(--text); }}
    .field span.help {{
      font-size: 12px;
      font-weight: 400;
      color: var(--muted);
    }}
    .field input {{
      width: 100%;
      padding: 13px 14px;
      border: 1px solid var(--border);
      border-radius: 12px;
      font-size: 15px;
      font-weight: 400;
      background: #fff;
      color: var(--text);
      outline: none;
      transition: border-color .15s, box-shadow .15s;
    }}
    .field input:focus {{
      border-color: var(--brand);
      box-shadow: 0 0 0 3px rgba(47,107,95,0.15);
    }}
    .check {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: var(--muted);
      font-weight: 500;
      user-select: none;
    }}
    .btn {{
      display: inline-flex;
      justify-content: center;
      align-items: center;
      width: 100%;
      padding: 14px 16px;
      border: 0;
      border-radius: 12px;
      font-size: 15px;
      font-weight: 700;
      font-family: inherit;
      text-decoration: none;
      cursor: pointer;
      transition: transform .12s ease, background .12s ease;
    }}
    .btn-primary {{
      background: var(--brand-dark);
      color: #fff;
    }}
    .btn-primary:hover {{ background: var(--brand); transform: translateY(-1px); }}
    .hint {{
      margin: 2px 0 0;
      text-align: center;
      font-size: 12.5px;
      color: var(--muted);
      line-height: 1.45;
    }}
    .security-note {{
      margin-top: 4px;
      padding: 12px 14px;
      border-radius: 12px;
      background: var(--cream);
      border: 1px solid var(--border);
      font-size: 12.5px;
      color: var(--muted);
      line-height: 1.45;
    }}
    .success-block, .status-block {{
      text-align: center;
      padding: 8px 0 4px;
    }}
    .success-icon, .status-icon {{
      width: 56px;
      height: 56px;
      margin: 0 auto 14px;
      border-radius: 50%;
      display: grid;
      place-items: center;
      font-size: 24px;
      font-weight: 700;
    }}
    .success-icon {{ background: var(--ok-bg); color: var(--brand-dark); }}
    .status-icon.error {{ background: var(--error-bg); color: var(--error); }}
    .success-block h2, .status-block h2 {{
      margin: 0 0 8px;
      font-size: 20px;
      letter-spacing: -0.3px;
    }}
    .success-block p, .status-block p {{
      margin: 0 0 18px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
    }}
    .foot {{
      margin: 16px 0 0;
      text-align: center;
      font-size: 11.5px;
      color: #9A9A94;
      line-height: 1.4;
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <header class="top">
        <span class="portal-badge">Therapist Portal</span>
        <p class="brand-name">SpeakEasy</p>
        <h1>{safe_heading}</h1>
        <p class="sub">{safe_subtitle}</p>
      </header>
      <div class="content">
        {banner_html}
        {body_html}
      </div>
    </section>
    <p class="foot">© SpeakEasy · Therapist Portal<br />Secure account access for licensed therapists</p>
  </div>
</body>
</html>"""


def banner(*, kind: str, text: str) -> str:
    css = "banner-ok" if kind == "ok" else "banner-error"
    return f"""
    <div class="banner {css}" role="{"status" if kind == "ok" else "alert"}">
      <span class="banner-dot"></span>
      <p>{escape(text)}</p>
    </div>"""


def success_body(*, title: str, message: str, cta_label: str = "Open Therapist Portal") -> str:
    app = escape(doctor_app_url(), quote=True)
    return f"""
    <div class="success-block">
      <div class="success-icon" aria-hidden="true">✓</div>
      <h2>{escape(title)}</h2>
      <p>{escape(message)}</p>
      <a class="btn btn-primary" href="{app}">{escape(cta_label)}</a>
    </div>"""


def error_body(*, title: str, message: str, cta_label: str = "Open Therapist Portal") -> str:
    app = escape(doctor_app_url(), quote=True)
    return f"""
    <div class="status-block">
      <div class="status-icon error" aria-hidden="true">!</div>
      <h2>{escape(title)}</h2>
      <p>{escape(message)}</p>
      <a class="btn btn-primary" href="{app}">{escape(cta_label)}</a>
    </div>"""
