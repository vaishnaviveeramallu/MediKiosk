import pytest
from httpx import AsyncClient, ASGITransport
import re
from app.main import app
from app.database import db_manager



@pytest.mark.anyio
async def test_health_check():
    """Verify backend health endpoint reports healthy with database connected."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"


@pytest.mark.anyio
async def test_patient_registration_lifecycle():
    """Test full dynamic patient registration, verification, and retrieval without mock data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step 1: Register a new patient
        new_patient_payload = {
            "full_name": "Suresh Kumar",
            "age": 46,
            "gender": "Male",
            "phone_number": "9876501234",
            "emergency_contact_name": "Anita Kumar",
            "emergency_contact_phone": "9876501235",
            "address_city": "Visakhapatnam",
            "address_state": "Andhra Pradesh",
            "government_id_type": "Aadhaar",
            "government_id_number": "XXXX-XXXX-1234",
            "initial_complaint": "Persistent cough with mild fever for 4 days",
        }

        create_res = await client.post("/api/patients/register", json=new_patient_payload)
        assert create_res.status_code == 201, f"Registration failed: {create_res.text}"
        patient_data = create_res.json()

        assert "id" in patient_data
        assert "token_number" in patient_data
        assert re.match(r"^MK-\d{8}-\d{4}$", patient_data["token_number"])
        assert patient_data["full_name"] == "Suresh Kumar"
        assert patient_data["age"] == 46
        assert patient_data["gender"] == "Male"
        assert patient_data["phone_number"] == "9876501234"
        assert patient_data["registration_status"] == "registered"

        patient_id = patient_data["id"]
        token_number = patient_data["token_number"]

        # Step 2: Fetch by MongoDB ID
        get_res = await client.get(f"/api/patients/{patient_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == patient_id
        assert get_res.json()["token_number"] == token_number

        # Step 3: Fetch by OPD Token Number
        get_by_token = await client.get(f"/api/patients/{token_number}")
        assert get_by_token.status_code == 200
        assert get_by_token.json()["id"] == patient_id

        # Step 4: Verify in patients list
        list_res = await client.get("/api/patients")
        assert list_res.status_code == 200
        patients_list = list_res.json()
        assert len(patients_list) >= 1
        found = any(p["id"] == patient_id for p in patients_list)
        assert found, f"Newly registered patient {patient_id} not found in listing"


@pytest.mark.anyio
async def test_patient_validation_rules():
    """Verify input validation rules strictly reject malformed data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid phone number (too short)
        res1 = await client.post(
            "/api/patients/register",
            json={
                "full_name": "Test User",
                "age": 30,
                "gender": "Female",
                "phone_number": "1234",
            },
        )
        assert res1.status_code == 422

        # Invalid age (> 125)
        res2 = await client.post(
            "/api/patients/register",
            json={
                "full_name": "Test User",
                "age": 140,
                "gender": "Female",
                "phone_number": "9876543210",
            },
        )
        assert res2.status_code == 422

        # Invalid gender
        res3 = await client.post(
            "/api/patients/register",
            json={
                "full_name": "Test User",
                "age": 30,
                "gender": "Alien",
                "phone_number": "9876543210",
            },
        )
        assert res3.status_code == 422
