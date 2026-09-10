import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId
from app.main import app
from app.database import db_manager, get_database


@pytest.mark.anyio
async def test_adaptive_branching_three_complaints():
    """
    Verify that 3 distinctly different chief complaints:
      1. Chest Pain
      2. Joint / Knee Pain
      3. Fever with Chills
    dynamically generate tailored follow-up question pathways.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # -------------------------------------------------------------
        # 1. Chest Pain Pathway (Cardiac SOCRATES)
        # -------------------------------------------------------------
        p_cardiac = (await client.post("/api/patients/register", json={
            "full_name": "Test Cardiac Patient",
            "age": 52,
            "gender": "Male",
            "phone_number": "9111222331",
            "initial_complaint": "Chest pain",
        })).json()
        await client.post(f"/api/patients/{p_cardiac['id']}/consent", json={"selected_language": "en", "consent_status": "granted"})
        sess_cardiac = (await client.post(f"/api/interview/start?patient_id={p_cardiac['id']}")).json()

        ans_cardiac = await client.post(
            f"/api/interview/{sess_cardiac['session_id']}/answer",
            json={
                "question_id": "chief_complaint",
                "question_text": sess_cardiac["current_question"]["text_en"],
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "Heavy squeezing chest pain spreading towards left arm",
                "skipped": False,
            },
        )
        cardiac_followup = ans_cardiac.json()["current_question"]
        assert cardiac_followup["question_id"] in ["hpi_radiation", "hpi_character"]
        assert "chest" in cardiac_followup["text_en"].lower() or "spread" in cardiac_followup["text_en"].lower() or "radiate" in cardiac_followup["text_en"].lower()

        # -------------------------------------------------------------
        # 2. Joint / Knee Pain Pathway (Musculoskeletal)
        # -------------------------------------------------------------
        p_msk = (await client.post("/api/patients/register", json={
            "full_name": "Test MSK Patient",
            "age": 60,
            "gender": "Male",
            "phone_number": "9111222332",
            "initial_complaint": "Joint pain",
        })).json()
        await client.post(f"/api/patients/{p_msk['id']}/consent", json={"selected_language": "en", "consent_status": "granted"})
        sess_msk = (await client.post(f"/api/interview/start?patient_id={p_msk['id']}")).json()

        ans_msk = await client.post(
            f"/api/interview/{sess_msk['session_id']}/answer",
            json={
                "question_id": "chief_complaint",
                "question_text": sess_msk["current_question"]["text_en"],
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "Severe swelling and pain in right knee joint",
                "skipped": False,
            },
        )
        msk_followup = ans_msk.json()["current_question"]
        assert msk_followup["question_id"] in ["hpi_location", "hpi_weight_bearing", "hpi_associated"]
        assert "joint" in msk_followup["text_en"].lower() or "walk" in msk_followup["text_en"].lower()

        # -------------------------------------------------------------
        # 3. Fever with Chills Pathway (Infectious / Systemic)
        # -------------------------------------------------------------
        p_fever = (await client.post("/api/patients/register", json={
            "full_name": "Test Fever Patient",
            "age": 29,
            "gender": "Female",
            "phone_number": "9111222333",
            "initial_complaint": "Fever with chills",
        })).json()
        await client.post(f"/api/patients/{p_fever['id']}/consent", json={"selected_language": "en", "consent_status": "granted"})
        sess_fever = (await client.post(f"/api/interview/start?patient_id={p_fever['id']}")).json()

        ans_fever = await client.post(
            f"/api/interview/{sess_fever['session_id']}/answer",
            json={
                "question_id": "chief_complaint",
                "question_text": sess_fever["current_question"]["text_en"],
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "High fever with shivering chills for 3 days",
                "skipped": False,
            },
        )
        fever_followup = ans_fever.json()["current_question"]
        assert fever_followup["question_id"] in ["hpi_pattern", "hpi_associated"]
        assert "fever" in fever_followup["text_en"].lower() or "chills" in fever_followup["text_en"].lower()

        # -------------------------------------------------------------
        # Verify Strict Pathway Divergence
        # -------------------------------------------------------------
        assert cardiac_followup["question_id"] != msk_followup["question_id"]
        assert cardiac_followup["question_id"] != fever_followup["question_id"]
        assert msk_followup["question_id"] != fever_followup["question_id"]


@pytest.mark.anyio
async def test_skip_and_idk_persistence():
    """
    Verify that 'I don't know' and 'Prefer not to answer' are accurately
    flagged and persisted into MongoDB with skipped=True.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p = (await client.post("/api/patients/register", json={
            "full_name": "Skip Test Patient",
            "age": 42,
            "gender": "Female",
            "phone_number": "9444001122",
        })).json()
        await client.post(f"/api/patients/{p['id']}/consent", json={"selected_language": "en", "consent_status": "granted"})
        sess = (await client.post(f"/api/interview/start?patient_id={p['id']}")).json()

        # 1. Answer Chief Complaint
        await client.post(
            f"/api/interview/{sess['session_id']}/answer",
            json={
                "question_id": "chief_complaint",
                "question_text": "Primary problem?",
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "General body weakness",
                "skipped": False,
            },
        )

        # 2. Answer Follow-up with 'I don't know' (skipped=True)
        res_idk = await client.post(
            f"/api/interview/{sess['session_id']}/answer",
            json={
                "question_id": "hpi_severity",
                "question_text": "Severity rating?",
                "section": "hpi",
                "stage_number": 2,
                "patient_answer": "I don't know",
                "skipped": True,
            },
        )
        assert res_idk.status_code == 200
        data_idk = res_idk.json()
        idk_record = next(a for a in data_idk["answers"] if a["question_id"] == "hpi_severity")
        assert idk_record["patient_answer"] == "I don't know"
        assert idk_record["skipped"] is True

        # 3. Answer next question with 'Prefer not to answer'
        res_pref = await client.post(
            f"/api/interview/{sess['session_id']}/answer",
            json={
                "question_id": "pmh_conditions",
                "question_text": "Chronic conditions?",
                "section": "past_medical",
                "stage_number": 3,
                "patient_answer": "Prefer not to answer",
                "skipped": True,
            },
        )
        assert res_pref.status_code == 200
        data_pref = res_pref.json()
        pref_record = next(a for a in data_pref["answers"] if a["question_id"] == "pmh_conditions")
        assert pref_record["patient_answer"] == "Prefer not to answer"
        assert pref_record["skipped"] is True

        # 4. Verify MongoDB collection directly
        db = get_database()
        session_doc = await db.interview_sessions.find_one({"session_id": sess["session_id"]})
        assert session_doc is not None
        saved_idk = next(a for a in session_doc["answers"] if a["question_id"] == "hpi_severity")
        assert saved_idk["skipped"] is True
        saved_pref = next(a for a in session_doc["answers"] if a["question_id"] == "pmh_conditions")
        assert saved_pref["skipped"] is True


@pytest.mark.anyio
async def test_multi_patient_adaptive_session_isolation():
    """Verify complete isolation between simultaneous adaptive interview sessions."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Patient 1: Cardiac
        p1 = (await client.post("/api/patients/register", json={
            "full_name": "Isolation Patient One",
            "age": 45,
            "gender": "Male",
            "phone_number": "9000000011",
        })).json()
        await client.post(f"/api/patients/{p1['id']}/consent", json={"selected_language": "en", "consent_status": "granted"})
        s1 = (await client.post(f"/api/interview/start?patient_id={p1['id']}")).json()

        # Patient 2: Respiratory
        p2 = (await client.post("/api/patients/register", json={
            "full_name": "Isolation Patient Two",
            "age": 28,
            "gender": "Female",
            "phone_number": "9000000022",
        })).json()
        await client.post(f"/api/patients/{p2['id']}/consent", json={"selected_language": "en", "consent_status": "granted"})
        s2 = (await client.post(f"/api/interview/start?patient_id={p2['id']}")).json()

        assert s1["session_id"] != s2["session_id"]
        assert s1["patient_id"] != s2["patient_id"]

        # Submit distinct answers
        await client.post(f"/api/interview/{s1['session_id']}/answer", json={
            "question_id": "chief_complaint",
            "question_text": "What is your primary complaint?",
            "section": "chief_complaint",
            "patient_answer": "Severe radiating chest pain",
            "skipped": False,
        })

        await client.post(f"/api/interview/{s2['session_id']}/answer", json={
            "question_id": "chief_complaint",
            "question_text": "What is your primary complaint?",
            "section": "chief_complaint",
            "patient_answer": "Continuous dry cough and wheezing",
            "skipped": False,
        })

        # Verify Session 1
        res1 = (await client.get(f"/api/interview/{s1['session_id']}")).json()
        assert len(res1["answers"]) == 1
        assert res1["answers"][0]["patient_answer"] == "Severe radiating chest pain"
        # Assert Patient 1 cannot see Patient 2's answer
        for ans in res1["answers"]:
            assert "cough" not in ans["patient_answer"]

        # Verify Session 2
        res2 = (await client.get(f"/api/interview/{s2['session_id']}")).json()
        assert len(res2["answers"]) == 1
        assert res2["answers"][0]["patient_answer"] == "Continuous dry cough and wheezing"
        # Assert Patient 2 cannot see Patient 1's answer
        for ans in res2["answers"]:
            assert "chest pain" not in ans["patient_answer"]


@pytest.mark.anyio
async def test_adaptive_resume_safety():
    """Verify session can be resumed across browser refreshes with full answers intact."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p = (await client.post("/api/patients/register", json={
            "full_name": "Resume Patient",
            "age": 40,
            "gender": "Female",
            "phone_number": "9222333444",
        })).json()
        await client.post(f"/api/patients/{p['id']}/consent", json={"selected_language": "en", "consent_status": "granted"})
        sess = (await client.post(f"/api/interview/start?patient_id={p['id']}")).json()

        # Submit answer 1
        await client.post(f"/api/interview/{sess['session_id']}/answer", json={
            "question_id": "chief_complaint",
            "question_text": "Primary problem?",
            "section": "chief_complaint",
            "patient_answer": "High fever with shaking chills",
            "skipped": False,
        })

        # Submit answer 2
        await client.post(f"/api/interview/{sess['session_id']}/answer", json={
            "question_id": "hpi_pattern",
            "question_text": "Duration?",
            "section": "hpi",
            "patient_answer": "3-5 days intermittent spikes",
            "skipped": False,
        })

        # Resume via GET /api/interview/{session_id} (simulates browser reload)
        resumed = (await client.get(f"/api/interview/{sess['session_id']}")).json()
        assert resumed["session_id"] == sess["session_id"]
        assert len(resumed["answers"]) == 2
        assert resumed["answers"][0]["patient_answer"] == "High fever with shaking chills"
        assert resumed["answers"][1]["patient_answer"] == "3-5 days intermittent spikes"
        assert resumed["current_question"] is not None
        assert resumed["status"] == "in_progress"


@pytest.mark.anyio
async def test_clinical_history_integrity():
    """
    Verify that the final clinical history contains strictly and only
    information explicitly entered by the patient, with no invented data.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        p = (await client.post("/api/patients/register", json={
            "full_name": "History Integrity Patient",
            "age": 35,
            "gender": "Male",
            "phone_number": "9555112233",
        })).json()
        p_id = p["id"]
        await client.post(f"/api/patients/{p_id}/consent", json={"selected_language": "en", "consent_status": "granted"})
        sess = (await client.post(f"/api/interview/start?patient_id={p_id}")).json()
        s_id = sess["session_id"]

        entered_answers = {
            "chief_complaint": "Occasional lower back dull ache",
            "hpi_location": "Lower back",
            "hpi_severity": "4",
        }

        for q_id, ans_text in entered_answers.items():
            await client.post(f"/api/interview/{s_id}/answer", json={
                "question_id": q_id,
                "question_text": f"Question for {q_id}",
                "section": "hpi" if q_id != "chief_complaint" else "chief_complaint",
                "patient_answer": ans_text,
                "skipped": False,
            })

        # Fetch patient from database
        db = get_database()
        patient_doc = await db.patients.find_one({"_id": ObjectId(p_id)})
        assert patient_doc is not None
        saved_history = patient_doc.get("clinical_history", {})

        # Assert all saved answers match patient-entered answers exactly
        for q_id, ans_text in entered_answers.items():
            assert q_id in saved_history
            assert saved_history[q_id]["answer"] == ans_text

        # Assert no phantom symptoms or invented keys exist in clinical history
        for key in saved_history:
            assert key in entered_answers


@pytest.mark.anyio
async def test_non_diagnostic_safety_constraint():
    """Verify the AI engine never emits diagnostic conclusions."""
    from app.services.ai_service import ClinicalHeuristicEngine

    patient_info = {"age": 55, "gender": "Male"}
    answers = [
        {"question_id": "chief_complaint", "question_text": "Primary problem?", "patient_answer": "Crushing chest pain and sweating"},
        {"question_id": "hpi_radiation", "question_text": "Radiation?", "patient_answer": "Spreads to my left arm and jaw"},
    ]

    next_q = ClinicalHeuristicEngine.get_next_question(patient_info, answers, "en")
    
    # Assert question is an inquiry, not a diagnosis
    for diagnostic_word in ["you have a heart attack", "myocardial infarction", "you are diagnosed with", "take nitroglycerin"]:
        assert diagnostic_word not in next_q.text_en.lower()
    
    # Assert it asks a question
    assert next_q.text_en.strip().endswith("?")
