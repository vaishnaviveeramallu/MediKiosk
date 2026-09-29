from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from bson import ObjectId
from bson.errors import InvalidId

from app.models.audit import AuditLogListResponse
from app.services.audit_service import audit_service
from app.utils.auth_deps import get_current_user, require_role, verify_patient_ownership
from app.database import get_patients_collection

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="List system audit logs",
    description="Authorized access for physicians and triage staff to review system-wide audit and security events.",
)
async def list_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    action: Optional[str] = Query(None, description="Filter by event action type"),
    actor_user_id: Optional[str] = Query(None, description="Filter by actor user ID"),
    patient_id: Optional[str] = Query(None, description="Filter by patient ID"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (success, failure, blocked)"),
    current_user: dict = Depends(require_role(["doctor", "triage_staff"])),
):
    return await audit_service.get_audit_logs(
        skip=skip,
        limit=limit,
        action=action,
        actor_user_id=actor_user_id,
        patient_id=patient_id,
        status=status_filter,
    )


@router.get(
    "/patient/{patient_id}",
    response_model=AuditLogListResponse,
    summary="Get patient-specific audit history",
    description="Retrieves chronological audit events for a patient. Patients may only view their own audit trail.",
)
async def get_patient_audit_trail(
    patient_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    patients_col = get_patients_collection()
    try:
        q = {"_id": ObjectId(patient_id)}
    except InvalidId:
        q = {"token_number": patient_id.upper().strip()}

    patient_doc = await patients_col.find_one(q)
    resolved_pid = str(patient_doc["_id"]) if patient_doc else patient_id

    # Enforce IDOR protection: patients can only access their own audit trail
    verify_patient_ownership(resolved_pid, current_user)

    return await audit_service.get_patient_audit_logs(
        patient_id=resolved_pid,
        skip=skip,
        limit=limit,
    )
