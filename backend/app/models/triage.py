from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class TriageAlertPriority(str, Enum):
    URGENT = "URGENT"
    HIGH = "HIGH"


class TriageAlertStatus(str, Enum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    HANDLED = "handled"


class TriageDetectionResult(BaseModel):
    has_red_flag: bool = Field(False, description="Whether any red flag symptom was detected")
    category: Optional[str] = Field(None, description="Clinical category of warning sign")
    priority: Optional[TriageAlertPriority] = Field(None, description="Triage priority level")
    matched_keywords: List[str] = Field(default_factory=list, description="Keywords that matched")
    rule_description: Optional[str] = Field(None, description="Transparent explanation of the triggered rule")
    patient_instruction_en: Optional[str] = Field(None, description="English emergency guidance")
    patient_instruction_hi: Optional[str] = Field(None, description="Hindi emergency guidance")


class TriageAlertRecord(BaseModel):
    alert_id: str = Field(..., description="Unique alert identifier (e.g. ALT-XXXX)")
    patient_id: str = Field(..., description="Patient identifier")
    token_number: str = Field(..., description="OPD Token number")
    patient_name: str = Field(..., description="Patient full name")
    session_id: str = Field(..., description="Interview session ID")
    question_id: Optional[str] = Field(None, description="Triggering question ID")
    question_text: Optional[str] = Field(None, description="Question prompt")
    triggering_answer: str = Field(..., description="Actual patient answer triggering the alert")
    detected_category: str = Field(..., description="Warning sign category")
    priority: TriageAlertPriority = Field(default=TriageAlertPriority.URGENT)
    rule_description: str = Field(..., description="Rule rationale")
    matched_keywords: List[str] = Field(default_factory=list)
    detected_at: datetime = Field(..., description="Timestamp when red flag was detected")
    status: TriageAlertStatus = Field(default=TriageAlertStatus.ACTIVE)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    handled_at: Optional[datetime] = None
    handled_by: Optional[str] = None
    staff_notes: Optional[str] = None
    patient_instruction_en: Optional[str] = None
    patient_instruction_hi: Optional[str] = None


class TriageCheckRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Patient response text to analyze")
    language: str = Field(default="en", description="Response language: 'en' or 'hi'")


class TriageUpdateRequest(BaseModel):
    status: Optional[TriageAlertStatus] = Field(None, description="New alert status: 'acknowledged' or 'handled'")
    staff_notes: Optional[str] = Field(None, description="Staff observation or resolution notes")
    staff_id: Optional[str] = Field(default="triage_nurse", description="Staff identifier")


class TriageListResponse(BaseModel):
    total_count: int
    active_count: int
    alerts: List[TriageAlertRecord]
