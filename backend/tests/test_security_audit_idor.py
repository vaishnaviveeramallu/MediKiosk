import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import db_manager, get_audit_logs_collection
from app.services.auth_service import auth_service
from app.models.auth import UserCreate
from app.models.audit import AuditEventType


@pytest.fixture(autouse=True)
async def clean_test_collections():
    settings_db = db_manager.db
    if settings_db is not None:
        await settings_db.patients.drop()
        await settings_db.users.drop()
        await settings_db.audit_logs.drop()
    yield


@pytest.mark.anyio
async def test_patient_idor_protection_and_audit_event():
    """Verify that cross-patient access returns 403 Forbidden and logs a SECURITY_IDOR_BLOCKED audit event."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Register Patient A
        reg_a = await client.post("/api/patients/register", json={
            "full_name": "Patient Alpha",
            "age": 30,
            "gender": "Male",
            "phone_number": "9000000001",
            "initial_complaint": "Headache",
        })
        pid_a = reg_a.json()["id"]

        # Create user account linked to Patient A
        user_a = await auth_service.create_user(UserCreate(
            username="patient_alpha",
            password="Password123!",
            full_name="Patient Alpha",
            role="patient",
            patient_id=pid_a,
        ))
        token_a = auth_service.create_access_token({
            "sub": user_a["user_id"],
            "role": "patient",
            "patient_id": pid_a,
        })

        # 2. Register Patient B
        reg_b = await client.post("/api/patients/register", json={
            "full_name": "Patient Beta",
            "age": 45,
            "gender": "Female",
            "phone_number": "9000000002",
            "initial_complaint": "Fever",
        })
        pid_b = reg_b.json()["id"]

        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 3. Patient A accesses own profile -> 200 OK
        own_res = await client.get(f"/api/patients/{pid_a}", headers=headers_a)
        assert own_res.status_code == 200

        # 4. Patient A attempts IDOR access to Patient B's profile -> 403 Forbidden
        idor_profile = await client.get(f"/api/patients/{pid_b}", headers=headers_a)
        assert idor_profile.status_code == 403
        assert "idor" in idor_profile.json()["detail"].lower()

        # 5. Patient A attempts IDOR access to Patient B's timeline -> 403 Forbidden
        idor_timeline = await client.get(f"/api/patients/{pid_b}/timeline", headers=headers_a)
        assert idor_timeline.status_code == 403

        # 6. Patient A attempts IDOR access to Patient B's summary -> 403 Forbidden
        idor_summary = await client.get(f"/api/patients/{pid_b}/summary", headers=headers_a)
        assert idor_summary.status_code == 403

        # 7. Patient A attempts IDOR access to Patient B's documents -> 403 Forbidden
        idor_docs = await client.get(f"/api/patients/{pid_b}/documents", headers=headers_a)
        assert idor_docs.status_code == 403

        # 8. Patient A attempts IDOR access to Patient B's audit trail -> 403 Forbidden
        idor_audit = await client.get(f"/api/audit/patient/{pid_b}", headers=headers_a)
        assert idor_audit.status_code == 403

        # 9. Verify in MongoDB audit_logs that SECURITY_IDOR_BLOCKED was recorded
        audit_col = get_audit_logs_collection()
        idor_events = await audit_col.find({
            "action": AuditEventType.SECURITY_IDOR_BLOCKED.value,
        }).to_list(length=10)

        assert len(idor_events) >= 1
        first_event = idor_events[0]
        assert first_event["actor_user_id"] == user_a["user_id"]
        assert first_event["status"] == "blocked"
        assert first_event["patient_id"] == pid_b


@pytest.mark.anyio
async def test_patient_to_doctor_dashboard_blocked_and_audited():
    """Verify that a patient cannot access the doctor queue and an unauthorized access event is audited."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        user_pat = await auth_service.create_user(UserCreate(
            username="kiosk_pat_user",
            password="Password123!",
            full_name="Kiosk Patient",
            role="patient",
        ))
        token_pat = auth_service.create_access_token({
            "sub": user_pat["user_id"],
            "role": "patient",
        })

        # Attempt to access doctor dashboard
        res = await client.get("/api/doctor/queue", headers={"Authorization": f"Bearer {token_pat}"})
        assert res.status_code == 403

        # Verify unauthorized access event was logged
        audit_col = get_audit_logs_collection()
        unauth_events = await audit_col.find({
            "action": AuditEventType.SECURITY_UNAUTHORIZED_ACCESS.value,
        }).to_list(length=10)
        assert len(unauth_events) >= 1
        assert unauth_events[0]["actor_user_id"] == user_pat["user_id"]


@pytest.mark.anyio
async def test_auth_login_audit_trail_without_password_leakage():
    """Verify that login success and failures are audited and passwords are never exposed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await auth_service.create_user(UserCreate(
            username="audit_login_user",
            password="CorrectPassword123!",
            full_name="Login Test User",
            role="patient",
        ))

        # 1. Failed login attempt
        fail_res = await client.post("/api/auth/login", json={
            "username": "audit_login_user",
            "password": "WrongPassword!",
        })
        assert fail_res.status_code == 401

        # 2. Successful login attempt
        succ_res = await client.post("/api/auth/login", json={
            "username": "audit_login_user",
            "password": "CorrectPassword123!",
        })
        assert succ_res.status_code == 200

        # 3. Check audit logs
        audit_col = get_audit_logs_collection()
        fail_log = await audit_col.find_one({"action": AuditEventType.AUTH_LOGIN_FAILURE.value})
        assert fail_log is not None
        assert "password" not in str(fail_log.get("details", {})).lower() or fail_log["details"].get("password") == "[REDACTED]"

        succ_log = await audit_col.find_one({"action": AuditEventType.AUTH_LOGIN_SUCCESS.value})
        assert succ_log is not None
        assert "password" not in str(succ_log.get("details", {})).lower() or succ_log["details"].get("password") == "[REDACTED]"
