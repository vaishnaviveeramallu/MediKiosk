from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class ConsentStatus(str, Enum):
    GRANTED = "granted"
    REVOKED = "revoked"
    DECLINED = "declined"


class ConsentType(str, Enum):
    GENERAL_INTAKE = "general_medical_intake"
    AYUSH_INTAKE = "ayush_intake"
    DATA_PROCESSING = "data_processing"
    RECORD_SHARING = "record_sharing"


class ConsentRecord(BaseModel):
    consent_id: str = Field(default_factory=lambda: f"con_{uuid.uuid4().hex[:12]}")
    patient_id: str
    session_id: Optional[str] = None
    consent_type: str = "general_medical_intake"
    status: str = "granted"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    language: str = "en"
    actor_user_id: Optional[str] = None
    actor_role: Optional[str] = None
    consent_text_version: str = "v1.2"
    revocation_reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConsentRevokeRequest(BaseModel):
    reason: str = Field(..., min_length=2, max_length=500, description="Reason for withdrawing/revoking consent")
    consent_type: Optional[str] = Field("general_medical_intake", description="Type of consent to revoke")


class ConsentCheckResponse(BaseModel):
    patient_id: str
    consent_type: str
    has_valid_consent: bool
    current_status: str
    last_updated: Optional[datetime] = None
    can_proceed_clinical: bool


class ConsentHistoryResponse(BaseModel):
    patient_id: str
    total_events: int
    current_status: str
    history: List[ConsentRecord]
