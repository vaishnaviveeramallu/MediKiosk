from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    PRESCRIPTION = "prescription"
    LAB_REPORT = "lab_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    MEDICAL_REPORT = "medical_report"
    IMAGING_SCAN = "imaging_scan"
    OTHER = "other"


class DocumentProcessingStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    NEEDS_REVIEW = "needs_review"
    VERIFIED = "verified"


# =========================================================
# Structured Extracted Medical Entities
# =========================================================

class ExtractedPatientInfo(BaseModel):
    name: Optional[str] = Field(None, description="Patient name stated in document")
    age: Optional[str] = Field(None, description="Patient age stated in document")
    gender: Optional[str] = Field(None, description="Patient gender stated in document")
    document_date: Optional[str] = Field(None, description="Date on the document")
    confidence: float = Field(default=0.0, description="Confidence score between 0.0 and 1.0")


class ExtractedMedication(BaseModel):
    name: str = Field(..., description="Medicine/Drug name")
    dosage: Optional[str] = Field(None, description="Strength/dosage e.g. 500mg, 10ml")
    dose: Optional[str] = Field(None, description="Quantity per dose e.g. 1 tab")
    frequency: Optional[str] = Field(None, description="Frequency e.g. OD, BD, TDS, once daily")
    duration: Optional[str] = Field(None, description="Duration e.g. 5 days, 1 month")
    route: Optional[str] = Field(None, description="Route e.g. oral, IV, topical")
    confidence: float = Field(default=0.0, description="Extraction confidence score")
    verification_status: str = Field(default="needs_review", description="unverified, needs_review, verified")


class ExtractedInvestigation(BaseModel):
    test_name: str = Field(..., description="Name of laboratory test or investigation")
    result_value: Optional[str] = Field(None, description="Result numerical or qualitative value")
    unit: Optional[str] = Field(None, description="Measurement unit e.g. mg/dL, g/dL, %")
    reference_range: Optional[str] = Field(None, description="Normal reference range if present")
    test_date: Optional[str] = Field(None, description="Date investigation performed")
    is_abnormal: Optional[bool] = Field(None, description="True if value appears outside reference range")
    confidence: float = Field(default=0.0, description="Extraction confidence score")
    verification_status: str = Field(default="needs_review", description="unverified, needs_review, verified")


class ExtractedDiagnosis(BaseModel):
    diagnosis: str = Field(..., description="Medical diagnosis or condition explicitly mentioned")
    symptoms: List[str] = Field(default_factory=list, description="Explicit symptoms mentioned")
    type: Optional[str] = Field(None, description="Type: primary, provisional, differential")
    confidence: float = Field(default=0.0, description="Extraction confidence score")
    verification_status: str = Field(default="needs_review", description="unverified, needs_review, verified")


class ExtractedProcedure(BaseModel):
    procedure_name: str = Field(..., description="Surgical or medical procedure name")
    procedure_date: Optional[str] = Field(None, description="Date procedure was performed")
    notes: Optional[str] = Field(None, description="Relevant procedure notes")
    confidence: float = Field(default=0.0, description="Extraction confidence score")
    verification_status: str = Field(default="needs_review", description="unverified, needs_review, verified")


class ExtractedAllergy(BaseModel):
    allergen: str = Field(..., description="Allergen name (drug, food, environment)")
    reaction: Optional[str] = Field(None, description="Documented allergic reaction")
    severity: Optional[str] = Field(None, description="Severity: mild, moderate, severe")
    confidence: float = Field(default=0.0, description="Extraction confidence score")
    verification_status: str = Field(default="needs_review", description="unverified, needs_review, verified")


class OCRMetadata(BaseModel):
    engine: str = Field(default="tesseract", description="OCR engine utilized")
    languages: List[str] = Field(default_factory=lambda: ["eng"], description="Languages recognized")
    page_count: int = Field(default=1, description="Number of pages processed")
    confidence: Optional[float] = Field(None, description="Average OCR confidence score")
    processing_time_ms: int = Field(default=0, description="Processing duration in milliseconds")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of OCR completion")
    handwritten_detected: bool = Field(default=False, description="Whether handwriting was suspected")
    handwriting_disclaimer: Optional[str] = Field(None, description="Disclaimer if handwriting suspected")


class ExtractedMedicalData(BaseModel):
    patient_info: Optional[ExtractedPatientInfo] = None
    diagnoses: List[ExtractedDiagnosis] = Field(default_factory=list)
    medications: List[ExtractedMedication] = Field(default_factory=list)
    investigations: List[ExtractedInvestigation] = Field(default_factory=list)
    procedures: List[ExtractedProcedure] = Field(default_factory=list)
    allergies: List[ExtractedAllergy] = Field(default_factory=list)
    other_findings: List[str] = Field(default_factory=list)
    doctor_info: Optional[str] = None
    hospital_clinic_info: Optional[str] = None
    unclear_findings: List[str] = Field(default_factory=list)
    requires_physician_review: bool = Field(default=True)
    extraction_notes: Optional[str] = None


# =========================================================
# Document Storage & API Schemas
# =========================================================

class DocumentMetadata(BaseModel):
    document_id: str = Field(..., description="Unique document ID (e.g. DOC-YYYYMMDD-XXXX)")
    patient_id: str = Field(..., description="Referenced Patient ID")
    token_number: str = Field(..., description="OPD Token number")
    original_filename: str = Field(..., description="Original client filename")
    sanitized_filename: str = Field(..., description="Filesystem-safe filename")
    document_type: str = Field(default="other", description="Category: prescription, lab_report, etc.")
    content_type: str = Field(..., description="MIME content type")
    file_size: int = Field(..., description="File size in bytes")
    file_hash: str = Field(..., description="SHA-256 cryptographic checksum")
    storage_path: str = Field(..., description="Relative local storage path")
    uploaded_at: datetime = Field(..., description="UTC timestamp of upload")
    upload_status: str = Field(default="completed", description="Upload completion status")
    processing_status: str = Field(default="uploaded", description="Lifecycle: uploaded, processing, processed, needs_review, failed")
    notes: Optional[str] = Field(None, description="Optional patient/staff note")

    # Phase 8 OCR & Medical Extraction Fields
    raw_ocr_text: Optional[str] = Field(None, description="Raw unparsed OCR output text")
    ocr_metadata: Optional[OCRMetadata] = Field(None, description="Technical OCR processing metadata")
    extracted_data: Optional[ExtractedMedicalData] = Field(None, description="Structured medical entities")
    verification_status: str = Field(default="unverified", description="Physician verification status: unverified, needs_review, verified")
    verified_by: Optional[str] = Field(None, description="Staff or Physician ID who verified")
    verified_at: Optional[datetime] = Field(None, description="Timestamp of physician verification")
    verification_notes: Optional[str] = Field(None, description="Physician clinical verification notes")


class DocumentResponse(BaseModel):
    document_id: str
    patient_id: str
    token_number: str
    original_filename: str
    document_type: str
    content_type: str
    file_size: int
    file_hash: str
    uploaded_at: datetime
    upload_status: str = "completed"
    processing_status: str = "uploaded"
    notes: Optional[str] = None

    # Phase 8 Fields
    raw_ocr_text: Optional[str] = None
    ocr_metadata: Optional[OCRMetadata] = None
    extracted_data: Optional[ExtractedMedicalData] = None
    verification_status: str = "unverified"
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None


class DocumentListResponse(BaseModel):
    total_count: int
    patient_id: str
    documents: List[DocumentResponse]


class OCRResultResponse(BaseModel):
    document_id: str
    patient_id: str
    processing_status: str
    raw_ocr_text: Optional[str]
    ocr_metadata: Optional[OCRMetadata]


class DocumentProcessResponse(BaseModel):
    document_id: str
    patient_id: str
    processing_status: str
    raw_ocr_text: Optional[str]
    ocr_metadata: Optional[OCRMetadata]
    extracted_data: Optional[ExtractedMedicalData]
    verification_status: str
    message: str = "Document processed successfully"


class VerificationUpdateRequest(BaseModel):
    verification_status: str = Field(..., description="Target status: unverified, needs_review, verified")
    verified_by: Optional[str] = Field(None, description="ID or name of physician/staff")
    verification_notes: Optional[str] = Field(None, description="Clinical verification notes")
