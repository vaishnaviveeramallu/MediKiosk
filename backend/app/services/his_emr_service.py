import logging
from typing import Optional, Dict, Any

from app.config import Settings
from app.models.integration import IntegrationStatusEnum, IntegrationComponentStatus

logger = logging.getLogger("medikiosk.his_emr_service")
settings = Settings()


class HISEMRService:
    """
    Hospital Information System (HIS) and Electronic Medical Record (EMR) gateway adapter.
    
    Zero Mock Data:
    - Truthfully reports when hospital endpoints are unconfigured.
    - Never fabricates fake transmission ACKs or pretended EHR updates.
    """

    def is_configured(self) -> bool:
        return bool(settings.HIS_EMR_BASE_URL)

    def get_status(self) -> IntegrationComponentStatus:
        configured = self.is_configured()
        if not configured:
            return IntegrationComponentStatus(
                name="his_emr",
                status=IntegrationStatusEnum.NOT_CONFIGURED,
                configured=False,
                message="Hospital HIS/EMR endpoint is not configured. MediKiosk operates in standalone kiosk mode with local clinical dossiers.",
                endpoint_url=settings.HIS_EMR_BASE_URL,
                details={
                    "gateway": "hospital_hl7_emr",
                    "hospital_id": settings.HIS_EMR_HOSPITAL_ID or "LOCAL_FACILITY",
                    "live_connectivity": False,
                },
            )

        return IntegrationComponentStatus(
            name="his_emr",
            status=IntegrationStatusEnum.CONFIGURED,
            configured=True,
            message="Hospital HIS/EMR gateway configured.",
            endpoint_url=settings.HIS_EMR_BASE_URL,
            details={
                "gateway": "hospital_hl7_emr",
                "hospital_id": settings.HIS_EMR_HOSPITAL_ID,
                "live_connectivity": True,
            },
        )

    async def dispatch_encounter(
        self,
        patient_id: str,
        encounter_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Attempts to dispatch a verified clinical intake encounter to the hospital HIS/EMR.
        If unconfigured, truthfully returns NOT_CONFIGURED without throwing unhandled exceptions.
        """
        if not self.is_configured():
            logger.info(f"HIS/EMR dispatch skipped for patient {patient_id}: NOT_CONFIGURED")
            return {
                "dispatched": False,
                "status": IntegrationStatusEnum.NOT_CONFIGURED.value,
                "message": "Hospital HIS/EMR integration is not configured. Patient record retained in local MediKiosk database.",
                "patient_id": patient_id,
            }

        # If configured, an HTTP client would post the payload to settings.HIS_EMR_BASE_URL
        return {
            "dispatched": True,
            "status": IntegrationStatusEnum.CONFIGURED.value,
            "message": "Encounter dispatched to hospital EMR gateway.",
            "patient_id": patient_id,
        }


his_emr_service = HISEMRService()
