import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.consent_service import consent_service
from app.database import db_manager, get_patients_collection, get_consent_records_collection, get_audit_logs_collection
from app.models.patient import PatientCreate


@pytest.fixture(autouse=True)
async def clean_test_collections():
    settings_db = db_manager.db
    if settings_db is not None:
        await settings_db.patients.drop()
        await settings_db.consent_records.drop()
        await settings_db.audit_logs.drop()
        await settings_db.interview_sessions.drop()
    yield


@pytest.mark.anyio
async def test_consent_record_and_lifecycle():
    """Verify that granting and revoking consent updates MongoDB and creates immutable records."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register a patient
        reg_res = await client.post("/api/patients/register", json={
            "full_name": "Consent Test Patient",
            "age": 35,
            "gender": "Female",
            "phone_number": "9876543210",
            "initial_complaint": "Persistent headache",
        })
        assert reg_res.status_code == 201
        patient_data = reg_res.json()
        pid = patient_data["id"]

        # 2. Record granted consent
        consent_res = await client.post(f"/api/patients/{pid}/consent", json={
            "selected_language": "en",
            "consent_status": "granted",
        })
        assert consent_res.status_code == 200
        assert consent_res.json()["consent_status"] == "granted"

        # Check preflight status
        check_res = await client.get(f"/api/patients/{pid}/consent/check")
        assert check_res.status_code == 200
        assert check_res.json()["has_valid_consent"] is True
        assert check_res.json()["can_proceed_clinical"] is True

        # 3. Revoke consent with reason
        revoke_res = await client.post(f"/api/patients/{pid}/consent/revoke", json={
            "reason": "Patient requested manual in-person consultation without AI assistance",
        })
        assert revoke_res.status_code == 200
        assert revoke_res.json()["status"] == "revoked"
        assert revoke_res.json()["can_proceed_clinical"] is False

        # 4. Check preflight status after revocation
        check_after = await client.get(f"/api/patients/{pid}/consent/check")
        assert check_after.status_code == 200
        assert check_after.json()["has_valid_consent"] is False
        assert check_after.json()["current_status"] == "revoked"
        assert check_after.json()["can_proceed_clinical"] is False

        # 5. Check consent history
        history_res = await client.get(f"/api/patients/{pid}/consent/history")
        assert history_res.status_code == 200
        history_data = history_res.json()
        assert history_data["total_events"] >= 2
        assert history_data["current_status"] == "revoked"

        # 6. Verify clinical intake gate blocks interview start
        interview_res = await client.post(f"/api/interview/start?patient_id={pid}")
        assert interview_res.status_code == 403
        assert "consent" in interview_res.json()["detail"].lower()
