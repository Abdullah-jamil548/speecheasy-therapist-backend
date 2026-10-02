from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.auth import AppointmentRespond, AvailabilityUpsert
from app.core.security import get_current_doctor
from app.repositories.supabase_client import get_db
from app.core.logging import get_logger

router = APIRouter(tags=["schedule"])
log = get_logger("schedule")


def _who(doctor: dict[str, Any]) -> str:
    return f"{doctor.get('full_name') or '?'} <{doctor.get('email')}>"


def _to_db_time(hhmm: str) -> str:
    raw = (hhmm or "").strip()
    if not raw:
        return "09:00:00"
    parts = raw.split(":")
    h = int(parts[0]) if parts else 9
    m = int(parts[1]) if len(parts) > 1 else 0
    return f"{h:02d}:{m:02d}:00"


@router.get("/availability")
def list_availability(doctor: dict[str, Any] = Depends(get_current_doctor)) -> list[dict[str, Any]]:
    db = get_db()
    return db.select("availability", filters={"doctor_id": f"eq.{doctor['id']}"})


@router.post("/availability")
def upsert_availability(
    body: AvailabilityUpsert,
    doctor: dict[str, Any] = Depends(get_current_doctor),
) -> dict[str, Any]:
    db = get_db()
    payload = {
        "doctor_id": doctor["id"],
        "day": body.day.strip(),
        "start_time": _to_db_time(body.start_time),
        "end_time": _to_db_time(body.end_time),
        "is_active": body.is_active,
    }
    if body.id:
        rows = db.update(
            "availability",
            {"id": f"eq.{body.id}", "doctor_id": f"eq.{doctor['id']}"},
            payload,
        )
        if rows:
            return rows[0]

    existing = db.select(
        "availability",
        filters={"doctor_id": f"eq.{doctor['id']}", "day": f"eq.{body.day.strip()}"},
        limit=1,
    )
    if existing:
        rows = db.update("availability", {"id": f"eq.{existing[0]['id']}"}, payload)
        log.info(
            "AVAILABILITY UPDATE | by %s | day=%s | %s-%s | active=%s",
            _who(doctor),
            body.day.strip(),
            payload["start_time"],
            payload["end_time"],
            body.is_active,
        )
        return rows[0]
    rows = db.insert("availability", payload)
    log.info(
        "AVAILABILITY CREATE | by %s | day=%s | %s-%s | active=%s",
        _who(doctor),
        body.day.strip(),
        payload["start_time"],
        payload["end_time"],
        body.is_active,
    )
    return rows[0]


@router.get("/appointments")
def list_appointments(doctor: dict[str, Any] = Depends(get_current_doctor)) -> list[dict[str, Any]]:
    db = get_db()
    return db.select(
        "appointments",
        filters={"doctor_id": f"eq.{doctor['id']}"},
        order="appointment_date.asc,start_time.asc",
    )


def _patch_appointment_status(
    *,
    appointment_id: str,
    doctor: dict[str, Any],
    new_status: str,
) -> dict[str, Any]:
    db = get_db()
    rows = db.select(
        "appointments",
        filters={"id": f"eq.{appointment_id}", "doctor_id": f"eq.{doctor['id']}"},
        limit=1,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Appointment not found")
    try:
        updated = db.update(
            "appointments",
            {"id": f"eq.{appointment_id}"},
            {"status": new_status},
        )
    except RuntimeError as exc:
        msg = str(exc)
        log.exception(
            "APPOINTMENT UPDATE FAILED | by %s | id=%s | %s",
            _who(doctor),
            appointment_id,
            msg,
        )
        if "updated_at" in msg:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Appointments table is missing updated_at. "
                    "Add an updated_at column on appointments in Supabase, then try again."
                ),
            ) from exc
        raise HTTPException(status_code=500, detail=msg) from exc
    return updated[0] if updated else {**rows[0], "status": new_status}


@router.post("/appointments/{appointment_id}/respond")
def respond_appointment(
    appointment_id: str,
    body: AppointmentRespond,
    doctor: dict[str, Any] = Depends(get_current_doctor),
) -> dict[str, Any]:
    # Schema allows: pending | confirmed | cancelled | completed (no declined)
    new_status = "confirmed" if body.confirm else "cancelled"
    result = _patch_appointment_status(
        appointment_id=appointment_id,
        doctor=doctor,
        new_status=new_status,
    )
    log.info(
        "APPOINTMENT %s | by %s | id=%s",
        new_status.upper(),
        _who(doctor),
        appointment_id,
    )
    return result


@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: str,
    doctor: dict[str, Any] = Depends(get_current_doctor),
) -> dict[str, Any]:
    result = _patch_appointment_status(
        appointment_id=appointment_id,
        doctor=doctor,
        new_status="cancelled",
    )
    log.info("APPOINTMENT CANCELLED | by %s | id=%s", _who(doctor), appointment_id)
    return result
