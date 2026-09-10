import logging
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query, status
from bson import ObjectId

from app.database import get_database
from app.models.triage import (
    TriageAlertPriority,
    TriageAlertStatus,
    TriageDetectionResult,
    TriageAlertRecord,
    TriageCheckRequest,
    TriageUpdateRequest,
    TriageListResponse,
)
from app.services.triage_detector import triage_detector

logger = logging.getLogger("medikiosk.triage")

router = APIRouter(prefix="/api/triage", tags=["triage"])


@router.post(
    "/check",
    response_model=TriageDetectionResult,
    summary="Dry-run scan of patient response text for red-flags",
    description="Evaluates a given text without persisting any alert record in the database.",
)
async def check_text_for_red_flags(request: TriageCheckRequest):
    return triage_detector.detect(request.text, request.language)


@router.get(
    "/alerts",
    response_model=TriageListResponse,
    summary="List triage alerts for staff dashboard",
    description="Fetches active and historical red-flag triage alerts from MongoDB, sorted by detection time.",
)
async def list_triage_alerts(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: 'active', 'acknowledged', 'handled'"),
    priority_filter: Optional[str] = Query(None, alias="priority", description="Filter by priority: 'URGENT', 'HIGH'"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of alerts to retrieve"),
):
    db = get_database()
    col = db["triage_alerts"]

    filter_query: dict = {}
    if status_filter:
        filter_query["status"] = status_filter.lower().strip()
    if priority_filter:
        filter_query["priority"] = priority_filter.upper().strip()

    cursor = col.find(filter_query).sort("detected_at", -1).limit(limit)
    raw_alerts = await cursor.to_list(length=limit)

    alerts: List[TriageAlertRecord] = []
    for doc in raw_alerts:
        doc.pop("_id", None)
        try:
            alerts.append(TriageAlertRecord(**doc))
        except Exception:
            # Skip documents that don't match the full TriageAlertRecord schema
            # (e.g. alerts inserted by other subsystems with partial fields)
            continue

    total_count = await col.count_documents({})
    active_count = await col.count_documents({"status": "active"})

    return TriageListResponse(
        total_count=total_count,
        active_count=active_count,
        alerts=alerts,
    )


@router.get(
    "/alerts/{alert_id}",
    response_model=TriageAlertRecord,
    summary="Get single triage alert details",
    description="Retrieves a specific triage alert by its unique alert_id.",
)
async def get_triage_alert(alert_id: str):
    db = get_database()
    col = db["triage_alerts"]

    doc = await col.find_one({"alert_id": alert_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Triage alert '{alert_id}' not found",
        )
    doc.pop("_id", None)
    return TriageAlertRecord(**doc)


@router.patch(
    "/alerts/{alert_id}",
    response_model=TriageAlertRecord,
    summary="Acknowledge or resolve a triage alert",
    description="Allows staff to update status ('acknowledged', 'handled') and record clinical notes.",
)
async def update_triage_alert(alert_id: str, payload: TriageUpdateRequest):
    db = get_database()
    col = db["triage_alerts"]

    doc = await col.find_one({"alert_id": alert_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Triage alert '{alert_id}' not found",
        )

    now = datetime.now(timezone.utc)
    update_fields: dict = {}

    if payload.status is not None:
        update_fields["status"] = payload.status.value
        if payload.status == TriageAlertStatus.ACKNOWLEDGED:
            update_fields["acknowledged_at"] = now
            update_fields["acknowledged_by"] = payload.staff_id or "triage_staff"
        elif payload.status == TriageAlertStatus.HANDLED:
            update_fields["handled_at"] = now
            update_fields["handled_by"] = payload.staff_id or "triage_staff"
            if not doc.get("acknowledged_at"):
                update_fields["acknowledged_at"] = now
                update_fields["acknowledged_by"] = payload.staff_id or "triage_staff"

    if payload.staff_notes is not None:
        existing_notes = doc.get("staff_notes") or ""
        new_note = payload.staff_notes.strip()
        if new_note:
            if existing_notes:
                update_fields["staff_notes"] = f"{existing_notes}\n[{now.strftime('%H:%M:%S')}] {new_note}"
            else:
                update_fields["staff_notes"] = f"[{now.strftime('%H:%M:%S')}] {new_note}"

    if update_fields:
        await col.update_one({"alert_id": alert_id}, {"$set": update_fields})

    updated_doc = await col.find_one({"alert_id": alert_id})
    updated_doc.pop("_id", None)
    return TriageAlertRecord(**updated_doc)

