from typing import Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class UserRole(str, Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    TRIAGE_STAFF = "triage_staff"


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username for login")
    password: str = Field(..., min_length=6, description="Plaintext password to be hashed securely with bcrypt")
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name of user")
    role: UserRole = Field(default=UserRole.PATIENT, description="System role: patient, doctor, or triage_staff")
    email_or_phone: Optional[str] = Field(None, description="Contact email or phone number")
    patient_id: Optional[str] = Field(None, description="Linked patient document ID if role is patient")


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, description="Username, email, or phone")
    password: str = Field(..., min_length=1, description="Account password")


class UserProfile(BaseModel):
    user_id: str
    username: str
    full_name: str
    role: UserRole
    patient_id: Optional[str] = None
    email_or_phone: Optional[str] = None
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserProfile
