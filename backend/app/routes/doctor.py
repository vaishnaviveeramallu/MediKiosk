import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.models.doctor import (
    DoctorQueueResponse,
    PatientClinicalDetailResponse,
    SummaryEditRequest,
    SummaryConfirmRequest,
    ReviewStatusUpdateRequest,
)
from app.services.doctor_service import doctor_service
from app.services.medical_timeline_service import medical_timeline_service
from app.services.clinical_summary_service import clinical_summary_service

logger = logging.getLogger("medikiosk.doctor_routes")

router = APIRouter(prefix="/api/doctor", tags=["doctor-dashboard"])


@router.get(
    "/queue",
    response_model=DoctorQueueResponse,
    summary="Get doctor patient queue with clinical metrics",
    description=(
        "Retrieves real patients from MongoDB with aggregated triage status, interview completion, "
        "document counts, summary status, and review progression. Supports search and filtering."
    ),
)
async def get_doctor_queue(
    search: Optional[str] = Query(None, description="Search by patient name, OPD token, or ID"),
    triage: Optional[str] = Query(None, description="Filter: all, normal, high_alert, critical"),
    status: Optional[str] = Query(None, description="Filter: all, pending_review, in_review, needs_verification, physician_confirmed"),
    limit: int = Query(100, ge=1, le=300),
    skip: int = Query(0, ge=0),
):
    try:
        return await doctor_service.get_doctor_queue(
            search=search,
            triage_filter=triage,
            review_status_filter=status,
            limit=limit,
            skip=skip,
        )
    except Exception as e:
        logger.error(f"Error fetching doctor queue: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch doctor queue: {str(e)}",
        )


@router.get(
    "/patients",
    response_model=DoctorQueueResponse,
    summary="Alias for doctor patient queue",
    description="Same as /api/doctor/queue for REST convention compatibility.",
)
async def get_doctor_patients(
    search: Optional[str] = Query(None),
    triage: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=300),
    skip: int = Query(0, ge=0),
):
    return await get_doctor_queue(
        search=search,
        triage=triage,
        status=status,
        limit=limit,
        skip=skip,
    )


@router.get(
    "/patients/{patient_id}",
    response_model=PatientClinicalDetailResponse,
    summary="Get full 8-section clinical dossier for a patient",
    description=(
        "Retrieves complete patient data across all 8 clinical dimensions: Profile, "
        "Verbatim Interview Q&A, Red Flags/Triage, Documents, OCR Extracted Info, Timeline, Conflicts, and AI Summary."
    ),
)
async def get_patient_clinical_detail(patient_id: str):
    try:
        return await doctor_service.get_patient_clinical_detail(patient_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching clinical detail for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch clinical detail: {str(e)}",
        )


@router.get(
    "/patients/{patient_id}/interview",
    summary="Get verbatim clinical interview session",
    description="Retrieves patient's authentic intake Q&A records without alteration.",
)
async def get_patient_interview(patient_id: str):
    try:
        detail = await doctor_service.get_patient_clinical_detail(patient_id)
        return detail.interview
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/patients/{patient_id}/documents",
    summary="Get medical documents and OCR extraction",
    description="Retrieves uploaded documents and structured OCR extracted entities.",
)
async def get_patient_documents(patient_id: str):
    try:
        detail = await doctor_service.get_patient_clinical_detail(patient_id)
        return {
            "documents": detail.documents,
            "ocr_extracted": detail.ocr_extracted,
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/patients/{patient_id}/timeline",
    summary="Get medical timeline for doctor review",
    description="Retrieves chronological timeline with source tags and conflict warnings.",
)
async def get_patient_timeline(patient_id: str):
    try:
        return await medical_timeline_service.build_timeline(patient_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/patients/{patient_id}/summary",
    summary="Get AI clinical summary for doctor review",
    description="Retrieves 14-section AI clinical summary draft.",
)
async def get_patient_summary(patient_id: str):
    try:
        return await clinical_summary_service.generate_summary(patient_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/patients/{patient_id}/summary",
    summary="Save physician edits to clinical summary draft",
    description=(
        "Persists physician modifications into MongoDB, creates a version history snapshot, "
        "and sets review status to in_review / physician_reviewed."
    ),
)
async def edit_patient_summary(patient_id: str, payload: SummaryEditRequest):
    try:
        updated = await doctor_service.save_summary_draft(patient_id, payload)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error saving summary edit for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save summary edits: {str(e)}",
        )


@router.post(
    "/patients/{patient_id}/summary/confirm",
    summary="Verify and confirm final clinical summary",
    description=(
        "Formally confirms clinical summary by attending physician. Records confirmation timestamp, "
        "transitions status to physician_confirmed, and prevents duplicate confirmation."
    ),
)
async def confirm_patient_summary(patient_id: str, payload: Optional[SummaryConfirmRequest] = None):
    try:
        confirmed = await doctor_service.confirm_summary(patient_id, payload)
        return confirmed
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error confirming summary for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to confirm clinical summary: {str(e)}",
        )


@router.get(
    "/patients/{patient_id}/conflicts",
    summary="Get cross-source clinical conflicts",
    description="Returns detected discrepancies between interview and documents requiring physician resolution.",
)
async def get_patient_conflicts(patient_id: str):
    try:
        detail = await doctor_service.get_patient_clinical_detail(patient_id)
        return {"patient_id": patient_id, "conflicts": detail.conflicts}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch(
    "/patients/{patient_id}/review-status",
    summary="Update doctor review status",
    description="Updates review status (pending_review, in_review, needs_verification, physician_confirmed).",
)
async def update_doctor_review_status(patient_id: str, payload: ReviewStatusUpdateRequest):
    try:
        return await doctor_service.update_review_status(patient_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating review status for patient {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update review status: {str(e)}",
        )
