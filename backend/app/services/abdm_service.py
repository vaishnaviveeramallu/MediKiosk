import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId

from app.config import Settings
from app.database import get_patients_collection
from app.models.integration import IntegrationStatusEnum, IntegrationComponentStatus
from app.services.audit_service import audit_service

logger = logging.getLogger("medikiosk.abdm_service")
settings = Settings()


class ABDMService:
    """
    Ayushman Bharat Digital Mission (ABDM) / ABHA integration boundary.
    Adheres strictly to the Zero Mock Data rule:
    - Reports truthfully whether official credentials and bridge endpoints are configured.
    - Never fabricates fake external ABHA identifiers or pretends live sandbox connectivity exists.
    - Manages authentic patient-provided ABHA numbers with format validation and local persistence.
    """

    def is_configured(self) -> bool:
        """
        Returns True only if official ABDM client credentials and base URL are configured.
        """
        return bool(
            settings.ABDM_CLIENT_ID
            and settings.ABDM_CLIENT_SECRET
            and settings.ABDM_BASE_URL
        )

    def get_status(self) -> IntegrationComponentStatus:
        """
        Returns truthful architectural status for ABDM/ABHA integration.
        """
        configured = self.is_configured()
        if not configured:
            return IntegrationComponentStatus(
                name="abdm_abha",
                status=IntegrationStatusEnum.NOT_CONFIGURED,
                configured=False,
                message="ABDM/ABHA gateway credentials are not configured. MediKiosk operates in standalone mode without mock external identifiers.",
                endpoint_url=settings.ABDM_BASE_URL,
                details={
                    "gateway": "abdm_bridge",
                    "live_connectivity": False,
                    "auth_mode": "local_patient_id",
                    "documentation": "https://sandbox.abdm.gov.in/docs",
                },
            )

        return IntegrationComponentStatus(
            name="abdm_abha",
            status=IntegrationStatusEnum.CONFIGURED,
            configured=True,
            message="ABDM gateway credentials configured.",
            endpoint_url=settings.ABDM_BASE_URL,
            details={
                "gateway": "abdm_bridge",
                "client_id": settings.ABDM_CLIENT_ID[:4] + "****" if settings.ABDM_CLIENT_ID else None,
                "live_connectivity": True,
            },
        )

    def validate_abha_number(self, abha_number: str) -> str:
        """
        Validates authentic ABHA format (14 digits, optional hyphens e.g. 12-3456-7890-1234).
        Returns normalized 14-digit string or raises ValueError.
        """
        cleaned = re.sub(r"[-\s]", "", abha_number.strip())
        if not (cleaned.isdigit() and len(cleaned) == 14):
            raise ValueError("Invalid ABHA number format. Authentic ABHA must be exactly 14 digits.")
        return cleaned

    def validate_abha_address(self, abha_address: str) -> str:
        """
        Validates authentic ABHA address format (e.g., name@abdm).
        """
        cleaned = abha_address.strip().lower()
        if not re.match(r"^[a-zA-Z0-9._]+@[a-zA-Z0-9]+$", cleaned):
            raise ValueError("Invalid ABHA address format. Must be like username@abdm.")
        return cleaned

    async def link_abha(
        self,
        patient_id: str,
        abha_number: str,
        abha_address: Optional[str] = None,
        actor_user_id: Optional[str] = None,
        actor_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Links a validated ABHA number/address to an existing real patient record in MongoDB.
        Zero mock data: stores only actual user-submitted ABHA identifiers.
        """
        clean_number = self.validate_abha_number(abha_number)
        clean_address = self.validate_abha_address(abha_address) if abha_address else None

        patients_col = get_patients_collection()
        try:
            q = {"_id": ObjectId(patient_id)}
        except InvalidId:
            q = {"token_number": patient_id.upper().strip()}

        patient_doc = await patients_col.find_one(q)
        if not patient_doc:
            raise ValueError(f"Patient '{patient_id}' not found.")

        now = datetime.now(timezone.utc)
        update_fields = {
            "abha_number": clean_number,
            "abha_linked": True,
            "abha_linked_at": now,
        }
        if clean_address:
            update_fields["abha_address"] = clean_address

        await patients_col.update_one(
            {"_id": patient_doc["_id"]},
            {"$set": update_fields},
        )

        resolved_id = str(patient_doc["_id"])
        await audit_service.log_event(
            action="patient_abha_linked",
            actor_user_id=actor_user_id,
            actor_role=actor_role,
            patient_id=resolved_id,
            resource_type="patient",
            resource_id=resolved_id,
            details={
                "abha_masked": clean_number[:2] + "XXXXXXXX" + clean_number[-4:],
                "has_abha_address": bool(clean_address),
            },
        )

        return {
            "patient_id": resolved_id,
            "abha_linked": True,
            "abha_masked": clean_number[:2] + "XXXXXXXX" + clean_number[-4:],
            "abha_address": clean_address,
            "linked_at": now.isoformat(),
        }

    async def get_patient_abha(self, patient_id: str) -> Dict[str, Any]:
        """
        Retrieves ABHA linking status for a patient without exposing sensitive information.
        """
        patients_col = get_patients_collection()
        try:
            q = {"_id": ObjectId(patient_id)}
        except InvalidId:
            q = {"token_number": patient_id.upper().strip()}

        patient_doc = await patients_col.find_one(q)
        if not patient_doc:
            raise ValueError(f"Patient '{patient_id}' not found.")

        linked = bool(patient_doc.get("abha_linked") is True)
        raw_num = patient_doc.get("abha_number")
        masked = (raw_num[:2] + "XXXXXXXX" + raw_num[-4:]) if (linked and raw_num and len(raw_num) == 14) else None

        return {
            "patient_id": str(patient_doc["_id"]),
            "abha_linked": linked,
            "abha_masked": masked,
            "abha_address": patient_doc.get("abha_address"),
            "linked_at": patient_doc.get("abha_linked_at"),
        }


abdm_service = ABDMService()
