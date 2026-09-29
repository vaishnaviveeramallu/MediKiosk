from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class AuditEventType(str, Enum):
    # Authentication & User Management
    AUTH_LOGIN_SUCCESS = "auth_login_success"
    AUTH_LOGIN_FAILURE = "auth_login_failure"
    AUTH_LOGOUT = "auth_logout"
    AUTH_REGISTER = "auth_register"

    # Patient Registration & Profile
    PATIENT_REGISTER = "patient_register"
    PATIENT_VIEW = "patient_view"

    # Consent Lifecycle
    CONSENT_GRANTED = "consent_granted"
    CONSENT_REVOKED = "consent_revoked"
    CONSENT_DECLINED = "consent_declined"
    CONSENT_CHECKED = "consent_checked"

    # Clinical Intake & Adaptive Interview
    INTERVIEW_START = "interview_start"
    INTERVIEW_ANSWER = "interview_answer"
    INTERVIEW_COMPLETE = "interview_complete"

    # Medical Documents & OCR
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_PROCESS = "document_process"
    DOCUMENT_VIEW = "document_view"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_VERIFY = "document_verify"

    # Clinical Timeline & Summary
    TIMELINE_GENERATE = "timeline_generate"
    SUMMARY_GENERATE = "summary_generate"
    SUMMARY_EDIT = "summary_edit"
    SUMMARY_CONFIRM = "summary_confirm"

    # Triage & Alerts
    TRIAGE_ALERT_ACKNOWLEDGED = "triage_alert_acknowledged"
    TRIAGE_ALERT_HANDLED = "triage_alert_handled"

    # Security & Access Violations
    SECURITY_IDOR_BLOCKED = "security_idor_blocked"
    SECURITY_UNAUTHORIZED_ACCESS = "security_unauthorized_access"


class AuditLogEntry(BaseModel):
    event_id: str = Field(default_factory=lambda: f"aud_{uuid.uuid4().hex[:12]}")
    action: str = Field(..., description="Action or event type")
    actor_user_id: Optional[str] = Field(None, description="User ID performing the action")
    actor_role: Optional[str] = Field(None, description="Role: patient, doctor, triage_staff, system")
    patient_id: Optional[str] = Field(None, description="Associated patient ID if applicable")
    session_id: Optional[str] = Field(None, description="Associated interview session ID if applicable")
    resource_type: Optional[str] = Field(None, description="e.g. patient, document, summary, session")
    resource_id: Optional[str] = Field(None, description="ID of the resource acted upon")
    status: str = Field("success", description="Status: success, failure, blocked")
    ip_address: Optional[str] = Field(None, description="Client IP address if available")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Optional[Dict[str, Any]] = Field(None, description="Sanitized safe metadata only")


class AuditLogListResponse(BaseModel):
    total_count: int
    skip: int = 0
    limit: int = 50
    logs: List[AuditLogEntry]
