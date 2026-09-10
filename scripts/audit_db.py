import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

async def inspect():
    client = AsyncIOMotorClient('mongodb://127.0.0.1:27017')
    db = client['medikiosk']
    patients = await db.patients.find({}).to_list(200)
    print(f"Total patient records in medikiosk.patients: {len(patients)}")
    for idx, p in enumerate(patients, 1):
        print(f"[{idx}] ID: {p.get('_id')} | Token: {p.get('token_number')} | Name: {p.get('full_name')} | Phone: {p.get('phone_number')} | Status: {p.get('registration_status')} | Consent: {p.get('consent_given')} | Created: {p.get('created_at')}")

    sessions = await db.interview_sessions.find({}).to_list(100)
    print(f"\nTotal interview sessions in medikiosk.interview_sessions: {len(sessions)}")
    for s in sessions:
        print(f"Session {s.get('_id')} | Patient: {s.get('patient_id')} | Status: {s.get('status')} | Answers: {len(s.get('answers', {}))}")

if __name__ == '__main__':
    asyncio.run(inspect())
