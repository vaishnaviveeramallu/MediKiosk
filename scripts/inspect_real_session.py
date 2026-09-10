import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def inspect():
    client = AsyncIOMotorClient("mongodb://127.0.0.1:27017")
    db = client["medikiosk"]
    patient = await db.patients.find_one({"token_number": "MK-20260910-0040"})
    if not patient:
        print("Patient MK-20260910-0040 not found.")
        return
    print(f"Patient: {patient.get('full_name')} | Token: {patient.get('token_number')} | Status: {patient.get('registration_status')}")
    print("\nClinical History in MongoDB (from user's real interactive session):")
    hist = patient.get("clinical_history", {})
    for k, v in hist.items():
        print(f"  [{k}]")
        print(f"    Question: {v.get('question')}")
        print(f"    Answer:   {v.get('answer')}")
        print(f"    Order:    {v.get('question_order')} | Timestamp: {v.get('timestamp')}")

    session = await db.interview_sessions.find_one({"patient_id": str(patient["_id"])})
    if session:
        print(f"\nInterview Session ID: {session.get('session_id')}")
        print(f"Session Status: {session.get('status')}")
        print(f"Answers Count: {len(session.get('answers', []))}")
        for a in session.get("answers", []):
            print(f"  - Order {a.get('question_order')}: [{a.get('question_id')}] '{a.get('patient_answer')}' (Skipped: {a.get('skipped')})")

if __name__ == '__main__':
    asyncio.run(inspect())
