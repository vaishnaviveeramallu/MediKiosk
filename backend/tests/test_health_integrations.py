import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import db_manager, get_patients_collection
from app.services.abdm_service import abdm_service
from app.services.fhir_service import fhir_service
from app.services.his_emr_service import his_emr_service
from app.services.auth_service import auth_service
from app.models.auth import UserCreate


@pytest.fixture(autouse=True)
async def clean_test_collections():
    settings_db = db_manager.db
    if settings_db is not None:
        await settings_db.patients.drop()
        await settings_db.medical_documents.drop()
        await settings_db.interview_sessions.drop()
        await settings_db.audit_logs.drop()
        await settings_db.users.drop()
    yield


@pytest.mark.anyio
async def test_integrations_status_endpoint():
    """Verify GET /api/integrations/status truthfully reports component statuses."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/integrations/status")
        assert res.status_code == 200
        data = res.json()
        assert "components" in data
        comps = data["components"]

        # 1. Database is connected
        assert comps["database"]["status"] == "AVAILABLE"

        # 2. Auth/RBAC is active
        assert comps["auth_rbac"]["status"] == "AVAILABLE"

        # 3. ABDM / ABHA is truthfully NOT_CONFIGURED
        assert comps["abdm_abha"]["status"] == "NOT_CONFIGURED"
        assert comps["abdm_abha"]["configured"] is False

        # 4. FHIR R4 is LOCAL_ONLY (ready for export, remote server not set)
        assert comps["fhir_r4"]["status"] == "LOCAL_ONLY"
        assert comps["fhir_r4"]["details"]["export_available"] is True

        # 5. HIS/EMR is NOT_CONFIGURED
        assert comps["his_emr"]["status"] == "NOT_CONFIGURED"


@pytest.mark.anyio
async def test_abdm_validation_and_linking():
    """Verify ABHA format validation, masking, and MongoDB persistence."""
    # Test valid/invalid formats
    clean = abdm_service.validate_abha_number("12-3456-7890-1234")
    assert clean == "12345678901234"

    with pytest.raises(ValueError):
        abdm_service.validate_abha_number("12345")  # Too short

    with pytest.raises(ValueError):
        abdm_service.validate_abha_number("12-3456-7890-abcd")  # Non-digit

    # Register patient
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create doctor user for linking
        doc_user = await auth_service.create_user(UserCreate(
            username="dr_abha_linker",
            password="Password123!",
            full_name="Dr. Abha Linker",
            role="doctor",
        ))
        doc_token = auth_service.create_access_token({"sub": doc_user["user_id"], "role": "doctor"})

        reg_res = await client.post("/api/patients/register", json={
            "full_name": "Ramesh Patel",
            "age": 42,
            "gender": "Male",
            "phone_number": "9123456780",
            "initial_complaint": "Joint stiffness",
        })
        pid = reg_res.json()["id"]

        # Link ABHA
        link_res = await client.post(
            "/api/integrations/abdm/link",
            headers={"Authorization": f"Bearer {doc_token}"},
            json={
                "patient_id": pid,
                "abha_number": "91-8888-7777-6666",
                "abha_address": "ramesh@abdm",
            },
        )
        assert link_res.status_code == 200
        link_data = link_res.json()
        assert link_data["abha_linked"] is True
        assert link_data["abha_masked"].startswith("91")
        assert link_data["abha_masked"].endswith("6666")

        # Check patient ABHA status
        status_res = await client.get(
            f"/api/integrations/abdm/patient/{pid}",
            headers={"Authorization": f"Bearer {doc_token}"},
        )
        assert status_res.status_code == 200
        assert status_res.json()["abha_linked"] is True
        assert status_res.json()["abha_address"] == "ramesh@abdm"


@pytest.mark.anyio
async def test_fhir_r4_bundle_export():
    """Verify FHIR R4 Bundle generation from authentic patient data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        doc_user = await auth_service.create_user(UserCreate(
            username="dr_fhir_exporter",
            password="Password123!",
            full_name="Dr. FHIR",
            role="doctor",
        ))
        doc_token = auth_service.create_access_token({"sub": doc_user["user_id"], "role": "doctor"})

        reg_res = await client.post("/api/patients/register", json={
            "full_name": "Priya Sharma",
            "age": 29,
            "gender": "Female",
            "phone_number": "9812345678",
            "initial_complaint": "Cough and fever",
        })
        pid = reg_res.json()["id"]

        # Export FHIR Bundle
        bundle_res = await client.get(
            f"/api/integrations/fhir/patient/{pid}",
            headers={"Authorization": f"Bearer {doc_token}"},
        )
        assert bundle_res.status_code == 200
        bundle = bundle_res.json()

        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "collection"
        assert bundle["total"] >= 1

        # Check Patient resource within bundle
        patient_entries = [e for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient"]
        assert len(patient_entries) == 1
        pat_resource = patient_entries[0]["resource"]
        assert pat_resource["name"][0]["text"] == "Priya Sharma"
        assert pat_resource["gender"] == "female"


@pytest.mark.anyio
async def test_his_emr_graceful_handling():
    """Verify that HIS/EMR unconfigured state returns truthful status without error."""
    status = his_emr_service.get_status()
    assert status.status == "NOT_CONFIGURED"
    assert status.configured is False

    dispatch_res = await his_emr_service.dispatch_encounter("test_pat_123")
    assert dispatch_res["dispatched"] is False
    assert dispatch_res["status"] == "NOT_CONFIGURED"
