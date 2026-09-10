import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import db_manager


@pytest.mark.anyio
async def test_triage_dry_run_check_endpoint():
    """Verify POST /api/triage/check with normal, urgent, Hindi, and mixed inputs without creating records."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Normal English answer -> no alert
        res_norm_en = await ac.post("/api/triage/check", json={"text": "I have a mild runny nose and cough for 2 days", "language": "en"})
        assert res_norm_en.status_code == 200
        data1 = res_norm_en.json()
        assert data1["has_red_flag"] is False

        # 2. Normal Hindi answer -> no alert
        res_norm_hi = await ac.post("/api/triage/check", json={"text": "मुझे दो दिन से हल्की जुकाम और खांसी है", "language": "hi"})
        assert res_norm_hi.status_code == 200
        data2 = res_norm_hi.json()
        assert data2["has_red_flag"] is False

        # 3. Severe English chest pain & breathlessness -> URGENT alert
        res_urg_en = await ac.post("/api/triage/check", json={"text": "I have severe chest pain and difficulty breathing", "language": "en"})
        assert res_urg_en.status_code == 200
        data3 = res_urg_en.json()
        assert data3["has_red_flag"] is True
        assert data3["category"] in ["cardiovascular_severe", "respiratory_distress"]
        assert data3["priority"] == "URGENT"
        assert len(data3["matched_keywords"]) > 0

        # 4. Severe Hindi chest pain -> URGENT alert
        res_urg_hi = await ac.post("/api/triage/check", json={
            "text": "मुझे बहुत तेज सीने में दर्द हो रहा है और सांस लेने में बहुत परेशानी हो रही है",
            "language": "hi"
        })
        assert res_urg_hi.status_code == 200
        data4 = res_urg_hi.json()
        assert data4["has_red_flag"] is True
        assert data4["priority"] == "URGENT"

        # 5. Hinglish mixed terminology -> alert
        res_hinglish = await ac.post("/api/triage/check", json={
            "text": "seene me tez dard hai aur saans phool rahi hai",
            "language": "hi"
        })
        assert res_hinglish.status_code == 200
        data5 = res_hinglish.json()
        assert data5["has_red_flag"] is True

        # 6. Unbearable pain -> HIGH priority
        res_pain = await ac.post("/api/triage/check", json={"text": "This is unbearable pain, cannot bear the pain", "language": "en"})
        assert res_pain.status_code == 200
        data6 = res_pain.json()
        assert data6["has_red_flag"] is True
        assert data6["priority"] == "HIGH"


@pytest.mark.anyio
async def test_triage_alert_creation_and_mongodb_persistence():
    """Verify end-to-end alert creation, MongoDB persistence, and patient session status update."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register a test patient in isolated test database
        reg_res = await ac.post("/api/patients/register", json={
            "full_name": "Triage Test Patient English",
            "age": 55,
            "gender": "male",
            "phone_number": "9988776655",
            "department": "General Medicine",
        })
        assert reg_res.status_code == 201
        patient = reg_res.json()
        patient_id = patient["id"]

        # 2. Grant consent
        consent_res = await ac.post(f"/api/patients/{patient_id}/consent", json={"selected_language": "en", "consent_status": "granted"})
        assert consent_res.status_code == 200

        # 3. Start interview session
        start_res = await ac.post(f"/api/interview/start?patient_id={patient_id}")
        assert start_res.status_code == 200
        session = start_res.json()
        session_id = session["session_id"]
        q1 = session["current_question"]

        # 4. Submit urgent red-flag answer
        urgent_answer = "I have severe chest pain radiating to left arm and I am choking"
        ans_res = await ac.post(f"/api/interview/{session_id}/answer", json={
            "question_id": q1["question_id"],
            "question_text": q1["text_en"],
            "section": q1["section"],
            "stage_number": q1["stage_number"],
            "patient_answer": urgent_answer,
            "skipped": False,
            "input_method": "text",
            "language": "en",
        })
        assert ans_res.status_code == 200
        updated_session = ans_res.json()

        # 5. Verify session response flags red flag
        assert updated_session["has_triage_alert"] is True
        assert updated_session["status"] == "triage_alert"
        assert updated_session["triage_alert"] is not None
        alert_info = updated_session["triage_alert"]
        assert alert_info["priority"] == "URGENT"
        assert alert_info["detected_category"] in ["cardiovascular_severe", "respiratory_distress"]
        alert_id = alert_info["alert_id"]

        # 6. Verify real alert record persisted in MongoDB triage_alerts
        alert_doc = await db_manager.db.triage_alerts.find_one({"alert_id": alert_id})
        assert alert_doc is not None
        assert alert_doc["patient_id"] == patient_id
        assert alert_doc["token_number"] == patient["token_number"]
        assert alert_doc["status"] == "active"
        assert alert_doc["triggering_answer"] == urgent_answer

        # 7. Verify patient document status updated to triage_alert
        from bson import ObjectId
        patient_doc = await db_manager.db.patients.find_one({"_id": ObjectId(patient_id)})
        assert patient_doc["registration_status"] == "triage_alert"


@pytest.mark.anyio
async def test_triage_alert_hindi_creation():
    """Verify red-flag alert creation when patient responds in Hindi."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register patient with Hindi consent
        reg_res = await ac.post("/api/patients/register", json={
            "full_name": "Triage Test Patient Hindi",
            "age": 62,
            "gender": "female",
            "phone_number": "9988776656",
            "department": "Cardiology",
        })
        assert reg_res.status_code == 201
        patient = reg_res.json()
        patient_id = patient["id"]

        await ac.post(f"/api/patients/{patient_id}/consent", json={"selected_language": "hi", "consent_status": "granted"})
        start_res = await ac.post(f"/api/interview/start?patient_id={patient_id}")
        session = start_res.json()
        session_id = session["session_id"]
        q1 = session["current_question"]

        hindi_urgent = "मुझे बहुत तेज सीने में दर्द हो रहा है और सांस लेने में बहुत परेशानी हो रही है"
        ans_res = await ac.post(f"/api/interview/{session_id}/answer", json={
            "question_id": q1["question_id"],
            "question_text": q1["text_hi"],
            "section": q1["section"],
            "stage_number": q1["stage_number"],
            "patient_answer": hindi_urgent,
            "skipped": False,
            "input_method": "voice",
            "language": "hi",
        })
        assert ans_res.status_code == 200
        updated_session = ans_res.json()
        assert updated_session["has_triage_alert"] is True
        assert updated_session["triage_alert"]["patient_instruction_hi"] is not None


@pytest.mark.anyio
async def test_triage_alerts_list_and_staff_workflow():
    """Verify staff listing, retrieval, acknowledgment, and resolution of triage alerts."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Fetch alerts list
        list_res = await ac.get("/api/triage/alerts")
        assert list_res.status_code == 200
        data = list_res.json()
        assert "total_count" in data
        assert "active_count" in data
        assert len(data["alerts"]) > 0

        target_alert = data["alerts"][0]
        alert_id = target_alert["alert_id"]

        # 2. Retrieve single alert details
        single_res = await ac.get(f"/api/triage/alerts/{alert_id}")
        assert single_res.status_code == 200
        assert single_res.json()["alert_id"] == alert_id

        # 3. Staff acknowledges the alert
        ack_res = await ac.patch(f"/api/triage/alerts/{alert_id}", json={
            "status": "acknowledged",
            "staff_notes": "Triage nurse alerted the physician on duty",
            "staff_id": "nurse_kavita",
        })
        assert ack_res.status_code == 200
        ack_data = ack_res.json()
        assert ack_data["status"] == "acknowledged"
        assert ack_data["acknowledged_at"] is not None
        assert ack_data["acknowledged_by"] == "nurse_kavita"
        assert "Triage nurse alerted" in ack_data["staff_notes"]

        # 4. Staff marks alert as handled
        handled_res = await ac.patch(f"/api/triage/alerts/{alert_id}", json={
            "status": "handled",
            "staff_notes": "Patient escorted to Emergency Casualty Room 3",
            "staff_id": "dr_sharma",
        })
        assert handled_res.status_code == 200
        handled_data = handled_res.json()
        assert handled_data["status"] == "handled"
        assert handled_data["handled_at"] is not None
        assert handled_data["handled_by"] == "dr_sharma"
        assert "Patient escorted to Emergency" in handled_data["staff_notes"]

        # 5. Verify status reflected in list filter
        handled_list = await ac.get("/api/triage/alerts?status=handled")
        assert handled_list.status_code == 200
        handled_ids = [a["alert_id"] for a in handled_list.json()["alerts"]]
        assert alert_id in handled_ids

