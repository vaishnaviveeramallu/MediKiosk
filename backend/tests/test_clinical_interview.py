import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId
from app.main import app
from app.database import db_manager, get_database



@pytest.mark.anyio
async def test_interview_consent_guard():
    """Verify that interview initiation is strictly blocked (HTTP 403) if consent is pending or declined."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case 1: Pending consent
        reg1 = await client.post("/api/patients/register", json={
            "full_name": "Consent Guard Patient 1",
            "age": 35,
            "gender": "Female",
            "phone_number": "9123456780",
        })
        p1_id = reg1.json()["id"]

        res1 = await client.post(f"/api/interview/start?patient_id={p1_id}")
        assert res1.status_code == 403
        assert "consent" in res1.json()["detail"].lower()

        # Case 2: Declined consent
        await client.post(f"/api/patients/{p1_id}/consent", json={
            "selected_language": "en",
            "consent_status": "declined",
        })

        res2 = await client.post(f"/api/interview/start?patient_id={p1_id}")
        assert res2.status_code == 403
        assert "declined" in res2.json()["detail"].lower()


@pytest.mark.anyio
async def test_clinical_interview_flow_and_persistence():
    """Verify starting interview, submitting multiple answers, MongoDB persistence, and resume safety."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Register and grant consent
        reg = await client.post("/api/patients/register", json={
            "full_name": "Harish Patel",
            "age": 54,
            "gender": "Male",
            "phone_number": "9812345678",
            "address_city": "Ahmedabad",
            "address_state": "Gujarat",
            "initial_complaint": "Severe chest pressure on walking",
        })
        patient = reg.json()
        patient_id = patient["id"]

        await client.post(f"/api/patients/{patient_id}/consent", json={
            "selected_language": "hi",
            "consent_status": "granted",
        })

        # Step 2: Start Interview
        start_res = await client.post(f"/api/interview/start?patient_id={patient_id}")
        assert start_res.status_code == 200
        session = start_res.json()
        session_id = session["session_id"]
        assert session["status"] == "in_progress"
        assert session["selected_language"] == "hi"
        assert session["total_questions"] >= 1
        assert session["current_question"] is not None
        assert session["answered_count"] == 0

        # Step 3: Submit Answer 1 (Chief Complaint)
        ans1_payload = {
            "question_id": "chief_complaint",
            "question_text": "What is your primary health problem?",
            "section": "chief_complaint",
            "patient_answer": "सीने में तेज दबाव और भारीपन",
            "skipped": False,
        }
        res_ans1 = await client.post(f"/api/interview/{session_id}/answer", json=ans1_payload)
        assert res_ans1.status_code == 200
        data1 = res_ans1.json()
        assert data1["answered_count"] == 1
        assert data1["answers"][0]["patient_answer"] == "सीने में तेज दबाव और भारीपन"

        # Step 4: Submit Answer 2 (Duration)
        ans2_payload = {
            "question_id": "duration",
            "question_text": "How long have you had this problem?",
            "section": "hpi",
            "patient_answer": "2 से 3 दिन से",
            "skipped": False,
        }
        res_ans2 = await client.post(f"/api/interview/{session_id}/answer", json=ans2_payload)
        assert res_ans2.status_code == 200
        data2 = res_ans2.json()
        assert data2["answered_count"] == 2

        # Step 5: Resume Safety - simulate page refresh by fetching session
        get_session = await client.get(f"/api/interview/{session_id}")
        assert get_session.status_code == 200
        resumed = get_session.json()
        assert resumed["answered_count"] == 2
        assert len(resumed["answers"]) == 2
        assert resumed["answers"][0]["question_id"] == "chief_complaint"
        assert resumed["answers"][1]["question_id"] == "duration"

        # Step 6: Verify directly in MongoDB collection 'interview_sessions'
        db = get_database()
        db_session = await db["interview_sessions"].find_one({"session_id": session_id})
        assert db_session is not None
        assert db_session["status"] == "in_progress"
        assert len(db_session["answers"]) == 2
        assert db_session["answers"][0]["patient_answer"] == "सीने में तेज दबाव और भारीपन"

        # Step 7: Complete Interview
        comp_res = await client.post(f"/api/interview/{session_id}/complete")
        assert comp_res.status_code == 200
        comp_data = comp_res.json()
        assert comp_data["status"] == "completed"
        assert comp_data["completed_at"] is not None

        # Verify patient record reflects completion
        db_patient = await db["patients"].find_one({"_id": ObjectId(patient_id)})
        assert db_patient["registration_status"] == "interview_completed"
        assert "chief_complaint" in db_patient["clinical_history"]


@pytest.mark.anyio
async def test_multi_patient_session_isolation():
    """Verify that multiple patient interview sessions remain strictly isolated in MongoDB."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Patient 1
        p1 = (await client.post("/api/patients/register", json={
            "full_name": "Isolation Patient 1",
            "age": 40,
            "gender": "Male",
            "phone_number": "9000000001",
        })).json()
        await client.post(f"/api/patients/{p1['id']}/consent", json={"selected_language": "en", "consent_status": "granted"})
        s1 = (await client.post(f"/api/interview/start?patient_id={p1['id']}")).json()

        # Patient 2
        p2 = (await client.post("/api/patients/register", json={
            "full_name": "Isolation Patient 2",
            "age": 28,
            "gender": "Female",
            "phone_number": "9000000002",
        })).json()
        await client.post(f"/api/patients/{p2['id']}/consent", json={"selected_language": "hi", "consent_status": "granted"})
        s2 = (await client.post(f"/api/interview/start?patient_id={p2['id']}")).json()

        assert s1["session_id"] != s2["session_id"]
        assert s1["patient_id"] != s2["patient_id"]

        # Patient 1 submits answer
        await client.post(f"/api/interview/{s1['session_id']}/answer", json={
            "question_id": "chief_complaint",
            "question_text": "Complaint?",
            "section": "chief_complaint",
            "patient_answer": "Severe back pain",
            "skipped": False,
        })

        # Patient 2 submits different answer
        await client.post(f"/api/interview/{s2['session_id']}/answer", json={
            "question_id": "chief_complaint",
            "question_text": "Complaint?",
            "section": "chief_complaint",
            "patient_answer": "बुखार और उल्टी",
            "skipped": False,
        })

        # Check Patient 1 session
        sess1 = (await client.get(f"/api/interview/{s1['session_id']}")).json()
        assert sess1["answers"][0]["patient_answer"] == "Severe back pain"

        # Check Patient 2 session
        sess2 = (await client.get(f"/api/interview/{s2['session_id']}")).json()
        assert sess2["answers"][0]["patient_answer"] == "बुखार और उल्टी"
