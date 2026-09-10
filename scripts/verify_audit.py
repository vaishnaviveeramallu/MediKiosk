import httpx
import pymongo
import sys
import json
from pathlib import Path

# UTF-8 on Windows
sys.stdout.reconfigure(encoding='utf-8')

BASE_API = "http://127.0.0.1:8000/api"
MONGO_URI = "mongodb://127.0.0.1:27017"

def test_audit():
    print("================================================================")
    print("           MediKiosk Data-Integrity Audit Verification          ")
    print("================================================================")

    # Connect to MongoDB
    client = pymongo.MongoClient(MONGO_URI)
    db = client["medikiosk"]

    # 1. Check current OPD queue - dynamic records only
    print("\n[Audit Check 1] Verifying Current OPD Queue (Dynamically created only)...")
    res_queue = httpx.get(f"{BASE_API}/patients", timeout=10.0)
    assert res_queue.status_code == 200
    queue = res_queue.json()
    print(f"Current OPD Queue count: {len(queue)}")
    for p in queue:
        print(f"  Patient in Queue: {p['token_number']} | Name: {p['full_name']} | Status: {p['registration_status']}")
        # Assert no test fixture artifacts remain in the queue
        assert "validation test" not in p["full_name"].lower(), f"Unexpected fixture record: {p['full_name']}"
        assert "consent guard" not in p["full_name"].lower(), f"Unexpected fixture record: {p['full_name']}"
        assert "isolation patient" not in p["full_name"].lower(), f"Unexpected fixture record: {p['full_name']}"
    print("✓ OPD queue contains only legitimate, dynamically created records.")

    # 2. Test registration of a new real patient and dynamic storage in MongoDB
    print("\n[Audit Check 2] Testing Dynamic Registration Flow & MongoDB Persistence...")
    test_registration = {
        "full_name": "Meera Swaminathan",
        "age": 39,
        "gender": "Female",
        "phone_number": "9844001122",
        "emergency_contact_name": "K. Swaminathan",
        "emergency_contact_phone": "9844001123",
        "address_city": "Chennai",
        "address_state": "Tamil Nadu",
        "initial_complaint": "Persistent joint pain and morning stiffness",
    }
    reg_res = httpx.post(f"{BASE_API}/patients/register", json=test_registration, timeout=10.0)
    assert reg_res.status_code == 201, f"Failed registration: {reg_res.text}"
    new_patient = reg_res.json()
    new_id = new_patient["id"]
    new_token = new_patient["token_number"]
    print(f"  ✓ Successfully registered: {new_patient['full_name']} with Token: {new_token}")

    # Verify directly in MongoDB
    mongo_doc = db.patients.find_one({"token_number": new_token})
    assert mongo_doc is not None, "Patient document was not persisted to MongoDB!"
    assert mongo_doc["full_name"] == "Meera Swaminathan"
    assert mongo_doc["phone_number"] == "9844001122"
    assert mongo_doc["registration_status"] == "registered"
    print("  ✓ Document verified directly inside MongoDB 'medikiosk.patients' collection.")

    # 3. Check that OPD queue now immediately reflects the new patient
    print("\n[Audit Check 3] Verifying Queue Update via API...")
    res_queue_updated = httpx.get(f"{BASE_API}/patients", timeout=10.0)
    assert res_queue_updated.status_code == 200
    updated_queue = res_queue_updated.json()
    assert any(p["token_number"] == new_token for p in updated_queue), "New patient not found in OPD Queue!"
    print(f"  ✓ New patient {new_patient['full_name']} immediately present in OPD Queue (Total: {len(updated_queue)}).")

    # 4. Verify no hard-coded patient JSON or static files
    print("\n[Audit Check 4] Checking for Hard-coded Patient JSON Files...")
    repo_root = Path(__file__).resolve().parent.parent
    json_files = list(repo_root.glob("**/*.json"))
    # Filter out package.json, node_modules, .next, and sbom
    suspect_files = [
        f for f in json_files
        if "node_modules" not in str(f)
        and ".next" not in str(f)
        and f.name not in ["package.json", "package-lock.json", "tsconfig.json", "sbom_from_silk.json"]
    ]
    print(f"  Non-standard JSON files found in repo: {len(suspect_files)}")
    assert len(suspect_files) == 0, f"Found unexpected JSON files: {suspect_files}"
    print("  ✓ Zero patient JSON files exist in the repository.")

    # 5. Verify no test fixtures loaded in production application flow
    print("\n[Audit Check 5] Verifying Production Application Architecture...")
    from app.main import app as fastapi_app
    from app.config import settings
    assert settings.DATABASE_NAME == "medikiosk", "Default production database must be 'medikiosk'"
    routes = [route.path for route in fastapi_app.routes if hasattr(route, "path")]
    print(f"  Active application routes: {len(routes)}")
    # Verify no test/mock routes mounted
    for r in routes:
        assert not r.startswith("/test"), f"Found testing route mounted in application: {r}"
        assert not r.startswith("/mock"), f"Found mock route mounted in application: {r}"
    print("  ✓ Zero mock or test fixture endpoints mounted in application.")

    print("\n================================================================")
    print("         DATA-INTEGRITY AUDIT VERIFIED 100% SUCCESSFUL!         ")
    print("================================================================")

if __name__ == '__main__':
    test_audit()
