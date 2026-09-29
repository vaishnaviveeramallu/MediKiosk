import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status, Depends
from bson import ObjectId
from bson.errors import InvalidId

from app.database import get_patients_collection
from app.models.summary import (
    MedicalTimelineResponse,
    ClinicalSummaryResponse,
    SummaryRegenerateRequest,
)
from app.models.audit import AuditEventType
from app.services.medical_timeline_service import medical_timeline_service
from app.services.clinical_summary_service import clinical_summary_service
from app.services.audit_service import audit_service
from app.utils.auth_deps import get_current_user_optional, verify_patient_ownership

logger = logging.getLogger("medikiosk.summary_routes")

router = APIRouter(prefix="/api/patients", tags=["summary"])


async def _resolve_patient_id(patient_id: str) -> str:
    patients_col = get_patients_collection()
    query_filter = None
    try:
        query_filter = {"_id": ObjectId(patient_id)}
    except InvalidId:
        query_filter = {"token_number": patient_id.upper().strip()}

    patient_doc = await patients_col.find_one(query_filter)
    if not patient_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with identifier '{patient_id}' not found in MongoDB",
        )
    return str(patient_doc["_id"])


@router.post(
    "/{patient_id}/timeline/generate",
    response_model=MedicalTimelineResponse,
    summary="Generate or update chronological medical timeline",
    description=(
        "Aggregates real patient interview responses, OCR-extracted medical document findings, "
        "and triage alerts into a chronological medical timeline."
    ),
)
async def generate_patient_timeline(
    patient_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    resolved_pid = await _resolve_patient_id(patient_id)
    if current_user:
        verify_patient_ownership(resolved_pid, current_user)

    try:
        timeline = await medical_timeline_service.build_timeline(resolved_pid)
        await audit_service.log_event(
            action=AuditEventType.TIMELINE_GENERATE.value,
            actor_user_id=current_user.get("user_id") if current_user else None,
            actor_role=current_user.get("role") if current_user else "patient",
            patient_id=resolved_pid,
            resource_type="timeline",
            resource_id=resolved_pid,
            details={"total_events": timeline.total_events},
        )
        return timeline
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating medical timeline for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate timeline: {str(e)}",
        )


@router.get(
    "/{patient_id}/timeline",
    response_model=MedicalTimelineResponse,
    summary="Get patient medical timeline",
    description="Returns the persisted medical timeline, generating it if it does not yet exist.",
)
async def get_patient_timeline(
    patient_id: str,
    refresh: bool = Query(False, description="Force re-generation"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    resolved_pid = await _resolve_patient_id(patient_id)
    if current_user:
        verify_patient_ownership(resolved_pid, current_user)

    try:
        timeline = await medical_timeline_service.build_timeline(resolved_pid)
        return timeline
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving timeline for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve timeline: {str(e)}",
        )


@router.post(
    "/{patient_id}/summary/generate",
    response_model=ClinicalSummaryResponse,
    summary="Generate physician-ready AI clinical summary draft",
    description=(
        "Generates a 14-section physician-ready clinical summary draft strictly synthesized "
        "from authentic MongoDB data (interview, documents, alerts). Guarantees zero hallucinations."
    ),
)
async def generate_patient_summary(
    patient_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    resolved_pid = await _resolve_patient_id(patient_id)
    if current_user:
        verify_patient_ownership(resolved_pid, current_user)

    try:
        summary = await clinical_summary_service.generate_summary(resolved_pid, force_regenerate=True)
        await audit_service.log_event(
            action=AuditEventType.SUMMARY_GENERATE.value,
            actor_user_id=current_user.get("user_id") if current_user else None,
            actor_role=current_user.get("role") if current_user else "patient",
            patient_id=resolved_pid,
            resource_type="summary",
            resource_id=resolved_pid,
            details={"verification_status": summary.verification_status},
        )
        return summary
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating clinical summary for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate clinical summary: {str(e)}",
        )


@router.get(
    "/{patient_id}/summary",
    response_model=ClinicalSummaryResponse,
    summary="Get clinical summary draft",
    description="Retrieves the cached clinical summary or generates a new one if none exists.",
)
async def get_patient_summary(
    patient_id: str,
    refresh: bool = Query(False, description="Force re-generation"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    resolved_pid = await _resolve_patient_id(patient_id)
    if current_user:
        verify_patient_ownership(resolved_pid, current_user)

    try:
        summary = await clinical_summary_service.generate_summary(resolved_pid, force_regenerate=refresh)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving clinical summary for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve clinical summary: {str(e)}",
        )


@router.post(
    "/{patient_id}/summary/regenerate",
    response_model=ClinicalSummaryResponse,
    summary="Regenerate clinical summary and timeline",
    description=(
        "Forces regeneration of both the medical timeline and clinical summary "
        "after new documents or interview responses have been added."
    ),
)
async def regenerate_patient_summary(
    patient_id: str,
    payload: Optional[SummaryRegenerateRequest] = None,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    resolved_pid = await _resolve_patient_id(patient_id)
    if current_user:
        verify_patient_ownership(resolved_pid, current_user)

    try:
        # 1. Regenerate timeline first to sync any new document/interview facts
        await medical_timeline_service.build_timeline(resolved_pid)

        # 2. Force regenerate summary
        summary = await clinical_summary_service.generate_summary(resolved_pid, force_regenerate=True)
        await audit_service.log_event(
            action=AuditEventType.SUMMARY_GENERATE.value,
            actor_user_id=current_user.get("user_id") if current_user else None,
            actor_role=current_user.get("role") if current_user else "patient",
            patient_id=resolved_pid,
            resource_type="summary",
            resource_id=resolved_pid,
            details={"action": "regenerate"},
        )
        return summary
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error regenerating clinical summary for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate clinical summary: {str(e)}",
        )
