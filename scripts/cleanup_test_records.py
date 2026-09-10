import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

LEGITIMATE_PATIENT_IDS = [
    ObjectId("6aa2c688343dcebbcace961f"),  # ppt (MK-20260910-0002) - registered by user via Kiosk UI
    ObjectId("6aa2cb13cefea34cc1227ce8"),  # anu (MK-20260910-0013) - registered interactively via Kiosk UI
]

async def execute_cleanup():
    client = AsyncIOMotorClient('mongodb://127.0.0.1:27017')
    db = client['medikiosk']
    
    # 1. Remove non-legitimate test patients
    result = await db.patients.delete_many({"_id": {"$nin": LEGITIMATE_PATIENT_IDS}})
    print(f"Removed {result.deleted_count} test patient records from 'medikiosk.patients'.")
    
    # 2. Remove any interview sessions associated with deleted patients
    keep_str_ids = [str(id_) for id_ in LEGITIMATE_PATIENT_IDS]
    sess_result = await db.interview_sessions.delete_many({"patient_id": {"$nin": keep_str_ids}})
    print(f"Removed {sess_result.deleted_count} orphaned test interview sessions from 'medikiosk.interview_sessions'.")
    
    # 3. Verify remaining patients
    remaining = await db.patients.find({}).to_list(100)
    print(f"\nRemaining legitimate patients in 'medikiosk.patients': {len(remaining)}")
    for p in remaining:
        print(f"  - {p.get('token_number')} | {p.get('full_name')} | Age: {p.get('age')} | Status: {p.get('registration_status')}")

if __name__ == '__main__':
    asyncio.run(execute_cleanup())
