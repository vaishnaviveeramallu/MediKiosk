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
    print("   MediKiosk Phase 4 - Adaptive AI Verification   ")
    print("==================================================")

    mongo_client = pymongo.MongoClient(MONGO_URI)
    db = mongo_client["medikiosk"]

    created_patient_ids = []
    created_session_ids = []

    try:
        with httpx.Client(timeout=10.0) as client:
            # =================================================================
            # SCENARIO 1: Cardiac Chief Complaint -> Adaptive Questioning
            # =================================================================
            print("\n[Scenario 1] Testing Adaptive Cardiac Pathway (English)...")
            reg1 = client.post(f"{BASE_API}/patients/register", json={
                "full_name": "Phase4 Cardiac Verification",
                "age": 55,
                "gender": "Male",
                "phone_number": "9333001122",
                "initial_complaint": "Chest pain",
            })
            assert reg1.status_code == 201, f"Registration failed: {reg1.text}"
            p1 = reg1.json()
            p1_id = p1["id"]
            created_patient_ids.append(p1_id)
            print(f"  ✓ Patient 1 registered: {p1['full_name']} (Token: {p1['token_number']})")

            # Grant consent
            c1 = client.post(f"{BASE_API}/patients/{p1_id}/consent", json={
                "selected_language": "en",
                "consent_status": "granted",
            })
            assert c1.status_code == 200

            # Start adaptive interview
            s1_res = client.post(f"{BASE_API}/interview/start?patient_id={p1_id}")
            assert s1_res.status_code == 200
            s1 = s1_res.json()
            s1_id = s1["session_id"]
            created_session_ids.append(s1_id)
            print(f"  ✓ Session initialized: {s1_id}")
            assert s1["current_question"]["question_id"] == "chief_complaint"

            # Submit Chief Complaint: "Heavy squeezing chest pain"
            ans1 = client.post(f"{BASE_API}/interview/{s1_id}/answer", json={
                "question_id": "chief_complaint",
                "question_text": s1["current_question"]["text_en"],
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "Heavy squeezing chest pain spreading towards left arm",
                "skipped": False,
            })
            assert ans1.status_code == 200
            data1 = ans1.json()
            next_q1 = data1["current_question"]
            print(f"  ✓ Adaptive Follow-up 1: [{next_q1['question_id']}] {next_q1['text_en']}")
            assert next_q1["question_id"] in ["hpi_radiation", "hpi_character"]

            # Submit Radiation Answer
            ans2 = client.post(f"{BASE_API}/interview/{s1_id}/answer", json={
                "question_id": next_q1["question_id"],
                "question_text": next_q1["text_en"],
                "section": next_q1["section"],
                "stage_number": next_q1["stage_number"],
                "patient_answer": "Spreads to left arm / shoulder",
                "skipped": False,
            })
            assert ans2.status_code == 200
            data2 = ans2.json()
            next_q2 = data2["current_question"]
            print(f"  ✓ Adaptive Follow-up 2: [{next_q2['question_id']}] {next_q2['text_en']}")
            assert len(data2["answers"]) == 2

            # =================================================================
            # SCENARIO 2: Neurological Chief Complaint (Hindi) -> Divergence Check
            # =================================================================
            print("\n[Scenario 2] Testing Adaptive Neurological Pathway (Hindi)...")
            reg2 = client.post(f"{BASE_API}/patients/register", json={
                "full_name": "Phase4 Neuro Verification",
                "age": 32,
                "gender": "Female",
                "phone_number": "9333001133",
                "initial_complaint": "तेज सिरदर्द",
            })
            assert reg2.status_code == 201
            p2 = reg2.json()
            p2_id = p2["id"]
            created_patient_ids.append(p2_id)
            print(f"  ✓ Patient 2 registered: {p2['full_name']} (Token: {p2['token_number']})")

            # Grant consent in Hindi
            c2 = client.post(f"{BASE_API}/patients/{p2_id}/consent", json={
                "selected_language": "hi",
                "consent_status": "granted",
            })
            assert c2.status_code == 200

            # Start adaptive interview
            s2_res = client.post(f"{BASE_API}/interview/start?patient_id={p2_id}")
            assert s2_res.status_code == 200
            s2 = s2_res.json()
            s2_id = s2["session_id"]
            created_session_ids.append(s2_id)
            print(f"  ✓ Session initialized: {s2_id}")

            # Submit Chief Complaint in Hindi: "तीन दिन से तेज सिरदर्द और उल्टी का मन"
            ans_neuro = client.post(f"{BASE_API}/interview/{s2_id}/answer", json={
                "question_id": "chief_complaint",
                "question_text": s2["current_question"]["text_hi"],
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "तीन दिन से तेज सिरदर्द और उल्टी का मन हो रहा है",
                "skipped": False,
            })
            assert ans_neuro.status_code == 200
            data_neuro = ans_neuro.json()
            next_q_neuro = data_neuro["current_question"]
            print(f"  ✓ Adaptive Follow-up (Neuro Hindi): [{next_q_neuro['question_id']}] {next_q_neuro['text_hi']}")
            assert next_q_neuro["question_id"] in ["hpi_character", "hpi_location"]

            # Verify divergence: Neuro question is completely different from Cardiac question!
            assert next_q_neuro["question_id"] != next_q1["question_id"] or next_q_neuro["text_en"] != next_q1["text_en"]
            print("  ✓ Strict Divergence Confirmed: Cardiac path != Neurological path.")

            # =================================================================
            # SCENARIO 3: Musculoskeletal Chief Complaint (Knee Pain)
            # =================================================================
            print("\n[Scenario 3] Testing Musculoskeletal Pathway (Knee Pain)...")
            reg3 = client.post(f"{BASE_API}/patients/register", json={
                "full_name": "Phase4 MSK Verification",
                "age": 63,
                "gender": "Male",
                "phone_number": "9333001144",
                "initial_complaint": "Right knee swelling and inability to walk",
            })
            assert reg3.status_code == 201
            p3 = reg3.json()
            p3_id = p3["id"]
            created_patient_ids.append(p3_id)

            c3 = client.post(f"{BASE_API}/patients/{p3_id}/consent", json={"selected_language": "en", "consent_status": "granted"})
            assert c3.status_code == 200

            s3_res = client.post(f"{BASE_API}/interview/start?patient_id={p3_id}")
            s3 = s3_res.json()
            s3_id = s3["session_id"]
            created_session_ids.append(s3_id)

            ans_msk = client.post(f"{BASE_API}/interview/{s3_id}/answer", json={
                "question_id": "chief_complaint",
                "question_text": s3["current_question"]["text_en"],
                "section": "chief_complaint",
                "stage_number": 1,
                "patient_answer": "Severe right knee swelling and locking when bending",
                "skipped": False,
            })
            data_msk = ans_msk.json()
            next_q_msk = data_msk["current_question"]
            print(f"  ✓ Adaptive Follow-up (MSK): [{next_q_msk['question_id']}] {next_q_msk['text_en']}")
            assert next_q_msk["question_id"] in ["hpi_location", "hpi_weight_bearing", "hpi_associated"]

            # Complete interview
            comp_res = client.post(f"{BASE_API}/interview/{s3_id}/complete")
            assert comp_res.status_code == 200
            comp_data = comp_res.json()
            assert comp_data["status"] == "completed"
            print("  ✓ Interview marked complete.")

            # =================================================================
            # SCENARIO 4: Direct MongoDB Clinical History Inspection
            # =================================================================
            print("\n[Scenario 4] Inspecting MongoDB Collection Data...")
            patient_doc = db.patients.find_one({"_id": pymongo.collection.ObjectId(p1_id)})
            assert patient_doc is not None
            assert "clinical_history" in patient_doc
            assert "chief_complaint" in patient_doc["clinical_history"]
            assert patient_doc["clinical_history"]["chief_complaint"]["answer"] == "Heavy squeezing chest pain spreading towards left arm"
            print("  ✓ MongoDB dynamic persistence verified in patient clinical_history.")

            session_doc = db.interview_sessions.find_one({"session_id": s1_id})
            assert session_doc is not None
            assert len(session_doc["answers"]) == 2
            assert session_doc["current_question"]["question_id"] == next_q2["question_id"]
            print("  ✓ MongoDB interview_sessions active state verified.")

            # =================================================================
            # SCENARIO 5: Next.js Frontend Routes Verification
            # =================================================================
            print("\n[Scenario 5] Checking Next.js Kiosk UI Routes...")
            r_home = client.get(f"{FRONTEND_URL}/")
            assert r_home.status_code == 200
            print("  - Kiosk Home Screen (/) -> 200 OK")

            r_reg = client.get(f"{FRONTEND_URL}/register")
            assert r_reg.status_code == 200
            print("  - Patient Register (/register) -> 200 OK")

            r_queue = client.get(f"{FRONTEND_URL}/queue")
            assert r_queue.status_code == 200
            print("  - Live OPD Queue (/queue) -> 200 OK")

            r_interview = client.get(f"{FRONTEND_URL}/interview?patientId={p1_id}")
            assert r_interview.status_code == 200
            print(f"  - Adaptive Interview (/interview?patientId={p1_id}) -> 200 OK")

    finally:
        # Clean up all verification test patients and sessions from development database
        if created_patient_ids:
            db.patients.delete_many({"_id": {"$in": [pymongo.collection.ObjectId(pid) for pid in created_patient_ids]}})
        if created_session_ids:
            db.interview_sessions.delete_many({"session_id": {"$in": created_session_ids}})
        print("\n✓ Verification test patients and sessions cleaned up from dev database.")

    print("\n==================================================")
    print("   PHASE 4 VERIFICATION 100% SUCCESSFUL!         ")
    print("==================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Phase 4 Verification Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
