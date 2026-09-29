import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from datetime import datetime, timezone

from app.models.integration import (
    IntegrationStatusEnum,
    IntegrationComponentStatus,
    SystemIntegrationsStatusResponse,
)
from app.services.abdm_service import abdm_service
from app.services.fhir_service import fhir_service
from app.services.his_emr_service import his_emr_service
from app.database import db_manager, get_patients_collection
from app.utils.auth_deps import get_current_user, get_current_user_optional, verify_patient_ownership
from bson import ObjectId
from bson.errors import InvalidId

logger = logging.getLogger("medikiosk.integrations_router")
router = APIRouter(prefix="/api/integrations", tags=["integrations"])


class LinkABHARequest(BaseModel):
    patient_id: str
    abha_number: str = Field(..., description="14-digit authentic ABHA number")
    abha_address: Optional[str] = Field(None, description="Optional authentic ABHA address e.g. user@abdm")


@router.get(
    "/status",
    response_model=SystemIntegrationsStatusResponse,
    summary="Get healthcare integration & system status",
    description="Truthfully reports live status of database, auth, ABDM, FHIR R4, and HIS/EMR integrations without exposing secrets.",
)
async def get_system_integrations_status(
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    db_connected = await db_manager.ping()
    db_status = IntegrationComponentStatus(
        name="database",
        status=IntegrationStatusEnum.AVAILABLE if db_connected else IntegrationStatusEnum.ERROR,
        configured=True,
        message="MongoDB cluster connected and operational" if db_connected else "MongoDB connection degraded or unavailable",
        details={"database": "MongoDB 7.0+", "live": db_connected},
    )

    auth_status = IntegrationComponentStatus(
        name="auth_rbac",
        status=IntegrationStatusEnum.AVAILABLE,
        configured=True,
        message="JWT authentication and role-based access control active",
        details={"roles_enforced": ["patient", "doctor", "triage_staff"], "algorithm": "HS256"},
    )

    abdm_comp = abdm_service.get_status()
    fhir_comp = fhir_service.get_status()
    his_comp = his_emr_service.get_status()

    return SystemIntegrationsStatusResponse(
        timestamp=datetime.now(timezone.utc),
        components={
            "database": db_status,
            "auth_rbac": auth_status,
            "abdm_abha": abdm_comp,
            "fhir_r4": fhir_comp,
            "his_emr": his_comp,
        },
    )


@router.get(
    "/fhir/patient/{patient_id}",
    summary="Export patient record as HL7 FHIR R4 Bundle",
    description="Exports authentic patient data, clinical interview transcript, and clinical summaries as a FHIR R4 Bundle.",
)
async def export_patient_fhir_bundle(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    patients_col = get_patients_collection()
    try:
        q = {"_id": ObjectId(patient_id)}
    except InvalidId:
        q = {"token_number": patient_id.upper().strip()}

    patient_doc = await patients_col.find_one(q)
    if not patient_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found",
        )

    resolved_pid = str(patient_doc["_id"])
    # IDOR enforcement
    verify_patient_ownership(resolved_pid, current_user)

    try:
        bundle = await fhir_service.build_patient_fhir_bundle(resolved_pid)
        return bundle
    except Exception as e:
        logger.error(f"Error generating FHIR Bundle for {patient_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate FHIR R4 Bundle: {str(e)}",
        )


@router.post(
    "/abdm/link",
    summary="Link authentic ABHA number to patient record",
    description="Links an authentic 14-digit ABHA number to patient in MongoDB. Zero mock data rule enforced.",
)
async def link_patient_abha(
    payload: LinkABHARequest,
    current_user: dict = Depends(get_current_user),
):
    patients_col = get_patients_collection()
    try:
        q = {"_id": ObjectId(payload.patient_id)}
    except InvalidId:
        q = {"token_number": payload.patient_id.upper().strip()}

    patient_doc = await patients_col.find_one(q)
    if not patient_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{payload.patient_id}' not found",
        )

    resolved_pid = str(patient_doc["_id"])
    verify_patient_ownership(resolved_pid, current_user)

    try:
        res = await abdm_service.link_abha(
            patient_id=resolved_pid,
            abha_number=payload.abha_number,
            abha_address=payload.abha_address,
            actor_user_id=current_user.get("user_id"),
            actor_role=current_user.get("role"),
        )
        return res
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(ve),
        )


@router.get(
    "/abdm/patient/{patient_id}",
    summary="Get patient ABHA linking status",
)
async def get_patient_abha_status(
    patient_id: str,
    current_user: dict = Depends(get_current_user),
):
    patients_col = get_patients_collection()
    try:
        q = {"_id": ObjectId(patient_id)}
    except InvalidId:
        q = {"token_number": patient_id.upper().strip()}

    patient_doc = await patients_col.find_one(q)
    if not patient_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' not found",
        )

    resolved_pid = str(patient_doc["_id"])
    verify_patient_ownership(resolved_pid, current_user)

    return await abdm_service.get_patient_abha(resolved_pid)
