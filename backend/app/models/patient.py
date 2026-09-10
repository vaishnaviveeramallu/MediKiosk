from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
import re


class PatientCreate(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Patient full legal name")
    age: int = Field(..., ge=1, le=125, description="Patient age in years")
    gender: str = Field(..., description="Gender (Male, Female, Other, Prefer not to say)")
    phone_number: str = Field(..., description="10-digit contact mobile number")
    emergency_contact_name: Optional[str] = Field(None, max_length=100)
    emergency_contact_phone: Optional[str] = Field(None)
    address_city: Optional[str] = Field(None, max_length=100)
    address_state: Optional[str] = Field(None, max_length=100)
    government_id_type: Optional[str] = Field(None, description="e.g. Aadhaar, ABHA, Voter ID, Passport")
    government_id_number: Optional[str] = Field(None, max_length=50)
    initial_complaint: Optional[str] = Field(None, max_length=500, description="Primary symptom or reason for OPD visit")

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Patient name must be at least 2 characters long")
        return cleaned

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v: str) -> str:
        valid_genders = ["Male", "Female", "Other", "Prefer not to say"]
        matched = [g for g in valid_genders if g.lower() == v.strip().lower()]
        if not matched:
            raise ValueError(f"Gender must be one of: {', '.join(valid_genders)}")
        return matched[0]

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        # Strip common formatting like spaces, dashes, +91
        digits = re.sub(r"\D", "", v)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        elif digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]

        if len(digits) != 10:
            raise ValueError("Mobile number must be a valid 10-digit Indian phone number")
        return digits

    @field_validator("emergency_contact_phone")
    @classmethod
    def validate_emergency_phone(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return None
        digits = re.sub(r"\D", "", v)
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        elif digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) != 10:
            raise ValueError("Emergency contact number must be a valid 10-digit number")
        return digits


class ConsentRequest(BaseModel):
    selected_language: str = Field(..., description="Language code e.g. 'en' or 'hi'")
    consent_status: str = Field(..., description="'granted' or 'declined'")
    session_id: Optional[str] = Field(None, description="Optional client session UUID")

    @field_validator("selected_language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        code = v.strip().lower()
        if code not in ["en", "hi"]:
            raise ValueError("Supported languages at this stage are 'en' (English) and 'hi' (Hindi)")
        return code

    @field_validator("consent_status")
    @classmethod
    def validate_consent_status(cls, v: str) -> str:
        status_val = v.strip().lower()
        if status_val not in ["granted", "declined"]:
            raise ValueError("consent_status must be either 'granted' or 'declined'")
        return status_val


class PatientResponse(BaseModel):
    id: str
    token_number: str
    full_name: str
    age: int
    gender: str
    phone_number: str
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    government_id_type: Optional[str] = None
    government_id_number: Optional[str] = None
    initial_complaint: Optional[str] = None
    registration_status: str
    created_at: datetime

    # Phase 2 Consent & Language Fields
    selected_language: Optional[str] = None
    consent_status: Optional[str] = None
    consent_given: Optional[bool] = None
    consent_timestamp: Optional[datetime] = None
    session_id: Optional[str] = None

    # Future phase extensibility placeholders
    preferred_language: Optional[str] = None
    clinical_history: Optional[Dict[str, Any]] = None
    red_flags: Optional[List[Dict[str, Any]]] = None
    documents: Optional[List[Dict[str, Any]]] = None
    clinical_summary: Optional[Dict[str, Any]] = None
