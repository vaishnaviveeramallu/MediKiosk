import io
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_database
from app.services.document_storage import document_storage


SAMPLE_PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\ntrailer\n<<\n>>\n%%EOF"
SAMPLE_JPEG_BYTES = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xFF\xDB\x00C\x00\xFF\xD9"
SAMPLE_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"


async def _register_test_patient(ac: AsyncClient, name: str = "Document Test Patient") -> dict:
    res = await ac.post("/api/patients/register", json={
        "full_name": name,
        "age": 42,
        "gender": "Female",
        "phone_number": "9123456780",
        "initial_complaint": "Follow-up consultation",
    })
    assert res.status_code == 201
    return res.json()


@pytest.mark.anyio
async def test_valid_pdf_upload_and_persistence():
    """Verify uploading a valid PDF persists file on disk, saves metadata in MongoDB, and sets status to uploaded."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "PDF Patient")
        patient_id = patient["id"]

        files = {"file": ("prescription_dr_verma.pdf", SAMPLE_PDF_BYTES, "application/pdf")}
        data = {"document_type": "prescription", "notes": "Previous cardiology prescription"}

        res = await ac.post(f"/api/patients/{patient_id}/documents", files=files, data=data)
        assert res.status_code == 201
        doc = res.json()

        assert doc["document_id"].startswith("DOC-")
        assert doc["patient_id"] == patient_id
        assert doc["token_number"] == patient["token_number"]
        assert doc["original_filename"] == "prescription_dr_verma.pdf"
        assert doc["document_type"] == "prescription"
        assert doc["content_type"] == "application/pdf"
        assert doc["file_size"] == len(SAMPLE_PDF_BYTES)
        assert doc["processing_status"] == "uploaded"
        assert doc["upload_status"] == "completed"
        assert doc["notes"] == "Previous cardiology prescription"

        # Verify in MongoDB
        db = get_database()
        mongo_doc = await db["medical_documents"].find_one({"document_id": doc["document_id"]})
        assert mongo_doc is not None
        assert mongo_doc["patient_id"] == patient_id
        assert mongo_doc["file_hash"] == doc["file_hash"]

        # Clean up file
        document_storage.delete_file(patient_id, mongo_doc["storage_path"])


@pytest.mark.anyio
async def test_valid_jpg_and_png_upload():
    """Verify uploading valid JPG and PNG images with correct content types."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "Image Patient")
        patient_id = patient["id"]

        # 1. JPEG upload
        files_jpg = {"file": ("lab_report_scan.jpg", SAMPLE_JPEG_BYTES, "image/jpeg")}
        res_jpg = await ac.post(f"/api/patients/{patient_id}/documents", files=files_jpg, data={"document_type": "lab_report"})
        assert res_jpg.status_code == 201
        doc_jpg = res_jpg.json()
        assert doc_jpg["content_type"] == "image/jpeg"
        assert doc_jpg["document_type"] == "lab_report"

        # 2. PNG upload
        files_png = {"file": ("ecg_trace.png", SAMPLE_PNG_BYTES, "image/png")}
        res_png = await ac.post(f"/api/patients/{patient_id}/documents", files=files_png, data={"document_type": "imaging_scan"})
        assert res_png.status_code == 201
        doc_png = res_png.json()
        assert doc_png["content_type"] == "image/png"
        assert doc_png["document_type"] == "imaging_scan"

        # Clean up files
        db = get_database()
        for doc_id in [doc_jpg["document_id"], doc_png["document_id"]]:
            m = await db["medical_documents"].find_one({"document_id": doc_id})
            if m:
                document_storage.delete_file(patient_id, m["storage_path"])


@pytest.mark.anyio
async def test_unsupported_file_type_rejection():
    """Verify rejection of unsupported extensions and files with mismatched magic bytes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "Format Reject Patient")
        patient_id = patient["id"]

        # Plain text file
        files_txt = {"file": ("medical_notes.txt", b"Blood pressure was 120/80", "text/plain")}
        res_txt = await ac.post(f"/api/patients/{patient_id}/documents", files=files_txt)
        assert res_txt.status_code == 400
        assert "Unsupported file format" in res_txt.json()["detail"]

        # Executable file
        files_exe = {"file": ("installer.exe", b"MZ\x90\x00", "application/x-msdownload")}
        res_exe = await ac.post(f"/api/patients/{patient_id}/documents", files=files_exe)
        assert res_exe.status_code == 400

        # Fake PDF: named .pdf but containing plain text without %PDF header
        files_fake_pdf = {"file": ("fake_report.pdf", b"This is not a real PDF document", "application/pdf")}
        res_fake_pdf = await ac.post(f"/api/patients/{patient_id}/documents", files=files_fake_pdf)
        assert res_fake_pdf.status_code == 400
        assert "missing standard PDF header" in res_fake_pdf.json()["detail"]


@pytest.mark.anyio
async def test_oversized_file_rejection():
    """Verify rejection of files exceeding the 10 MB maximum limit."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "Oversized Patient")
        patient_id = patient["id"]

        oversized_content = b"%PDF-1.4\n" + (b"0" * (10 * 1024 * 1024 + 100))
        files = {"file": ("huge_scan.pdf", oversized_content, "application/pdf")}

        res = await ac.post(f"/api/patients/{patient_id}/documents", files=files)
        assert res.status_code == 400
        assert "exceeds maximum allowed limit" in res.json()["detail"]


@pytest.mark.anyio
async def test_empty_file_rejection():
    """Verify rejection of empty (0-byte) files."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "Empty File Patient")
        patient_id = patient["id"]

        files = {"file": ("empty.pdf", b"", "application/pdf")}
        res = await ac.post(f"/api/patients/{patient_id}/documents", files=files)
        assert res.status_code == 400
        assert "empty" in res.json()["detail"].lower()


@pytest.mark.anyio
async def test_patient_not_found_rejection():
    """Verify rejection when uploading for non-existent patient ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        files = {"file": ("test.pdf", SAMPLE_PDF_BYTES, "application/pdf")}
        res = await ac.post("/api/patients/65a000000000000000000000/documents", files=files)
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()


@pytest.mark.anyio
async def test_duplicate_document_detection():
    """Verify SHA-256 duplicate detection blocks re-uploading identical file for same patient."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "Duplicate Test Patient")
        patient_id = patient["id"]

        files1 = {"file": ("original_prescription.pdf", SAMPLE_PDF_BYTES, "application/pdf")}
        res1 = await ac.post(f"/api/patients/{patient_id}/documents", files=files1, data={"document_type": "prescription"})
        assert res1.status_code == 201
        doc1 = res1.json()

        # Upload exact same file with different name
        files2 = {"file": ("duplicate_prescription.pdf", SAMPLE_PDF_BYTES, "application/pdf")}
        res2 = await ac.post(f"/api/patients/{patient_id}/documents", files=files2, data={"document_type": "prescription"})
        assert res2.status_code == 409
        assert "duplicate document detected" in res2.json()["detail"].lower()

        # Clean up
        db = get_database()
        m = await db["medical_documents"].find_one({"document_id": doc1["document_id"]})
        if m:
            document_storage.delete_file(patient_id, m["storage_path"])


@pytest.mark.anyio
async def test_document_listing_isolation_between_patients():
    """Verify documents are strictly isolated per patient in GET /api/patients/{id}/documents."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        p_a = await _register_test_patient(ac, "Patient Alpha")
        p_b = await _register_test_patient(ac, "Patient Beta")

        # Patient A uploads PDF
        res_a = await ac.post(
            f"/api/patients/{p_a['id']}/documents",
            files={"file": ("doc_a.pdf", SAMPLE_PDF_BYTES, "application/pdf")},
            data={"document_type": "prescription"}
        )
        assert res_a.status_code == 201

        # Patient B uploads JPEG
        res_b = await ac.post(
            f"/api/patients/{p_b['id']}/documents",
            files={"file": ("doc_b.jpg", SAMPLE_JPEG_BYTES, "image/jpeg")},
            data={"document_type": "lab_report"}
        )
        assert res_b.status_code == 201

        # Fetch Patient A documents
        list_a_res = await ac.get(f"/api/patients/{p_a['id']}/documents")
        assert list_a_res.status_code == 200
        list_a = list_a_res.json()
        assert list_a["total_count"] == 1
        assert list_a["documents"][0]["original_filename"] == "doc_a.pdf"

        # Fetch Patient B documents
        list_b_res = await ac.get(f"/api/patients/{p_b['id']}/documents")
        assert list_b_res.status_code == 200
        list_b = list_b_res.json()
        assert list_b["total_count"] == 1
        assert list_b["documents"][0]["original_filename"] == "doc_b.jpg"

        # Clean up
        db = get_database()
        for doc_res, pid in [(res_a.json(), p_a["id"]), (res_b.json(), p_b["id"])]:
            m = await db["medical_documents"].find_one({"document_id": doc_res["document_id"]})
            if m:
                document_storage.delete_file(pid, m["storage_path"])


@pytest.mark.anyio
async def test_cross_patient_document_access_rejection():
    """Verify Patient B cannot view, download, or delete Patient A's document."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        p_a = await _register_test_patient(ac, "Victim Patient")
        p_b = await _register_test_patient(ac, "Attacker Patient")

        res_a = await ac.post(
            f"/api/patients/{p_a['id']}/documents",
            files={"file": ("confidential_report.pdf", SAMPLE_PDF_BYTES, "application/pdf")},
            data={"document_type": "discharge_summary"}
        )
        assert res_a.status_code == 201
        doc_a_id = res_a.json()["document_id"]

        # Patient B tries to get metadata of Patient A's document
        hack_meta = await ac.get(f"/api/patients/{p_b['id']}/documents/{doc_a_id}")
        assert hack_meta.status_code == 403

        # Patient B tries to download Patient A's document file
        hack_file = await ac.get(f"/api/patients/{p_b['id']}/documents/{doc_a_id}/file")
        assert hack_file.status_code == 403

        # Patient B tries to delete Patient A's document
        hack_del = await ac.delete(f"/api/patients/{p_b['id']}/documents/{doc_a_id}")
        assert hack_del.status_code == 403

        # Clean up
        db = get_database()
        m = await db["medical_documents"].find_one({"document_id": doc_a_id})
        if m:
            document_storage.delete_file(p_a["id"], m["storage_path"])


@pytest.mark.anyio
async def test_document_file_download_and_view():
    """Verify authentic streaming of uploaded file with correct Content-Type and bytes."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "Download Patient")
        patient_id = patient["id"]

        res = await ac.post(
            f"/api/patients/{patient_id}/documents",
            files={"file": ("lab_report.pdf", SAMPLE_PDF_BYTES, "application/pdf")},
            data={"document_type": "lab_report"}
        )
        assert res.status_code == 201
        doc_id = res.json()["document_id"]

        # Download file
        download_res = await ac.get(f"/api/patients/{patient_id}/documents/{doc_id}/file")
        assert download_res.status_code == 200
        assert download_res.headers["content-type"] == "application/pdf"
        assert download_res.content == SAMPLE_PDF_BYTES

        # Clean up
        db = get_database()
        m = await db["medical_documents"].find_one({"document_id": doc_id})
        if m:
            document_storage.delete_file(patient_id, m["storage_path"])


@pytest.mark.anyio
async def test_document_deletion():
    """Verify document deletion removes record from MongoDB and file from disk."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "Delete Patient")
        patient_id = patient["id"]

        res = await ac.post(
            f"/api/patients/{patient_id}/documents",
            files={"file": ("delete_me.pdf", SAMPLE_PDF_BYTES, "application/pdf")}
        )
        assert res.status_code == 201
        doc_id = res.json()["document_id"]

        # Delete document
        del_res = await ac.delete(f"/api/patients/{patient_id}/documents/{doc_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "deleted"

        # Verify gone from MongoDB
        db = get_database()
        mongo_doc = await db["medical_documents"].find_one({"document_id": doc_id})
        assert mongo_doc is None

        # Verify file does not exist
        get_file_res = await ac.get(f"/api/patients/{patient_id}/documents/{doc_id}/file")
        assert get_file_res.status_code == 404


@pytest.mark.anyio
async def test_no_ocr_claims_verification():
    """Strictly verify Phase 7 constraint: processing_status is 'uploaded' and zero OCR results are returned."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "No OCR Patient")
        patient_id = patient["id"]

        res = await ac.post(
            f"/api/patients/{patient_id}/documents",
            files={"file": ("prescription_scan.png", SAMPLE_PNG_BYTES, "image/png")}
        )
        assert res.status_code == 201
        doc = res.json()

        assert doc["processing_status"] == "uploaded"
        # Verify no OCR fields exist
        assert "extracted_text" not in doc
        assert "ocr_text" not in doc
        assert "entities" not in doc
        assert "diagnoses" not in doc
        assert "medications" not in doc

        # Clean up
        db = get_database()
        m = await db["medical_documents"].find_one({"document_id": doc["document_id"]})
        if m:
            document_storage.delete_file(patient_id, m["storage_path"])
