"""
Shared FastAPI dependencies.
"""

from app.core.security import get_current_doctor, get_current_doctor_id

__all__ = ["get_current_doctor", "get_current_doctor_id"]
