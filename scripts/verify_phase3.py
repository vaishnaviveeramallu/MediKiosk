import httpx
import pymongo
import sys

# Ensure UTF-8 output on Windows console
sys.stdout.reconfigure(encoding='utf-8')

BASE_API = "http://127.0.0.1:8000/api"
FRONTEND_URL = "http://localhost:3000"
MONGO_URI = "mongodb://127.0.0.1:27017"


def main():
    print("==================================================")
    print("   MediKiosk Phase 3 - End-to-End Verification    ")
    print("==================================================")

    mongo_client = pymongo.MongoClient(MONGO_URI)
    db = mongo_client["medikiosk"]

    with httpx.Client(timeout=10.0) as client:
        # =====================================================================
        # SCENARIO A: Register -> Grant Consent -> Start Interview -> Submit Answer
        # =====================================================================
        print("\n[Scenario A] Registering Patient -> Granting Consent -> Submitting Answer...")
        patient_a_payload = {
            "full_name": "Rajeshwari Gupta",
            "age": 48,
            "gender": "Female",
            "phone_number": "9819876543",
            "address_city": "Indore",
            "address_state": "Madhya Pradesh",
            "initial_complaint": "Severe lower back stiffness",
        }

        # 1. Register
        reg_a = client.post(f"{BASE_API}/patients/register", json=patient_a_payload)
        assert reg_a.status_code == 201, f"Registration failed: {reg_a.text}"
        patient_a = reg_a.json()
        p_a_id = patient_a["id"]
        print(f"  ✓ Patient Registered: {patient_a['full_name']} (Token: {patient_a['token_number']})")

        # 2. Grant Consent (Hindi)
        consent_a = client.post(f"{BASE_API}/patients/{p_a_id}/consent", json={
            "selected_language": "hi",
            "consent_status": "granted",
        })
        assert consent_a.status_code == 200, f"Consent failed: {consent_a.text}"
        print(f"  ✓ Consent Granted in Hindi.")

        # 3. Start Interview
        start_a = client.post(f"{BASE_API}/interview/start?patient_id={p_a_id}")
        assert start_a.status_code == 200, f"Start interview failed: {start_a.text}"
        session_a = start_a.json()
        s_a_id = session_a["session_id"]
        print(f"  ✓ Interview Session Initialized: {s_a_id}")
        assert session_a["status"] == "in_progress"
        assert session_a["total_questions"] == 11
        assert session_a["answered_count"] == 0

        # 4. Submit Chief Complaint
        ans_a1 = client.post(f"{BASE_API}/interview/{s_a_id}/answer", json={
            "question_id": "chief_complaint",
            "question_text": "आज अस्पताल आने का आपका मुख्य कारण क्या है?",
            "section": "chief_complaint",
            "patient_answer": "कमर के निचले हिस्से में पिछले 4 दिन से असहनीय दर्द है।",
            "skipped": False,
        })
        assert ans_a1.status_code == 200, f"Submit answer failed: {ans_a1.text}"
        data_a1 = ans_a1.json()
        assert data_a1["answered_count"] == 1
        print(f"  ✓ Chief Complaint submitted and recorded.")

        # 5. Verify in MongoDB directly
        doc_session_a = db.interview_sessions.find_one({"session_id": s_a_id})
        assert doc_session_a is not None
        assert len(doc_session_a["answers"]) == 1
        assert doc_session_a["answers"][0]["patient_answer"] == "कमर के निचले हिस्से में पिछले 4 दिन से असहनीय दर्द है।"
        assert doc_session_a["patient_id"] == p_a_id
        print("  ✓ Verified directly in MongoDB collection 'interview_sessions'.")

        # =====================================================================
        # SCENARIO B: Multiple Answers -> Simulate Browser Refresh / Resume
        # =====================================================================
        print("\n[Scenario B] Submitting Multiple Answers and Verifying Resume Safety...")
        # Submit Answer 2: Duration
        client.post(f"{BASE_API}/interview/{s_a_id}/answer", json={
            "question_id": "duration",
            "question_text": "आपको यह समस्या कितने समय से है?",
            "section": "hpi",
            "patient_answer": "4 दिन से लगातार",
            "skipped": False,
        })

        # Submit Answer 3: Severity
        client.post(f"{BASE_API}/interview/{s_a_id}/answer", json={
            "question_id": "severity",
            "question_text": "आपकी तकलीफ अभी कितनी गंभीर है?",
            "section": "hpi",
            "patient_answer": "7 - Severe",
            "skipped": False,
        })

        # Simulate Browser Refresh: Fetch session by session_id
        resumed_res = client.get(f"{BASE_API}/interview/{s_a_id}")
        assert resumed_res.status_code == 200
        resumed = resumed_res.json()
        assert resumed["answered_count"] == 3
        assert len(resumed["answers"]) == 3
        assert resumed["answers"][0]["question_id"] == "chief_complaint"
        assert resumed["answers"][1]["question_id"] == "duration"
        assert resumed["answers"][2]["question_id"] == "severity"
        assert resumed["current_question_index"] == 2 or resumed["current_question_index"] == 3
        print(f"  ✓ Session reloaded successfully from MongoDB: 3 previously submitted answers intact.")

        # =====================================================================
        # SCENARIO C: Multiple Patients & Strict Session Isolation
        # =====================================================================
        print("\n[Scenario C] Testing Multi-Patient Session Isolation...")
        patient_c_payload = {
            "full_name": "Tariq Mahmood",
            "age": 36,
            "gender": "Male",
            "phone_number": "9812233445",
            "address_city": "Bhopal",
            "address_state": "Madhya Pradesh",
            "initial_complaint": "Persistent dry cough",
        }

        # Register Patient C
        reg_c = client.post(f"{BASE_API}/patients/register", json=patient_c_payload)
        patient_c = reg_c.json()
        p_c_id = patient_c["id"]
        client.post(f"{BASE_API}/patients/{p_c_id}/consent", json={"selected_language": "en", "consent_status": "granted"})

        # Start Interview for Patient C
        start_c = client.post(f"{BASE_API}/interview/start?patient_id={p_c_id}")
        session_c = start_c.json()
        s_c_id = session_c["session_id"]

        assert s_c_id != s_a_id, "Session IDs must be unique per patient"
        assert session_c["answered_count"] == 0, "Patient C must have 0 answers initially"

        # Submit answer for Patient C
        client.post(f"{BASE_API}/interview/{s_c_id}/answer", json={
            "question_id": "chief_complaint",
            "question_text": "What is your primary problem?",
            "section": "chief_complaint",
            "patient_answer": "Dry hacking cough for 1 week without fever",
            "skipped": False,
        })

        # Verify Patient A session still has 3 answers and is unaffected
        sess_a_check = client.get(f"{BASE_API}/interview/{s_a_id}").json()
        assert sess_a_check["answered_count"] == 3
        assert sess_a_check["answers"][0]["patient_answer"] == "कमर के निचले हिस्से में पिछले 4 दिन से असहनीय दर्द है।"

        # Verify Patient C session only has their own answer
        sess_c_check = client.get(f"{BASE_API}/interview/{s_c_id}").json()
        assert sess_c_check["answered_count"] == 1
        assert sess_c_check["answers"][0]["patient_answer"] == "Dry hacking cough for 1 week without fever"
        print("  ✓ Strict session isolation verified: Patient A and Patient C answers are completely segregated.")

        # =====================================================================
        # SCENARIO D: Consent Guard (Declined Consent Blocks Interview)
        # =====================================================================
        print("\n[Scenario D] Testing Consent Guard (Declined Consent Blocks Interview)...")
        patient_d_payload = {
            "full_name": "Manju Sharma",
            "age": 60,
            "gender": "Female",
            "phone_number": "9814455667",
        }
        reg_d = client.post(f"{BASE_API}/patients/register", json=patient_d_payload).json()
        p_d_id = reg_d["id"]

        # Patient declines consent
        client.post(f"{BASE_API}/patients/{p_d_id}/consent", json={"selected_language": "en", "consent_status": "declined"})

        # Attempt to start interview
        blocked_res = client.post(f"{BASE_API}/interview/start?patient_id={p_d_id}")
        assert blocked_res.status_code == 403, f"Expected 403, got: {blocked_res.status_code}"
        assert "consent" in blocked_res.json()["detail"].lower()
        print(f"  ✓ Interview successfully blocked with HTTP 403: {blocked_res.json()['detail']}")

        # =====================================================================
        # Frontend Routes Verification
        # =====================================================================
        print("\n[Step 5] Checking Frontend Kiosk Routes...")
        r_interview = client.get(f"{FRONTEND_URL}/interview")
        assert r_interview.status_code == 200
        print("  - Kiosk Interview Screen (/interview) -> 200 OK")

        r_interview_with_pid = client.get(f"{FRONTEND_URL}/interview?patientId={p_a_id}")
        assert r_interview_with_pid.status_code == 200
        print(f"  - Active Patient Interview Screen (/interview?patientId={p_a_id}) -> 200 OK")

        r_queue = client.get(f"{FRONTEND_URL}/queue")
        assert r_queue.status_code == 200
        print("  - Live OPD Queue (/queue) -> 200 OK")

    # 5. Clean up verification test patients and sessions
    db.patients.delete_many({"_id": {"$in": [
        pymongo.collection.ObjectId(p_a_id),
        pymongo.collection.ObjectId(p_b_id),
        pymongo.collection.ObjectId(p_c_id)
    ]}})
    db.interview_sessions.delete_many({"patient_id": {"$in": [p_a_id, p_b_id, p_c_id]}})
    print("✓ Verification test patients and interview sessions cleaned up from dev database.")

    print("\n==================================================")
    print("   PHASE 3 VERIFICATION 100% SUCCESSFUL!         ")
    print("==================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Verification Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
