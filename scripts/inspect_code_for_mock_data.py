import os
import sys
import pymongo

# Ensure UTF-8 output on Windows console
sys.stdout.reconfigure(encoding='utf-8')

print("=" * 60)
print("  MediKiosk Source Code & Database Mock-Data Audit")
print("=" * 60)

# 1. Audit Application Source Code
source_dirs = ["backend/app", "frontend/app"]
suspicious_patterns = [
    "demo", "mock", "dummy", "fake", "seed",
    "ravi", "rahul", "sample_patient", "mock_patient", "test_patient"
]

found_issues = []

print("\n[Audit 1] Scanning backend/app and frontend/app source files...")
for s_dir in source_dirs:
    for root, _, files in os.walk(s_dir):
        for f in files:
            if f.endswith((".py", ".ts", ".tsx", ".js")):
                filepath = os.path.join(root, f)
                with open(filepath, "r", encoding="utf-8") as file:
                    for line_num, line in enumerate(file, 1):
                        lower_line = line.lower()
                        for pat in suspicious_patterns:
                            if pat in lower_line:
                                found_issues.append((filepath, line_num, line.strip()))

if found_issues:
    print(f"⚠️ Found {len(found_issues)} suspicious keyword match(es):")
    for fp, ln, txt in found_issues:
        print(f"  {fp}:{ln} -> {txt}")
else:
    print("✓ ZERO mock, demo, sample, dummy, or predefined patient data found in application source code.")

# 2. Audit Database Records
print("\n[Audit 2] Inspecting live MongoDB database 'medikiosk'...")
try:
    client = pymongo.MongoClient("mongodb://127.0.0.1:27017", serverSelectionTimeoutMS=2000)
    db = client["medikiosk"]
    patients_col = db["patients"]
    count = patients_col.count_documents({})
    print(f"Total patient documents in MongoDB collection 'patients': {count}")
    
    docs = list(patients_col.find({}, {
        "token_number": 1,
        "full_name": 1,
        "age": 1,
        "gender": 1,
        "phone_number": 1,
        "created_at": 1,
        "registration_status": 1,
        "consent_status": 1,
        "selected_language": 1
    }))

    print("\nCurrent records in MongoDB:")
    for idx, d in enumerate(docs, 1):
        print(f"  {idx}. Token: {d.get('token_number')} | Name: {d.get('full_name')} | Age/Gender: {d.get('age')}/{d.get('gender')} | Status: {d.get('registration_status')} | Consent: {d.get('consent_status')} ({d.get('selected_language')}) | Created: {d.get('created_at')}")

except Exception as e:
    print(f"Could not connect to MongoDB: {e}")

print("\n" + "=" * 60)
