import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
import uuid

from app.database import get_consent_records_collection, get_patients_collection
from app.models.consent import (
    ConsentStatus,
    ConsentType,
    ConsentRecord,
    ConsentCheckResponse,
    ConsentHistoryResponse,
)
from app.models.audit import AuditEventType
from app.services.audit_service import audit_service

logger = logging.getLogger("medikiosk.consent_service")


class ConsentService:
    """
    Manages patient consent lifecycle:
    - Versioned recording of consent decisions (granted, declined, revoked)
    - Immutable audit trail in `consent_records` collection
    - Traceable revocation with required reasons
    - Pre-flight consent verification gate for downstream clinical flows
    - Zero mock data: all records derived from live user actions
    """

    async def _resolve_patient(self, patient_id: str) -> dict:
        patients_col = get_patients_collection()
        query_filter = None
        try:
            query_filter = {"_id": ObjectId(patient_id)}
        except InvalidId:
            query_filter = {"token_number": patient_id.upper().strip()}

        patient_doc = await patients_col.find_one(query_filter)
        if not patient_doc:
            raise ValueError(f"Patient with identifier '{patient_id}' not found.")
        return patient_doc

    async def record_consent(
        self,
        patient_id: str,
        session_id: Optional[str] = None,
        consent_type: str = ConsentType.GENERAL_INTAKE.value,
        status: str = ConsentStatus.GRANTED.value,
        language: str = "en",
        actor_user_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        consent_text_version: str = "v1.2",
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> ConsentRecord:
        """
        Records a new consent decision, updates the patient document,
        and logs an append-only audit event.
        """
        patient_doc = await self._resolve_patient(patient_id)
        resolved_patient_id = str(patient_doc["_id"])
        now = datetime.now(timezone.utc)

        record = ConsentRecord(
            consent_id=f"con_{uuid.uuid4().hex[:12]}",
            patient_id=resolved_patient_id,
            session_id=session_id,
            consent_type=consent_type,
            status=status,
            timestamp=now,
            language=language,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            consent_text_version=consent_text_version,
            revocation_reason=None,
            metadata=metadata,
        )

        # 1. Insert immutable consent record
        consent_col = get_consent_records_collection()
        await consent_col.insert_one(record.model_dump())

        # 2. Update active status on patient record
        patients_col = get_patients_collection()
        is_granted = (status == ConsentStatus.GRANTED.value)
        update_doc = {
            "consent_given": is_granted,
            "consent_status": status,
            "consent_timestamp": now,
            "consent_version": consent_text_version,
            "selected_language": language,
            "last_consent_id": record.consent_id,
            "registration_status": "consent_granted" if is_granted else "consent_declined",
        }
        if session_id:
            update_doc["session_id"] = session_id

        await patients_col.update_one(
            {"_id": patient_doc["_id"]},
            {
                "$set": update_doc,
                "$push": {
                    "consent_history": {
                        "consent_id": record.consent_id,
                        "action": "consent_recorded",
                        "status": status,
                        "consent_status": status,
                        "timestamp": now,
                        "language": language,
                    }
                },
            },
        )

        # 3. Log audit event
        audit_action = (
            AuditEventType.CONSENT_GRANTED.value
            if is_granted
            else AuditEventType.CONSENT_DECLINED.value
        )
        await audit_service.log_event(
            action=audit_action,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            patient_id=resolved_patient_id,
            session_id=session_id,
            resource_type="consent",
            resource_id=record.consent_id,
            status="success",
            ip_address=ip_address,
            details={
                "consent_type": consent_type,
                "version": consent_text_version,
                "decision": status,
                "language": language,
            },
        )

        return record

    async def revoke_consent(
        self,
        patient_id: str,
        reason: str,
        consent_type: str = ConsentType.GENERAL_INTAKE.value,
        actor_user_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> ConsentRecord:
        """
        Revokes an existing patient consent, sets consent_given to False,
        records the revocation reason, and logs an audit event.
        """
        patient_doc = await self._resolve_patient(patient_id)
        resolved_patient_id = str(patient_doc["_id"])
        now = datetime.now(timezone.utc)

        record = ConsentRecord(
            consent_id=f"con_{uuid.uuid4().hex[:12]}",
            patient_id=resolved_patient_id,
            session_id=patient_doc.get("session_id"),
            consent_type=consent_type,
            status=ConsentStatus.REVOKED.value,
            timestamp=now,
            language=patient_doc.get("selected_language", "en"),
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            consent_text_version=patient_doc.get("consent_version", "v1.2"),
            revocation_reason=reason,
            metadata={"revoked_by": actor_role or "patient"},
        )

        # 1. Insert immutable revocation record
        consent_col = get_consent_records_collection()
        await consent_col.insert_one(record.model_dump())

        # 2. Update patient document to revoked state
        patients_col = get_patients_collection()
        await patients_col.update_one(
            {"_id": patient_doc["_id"]},
            {
                "$set": {
                    "consent_given": False,
                    "consent_status": ConsentStatus.REVOKED.value,
                    "consent_revoked_at": now,
                    "consent_revocation_reason": reason,
                    "registration_status": "consent_revoked",
                },
                "$push": {
                    "consent_history": {
                        "consent_id": record.consent_id,
                        "action": "consent_revoked",
                        "status": ConsentStatus.REVOKED.value,
                        "reason": reason,
                        "timestamp": now,
                    }
                },
            },
        )

        # 3. Log audit event
        await audit_service.log_event(
            action=AuditEventType.CONSENT_REVOKED.value,
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            patient_id=resolved_patient_id,
            resource_type="consent",
            resource_id=record.consent_id,
            status="success",
            ip_address=ip_address,
            details={
                "consent_type": consent_type,
                "reason": reason,
            },
        )

        return record

    async def get_consent_history(self, patient_id: str) -> ConsentHistoryResponse:
        """
        Returns the full immutable history of all consent decisions for a patient.
        """
        patient_doc = await self._resolve_patient(patient_id)
        resolved_patient_id = str(patient_doc["_id"])

        consent_col = get_consent_records_collection()
        cursor = (
            consent_col.find({"patient_id": resolved_patient_id}, {"_id": 0})
            .sort("timestamp", -1)
        )
        docs = await cursor.to_list(length=100)
        history = [ConsentRecord(**doc) for doc in docs]

        current_status = patient_doc.get("consent_status", "none")
        if not current_status and history:
            current_status = history[0].status

        return ConsentHistoryResponse(
            patient_id=resolved_patient_id,
            total_events=len(history),
            current_status=current_status or "none",
            history=history,
        )

    async def check_consent(
        self,
        patient_id: str,
        consent_type: str = ConsentType.GENERAL_INTAKE.value,
    ) -> ConsentCheckResponse:
        """
        Pre-flight check: Verifies if patient currently holds active, granted consent.
        """
        patient_doc = await self._resolve_patient(patient_id)
        resolved_patient_id = str(patient_doc["_id"])

        # Check latest record from consent_records collection
        consent_col = get_consent_records_collection()
        latest = await consent_col.find_one(
            {"patient_id": resolved_patient_id, "consent_type": consent_type},
            sort=[("timestamp", -1)],
        )

        if latest:
            current_status = latest.get("status", "none")
            last_updated = latest.get("timestamp")
            has_valid = (current_status == ConsentStatus.GRANTED.value)
        else:
            # Fallback to patient doc if legacy
            has_valid = bool(patient_doc.get("consent_given") is True)
            current_status = patient_doc.get("consent_status", "granted" if has_valid else "none")
            last_updated = patient_doc.get("consent_timestamp")

        return ConsentCheckResponse(
            patient_id=resolved_patient_id,
            consent_type=consent_type,
            has_valid_consent=has_valid,
            current_status=current_status,
            last_updated=last_updated,
            can_proceed_clinical=has_valid,
        )


consent_service = ConsentService()
