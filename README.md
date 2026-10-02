# SpeakEasy for Therapists API

FastAPI backend for the therapist app. Auth is **email + password + SMTP** (plus Google).
Data lives in **Supabase Postgres**; the API talks via **Supabase REST** (service role). No raw SQL at runtime.

## Architecture

```
app/
  api/            HTTP routes + branded verify/reset HTML pages
  schemas/        Pydantic DTOs
  services/       Email and helpers
  repositories/   Supabase REST client
  core/           Config, JWT/security, logging, middleware
```

Schema changes are applied in the **Supabase SQL Editor** (not shipped inside this API).

## Setup

1. Ensure Supabase tables/auth columns already match your live project.
2. Copy env:

```bash
copy .env.example .env
```

3. Install and run:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Docs: http://localhost:8000/docs

## Auth

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create therapist + verify email |
| GET/POST | `/api/auth/verify-email` | Confirm via link or code |
| POST | `/api/auth/login` | JWT |
| POST | `/api/auth/forgot-password` | Reset email (link only) |
| POST | `/api/auth/reset-password` | Set new password |
| POST | `/api/auth/resend-verification` | Resend verify |

## Therapist APIs (Bearer JWT)

| Method | Path |
|--------|------|
| GET/PATCH | `/api/me` |
| GET/POST | `/api/patients` |
| PATCH/DELETE | `/api/patients/{id}` |
| GET | `/api/requests` |
| POST | `/api/requests/{id}/respond` |
| GET/POST | `/api/availability` |
| GET | `/api/appointments` |
| POST | `/api/appointments/{id}/respond` |
| POST | `/api/appointments/{id}/cancel` |

## Deploy note

Prefer **Railway / Render / Fly.io / Cloud Run** for this FastAPI service. Vercel is not a good fit.

## Deploy on Render (recommended)

Backend folder must be on **GitHub** first (this API is separate from the Flutter app).

### 1. Push this backend to GitHub

```bash
cd C:\Users\HP\Desktop\speakeasy-doctor-backend
git init
git add .
git commit -m "SpeakEasy therapist API"
```

Create a new empty repo on GitHub, then:

```bash
git remote add origin https://github.com/YOUR_USER/speakeasy-doctor-backend.git
git branch -M main
git push -u origin main
```

(`.env` stays local — it is gitignored.)

### 2. Create Web Service on Render

1. Open [https://dashboard.render.com](https://dashboard.render.com) → **New** → **Web Service**
2. Connect the GitHub repo
3. Settings:
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free (sleeps after idle; first request can take ~30–60s)

Or use **Blueprint** with the included `render.yaml`.

### 3. Environment variables (Render → Environment)

| Key | Value |
|-----|--------|
| `JWT_SECRET` | long random secret |
| `SUPABASE_URL` | from Supabase → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role (server only) |
| `APP_PUBLIC_URL` | `https://YOUR-SERVICE.onrender.com` |
| `DOCTOR_APP_URL` | your doctor web URL (or Flutter web URL) |
| `GOOGLE_CLIENT_IDS` | Google Web client ID(s), comma-separated |
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | your Gmail |
| `SMTP_PASSWORD` | Gmail App Password |
| `SMTP_FROM_EMAIL` | same as SMTP_USER |
| `SMTP_FROM_NAME` | `SpeakEasy for Therapists` |
| `SMTP_USE_TLS` | `true` |
| `DEBUG` | `false` |

### 4. After deploy

1. Open `https://YOUR-SERVICE.onrender.com/health` → should return `healthy`
2. Docs: `https://YOUR-SERVICE.onrender.com/docs`
3. In Flutter `lib/core/constants.dart`, set API base to:
   `https://YOUR-SERVICE.onrender.com/api`
4. Google Cloud Console → OAuth client → add authorized origins / redirect URIs for your web app
5. Verify/reset emails will use `APP_PUBLIC_URL` links automatically

**Free plan tip:** after sleep, Google login / first API call may look slow until the service wakes up.
