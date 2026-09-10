import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId

from app.main import app
from app.database import (
    get_database,
    get_patients_collection,
    get_documents_collection,
    get_interview_sessions_collection,
    get_triage_alerts_collection,
)
from app.models.summary import (
    TimelineEventType,
    MedicalTimelineResponse,
    ClinicalSummaryResponse,
)
from app.services.medical_timeline_service import medical_timeline_service
from app.services.clinical_summary_service import clinical_summary_service


async def _create_test_patient(ac: AsyncClient, name: str = "Timeline Test Patient") -> dict:
    res = await ac.post("/api/patients/register", json={
        "full_name": name,
        "age": 52,
        "gender": "Female",
        "phone_number": "9123456789",
        "initial_complaint": "Severe recurrent migraine and dizziness",
    })
    assert res.status_code == 201
    return res.json()


@pytest.mark.anyio
async def test_timeline_from_interview_answers():
    """Verify that clinical interview answers are converted into timeline events with provenance."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "Interview Timeline Patient")
        pid = pat["id"]

        # Insert authentic interview session
        sessions_col = get_interview_sessions_collection()
        session_id = f"sess-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)

        await sessions_col.insert_one({
            "session_id": session_id,
            "patient_id": pid,
            "started_at": now,
            "status": "completed",
            "answers": [
                {
                    "question_id": "chief_complaint",
                    "section": "chief_complaint",
                    "question_text": "What main symptom brings you to the hospital today?",
                    "patient_answer": "Pounding headache on the right side for 3 days",
                    "answered_at": now.isoformat(),
                    "skipped": False,
                },
                {
                    "question_id": "duration",
                    "section": "history_present_illness",
                    "question_text": "How long have you had this headache?",
                    "patient_answer": "Started 3 days ago, getting worse in mornings",
                    "answered_at": now.isoformat(),
                    "skipped": False,
                },
                {
                    "question_id": "allergies",
                    "section": "allergies",
                    "question_text": "Do you have any drug or food allergies?",
                    "patient_answer": "No known allergies",
                    "answered_at": now.isoformat(),
                    "skipped": False,
                },
            ],
        })

        timeline = await medical_timeline_service.build_timeline(pid)
        assert timeline is not None
        assert timeline.patient_id == pid
        assert timeline.total_events > 0

        # Check provenance and interview source label
        interview_events = [e for e in timeline.dated_events + timeline.undated_events if e.source == "patient_interview"]
        assert len(interview_events) >= 2
        for ev in interview_events:
            assert ev.source == "patient_interview"
            assert ev.source_label in ["Registration Intake", "Clinical Intake Interview"]


@pytest.mark.anyio
async def test_timeline_from_medical_documents():
    """Verify that OCR-extracted document entities populate the timeline with document IDs."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "Doc Timeline Patient")
        pid = pat["id"]

        docs_col = get_documents_collection()
        doc_id = f"DOC-{datetime.now().strftime('%Y%m%d')}-0001"
        now = datetime.now(timezone.utc)

        await docs_col.insert_one({
            "document_id": doc_id,
            "patient_id": pid,
            "original_filename": "prescription_sept.pdf",
            "document_type": "prescription",
            "uploaded_at": now,
            "ocr_status": "completed",
            "extracted_data": {
                "patient_info": {"name": pat["full_name"], "document_date": "2026-09-01"},
                "medications": [
                    {
                        "name": "Sumatriptan",
                        "dosage": "50mg",
                        "frequency": "SOS",
                        "duration": "As needed for migraine",
                        "confidence": 0.95,
                    },
                    {
                        "name": "Propranolol",
                        "dosage": "40mg",
                        "frequency": "OD",
                        "duration": "1 month",
                        "confidence": 0.90,
                    }
                ],
                "diagnoses": [
                    {
                        "diagnosis": "Migraine with Aura",
                        "confidence": 0.92,
                    }
                ],
                "investigations": [
                    {
                        "test_name": "MRI Brain",
                        "result_value": "Normal parenchymal architecture",
                        "is_abnormal": False,
                        "confidence": 0.88,
                    }
                ],
                "procedures": [],
                "allergies": [],
            }
        })

        timeline = await medical_timeline_service.build_timeline(pid)
        assert timeline.total_events >= 4

        doc_events = [e for e in timeline.dated_events + timeline.undated_events if e.source == "medical_document"]
        assert len(doc_events) >= 4

        # Check document id preservation
        for ev in doc_events:
            assert ev.source_document_id == doc_id
            assert doc_id in ev.source_label

        # Check medication event details
        med_events = [e for e in doc_events if e.event_type == TimelineEventType.MEDICATION_PRESCRIBED]
        assert len(med_events) == 2
        sumatriptan_ev = next(e for e in med_events if "Sumatriptan" in e.title)
        assert sumatriptan_ev.details.get("dosage") == "50mg"


@pytest.mark.anyio
async def test_chronological_ordering_dated_events():
    """Verify that dated events are sorted strictly chronologically descending (newest first)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "Ordering Patient")
        pid = pat["id"]

        docs_col = get_documents_collection()
        now = datetime.now(timezone.utc)

        # Doc 1: dated 2024-05-10
        await docs_col.insert_one({
            "document_id": f"DOC-20240510-{uuid.uuid4().hex[:4]}",
            "patient_id": pid,
            "original_filename": "old_report.pdf",
            "document_type": "lab_report",
            "uploaded_at": now,
            "extracted_data": {
                "patient_info": {"document_date": "2024-05-10"},
                "investigations": [{"test_name": "HbA1c", "result_value": "5.6%"}],
                "medications": [], "diagnoses": [], "procedures": [], "allergies": [],
            }
        })

        # Doc 2: dated 2026-08-15
        await docs_col.insert_one({
            "document_id": f"DOC-20260815-{uuid.uuid4().hex[:4]}",
            "patient_id": pid,
            "original_filename": "recent_report.pdf",
            "document_type": "lab_report",
            "uploaded_at": now,
            "extracted_data": {
                "patient_info": {"document_date": "2026-08-15"},
                "investigations": [{"test_name": "HbA1c", "result_value": "6.8%"}],
                "medications": [], "diagnoses": [], "procedures": [], "allergies": [],
            }
        })

        # Doc 3: dated 2025-11-20
        await docs_col.insert_one({
            "document_id": f"DOC-20251120-{uuid.uuid4().hex[:4]}",
            "patient_id": pid,
            "original_filename": "mid_report.pdf",
            "document_type": "prescription",
            "uploaded_at": now,
            "extracted_data": {
                "patient_info": {"document_date": "2025-11-20"},
                "medications": [{"name": "Metformin", "dosage": "500mg"}],
                "diagnoses": [], "investigations": [], "procedures": [], "allergies": [],
            }
        })

        timeline = await medical_timeline_service.build_timeline(pid)
        dated_dates = [e.event_date for e in timeline.dated_events if e.event_date]

        # Must have at least the 3 document dates
        assert "2026-08-15" in dated_dates
        assert "2025-11-20" in dated_dates
        assert "2024-05-10" in dated_dates

        # Verify sorted strictly descending (newest first)
        for i in range(len(dated_dates) - 1):
            assert dated_dates[i] >= dated_dates[i + 1], f"Events not in descending order: {dated_dates}"


@pytest.mark.anyio
async def test_undated_events_grouped_separately_zero_guessing():
    """Verify that events without verifiable calendar dates are kept under 'Date not specified' without guessing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "Undated Patient")
        pid = pat["id"]

        docs_col = get_documents_collection()
        now = datetime.now(timezone.utc)

        await docs_col.insert_one({
            "document_id": f"DOC-UNDATED-{uuid.uuid4().hex[:4]}",
            "patient_id": pid,
            "original_filename": "undated_slip.png",
            "document_type": "other",
            "uploaded_at": now,
            "extracted_data": {
                "patient_info": {"document_date": None},  # No date
                "medications": [{"name": "Pantoprazole", "dosage": "40mg"}],
                "diagnoses": [{"diagnosis": "GERD"}],
                "investigations": [], "procedures": [], "allergies": [],
            }
        })

        timeline = await medical_timeline_service.build_timeline(pid)
        assert len(timeline.undated_events) >= 2

        for ev in timeline.undated_events:
            assert ev.event_date is None
            assert ev.display_date == "Date not specified"


@pytest.mark.anyio
async def test_duplicate_event_handling():
    """Verify that duplicate entries are not duplicated in the timeline."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "Deduplication Patient")
        pid = pat["id"]

        docs_col = get_documents_collection()
        now = datetime.now(timezone.utc)

        # Two documents containing identical medication on the same date
        for i in range(2):
            await docs_col.insert_one({
                "document_id": f"DOC-DUP-{i}-{uuid.uuid4().hex[:4]}",
                "patient_id": pid,
                "original_filename": f"duplicate_scan_{i}.pdf",
                "document_type": "prescription",
                "uploaded_at": now,
                "extracted_data": {
                    "patient_info": {"document_date": "2026-09-05"},
                    "medications": [{"name": "Atorvastatin", "dosage": "20mg", "frequency": "HS"}],
                    "diagnoses": [], "investigations": [], "procedures": [], "allergies": [],
                }
            })

        timeline = await medical_timeline_service.build_timeline(pid)
        atorvastatin_events = [
            e for e in timeline.dated_events
            if "Atorvastatin" in e.title and e.event_date == "2026-09-05"
        ]
        # Duplicate key prevention: only one event generated
        assert len(atorvastatin_events) == 1


@pytest.mark.anyio
async def test_conflict_detection_and_flagging():
    """Verify that clinical contradictions (e.g. allergy reported vs document) are flagged with physician warning."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "Conflict Test Patient")
        pid = pat["id"]

        # 1. Interview states NKDA (no known drug allergies)
        sessions_col = get_interview_sessions_collection()
        now = datetime.now(timezone.utc)
        await sessions_col.insert_one({
            "session_id": f"sess-conflict-{uuid.uuid4().hex[:4]}",
            "patient_id": pid,
            "started_at": now,
            "status": "completed",
            "answers": [
                {
                    "question_id": "allergies",
                    "section": "allergies",
                    "question_text": "Do you have any drug or food allergies?",
                    "patient_answer": "No known allergies at all",
                    "answered_at": now.isoformat(),
                    "skipped": False,
                }
            ],
        })

        # 2. Medical document documents an active Penicillin allergy
        docs_col = get_documents_collection()
        await docs_col.insert_one({
            "document_id": f"DOC-ALLERGY-{uuid.uuid4().hex[:4]}",
            "patient_id": pid,
            "original_filename": "allergy_record.pdf",
            "document_type": "medical_report",
            "uploaded_at": now,
            "extracted_data": {
                "patient_info": {"document_date": "2026-01-10"},
                "medications": [], "diagnoses": [], "investigations": [], "procedures": [],
                "allergies": [
                    {
                        "allergen": "Penicillin",
                        "reaction": "Anaphylaxis / severe hives",
                        "severity": "High",
                    }
                ],
            }
        })

        timeline = await medical_timeline_service.build_timeline(pid)
        assert timeline.has_conflicts is True
        assert timeline.conflict_count >= 1

        # Locate flagged event
        conflicted_events = [e for e in timeline.dated_events + timeline.undated_events if e.is_conflict]
        assert len(conflicted_events) >= 1
        conflict_event = conflicted_events[0]
        assert "Conflicting information — physician verification required" in (conflict_event.conflict_notes or "")
        assert "Penicillin" in (conflict_event.conflict_notes or "")


@pytest.mark.anyio
async def test_14_clinical_sections_generated():
    """Verify that all 14 standard clinical sections are generated in the exact specified structure."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "14 Sections Patient")
        pid = pat["id"]

        summary = await clinical_summary_service.generate_summary(pid, force_regenerate=True)
        assert summary is not None
        assert summary.patient_id == pid
        assert len(summary.sections) == 14

        expected_slugs = [
            "patient_info",
            "chief_complaint",
            "hpi",
            "past_medical_history",
            "past_surgical_history",
            "medications",
            "allergies",
            "family_history",
            "social_history",
            "investigations",
            "procedures_hospitalizations",
            "red_flags_triage",
            "document_findings",
            "requires_verification",
        ]

        for slug in expected_slugs:
            assert slug in summary.sections, f"Missing clinical section: {slug}"
            sec = summary.sections[slug]
            assert sec.section_id == slug
            assert 1 <= sec.section_number <= 14
            assert sec.title != ""
            assert sec.content != ""


@pytest.mark.anyio
async def test_missing_data_explicit_not_available():
    """Verify that sections with no patient data state 'Not available in the provided history/documents.'"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "Missing Data Patient")
        pid = pat["id"]

        # Only registration, no interview or documents
        summary = await clinical_summary_service.generate_summary(pid, force_regenerate=True)
        assert summary is not None

        # Sections like family_history, social_history, past_surgical_history should be explicitly unavailable
        unavail_sections = ["family_history", "social_history", "past_surgical_history"]
        for s in unavail_sections:
            sec = summary.sections[s]
            assert sec.is_available is False
            assert sec.content == "Not available in the provided history/documents."


@pytest.mark.anyio
async def test_non_diagnostic_guard_and_disclaimer():
    """Verify that clinical summary enforces the non-diagnostic clinical safety guard."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "Safety Guard Patient")
        pid = pat["id"]

        summary = await clinical_summary_service.generate_summary(pid, force_regenerate=True)

        assert "AI-generated draft — physician verification required" in summary.disclaimer
        assert summary.verification_status == "needs_review"
        assert "CLINICAL GOVERNANCE NOTICE" in summary.summary_draft
        assert "does NOT constitute an autonomous diagnosis" in summary.summary_draft


@pytest.mark.anyio
async def test_summary_regeneration():
    """Verify that force_regenerate refreshes the summary with newly uploaded documents."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "Regen Patient")
        pid = pat["id"]

        # First generation without documents
        summary1 = await clinical_summary_service.generate_summary(pid, force_regenerate=True)
        assert summary1.source_counts["documents"] == 0

        # Now add an authentic document
        docs_col = get_documents_collection()
        now = datetime.now(timezone.utc)
        await docs_col.insert_one({
            "document_id": f"DOC-REGEN-{uuid.uuid4().hex[:4]}",
            "patient_id": pid,
            "original_filename": "post_op_summary.pdf",
            "document_type": "discharge_summary",
            "uploaded_at": now,
            "extracted_data": {
                "patient_info": {"document_date": "2026-08-01"},
                "medications": [{"name": "Amoxicillin", "dosage": "500mg"}],
                "diagnoses": [{"diagnosis": "Acute Appendicitis"}],
                "investigations": [], "procedures": [], "allergies": [],
            }
        })

        # Second generation with force_regenerate=True
        summary2 = await clinical_summary_service.generate_summary(pid, force_regenerate=True)
        assert summary2.source_counts["documents"] == 1
        assert "Acute Appendicitis" in summary2.summary_draft
        assert "Amoxicillin" in summary2.summary_draft


@pytest.mark.anyio
async def test_timeline_and_summary_api_endpoints():
    """Verify all 5 Phase 9 REST API endpoints via HTTP client."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pat = await _create_test_patient(ac, "API Endpoints Patient")
        pid = pat["id"]

        # 1. POST /api/patients/{id}/timeline/generate
        res = await ac.post(f"/api/patients/{pid}/timeline/generate")
        assert res.status_code == 200
        tl_data = res.json()
        assert tl_data["patient_id"] == pid
        assert "total_events" in tl_data
        assert "dated_events" in tl_data
        assert "undated_events" in tl_data

        # 2. GET /api/patients/{id}/timeline
        res = await ac.get(f"/api/patients/{pid}/timeline")
        assert res.status_code == 200
        assert res.json()["patient_id"] == pid

        # 3. POST /api/patients/{id}/summary/generate
        res = await ac.post(f"/api/patients/{pid}/summary/generate")
        assert res.status_code == 200
        sum_data = res.json()
        assert sum_data["patient_id"] == pid
        assert "summary_draft" in sum_data
        assert len(sum_data["sections"]) == 14
        assert sum_data["verification_status"] == "needs_review"

        # 4. GET /api/patients/{id}/summary
        res = await ac.get(f"/api/patients/{pid}/summary")
        assert res.status_code == 200
        assert res.json()["patient_id"] == pid

        # 5. POST /api/patients/{id}/summary/regenerate
        res = await ac.post(
            f"/api/patients/{pid}/summary/regenerate",
            json={"reason": "New document uploaded after intake"},
        )
        assert res.status_code == 200
        assert res.json()["patient_id"] == pid
