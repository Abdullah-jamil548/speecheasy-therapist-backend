from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.auth import PatientCreate, PatientUpdate, RequestRespond
from app.core.security import get_current_doctor
from app.repositories.supabase_client import get_db
from app.core.logging import get_logger
from app.services.email_service import send_simple_notice

router = APIRouter(tags=["patients"])
log = get_logger("patients")


def _who(doctor: dict[str, Any]) -> str:
    return f"{doctor.get('full_name') or '?'} <{doctor.get('email')}>"


@router.get("/patients")
def list_patients(doctor: dict[str, Any] = Depends(get_current_doctor)) -> list[dict[str, Any]]:
    db = get_db()
    return db.select(
        "patients",
        filters={"doctor_id": f"eq.{doctor['id']}"},
        order="created_at.desc",
    )


@router.post("/patients")
def create_patient(
    body: PatientCreate,
    doctor: dict[str, Any] = Depends(get_current_doctor),
) -> dict[str, Any]:
    db = get_db()
    payload: dict[str, Any] = {
        "doctor_id": doctor["id"],
        "name": body.name.strip(),
    }
    if body.age is not None:
        payload["age"] = body.age
    if body.condition:
        payload["condition"] = body.condition.strip()
    if body.phone:
        payload["phone"] = body.phone.strip()
    if body.parent_email:
        payload["parent_email"] = body.parent_email.strip()
    if body.notes:
        payload["notes"] = body.notes.strip()

    try:
        rows = db.insert("patients", payload)
        log.info("CREATE PATIENT | by %s | patient=%s", _who(doctor), body.name.strip())
        return rows[0]
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not create patient: {exc}") from exc


@router.patch("/patients/{patient_id}")
def update_patient(
    patient_id: str,
    body: PatientUpdate,
    doctor: dict[str, Any] = Depends(get_current_doctor),
) -> dict[str, Any]:
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        raise HTTPException(status_code=400, detail="Nothing to update")
    db = get_db()
    rows = db.update(
        "patients",
        {"id": f"eq.{patient_id}", "doctor_id": f"eq.{doctor['id']}"},
        patch,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Patient not found")
    log.info("UPDATE PATIENT | by %s | id=%s", _who(doctor), patient_id)
    return rows[0]


def _cancel_request(db: Any, doctor_id: str, request_id: str) -> None:
    try:
        db.update(
            "patient_requests",
            {"id": f"eq.{request_id}", "doctor_id": f"eq.{doctor_id}"},
            {"status": "cancelled"},
        )
    except Exception as exc:
        msg = str(exc)
        if "check_patient_request_status" in msg or "status" in msg.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Database does not allow status 'cancelled' on patient_requests. "
                    "Update the patient_requests status check in Supabase to allow 'cancelled', then remove again."
                ),
            ) from exc
        raise HTTPException(status_code=400, detail=f"Could not end the link: {exc}") from exc


def _accepted_requests_for_patient(db: Any, doctor_id: str, patient: dict[str, Any]) -> list[dict[str, Any]]:
    """Find accepted request rows for this patient (uid first, then name/email/phone)."""
    found: dict[str, dict[str, Any]] = {}

    uid = str(patient.get("patient_uid") or "").strip()
    if uid:
        for row in db.select(
            "patient_requests",
            filters={
                "doctor_id": f"eq.{doctor_id}",
                "patient_uid": f"eq.{uid}",
                "status": "eq.accepted",
            },
        ):
            found[str(row.get("id"))] = row

    name = str(patient.get("name") or "").strip()
    if name:
        filters: dict[str, str] = {
            "doctor_id": f"eq.{doctor_id}",
            "patient_name": f"eq.{name}",
            "status": "eq.accepted",
        }
        email = str(patient.get("parent_email") or "").strip()
        phone = str(patient.get("phone") or "").strip()
        if email:
            filters["parent_email"] = f"eq.{email}"
        if phone:
            filters["phone"] = f"eq.{phone}"
        for row in db.select("patient_requests", filters=filters):
            found[str(row.get("id"))] = row

    return list(found.values())


def _appointment_brief(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "doctor_id": row.get("doctor_id"),
        "patient_uid": row.get("patient_uid"),
        "patient_name": row.get("patient_name"),
        "appointment_date": row.get("appointment_date"),
        "start_time": row.get("start_time"),
        "end_time": row.get("end_time"),
        "status": row.get("status"),
        "created_at": row.get("created_at"),
    }


def _former_patient(req: dict[str, Any], appointments: list[dict[str, Any]]) -> dict[str, Any]:
    uid = str(req.get("patient_uid") or "").strip()
    name = str(req.get("patient_name") or "").strip()
    matched: list[dict[str, Any]] = []
    for row in appointments:
        row_uid = str(row.get("patient_uid") or "").strip()
        row_name = str(row.get("patient_name") or "").strip()
        if uid and row_uid == uid:
            matched.append(_appointment_brief(row))
        elif not uid and name and row_name == name:
            matched.append(_appointment_brief(row))
    return {
        "id": req.get("id"),
        "doctor_id": req.get("doctor_id"),
        "name": name or "Patient",
        "age": req.get("age"),
        "phone": req.get("phone"),
        "parent_email": req.get("parent_email"),
        "patient_uid": uid or None,
        "created_at": req.get("updated_at") or req.get("created_at"),
        "link_status": "cancelled",
        "appointments": matched,
    }


@router.get("/patients/former")
def list_former_patients(doctor: dict[str, Any] = Depends(get_current_doctor)) -> list[dict[str, Any]]:
    db = get_db()
    requests = db.select(
        "patient_requests",
        filters={"doctor_id": f"eq.{doctor['id']}", "status": "eq.cancelled"},
        order="updated_at.desc",
    )
    appointments = db.select(
        "appointments",
        filters={"doctor_id": f"eq.{doctor['id']}"},
        order="appointment_date.desc,start_time.desc",
    )
    return [_former_patient(req, appointments) for req in requests]


@router.delete("/patients/{patient_id}")
def delete_patient(
    patient_id: str,
    doctor: dict[str, Any] = Depends(get_current_doctor),
) -> dict[str, str]:
    db = get_db()
    rows = db.select(
        "patients",
        filters={"id": f"eq.{patient_id}", "doctor_id": f"eq.{doctor['id']}"},
        limit=1,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient = rows[0]
    requests = _accepted_requests_for_patient(db, doctor["id"], patient)
    for req in requests:
        _cancel_request(db, doctor["id"], str(req["id"]))

    filters = {"id": f"eq.{patient_id}", "doctor_id": f"eq.{doctor['id']}"}
    # Keep the patients row only when there is appointment/history value via uid;
    # otherwise delete. Former list is driven by cancelled patient_requests.
    db.delete("patients", filters)

    log.info(
        "END PATIENT LINK | by %s | id=%s | requests_cancelled=%s | moved_to=previous",
        _who(doctor),
        patient_id,
        len(requests),
    )
    return {
        "message": "Patient removed from your active list",
        "moved_to": "previous" if requests else "removed",
        "requests_cancelled": str(len(requests)),
    }


@router.get("/requests")
def list_requests(doctor: dict[str, Any] = Depends(get_current_doctor)) -> list[dict[str, Any]]:
    db = get_db()
    return db.select(
        "patient_requests",
        filters={"doctor_id": f"eq.{doctor['id']}", "status": "eq.pending"},
        order="created_at.desc",
    )


@router.post("/requests/{request_id}/respond")
def respond_request(
    request_id: str,
    body: RequestRespond,
    doctor: dict[str, Any] = Depends(get_current_doctor),
) -> dict[str, Any]:
    db = get_db()
    rows = db.select(
        "patient_requests",
        filters={"id": f"eq.{request_id}", "doctor_id": f"eq.{doctor['id']}"},
        limit=1,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Request not found")
    req = rows[0]
    if req.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Request already handled")

    if body.accept:
        patient = create_patient(
            PatientCreate(
                name=req.get("patient_name") or "Patient",
                age=req.get("age"),
                condition=req.get("condition"),
                phone=req.get("phone"),
                parent_email=req.get("parent_email"),
            ),
            doctor,
        )
        request_uid = str(req.get("patient_uid") or "").strip()
        if request_uid and patient.get("id"):
            db.update(
                "patients",
                {"id": f"eq.{patient['id']}", "doctor_id": f"eq.{doctor['id']}"},
                {"patient_uid": request_uid},
            )
            patient["patient_uid"] = request_uid
        db.update(
            "patient_requests",
            {"id": f"eq.{request_id}"},
            {"status": "accepted"},
        )
        email = (req.get("parent_email") or "").strip()
        if email:
            try:
                send_simple_notice(
                    to_email=email,
                    subject="SpeakEasy — request accepted",
                    message=f"Your request was accepted by {doctor.get('full_name') or 'your therapist'}.",
                )
            except Exception:
                pass
        log.info(
            "REQUEST ACCEPTED | by %s | request=%s | patient=%s",
            _who(doctor),
            request_id,
            req.get("patient_name"),
        )
        return {"status": "accepted", "patient": patient}

    db.update("patient_requests", {"id": f"eq.{request_id}"}, {"status": "declined"})
    log.info(
        "REQUEST DECLINED | by %s | request=%s | patient=%s",
        _who(doctor),
        request_id,
        req.get("patient_name"),
    )
    return {"status": "declined"}
