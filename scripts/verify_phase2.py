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
    print("   MediKiosk Phase 2 - End-to-End Verification    ")
    print("==================================================")

    # 1. Supported Languages
    print("\n[Step 1] Checking Language Registry API...")
    with httpx.Client(timeout=10.0) as client:
        res = client.get(f"{BASE_API}/languages")
        assert res.status_code == 200, f"Failed: {res.text}"
        langs = res.json()
        print(f"Supported Languages returned: {[l['name'] for l in langs]}")
        for l in langs:
            assert l["ui_supported"] is True
            assert l["voice_supported"] is False, "Voice must not be claimed as supported before Phase 6"
        print("✓ Language Registry verified: UI supported for English & Hindi, no false voice claims.")

    # 2. Existing Records Intact
    print("\n[Step 2] Verifying Existing Database Records Preserved...")
    mongo_client = pymongo.MongoClient(MONGO_URI)
    db = mongo_client["medikiosk"]
    existing_count = db.patients.count_documents({})
    print(f"Total patient records in MongoDB: {existing_count}")
    assert existing_count >= 1, "Existing patient records from previous sessions must not be deleted"
    print("✓ Existing records preserved rule verified.")

    # 3. Test Flow A: Dynamic Registration -> Language Selection -> Consent GRANTED
    print("\n[Step 3] Testing Consent GRANTED Flow (Language: Hindi)...")
    patient_a_payload = {
        "full_name": "Devendra Prasad",
        "age": 62,
        "gender": "Male",
        "phone_number": "9871122334",
        "address_city": "Patna",
        "address_state": "Bihar",
        "initial_complaint": "Severe joint pain and knee stiffness for 3 months",
    }

    with httpx.Client(timeout=10.0) as client:
        # Register
        reg_res = client.post(f"{BASE_API}/patients/register", json=patient_a_payload)
        assert reg_res.status_code == 201
        patient_a = reg_res.json()
        patient_a_id = patient_a["id"]
        print(f"Registered Patient A: {patient_a['full_name']} (Token: {patient_a['token_number']})")

        # Record Consent Granted
        consent_a_payload = {
            "selected_language": "hi",
            "consent_status": "granted",
        }
        res_consent_a = client.post(f"{BASE_API}/patients/{patient_a_id}/consent", json=consent_a_payload)
        assert res_consent_a.status_code == 200
        updated_a = res_consent_a.json()
        print(f"Consent Recorded for Patient A:")
        print(f"  - Selected Language: {updated_a['selected_language']}")
        print(f"  - Consent Status:    {updated_a['consent_status']}")
        print(f"  - Consent Given:     {updated_a['consent_given']}")
        print(f"  - Registration Status:{updated_a['registration_status']}")
        print(f"  - Session ID:        {updated_a['session_id']}")
        assert updated_a["consent_given"] is True
        assert updated_a["selected_language"] == "hi"
        assert updated_a["registration_status"] == "consent_granted"

        # Check Session State
        session_a_res = client.get(f"{BASE_API}/patients/{patient_a_id}/session")
        assert session_a_res.status_code == 200
        session_a = session_a_res.json()
        assert session_a["can_start_interview"] is True
        print("✓ Consent GRANTED verified: can_start_interview == True.")

    # 4. Test Flow B: Dynamic Registration -> Language Selection -> Consent DECLINED
    print("\n[Step 4] Testing Consent DECLINED Flow (Language: English)...")
    patient_b_payload = {
        "full_name": "Sunita Verma",
        "age": 45,
        "gender": "Female",
        "phone_number": "9872233445",
        "address_city": "Lucknow",
        "address_state": "Uttar Pradesh",
        "initial_complaint": "Mild intermittent fever and body aches",
    }

    with httpx.Client(timeout=10.0) as client:
        # Register
        reg_res_b = client.post(f"{BASE_API}/patients/register", json=patient_b_payload)
        assert reg_res_b.status_code == 201
        patient_b = reg_res_b.json()
        patient_b_id = patient_b["id"]
        print(f"Registered Patient B: {patient_b['full_name']} (Token: {patient_b['token_number']})")

        # Record Consent Declined
        consent_b_payload = {
            "selected_language": "en",
            "consent_status": "declined",
        }
        res_consent_b = client.post(f"{BASE_API}/patients/{patient_b_id}/consent", json=consent_b_payload)
        assert res_consent_b.status_code == 200
        updated_b = res_consent_b.json()
        print(f"Consent Recorded for Patient B:")
        print(f"  - Selected Language: {updated_b['selected_language']}")
        print(f"  - Consent Status:    {updated_b['consent_status']}")
        print(f"  - Consent Given:     {updated_b['consent_given']}")
        print(f"  - Registration Status:{updated_b['registration_status']}")
        assert updated_b["consent_given"] is False
        assert updated_b["selected_language"] == "en"
        assert updated_b["registration_status"] == "consent_declined"

        # Check Session State: interview CANNOT start
        session_b_res = client.get(f"{BASE_API}/patients/{patient_b_id}/session")
        assert session_b_res.status_code == 200
        session_b = session_b_res.json()
        assert session_b["can_start_interview"] is False
        print("✓ Consent DECLINED verified: can_start_interview == False, interview blocked.")

        # Verify demographic details intact
        assert updated_b["full_name"] == "Sunita Verma"
        assert updated_b["age"] == 45
        assert updated_b["phone_number"] == "9872233445"
        print("✓ Registration data preserved intact after decline.")

    # 5. Direct MongoDB Inspection
    print("\n[Step 5] Direct MongoDB Collection Inspection...")
    doc_a = db.patients.find_one({"_id": pymongo.collection.ObjectId(patient_a_id)})
    assert doc_a is not None
    assert doc_a["consent_given"] is True
    assert doc_a["selected_language"] == "hi"
    assert len(doc_a.get("consent_history", [])) >= 1
    print(f"MongoDB Patient A Consent History: {doc_a['consent_history']}")

    doc_b = db.patients.find_one({"_id": pymongo.collection.ObjectId(patient_b_id)})
    assert doc_b is not None
    assert doc_b["consent_given"] is False
    assert doc_b["selected_language"] == "en"
    assert len(doc_b.get("consent_history", [])) >= 1
    print(f"MongoDB Patient B Consent History: {doc_b['consent_history']}")
    print("✓ MongoDB dynamic persistence and audit logs verified.")

    # 6. Queue API Check
    print("\n[Step 6] Checking OPD Queue API for Consent Statuses...")
    with httpx.Client(timeout=10.0) as client:
        res_queue = client.get(f"{BASE_API}/patients")
        assert res_queue.status_code == 200
        queue_patients = res_queue.json()
        matching_a = next(p for p in queue_patients if p["id"] == patient_a_id)
        matching_b = next(p for p in queue_patients if p["id"] == patient_b_id)
        assert matching_a["consent_status"] == "granted"
        assert matching_b["consent_status"] == "declined"
        print(f"Patient A in Queue: Status = {matching_a['consent_status']} ({matching_a['selected_language']})")
        print(f"Patient B in Queue: Status = {matching_b['consent_status']} ({matching_b['selected_language']})")
        print("✓ OPD Queue reflects live consent states.")

    # 7. Frontend Route Check
    print("\n[Step 7] Checking Next.js Kiosk Frontend Routes...")
    with httpx.Client(timeout=10.0) as client:
        r_consent = client.get(f"{FRONTEND_URL}/consent")
        assert r_consent.status_code == 200
        print("  - Kiosk Consent Screen (/consent) -> 200 OK")

        r_consent_with_id = client.get(f"{FRONTEND_URL}/consent?patientId={patient_a_id}")
        assert r_consent_with_id.status_code == 200
        print("  - Kiosk Consent Screen with Patient ID -> 200 OK")

        r_queue = client.get(f"{FRONTEND_URL}/queue")
        assert r_queue.status_code == 200
        print("  - Live OPD Queue Screen (/queue) -> 200 OK")

        r_reg = client.get(f"{FRONTEND_URL}/register")
        assert r_reg.status_code == 200
        print("  - Patient Register Screen (/register) -> 200 OK")
    print("✓ All Next.js Routes Loaded Successfully.")

    # 8. Clean up verification test patients
    db.patients.delete_one({"_id": pymongo.collection.ObjectId(patient_a_id)})
    db.patients.delete_one({"_id": pymongo.collection.ObjectId(patient_b_id)})
    print("✓ Verification test patients cleaned up from dev database.")

    print("\n==================================================")
    print("   PHASE 2 VERIFICATION 100% SUCCESSFUL!         ")
    print("==================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Verification Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
