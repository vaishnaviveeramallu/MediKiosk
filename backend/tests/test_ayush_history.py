import uuid
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId

from app.main import app
from app.database import (
    get_patients_collection,
    get_interview_sessions_collection,
    get_users_collection,
)
from app.services.ayush_service import ayush_service


async def _register_and_consent_patient(ac: AsyncClient, name: str = "AYUSH Test Patient") -> tuple[str, str]:
    """Helper to register patient and grant consent."""
    reg = await ac.post("/api/patients/register", json={
        "full_name": name,
        "age": 42,
        "gender": "Female",
        "phone_number": "9811223344",
        "initial_complaint": "Ayurvedic consultation for digestive sluggishness",
    })
    assert reg.status_code == 201
    pid = reg.json()["id"]
    token = reg.json()["token_number"]

    consent = await ac.post(f"/api/patients/{pid}/consent", json={
        "selected_language": "hi",
        "consent_status": "granted",
    })
    assert consent.status_code == 200
    return pid, token


async def _get_doctor_headers(ac: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:6]
    res = await ac.post("/api/auth/register", json={
        "username": f"dr_ayush_{unique}",
        "password": "DoctorPass123!",
        "full_name": "Dr. AYUSH Reviewer MD",
        "role": "doctor",
    })
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.anyio
async def test_ayush_initial_question_and_options():
    """Verify that starting interview with mode=ayush presents the initial AYUSH chief complaint question."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pid, token = await _register_and_consent_patient(ac, "AYUSH Initial Question Patient")

        # Start interview in AYUSH mode
        res = await ac.post(f"/api/interview/start?patient_id={pid}&mode=ayush")
        assert res.status_code == 200
        data = res.json()

        assert data["history_mode"] == "ayush"
        q = data["current_question"]
        assert q is not None
        assert q["question_id"] == "ayush_chief_complaint"
        assert "AYUSH" in q["stage_title_en"]
        assert "आयुष" in q["stage_title_hi"]
        assert q["options_en"] is not None
        assert any("Digestive" in opt for opt in q["options_en"])
        assert any("पाचन" in opt for opt in q["options_hi"])

        # Cleanup
        sessions_col = get_interview_sessions_collection()
        patients_col = get_patients_collection()
        await sessions_col.delete_many({"patient_id": pid})
        await patients_col.delete_one({"_id": ObjectId(pid)})


@pytest.mark.anyio
async def test_ayush_adaptive_questioning_flow():
    """Verify adaptive progression through Agni, Koshta, Ahara, and Dashavidha Pariksha."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pid, token = await _register_and_consent_patient(ac, "AYUSH Adaptive Flow Patient")

        # 1. Start AYUSH interview
        start_res = await ac.post(f"/api/interview/start?patient_id={pid}&mode=ayush")
        sess = start_res.json()
        sess_id = sess["session_id"]
        q1 = sess["current_question"]

        # 2. Answer Chief Complaint reporting digestive issues
        ans1_res = await ac.post(f"/api/interview/{sess_id}/answer", json={
            "question_id": q1["question_id"],
            "question_text": q1["text_en"],
            "section": q1["section"],
            "stage_number": q1["stage_number"],
            "patient_answer": "Digestive issues / Acidity / Gas and slow digestion",
            "skipped": False,
            "mode": "ayush",
        })
        assert ans1_res.status_code == 200
        sess1 = ans1_res.json()
        q2 = sess1["current_question"]
        assert q2["question_id"] == "ayush_agni"
        assert "Agni" in q2["section_title_en"]

        # 3. Answer Agni question (Manda Agni)
        ans2_res = await ac.post(f"/api/interview/{sess_id}/answer", json={
            "question_id": q2["question_id"],
            "question_text": q2["text_en"],
            "section": q2["section"],
            "stage_number": q2["stage_number"],
            "patient_answer": "Low appetite / food feels heavy for hours (Manda Agni)",
            "skipped": False,
            "mode": "ayush",
        })
        assert ans2_res.status_code == 200
        sess2 = ans2_res.json()
        q3 = sess2["current_question"]
        # Because patient reported digestive complaint, Koshta question should trigger
        assert q3["question_id"] == "ayush_koshta"

        # 4. Answer Koshta question (Krura Koshta)
        ans3_res = await ac.post(f"/api/interview/{sess_id}/answer", json={
            "question_id": q3["question_id"],
            "question_text": q3["text_en"],
            "section": q3["section"],
            "stage_number": q3["stage_number"],
            "patient_answer": "Hard stools / prone to constipation / needs straining (Krura Koshta)",
            "skipped": False,
            "mode": "ayush",
        })
        assert ans3_res.status_code == 200
        sess3 = ans3_res.json()
        q4 = sess3["current_question"]
        assert q4["question_id"] == "ayush_ahara"

        # 5. Verify answers in MongoDB are recorded with mode='ayush'
        sessions_col = get_interview_sessions_collection()
        doc = await sessions_col.find_one({"session_id": sess_id})
        assert doc is not None
        assert doc["history_mode"] == "ayush"
        assert len(doc["answers"]) == 3
        assert all(a.get("mode") == "ayush" for a in doc["answers"])

        # Cleanup
        patients_col = get_patients_collection()
        await sessions_col.delete_many({"patient_id": pid})
        await patients_col.delete_one({"_id": ObjectId(pid)})


@pytest.mark.anyio
async def test_ayush_idk_and_prefer_not_to_answer():
    """Verify that 'I don't know' and 'Prefer not to answer' are preserved verbatim without guessing."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        pid, token = await _register_and_consent_patient(ac, "AYUSH IDK Patient")

        start_res = await ac.post(f"/api/interview/start?patient_id={pid}&mode=ayush")
        sess_id = start_res.json()["session_id"]
        q1 = start_res.json()["current_question"]

        # Submit 'I don't know / General checkup'
        ans1 = await ac.post(f"/api/interview/{sess_id}/answer", json={
            "question_id": q1["question_id"],
            "question_text": q1["text_en"],
            "section": q1["section"],
            "stage_number": q1["stage_number"],
            "patient_answer": "I don't know / General checkup",
            "skipped": False,
            "mode": "ayush",
        })
        assert ans1.status_code == 200
        q2 = ans1.json()["current_question"]

        # Submit 'I don't know / Not sure' for Agni
        ans2 = await ac.post(f"/api/interview/{sess_id}/answer", json={
            "question_id": q2["question_id"],
            "question_text": q2["text_en"],
            "section": q2["section"],
            "stage_number": q2["stage_number"],
            "patient_answer": "I don't know / Not sure",
            "skipped": False,
            "mode": "ayush",
        })
        assert ans2.status_code == 200

        # Verify in DB: answer is verbatim 'I don't know / Not sure'
        sessions_col = get_interview_sessions_collection()
        doc = await sessions_col.find_one({"session_id": sess_id})
        agni_ans = next(a for a in doc["answers"] if a["question_id"] == "ayush_agni")
        assert agni_ans["patient_answer"] == "I don't know / Not sure"

        # Cleanup
        patients_col = get_patients_collection()
        await sessions_col.delete_many({"patient_id": pid})
        await patients_col.delete_one({"_id": ObjectId(pid)})


@pytest.mark.anyio
async def test_ayush_integration_in_doctor_dossier():
    """Verify that doctor clinical detail dossier includes structured AYUSH data & Dashavidha Pariksha."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        headers = await _get_doctor_headers(ac)
        pid, token = await _register_and_consent_patient(ac, "AYUSH Doctor Review Patient")

        # 1. Conduct AYUSH interview answers
        start_res = await ac.post(f"/api/interview/start?patient_id={pid}&mode=ayush")
        sess_id = start_res.json()["session_id"]
        q1 = start_res.json()["current_question"]

        await ac.post(f"/api/interview/{sess_id}/answer", json={
            "question_id": q1["question_id"],
            "question_text": q1["text_en"],
            "section": q1["section"],
            "stage_number": 1,
            "patient_answer": "Digestive issues / Acidity / Gas",
            "skipped": False,
            "mode": "ayush",
        })
        await ac.post(f"/api/interview/{sess_id}/answer", json={
            "question_id": "ayush_agni",
            "question_text": "How is your natural appetite?",
            "section": "agni",
            "stage_number": 2,
            "patient_answer": "Normal & timely appetite (Sama Agni)",
            "skipped": False,
            "mode": "ayush",
        })
        await ac.post(f"/api/interview/{sess_id}/answer", json={
            "question_id": "ayush_nidra",
            "question_text": "How is your daily sleep quality?",
            "section": "nidra",
            "stage_number": 3,
            "patient_answer": "Sound, refreshing sleep for 6-8 hours",
            "skipped": False,
            "mode": "ayush",
        })

        # 2. Query Doctor Clinical Detail
        doc_res = await ac.get(f"/api/doctor/patients/{pid}", headers=headers)
        assert doc_res.status_code == 200
        data = doc_res.json()

        assert "ayush_history" in data
        ayush_h = data["ayush_history"]
        assert ayush_h is not None
        assert ayush_h["has_ayush_history"] is True
        assert ayush_h["total_ayush_answers"] >= 2

        # Check structured Dashavidha Pariksha
        structured = ayush_h["structured_data"]
        assert structured["agni"] == "Normal & timely appetite (Sama Agni)"
        assert structured["nidra"] == "Sound, refreshing sleep for 6-8 hours"
        assert "dashavidha_pariksha" in structured
        dp = structured["dashavidha_pariksha"]
        assert dp["ahara_shakti"] == "Normal & timely appetite (Sama Agni)"

        # Cleanup
        sessions_col = get_interview_sessions_collection()
        patients_col = get_patients_collection()
        await sessions_col.delete_many({"patient_id": pid})
        await patients_col.delete_one({"_id": ObjectId(pid)})
