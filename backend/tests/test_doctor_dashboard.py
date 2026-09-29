import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import (
    get_patients_collection,
    get_documents_collection,
    get_interview_sessions_collection,
    get_triage_alerts_collection,
    get_users_collection,
)
from app.models.doctor import DoctorReviewStatus
from app.services.doctor_service import doctor_service
from app.services.clinical_summary_service import clinical_summary_service


async def _create_test_patient(ac: AsyncClient, name: str = "Dr Test Patient", complaint: str = "Chest pain and dyspnea") -> dict:
    res = await ac.post("/api/patients/register", json={
        "full_name": name,
        "age": 58,
        "gender": "Male",
        "phone_number": "9876543210",
        "initial_complaint": complaint,
    })
    assert res.status_code == 201
    return res.json()


async def _get_doctor_headers(ac: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:6]
    res = await ac.post("/api/auth/register", json={
        "username": f"doc_{unique}",
        "password": "DoctorPass123!",
        "full_name": "Dr. Testing MD",
        "role": "doctor",
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_doctor_queue_retrieval_and_metrics():
    """Verify that doctor queue lists real patients and aggregates metrics correctly."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        pat = await _create_test_patient(ac, "Dr Queue Test Patient 1", "Persistent fever")
        pid = pat["id"]

        # Retrieve queue
        res = await ac.get("/api/doctor/queue", headers=headers)
        assert res.status_code == 200
        data = res.json()

        assert "total_patients" in data
        assert "pending_review_count" in data
        assert "in_review_count" in data
        assert "needs_verification_count" in data
        assert "confirmed_count" in data
        assert "high_triage_count" in data
        assert "patients" in data

        assert data["total_patients"] >= 1

        # Ensure our test patient is present in queue
        patient_record = next((p for p in data["patients"] if p["patient_id"] == pid), None)
        assert patient_record is not None
        assert patient_record["full_name"] == "Dr Queue Test Patient 1"
        assert patient_record["age"] == 58
        assert patient_record["gender"] == "Male"
        assert patient_record["initial_complaint"] == "Persistent fever"
        assert patient_record["doctor_review_status"] == DoctorReviewStatus.PENDING_REVIEW.value


@pytest.mark.anyio
async def test_doctor_queue_search_and_filters():
    """Verify search by name, token, and filters by triage level and review status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        unique_name = f"UniqueDoctorSearch-{uuid.uuid4().hex[:6]}"
        pat = await _create_test_patient(ac, unique_name, "Joint swelling")
        pid = pat["id"]
        token = pat["token_number"]

        # Search by exact full name
        res = await ac.get(f"/api/doctor/queue?search={unique_name}", headers=headers)
        assert res.status_code == 200
        matches = res.json()["patients"]
        assert len(matches) == 1
        assert matches[0]["patient_id"] == pid

        # Search by OPD token
        res = await ac.get(f"/api/doctor/queue?search={token}", headers=headers)
        assert res.status_code == 200
        token_matches = res.json()["patients"]
        assert any(p["patient_id"] == pid for p in token_matches)

        # Filter by review status
        res = await ac.get("/api/doctor/queue?review_status=pending_review", headers=headers)
        assert res.status_code == 200
        pending_matches = res.json()["patients"]
        assert all(p["doctor_review_status"] == "pending_review" for p in pending_matches)


@pytest.mark.anyio
async def test_patient_clinical_detail_full_aggregation():
    """Verify all 8 clinical sections in the comprehensive patient review dossier."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        pat = await _create_test_patient(ac, "Comprehensive Dossier Patient", "Severe abdominal pain")
        pid = pat["id"]
        token = pat["token_number"]
        now = datetime.now(timezone.utc)

        # 1. Insert authentic interview session
        sessions_col = get_interview_sessions_collection()
        await sessions_col.insert_one({
            "session_id": f"sess-{uuid.uuid4().hex[:6]}",
            "patient_id": pid,
            "started_at": now,
            "status": "completed",
            "answers": [
                {
                    "question_id": "chief_complaint",
                    "section": "chief_complaint",
                    "question_text": "Where is the pain located?",
                    "patient_answer": "Right lower quadrant with guarding and nausea",
                    "input_method": "voice_stt",
                    "answered_at": now.isoformat(),
                    "skipped": False,
                },
                {
                    "question_id": "allergies",
                    "section": "allergies",
                    "question_text": "Any known allergies?",
                    "patient_answer": "Penicillin allergic — causes severe rash",
                    "input_method": "text_touch",
                    "answered_at": now.isoformat(),
                    "skipped": False,
                },
            ],
        })

        # 2. Insert authentic triage alert (with all TriageAlertRecord-required fields)
        alerts_col = get_triage_alerts_collection()
        await alerts_col.insert_one({
            "alert_id": f"alt-{uuid.uuid4().hex[:6]}",
            "patient_id": pid,
            "token_number": token,
            "patient_name": "Comprehensive Dossier Patient",
            "session_id": f"sess-{uuid.uuid4().hex[:6]}",
            "rule_id": "rule_appendicitis_alert",
            "priority": "HIGH",
            "detected_category": "Orange",
            "rule_description": "Right lower quadrant pain with guarding suggestive of acute abdomen",
            "triggering_answer": "Right lower quadrant with guarding",
            "recommended_action": "Immediate surgical OPD evaluation",
            "status": "active",
            "staff_acknowledged": False,
            "detected_at": now,
        })

        # 3. Insert authentic document with extracted data
        docs_col = get_documents_collection()
        doc_id = f"doc-{uuid.uuid4().hex[:6]}"
        await docs_col.insert_one({
            "document_id": doc_id,
            "patient_id": pid,
            "opd_token": token,
            "original_filename": "past_usg_report.pdf",
            "file_type": "application/pdf",
            "ocr_status": "completed",
            "uploaded_at": now,
            "extracted_data": {
                "patient_info": {"document_date": "2026-06-15"},
                "diagnoses": [{"diagnosis": "Suspected Appendiceal Inflammation", "icd10": "K35.80"}],
                "medications": [{"name": "Ciprofloxacin", "dosage": "500mg", "frequency": "BD"}],
                "investigations": [{"test_name": "USG Abdomen", "result": "Thickened appendix"}],
                "procedures": [{"procedure": "Ultrasonography"}],
                "allergies": [{"allergen": "Sulfa drugs"}],
            }
        })

        # 4. Generate AI summary
        await clinical_summary_service.generate_summary(pid, force_regenerate=True)

        # Retrieve full clinical detail dossier
        res = await ac.get(f"/api/doctor/patients/{pid}", headers=headers)
        assert res.status_code == 200
        detail = res.json()

        # Section 1: Patient Profile
        profile = detail["patient"]
        assert profile["full_name"] == "Comprehensive Dossier Patient"
        assert profile["token_number"] == token
        assert profile["initial_complaint"] == "Severe abdominal pain"

        # Section 2: Clinical Interview
        interview = detail["interview"]
        assert interview["answered_count"] == 2
        assert len(interview["answers"]) == 2
        assert interview["answers"][0]["input_method"] == "voice_stt"
        assert "Right lower quadrant" in interview["answers"][0]["patient_answer"]

        # Section 3: Red Flags / Triage
        triage = detail["triage_alerts"]
        assert len(triage) == 1
        assert triage[0]["priority"] == "HIGH"

        # Section 4: Medical Documents
        docs = detail["documents"]
        assert len(docs) == 1
        assert docs[0]["original_filename"] == "past_usg_report.pdf"
        assert docs[0]["ocr_status"] == "completed"

        # Section 5: Extracted Entities
        entities = detail["ocr_extracted"]
        assert len(entities["diagnoses"]) >= 1
        assert len(entities["medications"]) >= 1
        assert entities["medications"][0]["dosage"] == "500mg"

        # Section 6: Timeline
        timeline = detail["timeline"]
        assert timeline is not None
        assert "total_events" in timeline

        # Section 7: Conflicts
        conflicts = detail["conflicts"]
        assert isinstance(conflicts, list)

        # Section 8: Summary & Review
        summary = detail["summary"]
        assert summary is not None
        assert summary["verification_status"] == "needs_review"
        assert len(summary["sections"]) == 14
        assert detail["review_info"]["doctor_review_status"] == DoctorReviewStatus.PENDING_REVIEW.value


@pytest.mark.anyio
async def test_verbatim_interview_no_rewriting():
    """Verify that interview answers are returned 100% verbatim without AI hallucination or paraphrasing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        pat = await _create_test_patient(ac, "Verbatim Test Patient", "Back spasm")
        pid = pat["id"]
        verbatim_text = "Severe shooting pain in lower spine radiating to left calf since lifting gas cylinder."

        sessions_col = get_interview_sessions_collection()
        await sessions_col.insert_one({
            "session_id": f"sess-{uuid.uuid4().hex[:6]}",
            "patient_id": pid,
            "started_at": datetime.now(timezone.utc),
            "status": "completed",
            "answers": [
                {
                    "question_id": "pain_character",
                    "section": "history_present_illness",
                    "question_text": "Describe the character of the back pain.",
                    "patient_answer": verbatim_text,
                    "input_method": "voice_stt",
                    "answered_at": datetime.now(timezone.utc).isoformat(),
                    "skipped": False,
                }
            ],
        })

        res = await ac.get(f"/api/doctor/patients/{pid}/interview", headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert len(data["answers"]) == 1
        assert data["answers"][0]["patient_answer"] == verbatim_text


@pytest.mark.anyio
async def test_summary_draft_editing_and_version_history():
    """Verify that doctor can edit the summary draft, saving audit trail in version_history."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        pat = await _create_test_patient(ac, "Draft Edit Patient", "Chronic cough")
        pid = pat["id"]

        # Generate initial summary
        await clinical_summary_service.generate_summary(pid, force_regenerate=True)

        # First edit
        edit_1_text = "PHYSICIAN AMENDED DRAFT (v1): Patient presents with 3-week chronic cough, suspected post-viral bronchospasm."
        res1 = await ac.patch(f"/api/doctor/patients/{pid}/summary", json={
            "summary_draft": edit_1_text,
            "physician_notes": "Corrected cough timeline based on bedside verification.",
            "doctor_name": "Dr. Sharma",
        }, headers=headers)
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["summary_draft"] == edit_1_text
        assert data1["verification_status"] == "physician_reviewed"
        assert len(data1["version_history"]) == 1
        assert data1["version_history"][0]["version"] == 1
        assert data1["version_history"][0]["modified_by"] == "Dr. Sharma"

        # Second edit
        edit_2_text = "PHYSICIAN AMENDED DRAFT (v2): Patient presents with 3-week chronic cough, rule out atypical infection or asthma."
        res2 = await ac.patch(f"/api/doctor/patients/{pid}/summary", json={
            "summary_draft": edit_2_text,
            "physician_notes": "Added differential diagnosis.",
            "doctor_name": "Dr. Verma",
        }, headers=headers)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["summary_draft"] == edit_2_text
        assert len(data2["version_history"]) == 2
        assert data2["version_history"][1]["version"] == 2
        assert data2["version_history"][1]["modified_by"] == "Dr. Verma"


@pytest.mark.anyio
async def test_physician_confirmation_workflow_and_idempotency():
    """Verify physician confirmation workflow, timestamp recording, and duplicate confirmation safety."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        pat = await _create_test_patient(ac, "Confirmation Patient", "Joint pains")
        pid = pat["id"]

        # Generate summary
        await clinical_summary_service.generate_summary(pid, force_regenerate=True)

        # Confirm summary
        res = await ac.post(f"/api/doctor/patients/{pid}/summary/confirm", json={
            "confirmed_by": "Dr. Arvind Sharma, MD",
            "doctor_notes": "Bedside examination verified; summary accurately captures clinical history.",
        }, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert data["confirmed_by"] == "Dr. Arvind Sharma, MD"
        assert data["confirmed_at"] is not None
        assert data["verification_status"] == "physician_confirmed"

        # Check patient document review_status updated in DB
        pat_res = await ac.get(f"/api/doctor/patients/{pid}", headers=headers)
        assert pat_res.status_code == 200
        assert pat_res.json()["review_info"]["doctor_review_status"] == DoctorReviewStatus.PHYSICIAN_CONFIRMED.value

        # Idempotent second confirmation call
        res_repeat = await ac.post(f"/api/doctor/patients/{pid}/summary/confirm", json={
            "confirmed_by": "Dr. Arvind Sharma, MD",
            "doctor_notes": "Re-confirmed after prescription entry.",
        }, headers=headers)
        assert res_repeat.status_code == 200
        assert res_repeat.json()["verification_status"] == "physician_confirmed"


@pytest.mark.anyio
async def test_review_status_update_endpoint():
    """Verify manual review status updates (e.g., in_review, needs_verification)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        pat = await _create_test_patient(ac, "Status Update Patient", "Fatigue")
        pid = pat["id"]

        res = await ac.patch(f"/api/doctor/patients/{pid}/review-status", json={
            "review_status": "needs_verification",
            "notes": "ECG required before completing summary sign-off.",
        }, headers=headers)
        assert res.status_code == 200
        assert res.json()["doctor_review_status"] == "needs_verification"

        # Verify reflected in doctor queue
        q_res = await ac.get(f"/api/doctor/queue?review_status=needs_verification", headers=headers)
        assert q_res.status_code == 200
        matches = q_res.json()["patients"]
        assert any(p["patient_id"] == pid for p in matches)


@pytest.mark.anyio
async def test_doctor_sub_endpoints():
    """Verify individual sub-endpoints for interview, documents, timeline, summary, conflicts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        pat = await _create_test_patient(ac, "Sub Endpoints Patient", "Skin allergy")
        pid = pat["id"]

        # Interview endpoint
        r1 = await ac.get(f"/api/doctor/patients/{pid}/interview", headers=headers)
        assert r1.status_code == 200
        assert "answers" in r1.json()

        # Documents endpoint
        r2 = await ac.get(f"/api/doctor/patients/{pid}/documents", headers=headers)
        assert r2.status_code == 200
        assert "documents" in r2.json()
        assert "ocr_extracted" in r2.json()

        # Timeline endpoint
        r3 = await ac.get(f"/api/doctor/patients/{pid}/timeline", headers=headers)
        assert r3.status_code == 200
        assert "dated_events" in r3.json()

        # Summary endpoint
        r4 = await ac.get(f"/api/doctor/patients/{pid}/summary", headers=headers)
        assert r4.status_code == 200
        assert "summary_draft" in r4.json()

        # Conflicts endpoint
        r5 = await ac.get(f"/api/doctor/patients/{pid}/conflicts", headers=headers)
        assert r5.status_code == 200
        assert "conflicts" in r5.json()


@pytest.mark.anyio
async def test_doctor_nonexistent_patient_404():
    """Verify 404 response for non-existent patient ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        fake_id = "pat-nonexistent-12345"
        res = await ac.get(f"/api/doctor/patients/{fake_id}", headers=headers)
        assert res.status_code == 404
        assert "not found" in res.json()["detail"].lower()
