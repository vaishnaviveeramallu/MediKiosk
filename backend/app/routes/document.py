import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status, Body, Depends
from fastapi.responses import FileResponse
from bson import ObjectId
from bson.errors import InvalidId

from app.database import get_database, get_patients_collection, get_documents_collection
from app.utils.auth_deps import get_current_user_optional, get_current_user, require_role, verify_patient_ownership
from app.models.audit import AuditEventType
from app.services.audit_service import audit_service
from app.models.document import (
    DocumentType,
    DocumentProcessingStatus,
    VerificationStatus,
    DocumentMetadata,
    DocumentResponse,
    DocumentListResponse,
    OCRResultResponse,
    DocumentProcessResponse,
    VerificationUpdateRequest,
    ExtractedMedicalData,
    OCRMetadata,
)
from app.services.document_storage import document_storage
from app.services.ocr_service import ocr_service
from app.services.medical_extraction_service import medical_extraction_service

logger = logging.getLogger("medikiosk.document_routes")

router = APIRouter(prefix="/api/patients", tags=["documents"])
documents_direct_router = APIRouter(prefix="/api/documents", tags=["documents-direct"])


async def _resolve_patient(patient_id: str) -> dict:
    """Helper to find and validate patient by ObjectId or Token Number."""
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
    return patient_doc


def _serialize_document(doc: dict) -> DocumentResponse:
    """Helper to convert MongoDB document to DocumentResponse."""
    return DocumentResponse(
        document_id=doc["document_id"],
        patient_id=str(doc["patient_id"]),
        token_number=doc.get("token_number", ""),
        original_filename=doc.get("original_filename", "document"),
        document_type=doc.get("document_type", "other"),
        content_type=doc.get("content_type", "application/octet-stream"),
        file_size=doc.get("file_size", 0),
        file_hash=doc.get("file_hash", ""),
        uploaded_at=doc.get("uploaded_at", datetime.now(timezone.utc)),
        upload_status=doc.get("upload_status", "completed"),
        processing_status=doc.get("processing_status", "uploaded"),
        notes=doc.get("notes"),
        raw_ocr_text=doc.get("raw_ocr_text"),
        ocr_metadata=doc.get("ocr_metadata"),
        extracted_data=doc.get("extracted_data"),
        verification_status=doc.get("verification_status", "unverified"),
        verified_by=doc.get("verified_by"),
        verified_at=doc.get("verified_at"),
        verification_notes=doc.get("verification_notes"),
    )


@router.post(
    "/{patient_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a medical document for a patient",
    description="Validates patient existence, file format (PDF, JPG, PNG), file size (<=10MB), detects duplicates via SHA-256, stores file safely, and records metadata in MongoDB.",
)
async def upload_patient_document(
    patient_id: str,
    file: UploadFile = File(..., description="Uploaded medical document (PDF, JPG, JPEG, PNG)"),
    document_type: str = Form("other", description="Category: prescription, lab_report, discharge_summary, medical_report, imaging_scan, other"),
    notes: Optional[str] = Form(None, description="Optional patient or nurse note"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    # 1. Validate patient existence
    patient_doc = await _resolve_patient(patient_id)
    canonical_pid = str(patient_doc["_id"])
    token_number = patient_doc.get("token_number", "")

    # IDOR check
    if current_user:
        verify_patient_ownership(canonical_pid, current_user)

    # 2. Read file content safely
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided. Please upload a valid file.",
        )

    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Error reading uploaded file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read uploaded file.",
        )

    # 3. Validate content, extensions, and magic bytes
    try:
        sanitized_filename, canonical_mime = document_storage.validate_file(
            filename=file.filename,
            content=content,
            client_content_type=file.content_type,
        )
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err),
        )

    # 4. Compute SHA-256 for duplicate detection
    file_hash = document_storage.compute_sha256(content)

    docs_col = get_documents_collection()
    existing_duplicate = await docs_col.find_one({
        "patient_id": canonical_pid,
        "file_hash": file_hash,
    })

    if existing_duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Duplicate document detected: this exact file has already been uploaded for patient '{patient_doc.get('full_name')}' (Document ID: {existing_duplicate.get('document_id')}).",
        )

    # 5. Generate server-side unique document ID
    document_id = document_storage.generate_document_id()

    # 6. Save file safely to disk
    try:
        storage_rel_path = document_storage.save_file(
            patient_id=canonical_pid,
            document_id=document_id,
            filename=sanitized_filename,
            content=content,
        )
    except Exception as save_err:
        logger.error(f"Failed to store file to disk: {save_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage error: could not save file to disk.",
        )

    # 7. Store metadata in MongoDB medical_documents collection
    now = datetime.now(timezone.utc)
    doc_metadata = {
        "document_id": document_id,
        "patient_id": canonical_pid,
        "token_number": token_number,
        "original_filename": file.filename,
        "sanitized_filename": sanitized_filename,
        "document_type": document_type.lower().strip() if document_type else "other",
        "content_type": canonical_mime,
        "file_size": len(content),
        "file_hash": file_hash,
        "storage_path": storage_rel_path,
        "uploaded_at": now,
        "upload_status": "completed",
        "processing_status": "uploaded",
        "notes": notes.strip() if notes else None,
        "raw_ocr_text": None,
        "ocr_metadata": None,
        "extracted_data": None,
        "verification_status": "unverified",
        "verified_by": None,
        "verified_at": None,
        "verification_notes": None,
    }

    try:
        await docs_col.insert_one(doc_metadata)
    except Exception as db_err:
        document_storage.delete_file(canonical_pid, storage_rel_path)
        logger.error(f"Failed to insert document metadata into MongoDB: {db_err}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error: could not persist document metadata.",
        )

    # Log audit event
    await audit_service.log_event(
        action=AuditEventType.DOCUMENT_UPLOAD.value,
        actor_user_id=current_user.get("user_id") if current_user else None,
        actor_role=current_user.get("role") if current_user else "patient",
        patient_id=canonical_pid,
        resource_type="document",
        resource_id=document_id,
        details={
            "filename": sanitized_filename,
            "document_type": document_type,
            "file_size": len(content),
        },
    )

    logger.info(f"Successfully uploaded document {document_id} for patient {canonical_pid}")
    return _serialize_document(doc_metadata)


@router.get(
    "/{patient_id}/documents",
    response_model=DocumentListResponse,
    summary="List all uploaded documents for a patient",
    description="Returns all medical documents linked to the verified patient in MongoDB, sorted by upload timestamp.",
)
async def list_patient_documents(
    patient_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    patient_doc = await _resolve_patient(patient_id)
    canonical_pid = str(patient_doc["_id"])

    # IDOR check
    if current_user:
        verify_patient_ownership(canonical_pid, current_user)

    docs_col = get_documents_collection()
    cursor = docs_col.find({"patient_id": canonical_pid}).sort("uploaded_at", -1)
    raw_docs = await cursor.to_list(length=200)

    docs: List[DocumentResponse] = [_serialize_document(d) for d in raw_docs]

    return DocumentListResponse(
        total_count=len(docs),
        patient_id=canonical_pid,
        documents=docs,
    )


@router.get(
    "/{patient_id}/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Get single document metadata",
    description="Retrieves document metadata, strictly validating that the document belongs to the requested patient.",
)
async def get_patient_document_metadata(
    patient_id: str,
    document_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    patient_doc = await _resolve_patient(patient_id)
    canonical_pid = str(patient_doc["_id"])

    # IDOR check
    if current_user:
        verify_patient_ownership(canonical_pid, current_user)

    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    # Verify patient ownership
    if doc.get("patient_id") != canonical_pid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: document does not belong to the specified patient.",
        )

    return _serialize_document(doc)


@router.get(
    "/{patient_id}/documents/{document_id}/file",
    summary="Securely view or download the uploaded document file",
    description="Streams the authentic uploaded file, validating patient authorization and preventing path traversal.",
)
async def download_patient_document_file(
    patient_id: str,
    document_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    patient_doc = await _resolve_patient(patient_id)
    canonical_pid = str(patient_doc["_id"])

    # IDOR check
    if current_user:
        verify_patient_ownership(canonical_pid, current_user)

    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    # Security check: Ownership isolation
    if doc.get("patient_id") != canonical_pid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: unauthorized access to another patient's medical document.",
        )

    storage_path = doc.get("storage_path")
    if not storage_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document storage reference missing.",
        )

    try:
        file_path = document_storage.get_file_path(canonical_pid, storage_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Physical document file missing from storage.",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security violation: invalid file path.",
        )

    await audit_service.log_event(
        action=AuditEventType.DOCUMENT_VIEW.value,
        actor_user_id=current_user.get("user_id") if current_user else None,
        actor_role=current_user.get("role") if current_user else "patient",
        patient_id=canonical_pid,
        resource_type="document",
        resource_id=document_id,
        details={"filename": doc.get("original_filename")},
    )

    return FileResponse(
        path=file_path,
        media_type=doc.get("content_type", "application/octet-stream"),
        filename=doc.get("original_filename", "medical_document"),
    )


@router.delete(
    "/{patient_id}/documents/{document_id}",
    summary="Delete an uploaded document",
    description="Removes the file from local storage and deletes metadata from MongoDB.",
)
async def delete_patient_document(
    patient_id: str,
    document_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    patient_doc = await _resolve_patient(patient_id)
    canonical_pid = str(patient_doc["_id"])

    # IDOR check
    if current_user:
        verify_patient_ownership(canonical_pid, current_user)

    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    if doc.get("patient_id") != canonical_pid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: cannot delete document belonging to another patient.",
        )

    # Remove file from disk
    storage_path = doc.get("storage_path")
    if storage_path:
        document_storage.delete_file(canonical_pid, storage_path)

    # Delete record from MongoDB
    await docs_col.delete_one({"_id": doc["_id"]})
    logger.info(f"Deleted document {document_id} for patient {canonical_pid}")

    await audit_service.log_event(
        action=AuditEventType.DOCUMENT_DELETE.value,
        actor_user_id=current_user.get("user_id") if current_user else None,
        actor_role=current_user.get("role") if current_user else "patient",
        patient_id=canonical_pid,
        resource_type="document",
        resource_id=document_id,
        details={"filename": doc.get("original_filename")},
    )

    return {
        "status": "deleted",
        "document_id": document_id,
        "message": f"Document '{doc.get('original_filename')}' deleted successfully.",
    }


# =========================================================
# Phase 8: OCR & Medical Entity Extraction Endpoints
# =========================================================

async def _process_document_internal(patient_doc: dict, doc: dict) -> DocumentProcessResponse:
    """Core logic to run OCR and clinical entity extraction on an authentic uploaded file."""
    canonical_pid = str(patient_doc["_id"])
    document_id = doc["document_id"]
    docs_col = get_documents_collection()

    # Verify physical file existence
    storage_path = doc.get("storage_path")
    if not storage_path:
        raise HTTPException(status_code=404, detail="Storage path missing for document.")

    try:
        abs_file_path = document_storage.get_file_path(canonical_pid, storage_path)
    except (FileNotFoundError, PermissionError) as e:
        raise HTTPException(status_code=404, detail=f"File not accessible: {str(e)}")

    # Update status to processing
    await docs_col.update_one(
        {"_id": doc["_id"]},
        {"$set": {"processing_status": "processing"}}
    )

    # Preferred language from patient record (e.g. "hi" or "en")
    pref_lang = patient_doc.get("consent", {}).get("language") or patient_doc.get("language")

    # Step 1: OCR Text Extraction
    ocr_result = ocr_service.extract_from_file(
        file_path=abs_file_path,
        content_type=doc.get("content_type", ""),
        preferred_language=pref_lang,
    )

    now = datetime.now(timezone.utc)
    ocr_meta = {
        "engine": ocr_result.engine,
        "languages": ocr_result.languages,
        "page_count": ocr_result.page_count,
        "confidence": ocr_result.confidence,
        "processing_time_ms": ocr_result.processing_time_ms,
        "processed_at": now,
        "handwritten_detected": ocr_result.handwritten_detected,
        "handwriting_disclaimer": ocr_result.handwriting_disclaimer,
    }

    if ocr_result.is_empty:
        # Unable to reliably extract text
        update_data = {
            "processing_status": "failed",
            "raw_ocr_text": "",
            "ocr_metadata": ocr_meta,
            "extracted_data": None,
            "notes": "Unable to reliably read this document. Please verify the original document manually."
        }
        await docs_col.update_one({"_id": doc["_id"]}, {"$set": update_data})
        return DocumentProcessResponse(
            document_id=document_id,
            patient_id=canonical_pid,
            processing_status="failed",
            raw_ocr_text="",
            ocr_metadata=OCRMetadata(**ocr_meta),
            extracted_data=None,
            verification_status=doc.get("verification_status", "unverified"),
            message="Unable to reliably read this document. Please verify original file."
        )

    # Step 2: Structured Clinical Entity Extraction
    extracted_entities = medical_extraction_service.extract_medical_entities(ocr_result.raw_text)
    extracted_dict = extracted_entities.model_dump()

    # Determine processing status
    target_status = "processed"
    if ocr_result.handwritten_detected or (ocr_result.confidence and ocr_result.confidence < 0.65):
        target_status = "needs_review"

    update_data = {
        "processing_status": target_status,
        "raw_ocr_text": ocr_result.raw_text,
        "ocr_metadata": ocr_meta,
        "extracted_data": extracted_dict,
        "verification_status": "needs_review",  # Requires physician verification
    }

    await docs_col.update_one({"_id": doc["_id"]}, {"$set": update_data})
    logger.info(f"Document {document_id} processed successfully. Status: {target_status}")

    await audit_service.log_event(
        action=AuditEventType.DOCUMENT_PROCESS.value,
        patient_id=canonical_pid,
        resource_type="document",
        resource_id=document_id,
        details={"status": target_status, "confidence": ocr_result.confidence},
    )

    return DocumentProcessResponse(
        document_id=document_id,
        patient_id=canonical_pid,
        processing_status=target_status,
        raw_ocr_text=ocr_result.raw_text,
        ocr_metadata=OCRMetadata(**ocr_meta),
        extracted_data=extracted_entities,
        verification_status="needs_review",
        message="Document processed successfully. Awaiting physician verification."
    )


@router.post(
    "/{patient_id}/documents/{document_id}/process",
    response_model=DocumentProcessResponse,
    summary="Process an uploaded medical document with OCR and entity extraction",
    description="Retrieves the authentic stored document, executes OCR (PDF/images, multilingual), extracts structured clinical entities (medications, labs, diagnoses, procedures, allergies), and persists results in MongoDB.",
)
async def process_patient_document(
    patient_id: str,
    document_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    patient_doc = await _resolve_patient(patient_id)
    canonical_pid = str(patient_doc["_id"])

    if current_user:
        verify_patient_ownership(canonical_pid, current_user)

    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    if doc.get("patient_id") != canonical_pid:
        raise HTTPException(status_code=403, detail="Access denied: document does not belong to specified patient.")

    return await _process_document_internal(patient_doc, doc)


@router.get(
    "/{patient_id}/documents/{document_id}/ocr",
    response_model=OCRResultResponse,
    summary="Get raw OCR text and OCR metadata for a document",
    description="Returns the unparsed OCR output text along with recognition metadata (engine, languages, confidence).",
)
async def get_patient_document_ocr(
    patient_id: str,
    document_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    patient_doc = await _resolve_patient(patient_id)
    canonical_pid = str(patient_doc["_id"])

    if current_user:
        verify_patient_ownership(canonical_pid, current_user)

    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    if doc.get("patient_id") != canonical_pid:
        raise HTTPException(status_code=403, detail="Access denied.")

    return OCRResultResponse(
        document_id=document_id,
        patient_id=canonical_pid,
        processing_status=doc.get("processing_status", "uploaded"),
        raw_ocr_text=doc.get("raw_ocr_text"),
        ocr_metadata=doc.get("ocr_metadata"),
    )


@router.get(
    "/{patient_id}/documents/{document_id}/extracted-data",
    response_model=ExtractedMedicalData,
    summary="Get structured extracted medical entities for a document",
    description="Returns structured diagnoses, medications, laboratory investigations, procedures, allergies, and patient info.",
)
async def get_patient_document_extracted_data(
    patient_id: str,
    document_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    patient_doc = await _resolve_patient(patient_id)
    canonical_pid = str(patient_doc["_id"])

    if current_user:
        verify_patient_ownership(canonical_pid, current_user)

    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    if doc.get("patient_id") != canonical_pid:
        raise HTTPException(status_code=403, detail="Access denied.")

    extracted = doc.get("extracted_data")
    if not extracted:
        raise HTTPException(
            status_code=404,
            detail="Document has not been processed yet or no medical data extracted."
        )

    return ExtractedMedicalData(**extracted)


@router.patch(
    "/{patient_id}/documents/{document_id}/verification",
    response_model=DocumentResponse,
    summary="Update physician verification status for a document",
    description="Allows healthcare providers to review and mark extracted medical findings as verified, needs_review, or unverified.",
)
async def update_document_verification(
    patient_id: str,
    document_id: str,
    payload: VerificationUpdateRequest = Body(...),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    if current_user and current_user.get("role") not in ("doctor", "triage_staff"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Role '{current_user.get('role')}' is not authorized to verify documents.",
        )

    patient_doc = await _resolve_patient(patient_id)
    canonical_pid = str(patient_doc["_id"])

    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    if doc.get("patient_id") != canonical_pid:
        raise HTTPException(status_code=403, detail="Access denied.")

    v_status = payload.verification_status.lower().strip()
    if v_status not in ("unverified", "needs_review", "verified"):
        raise HTTPException(
            status_code=400,
            detail="Invalid verification_status. Allowed: unverified, needs_review, verified",
        )

    now = datetime.now(timezone.utc)
    verified_by_user = payload.verified_by or current_user.get("user_id") or doc.get("verified_by")
    update_fields: Dict[str, Any] = {
        "verification_status": v_status,
        "verified_by": verified_by_user,
        "verified_at": now if v_status == "verified" else doc.get("verified_at"),
        "verification_notes": payload.verification_notes or doc.get("verification_notes"),
    }

    await docs_col.update_one({"_id": doc["_id"]}, {"$set": update_fields})
    updated_doc = await docs_col.find_one({"_id": doc["_id"]})

    await audit_service.log_event(
        action=AuditEventType.DOCUMENT_VERIFY.value,
        actor_user_id=current_user.get("user_id") if current_user else None,
        actor_role=current_user.get("role") if current_user else "doctor",
        patient_id=canonical_pid,
        resource_type="document",
        resource_id=document_id,
        details={
            "verification_status": v_status,
            "verified_by": verified_by_user,
        },
    )

    return _serialize_document(updated_doc)


# Direct /api/documents routes for convenience
@documents_direct_router.post("/{document_id}/process", response_model=DocumentProcessResponse)
async def direct_process_document(
    document_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    patient_doc = await _resolve_patient(doc["patient_id"])
    if current_user:
        verify_patient_ownership(str(patient_doc["_id"]), current_user)

    return await _process_document_internal(patient_doc, doc)


@documents_direct_router.get("/{document_id}/ocr", response_model=OCRResultResponse)
async def direct_get_document_ocr(
    document_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    if current_user:
        verify_patient_ownership(str(doc["patient_id"]), current_user)

    return OCRResultResponse(
        document_id=document_id,
        patient_id=str(doc["patient_id"]),
        processing_status=doc.get("processing_status", "uploaded"),
        raw_ocr_text=doc.get("raw_ocr_text"),
        ocr_metadata=doc.get("ocr_metadata"),
    )


@documents_direct_router.get("/{document_id}/extracted-data", response_model=ExtractedMedicalData)
async def direct_get_document_extracted_data(
    document_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    docs_col = get_documents_collection()
    doc = await docs_col.find_one({"document_id": document_id})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found.")

    if current_user:
        verify_patient_ownership(str(doc["patient_id"]), current_user)

    extracted = doc.get("extracted_data")
    if not extracted:
        raise HTTPException(status_code=404, detail="Document has not been processed yet.")
    return ExtractedMedicalData(**extracted)
