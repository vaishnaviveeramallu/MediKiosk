import os
import io
import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId
from PIL import Image, ImageDraw

from app.main import app
from app.database import get_database, get_patients_collection, get_documents_collection
from app.services.ocr_service import ocr_service
from app.services.medical_extraction_service import medical_extraction_service
from app.services.document_storage import document_storage


def create_test_image_content(text: str) -> bytes:
    """Helper to create an image with rendered text for OCR testing."""
    img = Image.new("RGB", (600, 150), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((15, 30), text, fill=(0, 0, 0))
    stream = io.BytesIO()
    img.save(stream, format="PNG")
    return stream.getvalue()


async def _register_test_patient(ac: AsyncClient, name: str = "OCR Test Patient") -> dict:
    res = await ac.post("/api/patients/register", json={
        "full_name": name,
        "age": 45,
        "gender": "Male",
        "phone_number": "9876543210",
        "initial_complaint": "Clinical review with documents",
    })
    assert res.status_code == 201
    return res.json()


@pytest.mark.anyio
async def test_ocr_service_initialization():
    """Verify OCR service is properly initialized with Tesseract and Tessdata."""
    assert ocr_service is not None
    assert ocr_service.tesseract_available is True


@pytest.mark.anyio
async def test_image_ocr_text_extraction(tmp_path):
    """Verify raw OCR extraction on image file."""
    img_bytes = create_test_image_content("Paracetamol 500mg BD x 5 days")
    img_path = str(tmp_path / "test_ocr_rx.png")
    with open(img_path, "wb") as f:
        f.write(img_bytes)

    result = ocr_service.extract_from_file(img_path, "image/png", preferred_language="en")
    assert result is not None
    assert not result.is_empty
    assert "Paracetamol" in result.raw_text or "500" in result.raw_text
    assert result.confidence is not None
    assert result.page_count == 1


@pytest.mark.anyio
async def test_medical_extraction_prescriptions():
    """Verify structured medication extraction with strength, frequency, and duration."""
    prescription_text = """
    Patient Name: Suresh Babu
    Age: 48 Yrs   Gender: Male   Date: 10/09/2026
    Diagnosis: Essential Hypertension

    Rx:
    1. Tab. Telmisartan 40mg OD x 30 days
    2. Tab. Metformin 500mg BD x 30 days
    3. Tab. Paracetamol 650mg SOS

    Allergies: NKDA
    """
    extracted = medical_extraction_service.extract_medical_entities(prescription_text)

    # 1. Patient info
    assert extracted.patient_info is not None
    assert extracted.patient_info.name == "Suresh Babu"
    assert "48" in extracted.patient_info.age
    assert extracted.patient_info.gender == "Male"

    # 2. Medications
    med_names = [m.name.lower() for m in extracted.medications]
    assert any("telmisartan" in m for m in med_names)
    assert any("metformin" in m for m in med_names)
    assert any("paracetamol" in m for m in med_names)

    telmi = next(m for m in extracted.medications if "telmisartan" in m.name.lower())
    assert telmi.dosage == "40mg"
    assert telmi.frequency == "OD"
    assert "30 days" in telmi.duration

    # 3. Diagnoses
    diag_names = [d.diagnosis for d in extracted.diagnoses]
    assert "Essential Hypertension" in diag_names

    # 4. Allergies
    assert len(extracted.allergies) == 1
    assert "NKDA" in extracted.allergies[0].allergen


@pytest.mark.anyio
async def test_medical_extraction_investigations():
    """Verify structured laboratory investigations, units, values, and reference ranges."""
    lab_text = """
    CENTRAL PATHOLOGY LABORATORY
    Patient: Ramesh Rao   Date: 08/09/2026
    Test Report:

    Fasting Blood Sugar: 148 mg/dL (Ref: 70 - 100)
    HbA1c: 8.1 % (Ref: 4.0 - 5.6)
    Serum Creatinine: 1.1 mg/dL (Ref: 0.6 - 1.2)
    Total Bilirubin: 0.8 mg/dL (Ref: 0.2 - 1.2)
    """
    extracted = medical_extraction_service.extract_medical_entities(lab_text)

    assert len(extracted.investigations) >= 3
    tests_dict = {inv.test_name: inv for inv in extracted.investigations}

    assert "Fasting Blood Sugar" in tests_dict
    fbs = tests_dict["Fasting Blood Sugar"]
    assert fbs.result_value == "148"
    assert fbs.unit == "mg/dL"
    assert fbs.reference_range == "70 - 100"
    assert fbs.is_abnormal is True

    assert "HbA1c" in tests_dict
    hba1c = tests_dict["HbA1c"]
    assert hba1c.result_value == "8.1"
    assert hba1c.is_abnormal is True

    assert "Serum Creatinine" in tests_dict
    creat = tests_dict["Serum Creatinine"]
    assert creat.result_value == "1.1"
    assert creat.is_abnormal is False


@pytest.mark.anyio
async def test_medical_extraction_procedures_and_discharge():
    """Verify procedures and surgical details extraction."""
    discharge_text = """
    DEPARTMENT OF GENERAL SURGERY
    Patient Name: Anita Roy   Age: 38 Yrs   Sex: Female
    Diagnosis: Acute Appendicitis
    Procedure: Appendectomy
    Surgical Notes: Successful laparoscopic appendectomy performed.
    Discharge Rx: Tab. Amoxicillin 500mg TDS x 5 days
    Allergies: Allergic to Sulfa drugs
    """
    extracted = medical_extraction_service.extract_medical_entities(discharge_text)

    # Diagnoses
    assert any("Appendicitis" in d.diagnosis for d in extracted.diagnoses)

    # Procedures
    proc_names = [p.procedure_name for p in extracted.procedures]
    assert "Appendectomy" in proc_names

    # Medications
    assert any("Amoxicillin" in m.name for m in extracted.medications)

    # Allergies
    assert any("Sulfa" in a.allergen for a in extracted.allergies)


@pytest.mark.anyio
async def test_no_hallucination_or_invention():
    """Strict verification: Ensure unmentioned medical entities are NEVER invented."""
    sparse_text = """
    Visit Slip
    Date: 01/01/2026
    Advised to rest and drink warm water.
    """
    extracted = medical_extraction_service.extract_medical_entities(sparse_text)

    assert len(extracted.medications) == 0
    assert len(extracted.investigations) == 0
    assert len(extracted.diagnoses) == 0
    assert len(extracted.procedures) == 0
    assert len(extracted.allergies) == 0


@pytest.mark.anyio
async def test_empty_or_blank_ocr_handling(tmp_path):
    """Verify handling when an image is completely blank."""
    blank_img = Image.new("RGB", (200, 200), color=(255, 255, 255))
    blank_path = str(tmp_path / "blank.png")
    blank_img.save(blank_path)

    result = ocr_service.extract_from_file(blank_path, "image/png")
    assert result.is_empty is True
    assert result.raw_text == ""


@pytest.mark.anyio
async def test_document_process_lifecycle():
    """End-to-end API test: Upload -> Process Document -> Verify Extraction -> Verify DB Persistence."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        patient = await _register_test_patient(ac, "Lifecycle OCR Patient")
        pid = patient["id"]
        rx_img_bytes = create_test_image_content("Tab. Paracetamol 500mg BD x 5 days")

        # 1. Upload
        upload_resp = await ac.post(
            f"/api/patients/{pid}/documents",
            files={"file": ("rx_test.png", rx_img_bytes, "image/png")},
            data={"document_type": "prescription"}
        )
        assert upload_resp.status_code == 201
        doc_data = upload_resp.json()
        doc_id = doc_data["document_id"]
        assert doc_data["processing_status"] == "uploaded"

        # 2. Process Document
        proc_resp = await ac.post(f"/api/patients/{pid}/documents/{doc_id}/process")
        assert proc_resp.status_code == 200
        proc_data = proc_resp.json()
        assert proc_data["document_id"] == doc_id
        assert proc_data["processing_status"] in ("processed", "needs_review")
        assert proc_data["raw_ocr_text"] is not None
        assert proc_data["ocr_metadata"] is not None

        # 3. Retrieve raw OCR
        ocr_resp = await ac.get(f"/api/patients/{pid}/documents/{doc_id}/ocr")
        assert ocr_resp.status_code == 200
        ocr_data = ocr_resp.json()
        assert ocr_data["document_id"] == doc_id
        assert "Paracetamol" in ocr_data["raw_ocr_text"] or "500" in ocr_data["raw_ocr_text"]

        # 4. Retrieve structured extracted data
        ext_resp = await ac.get(f"/api/patients/{pid}/documents/{doc_id}/extracted-data")
        assert ext_resp.status_code == 200
        ext_data = ext_resp.json()
        assert "medications" in ext_data

        # 5. Physician verification
        patch_resp = await ac.patch(
            f"/api/patients/{pid}/documents/{doc_id}/verification",
            json={
                "verification_status": "verified",
                "verified_by": "Dr. Sharma",
                "verification_notes": "Prescription verified against uploaded record."
            }
        )
        assert patch_resp.status_code == 200
        updated_doc = patch_resp.json()
        assert updated_doc["verification_status"] == "verified"
        assert updated_doc["verified_by"] == "Dr. Sharma"

        # Clean up
        await ac.delete(f"/api/patients/{pid}/documents/{doc_id}")
        patients_col = get_patients_collection()
        await patients_col.delete_one({"_id": ObjectId(pid)})


@pytest.mark.anyio
async def test_cross_patient_ocr_isolation():
    """Verify Patient B cannot process or access Patient A's document."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat_a = await _register_test_patient(ac, "Patient A")
        pat_b = await _register_test_patient(ac, "Patient B")
        pid_a = pat_a["id"]
        pid_b = pat_b["id"]
        img_bytes = create_test_image_content("Confidential Medical Test")

        upload_resp = await ac.post(
            f"/api/patients/{pid_a}/documents",
            files={"file": ("secret.png", img_bytes, "image/png")},
            data={"document_type": "prescription"}
        )
        doc_id = upload_resp.json()["document_id"]

        # Attempt process from Patient B -> 403
        cross_proc = await ac.post(f"/api/patients/{pid_b}/documents/{doc_id}/process")
        assert cross_proc.status_code == 403

        # Attempt view OCR from Patient B -> 403
        cross_ocr = await ac.get(f"/api/patients/{pid_b}/documents/{doc_id}/ocr")
        assert cross_ocr.status_code == 403

        # Attempt view extracted data from Patient B -> 403
        cross_ext = await ac.get(f"/api/patients/{pid_b}/documents/{doc_id}/extracted-data")
        assert cross_ext.status_code == 403

        # Clean up
        await ac.delete(f"/api/patients/{pid_a}/documents/{doc_id}")
        patients_col = get_patients_collection()
        await patients_col.delete_one({"_id": ObjectId(pid_a)})
        await patients_col.delete_one({"_id": ObjectId(pid_b)})


@pytest.mark.anyio
async def test_text_based_pdf_extraction(tmp_path):
    """Verify digital text-based PDF text extraction via pypdf."""
    from pypdf import PdfWriter
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    pdf_path = str(tmp_path / "digital_rx.pdf")
    
    # Write valid PDF with text annotation or metadata
    with open(pdf_path, "wb") as f:
        writer.write(f)

    # Test PDF extraction handles clean empty/digital paths
    res = ocr_service.extract_from_file(pdf_path, "application/pdf")
    assert res.page_count >= 1
    assert res.engine in ("pypdf_digital", "tesseract_pdf_images")


@pytest.mark.anyio
async def test_corrupted_file_handling(tmp_path):
    """Verify corrupted file does not crash the server and returns structured failure."""
    bad_path = str(tmp_path / "corrupt.png")
    with open(bad_path, "wb") as f:
        f.write(b"NOT_A_VALID_IMAGE_DATA_CORRUPTED_BYTES")

    res = ocr_service.extract_from_file(bad_path, "image/png")
    assert res.is_empty is True
    assert res.error is not None


@pytest.mark.anyio
async def test_hindi_language_configuration():
    """Verify Hindi OCR language configuration and model availability."""
    lang = ocr_service._get_ocr_lang("hi")
    assert "hin" in lang
    tessdata_path = os.environ.get("TESSDATA_PREFIX")
    if tessdata_path and os.path.exists(tessdata_path):
        assert os.path.exists(os.path.join(tessdata_path, "hin.traineddata"))


@pytest.mark.anyio
async def test_unclear_and_low_confidence_flagging():
    """Verify ambiguous findings are flagged in unclear_findings for physician review."""
    ambiguous_text = """
    Rx:
    Tab. Azithromycin
    """
    extracted = medical_extraction_service.extract_medical_entities(ambiguous_text)
    assert len(extracted.medications) == 1
    med = extracted.medications[0]
    assert med.name == "Azithromycin"
    assert med.dosage is None
    assert med.verification_status == "needs_review"
    assert len(extracted.unclear_findings) >= 1
    assert extracted.requires_physician_review is True

