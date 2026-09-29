import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.audit_service import audit_service, sanitize_audit_details
from app.models.audit import AuditEventType
from app.database import db_manager, get_patients_collection, get_audit_logs_collection
from app.services.auth_service import auth_service
from app.models.auth import UserCreate


@pytest.fixture(autouse=True)
async def clean_test_collections():
    settings_db = db_manager.db
    if settings_db is not None:
        await settings_db.audit_logs.drop()
        await settings_db.patients.drop()
        await settings_db.users.drop()
    yield


@pytest.mark.anyio
async def test_audit_log_event_persistence():
    """Verify that audit events are securely persisted to the audit_logs collection."""
    entry = await audit_service.log_event(
        action=AuditEventType.PATIENT_REGISTER.value,
        actor_user_id="usr_test_123",
        actor_role="patient",
        patient_id="pat_test_999",
        resource_type="patient",
        resource_id="pat_test_999",
        status="success",
        details={"registration_type": "kiosk_self_service"},
    )

    assert entry.event_id.startswith("aud_")
    assert entry.action == "patient_register"
    assert entry.status == "success"

    col = get_audit_logs_collection()
    saved = await col.find_one({"event_id": entry.event_id})
    assert saved is not None
    assert saved["actor_user_id"] == "usr_test_123"
    assert saved["patient_id"] == "pat_test_999"
    assert saved["details"]["registration_type"] == "kiosk_self_service"


@pytest.mark.anyio
async def test_audit_credential_sanitization():
    """Verify that passwords, tokens, and secrets are strictly redacted from audit logs."""
    dirty_data = {
        "username": "dr_smith",
        "password": "SuperSecretPassword123!",
        "access_token": "eyJhbGciOiJIUzI1NiIsIn...",
        "api_key": "live_key_99999",
        "client_secret": "shhh_top_secret",
        "metadata": {
            "nested_token": "secret_nested_token",
            "safe_counter": 42,
        },
    }

    sanitized = sanitize_audit_details(dirty_data)
    assert sanitized["username"] == "dr_smith"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["access_token"] == "[REDACTED]"
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["client_secret"] == "[REDACTED]"
    assert sanitized["metadata"]["nested_token"] == "[REDACTED]"
    assert sanitized["metadata"]["safe_counter"] == 42

    # Verify through log_event
    entry = await audit_service.log_event(
        action="auth_login_test",
        actor_user_id="usr_san_1",
        status="success",
        details=dirty_data,
    )
    col = get_audit_logs_collection()
    saved = await col.find_one({"event_id": entry.event_id})
    assert saved["details"]["password"] == "[REDACTED]"
    assert saved["details"]["access_token"] == "[REDACTED]"


@pytest.mark.anyio
async def test_audit_logs_filtering_and_pagination():
    """Verify that audit logs can be filtered by action, patient_id, and paginated."""
    # Create 5 distinct events
    for i in range(5):
        await audit_service.log_event(
            action=AuditEventType.DOCUMENT_VIEW.value if i % 2 == 0 else AuditEventType.DOCUMENT_UPLOAD.value,
            actor_user_id=f"usr_{i}",
            patient_id="pat_filter_test" if i < 3 else "pat_other",
            status="success",
        )

    # Filter by patient
    pat_logs = await audit_service.get_audit_logs(patient_id="pat_filter_test")
    assert pat_logs.total_count == 3
    assert len(pat_logs.logs) == 3

    # Filter by action
    view_logs = await audit_service.get_audit_logs(action=AuditEventType.DOCUMENT_VIEW.value)
    assert view_logs.total_count == 3

    # Pagination
    paged = await audit_service.get_audit_logs(limit=2, skip=0)
    assert len(paged.logs) == 2
    assert paged.total_count == 5


@pytest.mark.anyio
async def test_audit_api_rbac_protection():
    """Verify that only doctors and triage staff can view the system audit trail."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Unauthenticated request -> 401
        res = await client.get("/api/audit")
        assert res.status_code == 401

        # 2. Patient role user -> 403
        pat_user = await auth_service.create_user(UserCreate(
            username="audit_patient_usr",
            password="Password123!",
            full_name="Patient User",
            role="patient",
        ))
        pat_token = auth_service.create_access_token({"sub": pat_user["user_id"], "role": "patient"})

        res = await client.get("/api/audit", headers={"Authorization": f"Bearer {pat_token}"})
        assert res.status_code == 403

        # 3. Doctor role user -> 200
        doc_user = await auth_service.create_user(UserCreate(
            username="audit_doctor_usr",
            password="Password123!",
            full_name="Dr. Auditor",
            role="doctor",
        ))
        doc_token = auth_service.create_access_token({"sub": doc_user["user_id"], "role": "doctor"})

        res = await client.get("/api/audit", headers={"Authorization": f"Bearer {doc_token}"})
        assert res.status_code == 200
        data = res.json()
        assert "total_count" in data
        assert "logs" in data
