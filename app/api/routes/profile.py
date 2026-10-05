from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.schemas.auth import MessageResponse, SetPasswordRequest, TherapistUpdate
from app.core.security import (
    get_current_doctor,
    hash_password,
    public_therapist,
    verify_password,
)
from app.repositories.supabase_client import get_db
from app.core.logging import get_logger

router = APIRouter(prefix="/me", tags=["profile"])
log = get_logger("profile")


@router.get("")
def get_me(doctor: dict[str, Any] = Depends(get_current_doctor)) -> dict[str, Any]:
    return public_therapist(doctor)


@router.patch("")
def update_me(
    body: TherapistUpdate,
    doctor: dict[str, Any] = Depends(get_current_doctor),
) -> dict[str, Any]:
    patch = body.model_dump(exclude_unset=True)
    if not patch:
        return public_therapist(doctor)
    db = get_db()
    rows = db.update("therapists", {"id": f"eq.{doctor['id']}"}, patch)
    if not rows:
        raise HTTPException(status_code=400, detail="Could not update profile")
    log.info(
        "PROFILE UPDATE | %s <%s> | fields=%s",
        doctor.get("full_name"),
        doctor.get("email"),
        list(patch.keys()),
    )
    return public_therapist(rows[0])


@router.post("/password", response_model=MessageResponse)
def set_or_update_password(
    body: SetPasswordRequest,
    doctor: dict[str, Any] = Depends(get_current_doctor),
) -> MessageResponse:
    """Google users set a password; email users update with current password."""
    existing_hash = doctor.get("password_hash") or ""
    has_password = bool(existing_hash)

    if has_password:
        current = (body.current_password or "").strip()
        if not current:
            raise HTTPException(status_code=400, detail="Current password is required.")
        if not verify_password(current, existing_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")
    elif body.current_password:
        raise HTTPException(
            status_code=400,
            detail="No password is set yet. Leave current password empty.",
        )

    db = get_db()
    rows = db.update(
        "therapists",
        {"id": f"eq.{doctor['id']}"},
        {"password_hash": hash_password(body.new_password)},
    )
    if not rows:
        raise HTTPException(status_code=400, detail="Could not save password.")

    log.info(
        "PASSWORD %s | %s <%s>",
        "UPDATED" if has_password else "SET",
        doctor.get("full_name"),
        doctor.get("email"),
    )
    return MessageResponse(
        message="Password updated." if has_password else "Password set. You can also sign in with email."
    )


@router.delete("")
def delete_me(doctor: dict[str, Any] = Depends(get_current_doctor)) -> dict[str, str]:
    """
    Permanently delete this therapist from the database.

    Cascades (via FK or explicit deletes):
    patients, patient_requests, availability, appointments, therapist_ratings.
    Also removes email_tokens and clears profiles.doctor_uid links.
    Patient practice data (attempts / focus_sound) is NOT deleted — it belongs
    to the child/parent account.
    """
    db = get_db()
    doctor_id = str(doctor["id"])
    email = str(doctor.get("email") or "")

    # Auth tokens (no guaranteed FK cascade)
    try:
        db.delete("email_tokens", {"doctor_id": f"eq.{doctor_id}"})
    except Exception as exc:
        log.warning("email_tokens cleanup failed for %s: %s", doctor_id, exc)

    # Explicit child rows first (safe even if DB cascade is missing)
    for table in (
        "therapist_ratings",
        "appointments",
        "availability",
        "patient_requests",
        "patients",
    ):
        try:
            db.delete(table, {"doctor_id": f"eq.{doctor_id}"})
        except Exception as exc:
            log.warning("%s cleanup failed for %s: %s", table, doctor_id, exc)

    # Unlink from parent/user profiles (ON DELETE SET NULL — do it explicitly too)
    try:
        db.update(
            "profiles",
            {"doctor_uid": f"eq.{doctor_id}"},
            {"doctor_uid": None},
        )
    except Exception as exc:
        log.warning("profiles.doctor_uid clear failed for %s: %s", doctor_id, exc)

    try:
        db.delete("therapists", {"id": f"eq.{doctor_id}"})
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not delete account: {exc}",
        ) from exc

    # Confirm gone
    left = db.select("therapists", filters={"id": f"eq.{doctor_id}"}, limit=1)
    if left:
        raise HTTPException(status_code=500, detail="Account delete did not complete.")

    log.info("ACCOUNT DELETED | %s <%s> | id=%s", doctor.get("full_name"), email, doctor_id)
    return {"message": "Account permanently deleted from the database."}
