import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import uuid

from app.database import get_audit_logs_collection
from app.models.audit import AuditEventType, AuditLogEntry, AuditLogListResponse

logger = logging.getLogger("medikiosk.audit_service")

# Sensitive fields that must NEVER appear in audit details or logs
SENSITIVE_KEYS = {
    "password", "hashed_password", "token", "access_token",
    "refresh_token", "authorization", "secret", "api_key",
    "client_secret", "jwt_secret", "bearer"
}


def is_sensitive_key(key: str) -> bool:
    k = str(key).lower()
    if "token_number" in k or "token_no" in k:
        return False
    return any(s in k for s in SENSITIVE_KEYS)


def sanitize_audit_details(data: Any, depth: int = 0) -> Any:
    """
    Recursively sanitize dictionaries/lists to ensure no secrets or credential leaks
    are ever persisted to the audit trail.
    """
    if depth > 5:
        return "[MaxDepth]"
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if is_sensitive_key(k):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                sanitized[k] = sanitize_audit_details(v, depth + 1)
            else:
                sanitized[k] = v
        return sanitized
    elif isinstance(data, list):
        return [sanitize_audit_details(item, depth + 1) for item in data]
    return data


class AuditService:
    """
    Append-only security and clinical audit service.
    Guarantees that sensitive actions are recorded for traceability and compliance,
    without storing plaintext credentials, JWTs, or raw PHI text.
    """

    async def log_event(
        self,
        action: str,
        actor_user_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        patient_id: Optional[str] = None,
        session_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = "success",
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLogEntry:
        """
        Appends an immutable audit event to MongoDB audit_logs collection.
        """
        sanitized_details = sanitize_audit_details(details) if details else None

        entry = AuditLogEntry(
            event_id=f"aud_{uuid.uuid4().hex[:12]}",
            action=action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            patient_id=patient_id,
            session_id=session_id,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            ip_address=ip_address,
            timestamp=datetime.now(timezone.utc),
            details=sanitized_details,
        )

        try:
            col = get_audit_logs_collection()
            doc = entry.model_dump()
            await col.insert_one(doc)
            logger.info(
                f"[AUDIT] action={action} actor={actor_user_id} role={actor_role} "
                f"patient={patient_id} status={status}"
            )
        except Exception as e:
            # Audit logging failure should not crash core user flows, but must be logged loudly
            logger.error(f"[AUDIT_ERROR] Failed to persist audit log: {str(e)}", exc_info=True)

        return entry

    async def get_audit_logs(
        self,
        skip: int = 0,
        limit: int = 50,
        action: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> AuditLogListResponse:
        """
        Retrieves paginated audit log entries with optional filters.
        """
        col = get_audit_logs_collection()
        query_filter: Dict[str, Any] = {}

        if action:
            query_filter["action"] = action
        if actor_user_id:
            query_filter["actor_user_id"] = actor_user_id
        if patient_id:
            query_filter["patient_id"] = patient_id
        if status:
            query_filter["status"] = status

        total_count = await col.count_documents(query_filter)
        cursor = (
            col.find(query_filter, {"_id": 0})
            .sort("timestamp", -1)
            .skip(skip)
            .limit(limit)
        )

        docs = await cursor.to_list(length=limit)
        entries = [AuditLogEntry(**doc) for doc in docs]

        return AuditLogListResponse(
            total_count=total_count,
            skip=skip,
            limit=limit,
            logs=entries,
        )

    async def get_patient_audit_logs(
        self,
        patient_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> AuditLogListResponse:
        """
        Retrieves all audit events associated with a specific patient.
        """
        return await self.get_audit_logs(
            skip=skip,
            limit=limit,
            patient_id=patient_id,
        )


audit_service = AuditService()
