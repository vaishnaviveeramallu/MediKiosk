from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TimelineEventType(str, Enum):
    SYMPTOM_REPORTED = "symptom_reported"
    DIAGNOSIS_DOCUMENTED = "diagnosis_documented"
    MEDICATION_PRESCRIBED = "medication_prescribed"
    INVESTIGATION_RESULT = "investigation_result"
    PROCEDURE_PERFORMED = "procedure_performed"
    HOSPITAL_DISCHARGE = "hospital_discharge"
    ALLERGY_DOCUMENTED = "allergy_documented"
    TRIAGE_ALERT = "triage_alert"
    CLINICAL_HISTORY = "clinical_history"


class TimelineEvent(BaseModel):
    event_id: str = Field(..., description="Unique event identifier (e.g. TLE-YYYYMMDD-XXXX)")
    event_date: Optional[str] = Field(None, description="ISO formatted date if known; None for undated")
    display_date: str = Field(..., description="Human-readable date string or 'Date not specified'")
    event_type: TimelineEventType = Field(..., description="Clinical category of event")
    title: str = Field(..., description="Concise event title")
    details: Dict[str, Any] = Field(default_factory=dict, description="Structured clinical payload")
    source: str = Field(..., description="Source provenance: patient_interview, medical_document, triage")
    source_label: str = Field(..., description="User-facing source label")
    source_document_id: Optional[str] = Field(None, description="Linked DOC-... identifier if from document")
    source_session_id: Optional[str] = Field(None, description="Linked interview session identifier")
    verification_status: str = Field(default="needs_review", description="unverified, needs_review, verified")
    is_conflict: bool = Field(default=False, description="True if this event contradicts other patient data")
    conflict_notes: Optional[str] = Field(None, description="Explanation of contradiction")


class MedicalTimelineResponse(BaseModel):
    patient_id: str
    token_number: str
    patient_name: str
    total_events: int
    dated_events: List[TimelineEvent] = Field(default_factory=list, description="Events sorted chronologically")
    undated_events: List[TimelineEvent] = Field(default_factory=list, description="Events with unspecified date")
    has_conflicts: bool = False
    conflict_count: int = 0
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class ClinicalSummarySection(BaseModel):
    section_id: str = Field(..., description="Unique slug for section e.g. chief_complaint")
    section_number: int = Field(..., description="Standard order 1-14")
    title: str = Field(..., description="Section title")
    content: str = Field(..., description="Narrative summary text or 'Not available...'")
    items: List[Dict[str, Any]] = Field(default_factory=list, description="Structured bullet items if applicable")
    is_available: bool = Field(default=True, description="False if no data was provided")
    source_references: List[str] = Field(default_factory=list, description="List of source attributions")
    requires_verification: bool = Field(default=True)


class ClinicalSummaryResponse(BaseModel):
    patient_id: str
    token_number: str
    patient_name: str
    summary_draft: str = Field(..., description="Full physician-ready narrative summary draft")
    sections: Dict[str, ClinicalSummarySection] = Field(..., description="Map of 14 standard clinical sections")
    disclaimer: str = Field(
        default="AI-generated draft — physician verification required. Not a medical diagnosis.",
        description="Clinical safety disclaimer"
    )
    verification_status: str = Field(default="needs_review", description="needs_review, verified")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    source_counts: Dict[str, int] = Field(
        default_factory=lambda: {"interview_answers": 0, "documents": 0, "triage_alerts": 0}
    )
    conflicting_findings: List[str] = Field(default_factory=list)


class SummaryRegenerateRequest(BaseModel):
    reason: Optional[str] = Field(None, description="Optional note or reason for regeneration")
