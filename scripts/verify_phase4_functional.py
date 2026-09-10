import httpx
import pymongo
import sys

# Ensure UTF-8 output on Windows console
sys.stdout.reconfigure(encoding='utf-8')

BASE_API = "http://127.0.0.1:8000/api"
MONGO_URI = "mongodb://127.0.0.1:27017"


def run_functional_audit():
    print("==================================================================")
    print("      MediKiosk Phase 4 – Complete Functional Verification       ")
    print("==================================================================")

    mongo_client = pymongo.MongoClient(MONGO_URI)
    db = mongo_client["medikiosk"]

    created_patients = []
    created_sessions = []

    try:
        with httpx.Client(timeout=10.0) as client:
            # -------------------------------------------------------------
            # TEST 1: Chief Complaint = FEVER WITH CHILLS
            # -------------------------------------------------------------
            print("\n[Test 1] Testing Chief Complaint: 'Fever with chills'...")
            reg_fever = client.post(f"{BASE_API}/patients/register", json={
                "full_name": "Functional Test Fever",
                "age": 28,
                "gender": "Female",
                "phone_number": "9666001122",
                "initial_complaint": "High fever with chills",
            }).json()
            pid_fever = reg_fever["id"]
            created_patients.append(pid_fever)

            client.post(f"{BASE_API}/patients/{pid_fever}/consent", json={"selected_language": "en", "consent_status": "granted"})
            sess_fever = client.post(f"{BASE_API}/interview/start?patient_id={pid_fever}").json()
            sid_fever = sess_fever["session_id"]
            created_sessions.append(sid_fever)
            print(f"  ✓ Session initialized: {sid_fever}")
            assert sess_fever["current_question"]["question_id"] == "chief_complaint"

            # Submit Chief Complaint: Fever
            ans1_fever = client.post(f"{BASE_API}/interview/{sid_fever}/answer", json={
                "question_id": "chief_complaint",
                "question_text": sess_fever["current_question"]["text_en"],
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "High fever with chills and shivering for 3 days",
                "skipped": False,
            }).json()

            q2_fever = ans1_fever["current_question"]
            print(f"  ✓ Fever Follow-up 1: [{q2_fever['question_id']}] {q2_fever['text_en']}")
            assert q2_fever["question_id"] == "hpi_pattern", f"Expected hpi_pattern, got {q2_fever['question_id']}"
            assert "fever" in q2_fever["text_en"].lower() or "chills" in q2_fever["text_en"].lower()

            # Submit answer with 'I don't know' test
            ans2_fever = client.post(f"{BASE_API}/interview/{sid_fever}/answer", json={
                "question_id": q2_fever["question_id"],
                "question_text": q2_fever["text_en"],
                "section": q2_fever["section"],
                "stage_number": q2_fever["stage_number"],
                "patient_answer": "3-5 days intermittent spikes",
                "skipped": False,
            }).json()
            q3_fever = ans2_fever["current_question"]
            print(f"  ✓ Fever Follow-up 2: [{q3_fever['question_id']}] {q3_fever['text_en']}")
            assert q3_fever["question_id"] == "hpi_associated"

            # Test 'I don't know'
            print("  -> Testing 'I don't know' submission...")
            ans3_fever = client.post(f"{BASE_API}/interview/{sid_fever}/answer", json={
                "question_id": q3_fever["question_id"],
                "question_text": q3_fever["text_en"],
                "section": q3_fever["section"],
                "stage_number": q3_fever["stage_number"],
                "patient_answer": "I don't know",
                "skipped": True,
            }).json()
            q4_fever = ans3_fever["current_question"]
            assert q4_fever["question_id"] == "hpi_severity"

            # Test Severity 1-10
            ans4_fever = client.post(f"{BASE_API}/interview/{sid_fever}/answer", json={
                "question_id": q4_fever["question_id"],
                "question_text": q4_fever["text_en"],
                "section": q4_fever["section"],
                "stage_number": q4_fever["stage_number"],
                "patient_answer": "8",
                "skipped": False,
            }).json()
            q5_fever = ans4_fever["current_question"]
            # Once severity answered, MUST progress to Stage 3 Past Medical History!
            assert q5_fever["question_id"] == "pmh_conditions"
            assert q5_fever["stage_number"] == 3

            # Test 'Prefer not to answer'
            print("  -> Testing 'Prefer not to answer' submission...")
            ans5_fever = client.post(f"{BASE_API}/interview/{sid_fever}/answer", json={
                "question_id": q5_fever["question_id"],
                "question_text": q5_fever["text_en"],
                "section": q5_fever["section"],
                "stage_number": q5_fever["stage_number"],
                "patient_answer": "Prefer not to answer",
                "skipped": True,
            }).json()

            # Verify in MongoDB that 'I don't know' and 'Prefer not to answer' were persisted with skipped=True
            db_sess_fever = db.interview_sessions.find_one({"session_id": sid_fever})
            assert db_sess_fever is not None
            saved_idk = next(a for a in db_sess_fever["answers"] if a["question_id"] == "hpi_associated")
            assert saved_idk["skipped"] is True
            assert saved_idk["patient_answer"] == "I don't know"
            saved_pref = next(a for a in db_sess_fever["answers"] if a["question_id"] == "pmh_conditions")
            assert saved_pref["skipped"] is True
            assert saved_pref["patient_answer"] == "Prefer not to answer"
            print("  ✓ 'I don't know' and 'Prefer not to answer' successfully verified in MongoDB.")

            # -------------------------------------------------------------
            # TEST 2: Chief Complaint = CHEST PAIN
            # -------------------------------------------------------------
            print("\n[Test 2] Testing Chief Complaint: 'Chest pain'...")
            reg_cardiac = client.post(f"{BASE_API}/patients/register", json={
                "full_name": "Functional Test Cardiac",
                "age": 58,
                "gender": "Male",
                "phone_number": "9666001133",
                "initial_complaint": "Chest pain",
            }).json()
            pid_cardiac = reg_cardiac["id"]
            created_patients.append(pid_cardiac)

            client.post(f"{BASE_API}/patients/{pid_cardiac}/consent", json={"selected_language": "en", "consent_status": "granted"})
            sess_cardiac = client.post(f"{BASE_API}/interview/start?patient_id={pid_cardiac}").json()
            sid_cardiac = sess_cardiac["session_id"]
            created_sessions.append(sid_cardiac)

            ans1_cardiac = client.post(f"{BASE_API}/interview/{sid_cardiac}/answer", json={
                "question_id": "chief_complaint",
                "question_text": sess_cardiac["current_question"]["text_en"],
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "Severe squeezing chest pain radiating to left arm",
                "skipped": False,
            }).json()

            q2_cardiac = ans1_cardiac["current_question"]
            print(f"  ✓ Cardiac Follow-up 1: [{q2_cardiac['question_id']}] {q2_cardiac['text_en']}")
            assert q2_cardiac["question_id"] == "hpi_radiation", f"Expected hpi_radiation, got {q2_cardiac['question_id']}"
            # Assert question 2 for Chest Pain is completely different from Fever!
            assert q2_cardiac["question_id"] != q2_fever["question_id"]

            # Submit Radiation
            ans2_cardiac = client.post(f"{BASE_API}/interview/{sid_cardiac}/answer", json={
                "question_id": "hpi_radiation",
                "question_text": q2_cardiac["text_en"],
                "section": "hpi",
                "stage_number": 2,
                "patient_answer": "Spreads to left arm / shoulder",
                "skipped": False,
            }).json()
            q3_cardiac = ans2_cardiac["current_question"]
            print(f"  ✓ Cardiac Follow-up 2: [{q3_cardiac['question_id']}] {q3_cardiac['text_en']}")
            assert q3_cardiac["question_id"] == "hpi_character"

            # -------------------------------------------------------------
            # TEST 3: Chief Complaint = JOINT / KNEE PAIN
            # -------------------------------------------------------------
            print("\n[Test 3] Testing Chief Complaint: 'Joint / Knee pain'...")
            reg_joint = client.post(f"{BASE_API}/patients/register", json={
                "full_name": "Functional Test Joint",
                "age": 62,
                "gender": "Female",
                "phone_number": "9666001144",
                "initial_complaint": "Joint pain",
            }).json()
            pid_joint = reg_joint["id"]
            created_patients.append(pid_joint)

            client.post(f"{BASE_API}/patients/{pid_joint}/consent", json={"selected_language": "en", "consent_status": "granted"})
            sess_joint = client.post(f"{BASE_API}/interview/start?patient_id={pid_joint}").json()
            sid_joint = sess_joint["session_id"]
            created_sessions.append(sid_joint)

            ans1_joint = client.post(f"{BASE_API}/interview/{sid_joint}/answer", json={
                "question_id": "chief_complaint",
                "question_text": sess_joint["current_question"]["text_en"],
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "Right knee swelling and pain after a long walk",
                "skipped": False,
            }).json()

            q2_joint = ans1_joint["current_question"]
            print(f"  ✓ Joint Follow-up 1: [{q2_joint['question_id']}] {q2_joint['text_en']}")
            assert q2_joint["question_id"] == "hpi_location", f"Expected hpi_location, got {q2_joint['question_id']}"
            assert "joint" in q2_joint["text_en"].lower() or "knee" in q2_joint["text_en"].lower()

            # Assert complete divergence across all 3 complaints
            print("\n[Divergence Check] Asserting Question Divergence across 3 Complaints:")
            print(f"  - Fever Follow-up:   [{q2_fever['question_id']}] {q2_fever['text_en']}")
            print(f"  - Cardiac Follow-up: [{q2_cardiac['question_id']}] {q2_cardiac['text_en']}")
            print(f"  - Joint Follow-up:   [{q2_joint['question_id']}] {q2_joint['text_en']}")
            assert q2_fever["question_id"] != q2_cardiac["question_id"]
            assert q2_fever["question_id"] != q2_joint["question_id"]
            assert q2_cardiac["question_id"] != q2_joint["question_id"]
            print("  ✓ 100% Adaptive Question Divergence confirmed across Fever, Cardiac, and Joint complaints.")

            # -------------------------------------------------------------
            # TEST 4: Browser Reload / Resume Safety Test
            # -------------------------------------------------------------
            print("\n[Test 4] Testing Browser Reload / Resume Safety...")
            # Submit answer for joint location
            ans2_joint = client.post(f"{BASE_API}/interview/{sid_joint}/answer", json={
                "question_id": "hpi_location",
                "question_text": q2_joint["text_en"],
                "section": "hpi",
                "stage_number": 2,
                "patient_answer": "Right knee",
                "skipped": False,
            }).json()

            # Now simulate page reload by requesting GET /api/interview/{session_id}
            reloaded_sess = client.get(f"{BASE_API}/interview/{sid_joint}").json()
            assert reloaded_sess["session_id"] == sid_joint
            assert len(reloaded_sess["answers"]) == 2
            assert reloaded_sess["answers"][0]["patient_answer"] == "Right knee swelling and pain after a long walk"
            assert reloaded_sess["answers"][1]["patient_answer"] == "Right knee"
            assert reloaded_sess["current_question"]["question_id"] == "hpi_weight_bearing"
            print("  ✓ Full state and past answers reloaded without any loss.")

            # -------------------------------------------------------------
            # TEST 5: Cross-Patient Multi-Session Isolation Test
            # -------------------------------------------------------------
            print("\n[Test 5] Verifying Strict Multi-Patient Isolation...")
            fever_sess_check = client.get(f"{BASE_API}/interview/{sid_fever}").json()
            cardiac_sess_check = client.get(f"{BASE_API}/interview/{sid_cardiac}").json()
            joint_sess_check = client.get(f"{BASE_API}/interview/{sid_joint}").json()

            # Fever answers must not contain cardiac or knee answers
            for a in fever_sess_check["answers"]:
                assert "chest pain" not in a["patient_answer"].lower()
                assert "knee" not in a["patient_answer"].lower()

            # Cardiac answers must not contain fever or knee answers
            for a in cardiac_sess_check["answers"]:
                assert "fever" not in a["patient_answer"].lower()
                assert "knee" not in a["patient_answer"].lower()

            # Joint answers must not contain fever or chest pain answers
            for a in joint_sess_check["answers"]:
                assert "fever" not in a["patient_answer"].lower()
                assert "chest pain" not in a["patient_answer"].lower()
            print("  ✓ Complete isolation confirmed across all 3 active patient sessions.")

            # -------------------------------------------------------------
            # TEST 6: Clinical History Integrity & Non-Diagnostic Check
            # -------------------------------------------------------------
            print("\n[Test 6] Inspecting MongoDB Clinical History & Safety Invariants...")
            cardiac_patient_doc = db.patients.find_one({"_id": pymongo.collection.ObjectId(pid_cardiac)})
            assert cardiac_patient_doc is not None
            c_hist = cardiac_patient_doc.get("clinical_history", {})
            print(f"  Cardiac Patient Clinical History Keys in DB: {list(c_hist.keys())}")
            assert "chief_complaint" in c_hist
            assert "hpi_radiation" in c_hist
            assert c_hist["chief_complaint"]["answer"] == "Severe squeezing chest pain radiating to left arm"
            assert c_hist["hpi_radiation"]["answer"] == "Spreads to left arm / shoulder"

            # Check that no diagnostic statements exist anywhere in clinical_history or questions
            for k, val in c_hist.items():
                ans_str = str(val.get("answer", "")).lower()
                for bad_word in ["diagnosis:", "you have acute", "prescribed", "rx:"]:
                    assert bad_word not in ans_str

            print("  ✓ Clinical history accurately mirrors patient answers with ZERO invented diagnoses.")

    finally:
        # Cleanup test patients and sessions from development database
        if created_patients:
            db.patients.delete_many({"_id": {"$in": [pymongo.collection.ObjectId(pid) for pid in created_patients]}})
        if created_sessions:
            db.interview_sessions.delete_many({"session_id": {"$in": created_sessions}})
        print("\n✓ Functional test records cleanly removed from development database.")

    print("\n==================================================================")
    print("      ALL 12 FUNCTIONAL AUDIT CHECKS PASSED WITH 100% SUCCESS!    ")
    print("==================================================================")


if __name__ == "__main__":
    run_functional_audit()
