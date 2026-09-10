import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId
from app.main import app
from app.database import db_manager, get_patients_collection



@pytest.mark.anyio
async def test_supported_languages_endpoint():
    """Verify supported languages endpoint returns valid language options with explicit capability flags."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/languages")
        assert res.status_code == 200
        languages = res.json()
        assert len(languages) >= 2
        codes = [lang["code"] for lang in languages]
        assert "en" in codes
        assert "hi" in codes

        # Verify language capability flags
        for lang in languages:
            assert lang["ui_supported"] is True
            assert isinstance(lang["voice_supported"], bool)


@pytest.mark.anyio
async def test_patient_consent_granted_workflow():
    """Verify granting consent stores language, session, and consent timestamp in MongoDB."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Register patient
        reg_payload = {
            "full_name": "Vikram Rao",
            "age": 50,
            "gender": "Male",
            "phone_number": "9811223344",
            "address_city": "Bengaluru",
            "address_state": "Karnataka",
            "initial_complaint": "Difficulty walking due to knee swelling",
        }
        reg_res = await client.post("/api/patients/register", json=reg_payload)
        assert reg_res.status_code == 201
        patient = reg_res.json()
        patient_id = patient["id"]

        # Step 2: Record Consent Granted in Hindi
        consent_payload = {
            "selected_language": "hi",
            "consent_status": "granted",
        }
        consent_res = await client.post(f"/api/patients/{patient_id}/consent", json=consent_payload)
        assert consent_res.status_code == 200
        updated = consent_res.json()

        assert updated["selected_language"] == "hi"
        assert updated["consent_status"] == "granted"
        assert updated["consent_given"] is True
        assert updated["consent_timestamp"] is not None
        assert updated["session_id"] is not None
        assert updated["registration_status"] == "consent_granted"

        # Step 3: Check Session Endpoint
        session_res = await client.get(f"/api/patients/{patient_id}/session")
        assert session_res.status_code == 200
        session_data = session_res.json()
        assert session_data["can_start_interview"] is True
        assert session_data["selected_language"] == "hi"
        assert session_data["consent_status"] == "granted"

        # Step 4: Inspect MongoDB document directly
        col = get_patients_collection()
        doc = await col.find_one({"_id": ObjectId(patient_id)})
        assert doc is not None
        assert doc["consent_given"] is True
        assert doc["selected_language"] == "hi"
        assert len(doc["consent_history"]) >= 1
        assert doc["consent_history"][-1]["consent_status"] == "granted"


@pytest.mark.anyio
async def test_patient_consent_declined_workflow():
    """Verify declining consent blocks interview, records status, and preserves demographic data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Register patient
        reg_payload = {
            "full_name": "Kavita Nair",
            "age": 38,
            "gender": "Female",
            "phone_number": "9822334455",
            "address_city": "Kochi",
            "address_state": "Kerala",
            "initial_complaint": "Occasional dizziness",
        }
        reg_res = await client.post("/api/patients/register", json=reg_payload)
        assert reg_res.status_code == 201
        patient = reg_res.json()
        patient_id = patient["id"]

        # Step 2: Record Consent Declined in English
        consent_payload = {
            "selected_language": "en",
            "consent_status": "declined",
        }
        consent_res = await client.post(f"/api/patients/{patient_id}/consent", json=consent_payload)
        assert consent_res.status_code == 200
        updated = consent_res.json()

        assert updated["selected_language"] == "en"
        assert updated["consent_status"] == "declined"
        assert updated["consent_given"] is False
        assert updated["registration_status"] == "consent_declined"

        # Step 3: Check Session Endpoint - interview CANNOT start
        session_res = await client.get(f"/api/patients/{patient_id}/session")
        assert session_res.status_code == 200
        session_data = session_res.json()
        assert session_data["can_start_interview"] is False
        assert session_data["consent_status"] == "declined"

        # Step 4: Verify demographic registration data is intact
        assert updated["full_name"] == "Kavita Nair"
        assert updated["age"] == 38
        assert updated["phone_number"] == "9822334455"


@pytest.mark.anyio
async def test_consent_validation_rules():
    """Verify validation errors for unsupported language, invalid status, and missing patient."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register a valid patient first
        reg_res = await client.post(
            "/api/patients/register",
            json={
                "full_name": "Validation Test",
                "age": 25,
                "gender": "Other",
                "phone_number": "9833445566",
            },
        )
        patient_id = reg_res.json()["id"]

        # 1. Unsupported language (e.g. French 'fr')
        res1 = await client.post(
            f"/api/patients/{patient_id}/consent",
            json={"selected_language": "fr", "consent_status": "granted"},
        )
        assert res1.status_code == 422

        # 2. Invalid consent_status
        res2 = await client.post(
            f"/api/patients/{patient_id}/consent",
            json={"selected_language": "en", "consent_status": "undecided"},
        )
        assert res2.status_code == 422

        # 3. Nonexistent patient ID
        res3 = await client.post(
            "/api/patients/000000000000000000000000/consent",
            json={"selected_language": "en", "consent_status": "granted"},
        )
        assert res3.status_code == 404
