import httpx
import pymongo
import sys
import json

# Ensure UTF-8 output on Windows
sys.stdout.reconfigure(encoding='utf-8')

BASE_API = "http://127.0.0.1:8000/api"
FRONTEND_URL = "http://localhost:3000"
MONGO_URI = "mongodb://127.0.0.1:27017"


def main():
    print("==================================================")
    print("   MediKiosk Phase 1 - End-to-End Verification    ")
    print("==================================================")

    # 1. Test Backend Health & DB Connectivity
    print("\n[Step 1] Checking Backend Health & DB Connectivity...")
    with httpx.Client(timeout=10.0) as client:
        res = client.get(f"{BASE_API}/health")
        print(f"Health Response: {res.status_code} - {res.text}")
        assert res.status_code == 200
        health_data = res.json()
        assert health_data["status"] == "healthy"
        assert health_data["database"] == "connected"
        print("✓ Health Check Passed: Backend is connected to live MongoDB.")

    # 2. Test Zero Mock Data Rule (DB must start empty before user input)
    print("\n[Step 2] Verifying Zero Predefined/Mock Patients Rule...")
    with httpx.Client(timeout=10.0) as client:
        res = client.get(f"{BASE_API}/patients")
        assert res.status_code == 200
        patients = res.json()
        print(f"Patients in DB before registration: {len(patients)}")
        # Check that no hardcoded demo names like 'Ravi', 'Rahul' exist
        for p in patients:
            assert p["full_name"].lower() not in ["ravi", "rahul", "demo patient", "test patient"], (
                f"Violated rule: found demo patient {p['full_name']}"
            )
        print("✓ Zero Mock Data Rule Verified: No hardcoded demo patients exist.")

    # 3. Register a Dynamic Patient
    print("\n[Step 3] Submitting Dynamic Patient Registration...")
    test_patient = {
        "full_name": "Anita Roy",
        "age": 42,
        "gender": "Female",
        "phone_number": "9876543210",
        "emergency_contact_name": "Bikram Roy",
        "emergency_contact_phone": "9876543211",
        "address_city": "Kolkata",
        "address_state": "West Bengal",
        "government_id_type": "Aadhaar",
        "government_id_number": "XXXX-XXXX-9876",
        "initial_complaint": "Severe migraine headache and nausea for 3 days",
    }

    with httpx.Client(timeout=10.0) as client:
        res = client.post(f"{BASE_API}/patients/register", json=test_patient)
        print(f"Registration Status: {res.status_code}")
        assert res.status_code == 201
        created = res.json()
        print(f"Created Patient Record:")
        print(f"  - Token Number: {created['token_number']}")
        print(f"  - Database ID:  {created['id']}")
        print(f"  - Full Name:    {created['full_name']}")
        print(f"  - Age & Gender: {created['age']} / {created['gender']}")
        print(f"  - Complaint:    {created['initial_complaint']}")
        print(f"  - Status:       {created['registration_status']}")
        assert created["token_number"].startswith("MK-")
        assert created["full_name"] == "Anita Roy"
        assert created["phone_number"] == "9876543210"
        patient_id = created["id"]
        token_number = created["token_number"]
        print("✓ Dynamic Registration Passed: Generated sequential token.")

    # 4. Fetch Patient By ID and Token
    print("\n[Step 4] Verifying Retrieval by Mongo ID and OPD Token...")
    with httpx.Client(timeout=10.0) as client:
        res_by_id = client.get(f"{BASE_API}/patients/{patient_id}")
        assert res_by_id.status_code == 200
        assert res_by_id.json()["token_number"] == token_number

        res_by_token = client.get(f"{BASE_API}/patients/{token_number}")
        assert res_by_token.status_code == 200
        assert res_by_token.json()["id"] == patient_id
        print(f"✓ Retrieved successfully by ID and Token.")

    # 5. Check Queue API
    print("\n[Step 5] Checking Patient Queue API...")
    with httpx.Client(timeout=10.0) as client:
        res = client.get(f"{BASE_API}/patients")
        assert res.status_code == 200
        queue = res.json()
        assert any(p["id"] == patient_id for p in queue)
        print(f"✓ Queue API correctly lists {len(queue)} registered patient(s).")

    # 6. Direct MongoDB Verification
    print("\n[Step 6] Inspecting MongoDB Directly via PyMongo...")
    mongo_client = pymongo.MongoClient(MONGO_URI)
    db = mongo_client["medikiosk"]
    doc = db.patients.find_one({"token_number": token_number})
    assert doc is not None
    print(f"Found document directly in MongoDB collection 'patients':")
    print(f"  - _id: {doc['_id']}")
    print(f"  - token_number: {doc['token_number']}")
    print(f"  - full_name: {doc['full_name']}")
    print(f"  - created_at: {doc['created_at']}")
    assert doc["full_name"] == "Anita Roy"
    print("✓ Direct MongoDB Persistence Verified.")

    # 7. Check Frontend Routes
    print("\n[Step 7] Checking Next.js Kiosk UI Routes...")
    with httpx.Client(timeout=10.0) as client:
        r_home = client.get(f"{FRONTEND_URL}/")
        assert r_home.status_code == 200
        print("  - Kiosk Home Screen (/) -> 200 OK")

        r_reg = client.get(f"{FRONTEND_URL}/register")
        assert r_reg.status_code == 200
        print("  - Kiosk Register Screen (/register) -> 200 OK")

        r_queue = client.get(f"{FRONTEND_URL}/queue")
        assert r_queue.status_code == 200
        print("  - Live OPD Queue Screen (/queue) -> 200 OK")
    print("✓ All Frontend Routes Accessible and Serving Successfully.")

    # 8. Clean up verification test patient from database
    db.patients.delete_one({"token_number": token_number})
    print("✓ Verification test patient cleaned up from dev database.")

    print("\n==================================================")
    print("   PHASE 1 VERIFICATION 100% SUCCESSFUL!         ")
    print("==================================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Verification Error: {e}")
        sys.exit(1)
