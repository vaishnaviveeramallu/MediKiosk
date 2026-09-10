import os
import re
import hashlib
import logging
from pathlib import Path
from typing import Tuple
from datetime import datetime, timezone
import uuid

logger = logging.getLogger("medikiosk.document_storage")


class DocumentStorageService:
    """
    Secure, modular file storage service for patient medical documents.
    Validates file formats via magic bytes, enforces size limits, computes SHA-256
    hashes for duplicate detection, and prevents path traversal.
    """

    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
    MIN_FILE_SIZE_BYTES = 1  # Reject 0-byte empty files

    ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

    # Canonical MIME mapping
    MIME_MAP = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }

    def __init__(self, base_upload_dir: str = None):
        if base_upload_dir:
            self.base_dir = Path(base_upload_dir).resolve()
        else:
            # Default to backend/uploads/medical_documents
            current_dir = Path(__file__).resolve().parent  # app/services
            backend_root = current_dir.parent.parent  # backend
            self.base_dir = (backend_root / "uploads" / "medical_documents").resolve()

        # Ensure base directory exists
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"DocumentStorageService initialized with root: {self.base_dir}")

    @staticmethod
    def generate_document_id() -> str:
        """Generates a human-readable, unique document ID (e.g. DOC-20260910-A1B2C3D4)."""
        now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
        rand_hex = uuid.uuid4().hex[:8].upper()
        return f"DOC-{now_str}-{rand_hex}"

    @staticmethod
    def compute_sha256(content: bytes) -> str:
        """Computes SHA-256 cryptographic digest of file bytes for duplicate detection."""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitizes client filename to prevent directory traversal and special character injection.
        """
        if not filename:
            return "medical_document"
        basename = os.path.basename(filename)
        # Separate name and extension
        stem, ext = os.path.splitext(basename)
        safe_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", stem)[:60]
        safe_ext = ext.lower()
        if not safe_stem:
            safe_stem = "document"
        return f"{safe_stem}{safe_ext}"

    def validate_file(self, filename: str, content: bytes, client_content_type: str = None) -> Tuple[str, str]:
        """
        Performs thorough validation:
        1. Non-empty check
        2. Size boundary check (<= 10MB)
        3. Extension whitelist check
        4. Magic bytes content signature inspection (PDF, JPG, PNG)

        Returns (sanitized_filename, canonical_mime_type) or raises ValueError.
        """
        file_size = len(content)
        if file_size < self.MIN_FILE_SIZE_BYTES:
            raise ValueError("Uploaded file is empty (0 bytes). Please upload a valid medical document.")

        if file_size > self.MAX_FILE_SIZE_BYTES:
            max_mb = self.MAX_FILE_SIZE_BYTES // (1024 * 1024)
            actual_mb = file_size / (1024 * 1024)
            raise ValueError(
                f"File size ({actual_mb:.2f} MB) exceeds maximum allowed limit of {max_mb} MB."
            )

        sanitized_name = self.sanitize_filename(filename)
        ext = os.path.splitext(sanitized_name)[1].lower()

        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{ext}'. Allowed formats are: PDF, JPG, JPEG, PNG."
            )

        # Magic bytes signature validation
        canonical_mime = self.MIME_MAP.get(ext, "application/octet-stream")

        if ext == ".pdf":
            if not content.startswith(b"%PDF"):
                raise ValueError("Corrupted or invalid PDF file: missing standard PDF header signature.")
        elif ext in {".jpg", ".jpeg"}:
            if not (content.startswith(b"\xFF\xD8\xFF") or content.startswith(b"\xFF\xD8")):
                raise ValueError("Corrupted or invalid JPEG image: missing standard JPEG header signature.")
        elif ext == ".png":
            if not content.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("Corrupted or invalid PNG image: missing standard PNG header signature.")

        return sanitized_name, canonical_mime

    def save_file(self, patient_id: str, document_id: str, filename: str, content: bytes) -> str:
        """
        Stores the verified document file securely in patient-specific subdirectory.
        Prevents path traversal by resolving canonical absolute paths.
        Returns the relative storage path (e.g. '{patient_id}/{doc_id}_{filename}').
        """
        safe_pid = re.sub(r"[^a-zA-Z0-9_\-]", "", str(patient_id))
        safe_doc_id = re.sub(r"[^a-zA-Z0-9_\-]", "", str(document_id))
        safe_filename = self.sanitize_filename(filename)

        patient_dir = self.base_dir / safe_pid
        patient_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{safe_doc_id}_{safe_filename}"
        target_path = (patient_dir / stored_filename).resolve()

        # Strict security guard against path traversal
        if not str(target_path).startswith(str(self.base_dir.resolve())):
            raise PermissionError("Access denied: path traversal attempt detected.")

        with open(target_path, "wb") as f:
            f.write(content)

        relative_path = f"{safe_pid}/{stored_filename}"
        logger.info(f"Saved document {document_id} ({len(content)} bytes) to {relative_path}")
        return relative_path

    def get_file_path(self, patient_id: str, relative_storage_path: str) -> Path:
        """
        Returns verified canonical Path for reading/streaming, guarding against path traversal.
        """
        safe_pid = re.sub(r"[^a-zA-Z0-9_\-]", "", str(patient_id))
        target_path = (self.base_dir / relative_storage_path).resolve()

        # Security check: must reside inside patient's subfolder and base_dir
        expected_patient_dir = (self.base_dir / safe_pid).resolve()
        if not (str(target_path).startswith(str(expected_patient_dir)) and str(target_path).startswith(str(self.base_dir))):
            raise PermissionError("Access denied: path traversal attempt detected.")

        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError(f"Document file not found at storage reference: {relative_storage_path}")

        return target_path

    def delete_file(self, patient_id: str, relative_storage_path: str) -> bool:
        """Removes a document from disk safely."""
        try:
            target_path = self.get_file_path(patient_id, relative_storage_path)
            if target_path.exists():
                target_path.unlink()
                logger.info(f"Deleted document file: {relative_storage_path}")
                return True
        except Exception as e:
            logger.warning(f"Could not delete document file '{relative_storage_path}': {e}")
        return False


document_storage = DocumentStorageService()
