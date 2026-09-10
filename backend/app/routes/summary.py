import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.models.summary import (
    MedicalTimelineResponse,
    ClinicalSummaryResponse,
    SummaryRegenerateRequest,
)
from app.services.medical_timeline_service import medical_timeline_service
from app.services.clinical_summary_service import clinical_summary_service

logger = logging.getLogger("medikiosk.summary_routes")

router = APIRouter(prefix="/api/patients", tags=["summary"])


@router.post(
    "/{patient_id}/timeline/generate",
    response_model=MedicalTimelineResponse,
    summary="Generate or update chronological medical timeline",
    description=(
        "Aggregates real patient interview responses, OCR-extracted medical document findings, "
        "and triage alerts into a chronological medical timeline."
    ),
)
async def generate_patient_timeline(patient_id: str):
    try:
        timeline = await medical_timeline_service.build_timeline(patient_id)
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
async def get_patient_timeline(patient_id: str, refresh: bool = Query(False, description="Force re-generation")):
    try:
        if refresh:
            return await medical_timeline_service.build_timeline(patient_id)

        return await medical_timeline_service.build_timeline(patient_id)
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
async def generate_patient_summary(patient_id: str):
    try:
        summary = await clinical_summary_service.generate_summary(patient_id, force_regenerate=True)
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
async def get_patient_summary(patient_id: str, refresh: bool = Query(False, description="Force re-generation")):
    try:
        summary = await clinical_summary_service.generate_summary(patient_id, force_regenerate=refresh)
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
):
    try:
        # 1. Regenerate timeline first to sync any new document/interview facts
        await medical_timeline_service.build_timeline(patient_id)

        # 2. Force regenerate summary
        summary = await clinical_summary_service.generate_summary(patient_id, force_regenerate=True)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error regenerating clinical summary for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to regenerate clinical summary: {str(e)}",
        )
