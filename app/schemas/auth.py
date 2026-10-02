from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=72)
    full_name: str = Field(min_length=2, max_length=80)
    phone: str = ""
    qualification: str = ""
    license_number: str = ""
    years_of_experience: int = Field(default=0, ge=0, le=50)
    languages_spoken: str = ""
    consultation_fee: float = Field(default=0, ge=0)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    doctor: dict[str, Any]


class MessageResponse(BaseModel):
    message: str


class VerifyEmailRequest(BaseModel):
    token: str | None = None
    email: EmailStr | None = None
    code: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str | None = None
    email: EmailStr | None = None
    code: str | None = None
    new_password: str = Field(min_length=6, max_length=72)


class GoogleLoginRequest(BaseModel):
    id_token: str


class TherapistUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    qualification: Optional[str] = None
    license_number: Optional[str] = None
    years_of_experience: Optional[int] = None
    languages_spoken: Optional[str] = None
    consultation_fee: Optional[float] = None


class SetPasswordRequest(BaseModel):
    """Set password (Google accounts) or update with current password."""
    new_password: str = Field(min_length=6, max_length=72)
    current_password: Optional[str] = None


class PatientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    condition: Optional[str] = None
    phone: Optional[str] = None
    parent_email: Optional[str] = None
    notes: Optional[str] = None


class PatientUpdate(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    phone: Optional[str] = None
    parent_email: Optional[str] = None
    notes: Optional[str] = None
    condition: Optional[str] = None


class RequestRespond(BaseModel):
    accept: bool


class AvailabilityUpsert(BaseModel):
    day: str
    start_time: str  # HH:MM
    end_time: str
    is_active: bool = True
    id: Optional[str] = None


class AppointmentRespond(BaseModel):
    confirm: bool


class AppointmentCancel(BaseModel):
    reason: Optional[str] = None
