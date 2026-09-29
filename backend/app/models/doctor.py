from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class DoctorReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    NEEDS_VERIFICATION = "needs_verification"
    PHYSICIAN_CONFIRMED = "physician_confirmed"


class DoctorQueuePatient(BaseModel):
    patient_id: str = Field(..., description="Canonical MongoDB ObjectId string")
    token_number: str = Field(..., description="OPD Token e.g. MK-YYYYMMDD-XXXX")
    full_name: str
    age: int
    gender: str
    phone_number: str
    address_city: Optional[str] = None
    registration_date: datetime
    preferred_language: Optional[str] = "en"
    initial_complaint: Optional[str] = None
    triage_status: str = Field(default="normal", description="normal, high_alert, critical")
    active_triage_alerts: int = 0
    highest_triage_priority: Optional[str] = None
    interview_status: str = Field(default="not_started", description="not_started, in_progress, completed")
    interview_answers_count: int = 0
    document_count: int = 0
    processed_document_count: int = 0
    has_summary: bool = False
    summary_status: str = Field(default="not_generated", description="not_generated, ai_generated, physician_reviewed, physician_confirmed")
    doctor_review_status: str = Field(default="pending_review", description="pending_review, in_review, needs_verification, physician_confirmed")
    has_conflicts: bool = False
    conflict_count: int = 0
    last_activity: datetime


class DoctorQueueResponse(BaseModel):
    total_patients: int
    pending_review_count: int
    in_review_count: int
    needs_verification_count: int
    confirmed_count: int
    high_triage_count: int
    patients: List[DoctorQueuePatient]


class SummaryVersionRecord(BaseModel):
    version: int
    summary_draft: str
    modified_at: datetime
    modified_by: str = "Attending Physician"
    reason: Optional[str] = None


class SummaryEditRequest(BaseModel):
    summary_draft: Optional[str] = Field(None, description="Updated full text narrative summary")
    sections: Optional[Dict[str, Dict[str, Any]]] = Field(None, description="Optional per-section content modifications")
    physician_notes: Optional[str] = Field(None, description="Clinical commentary from attending physician")
    doctor_name: Optional[str] = Field("Attending Physician", description="Physician identifier/name")


class SummaryConfirmRequest(BaseModel):
    doctor_notes: Optional[str] = Field(None, description="Final sign-off notes")
    confirmed_by: Optional[str] = Field("Attending Physician", description="Name of signing physician")


class ReviewStatusUpdateRequest(BaseModel):
    review_status: str = Field(..., description="pending_review, in_review, needs_verification, physician_confirmed")
    notes: Optional[str] = Field(None, description="Review notes")


class PatientClinicalDetailResponse(BaseModel):
    patient: Dict[str, Any]
    interview: Dict[str, Any]
    triage_alerts: List[Dict[str, Any]]
    documents: List[Dict[str, Any]]
    ocr_extracted: Dict[str, Any]
    timeline: Dict[str, Any]
    summary: Dict[str, Any]
    conflicts: List[Dict[str, Any]]
    review_info: Dict[str, Any]
    ayush_history: Optional[Dict[str, Any]] = None
