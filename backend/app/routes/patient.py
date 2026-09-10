from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Query
from bson import ObjectId
from bson.errors import InvalidId

import uuid
from app.database import get_patients_collection, db_manager
from app.models.patient import PatientCreate, PatientResponse, ConsentRequest
from app.utils.token_generator import generate_opd_token

router = APIRouter(prefix="/api", tags=["patients"])


def serialize_patient(doc: dict) -> PatientResponse:
    """Helper to convert MongoDB document to PatientResponse."""
    doc_copy = dict(doc)
    doc_copy["id"] = str(doc_copy.pop("_id"))
    return PatientResponse(**doc_copy)


@router.get("/health")
async def health_check():
    """Healthcheck endpoint reporting backend and MongoDB status."""
    is_db_connected = await db_manager.ping()
    return {
        "status": "healthy" if is_db_connected else "degraded",
        "database": "connected" if is_db_connected else "disconnected",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post(
    "/patients/register",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new patient",
    description="Registers a patient dynamically into the MongoDB database and generates an OPD token.",
)
async def register_patient(payload: PatientCreate):
    patients_col = get_patients_collection()

    token = await generate_opd_token()
    now = datetime.now(timezone.utc)

    patient_doc = {
        "token_number": token,
        "full_name": payload.full_name,
        "age": payload.age,
        "gender": payload.gender,
        "phone_number": payload.phone_number,
        "emergency_contact_name": payload.emergency_contact_name,
        "emergency_contact_phone": payload.emergency_contact_phone,
        "address_city": payload.address_city,
        "address_state": payload.address_state,
        "government_id_type": payload.government_id_type,
        "government_id_number": payload.government_id_number,
        "initial_complaint": payload.initial_complaint,
        "registration_status": "registered",
        "created_at": now,
        # Extensible placeholders for future phases
        "consent_given": None,
        "consent_timestamp": None,
        "preferred_language": None,
        "clinical_history": None,
        "red_flags": None,
        "documents": [],
        "clinical_summary": None,
    }

    result = await patients_col.insert_one(patient_doc)
    patient_doc["_id"] = result.inserted_id

    return serialize_patient(patient_doc)


@router.get(
    "/patients",
    response_model=List[PatientResponse],
    summary="List registered patients",
    description="Fetches live patient registrations from the database. Zero mock data.",
)
async def list_patients(
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Search by name, token, or phone number"),
):
    patients_col = get_patients_collection()

    query_filter = {}
    if search and search.strip():
        term = search.strip()
        query_filter["$or"] = [
            {"full_name": {"$regex": term, "$options": "i"}},
            {"token_number": {"$regex": term, "$options": "i"}},
            {"phone_number": {"$regex": term, "$options": "i"}},
        ]

    cursor = patients_col.find(query_filter).sort("created_at", -1).skip(skip).limit(limit)
    documents = await cursor.to_list(length=limit)

    return [serialize_patient(doc) for doc in documents]


@router.get(
    "/patients/{patient_id}",
    response_model=PatientResponse,
    summary="Get patient details",
    description="Fetches a single patient record by MongoDB ObjectId or OPD token number.",
)
async def get_patient(patient_id: str):
    patients_col = get_patients_collection()

    query_filter = None
    try:
        query_filter = {"_id": ObjectId(patient_id)}
    except InvalidId:
        # If not a valid ObjectId, try finding by token_number
        query_filter = {"token_number": patient_id.upper()}

    doc = await patients_col.find_one(query_filter)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with identifier '{patient_id}' not found",
        )

    return serialize_patient(doc)


@router.post(
    "/patients/{patient_id}/consent",
    response_model=PatientResponse,
    summary="Record patient consent and language preference",
    description="Dynamically records patient consent decision (granted or declined) and selected language into MongoDB.",
)
async def record_patient_consent(patient_id: str, payload: ConsentRequest):
    patients_col = get_patients_collection()

    query_filter = None
    try:
        query_filter = {"_id": ObjectId(patient_id)}
    except InvalidId:
        query_filter = {"token_number": patient_id.upper()}

    existing_doc = await patients_col.find_one(query_filter)
    if not existing_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with identifier '{patient_id}' not found",
        )

    now = datetime.now(timezone.utc)
    session_id = payload.session_id or f"ses_{uuid.uuid4().hex[:12]}"
    consent_granted = (payload.consent_status == "granted")
    new_status = "consent_granted" if consent_granted else "consent_declined"

    audit_entry = {
        "action": "consent_recorded",
        "consent_status": payload.consent_status,
        "selected_language": payload.selected_language,
        "timestamp": now,
        "session_id": session_id,
    }

    update_fields = {
        "selected_language": payload.selected_language,
        "consent_status": payload.consent_status,
        "consent_given": consent_granted,
        "consent_timestamp": now,
        "session_id": session_id,
        "registration_status": new_status,
    }

    await patients_col.update_one(
        {"_id": existing_doc["_id"]},
        {
            "$set": update_fields,
            "$push": {"consent_history": audit_entry},
        },
    )

    updated_doc = await patients_col.find_one({"_id": existing_doc["_id"]})
    return serialize_patient(updated_doc)


@router.get(
    "/patients/{patient_id}/session",
    summary="Get patient session and intake status",
    description="Retrieves patient intake session state from MongoDB, ensuring frontend never relies purely on local state.",
)
async def get_patient_session(patient_id: str):
    patients_col = get_patients_collection()

    query_filter = None
    try:
        query_filter = {"_id": ObjectId(patient_id)}
    except InvalidId:
        query_filter = {"token_number": patient_id.upper()}

    doc = await patients_col.find_one(query_filter)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient with identifier '{patient_id}' not found",
        )

    return {
        "patient_id": str(doc["_id"]),
        "token_number": doc.get("token_number"),
        "full_name": doc.get("full_name"),
        "registration_status": doc.get("registration_status", "registered"),
        "selected_language": doc.get("selected_language"),
        "consent_status": doc.get("consent_status"),
        "consent_given": doc.get("consent_given"),
        "consent_timestamp": doc.get("consent_timestamp"),
        "session_id": doc.get("session_id"),
        "can_start_interview": bool(doc.get("consent_given") is True),
    }
