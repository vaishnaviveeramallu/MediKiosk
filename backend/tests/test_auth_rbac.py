import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_database, get_users_collection, get_patients_collection


@pytest.mark.anyio
async def test_user_registration_and_password_hashing():
    """Verify user registration, role assignment, and bcrypt password hashing (zero plaintext)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        unique = uuid.uuid4().hex[:6]
        username = f"patient_{unique}"
        plain_pw = "SecureP@ssw0rd123"

        res = await ac.post("/api/auth/register", json={
            "username": username,
            "password": plain_pw,
            "full_name": "Test Patient User",
            "role": "patient",
            "email_or_phone": f"{unique}@test.com",
        })
        assert res.status_code == 201
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == username
        assert data["user"]["role"] == "patient"

        # Verify password in MongoDB is hashed and NOT plaintext
        users_col = get_users_collection()
        user_in_db = await users_col.find_one({"username": username})
        assert user_in_db is not None
        assert user_in_db["password_hash"] != plain_pw
        assert user_in_db["password_hash"].startswith("$2b$") or user_in_db["password_hash"].startswith("$2a$")

        # Cleanup
        await users_col.delete_one({"_id": user_in_db["_id"]})


@pytest.mark.anyio
async def test_valid_login_and_token_authentication():
    """Verify login with valid credentials returns a valid JWT with sub and role claims."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        unique = uuid.uuid4().hex[:6]
        username = f"doctor_{unique}"
        plain_pw = "DoctorSecret789!"

        # Register doctor
        reg_res = await ac.post("/api/auth/register", json={
            "username": username,
            "password": plain_pw,
            "full_name": "Dr. Verification Test",
            "role": "doctor",
        })
        assert reg_res.status_code == 201

        # Login
        login_res = await ac.post("/api/auth/login", json={
            "username": username,
            "password": plain_pw,
        })
        assert login_res.status_code == 200
        data = login_res.json()
        token = data["access_token"]
        assert data["user"]["role"] == "doctor"

        # Test /api/auth/me
        me_res = await ac.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["username"] == username
        assert me_data["role"] == "doctor"

        # Cleanup
        users_col = get_users_collection()
        await users_col.delete_one({"username": username})


@pytest.mark.anyio
async def test_invalid_credentials_rejected():
    """Verify invalid password or non-existent username returns HTTP 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        unique = uuid.uuid4().hex[:6]
        username = f"user_{unique}"
        plain_pw = "ValidPassword123"

        await ac.post("/api/auth/register", json={
            "username": username,
            "password": plain_pw,
            "full_name": "Auth Fail Test",
            "role": "patient",
        })

        # Wrong password
        bad_pw = await ac.post("/api/auth/login", json={
            "username": username,
            "password": "WrongPassword!",
        })
        assert bad_pw.status_code == 401

        # Non-existent user
        bad_user = await ac.post("/api/auth/login", json={
            "username": "nonexistent_user_xyz",
            "password": "AnyPassword",
        })
        assert bad_user.status_code == 401

        # Cleanup
        users_col = get_users_collection()
        await users_col.delete_one({"username": username})


@pytest.mark.anyio
async def test_rbac_doctor_queue_protection():
    """Verify that /api/doctor/queue rejects unauthenticated users and patient roles, but allows doctor role."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        unique = uuid.uuid4().hex[:6]
        pat_user = f"pat_{unique}"
        doc_user = f"doc_{unique}"
        pw = "TestPassword123"

        # 1. Unauthenticated request -> 401
        unauth_res = await ac.get("/api/doctor/queue")
        assert unauth_res.status_code == 401

        # 2. Register patient and attempt access -> 403 Forbidden
        reg_pat = await ac.post("/api/auth/register", json={
            "username": pat_user,
            "password": pw,
            "full_name": "Patient Role Test",
            "role": "patient",
        })
        pat_token = reg_pat.json()["access_token"]

        pat_res = await ac.get("/api/doctor/queue", headers={"Authorization": f"Bearer {pat_token}"})
        assert pat_res.status_code == 403
        assert "forbidden" in pat_res.json()["detail"].lower()

        # 3. Register doctor and attempt access -> 200 OK
        reg_doc = await ac.post("/api/auth/register", json={
            "username": doc_user,
            "password": pw,
            "full_name": "Doctor Role Test",
            "role": "doctor",
        })
        doc_token = reg_doc.json()["access_token"]

        doc_res = await ac.get("/api/doctor/queue", headers={"Authorization": f"Bearer {doc_token}"})
        assert doc_res.status_code == 200

        # Cleanup
        users_col = get_users_collection()
        await users_col.delete_one({"username": pat_user})
        await users_col.delete_one({"username": doc_user})


@pytest.mark.anyio
async def test_idor_patient_isolation():
    """Verify IDOR protection: Patient A cannot access Patient B's data, documents, or interview."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        unique = uuid.uuid4().hex[:6]

        # 1. Create Patient Record A
        reg_a = await ac.post("/api/patients/register", json={
            "full_name": f"Patient A {unique}",
            "age": 30,
            "gender": "Female",
            "phone_number": "9111111111",
            "initial_complaint": "Headache",
        })
        pid_a = reg_a.json()["id"]

        # 2. Create Patient Record B
        reg_b = await ac.post("/api/patients/register", json={
            "full_name": f"Patient B {unique}",
            "age": 40,
            "gender": "Male",
            "phone_number": "9222222222",
            "initial_complaint": "Back pain",
        })
        pid_b = reg_b.json()["id"]

        # 3. Create User Account for Patient A linked to pid_a
        user_a_res = await ac.post("/api/auth/register", json={
            "username": f"usera_{unique}",
            "password": "PasswordA123!",
            "full_name": f"User A {unique}",
            "role": "patient",
            "patient_id": pid_a,
        })
        token_a = user_a_res.json()["access_token"]

        # 4. Patient A accesses own data -> 200 OK
        own_res = await ac.get(f"/api/patients/{pid_a}", headers={"Authorization": f"Bearer {token_a}"})
        assert own_res.status_code == 200
        assert own_res.json()["full_name"] == f"Patient A {unique}"

        # 5. Patient A attempts to access Patient B's record (IDOR) -> 403 Forbidden!
        idor_res = await ac.get(f"/api/patients/{pid_b}", headers={"Authorization": f"Bearer {token_a}"})
        assert idor_res.status_code == 403
        assert "IDOR protection" in idor_res.json()["detail"]

        # 6. Patient A attempts to list Patient B's documents (IDOR) -> 403 Forbidden!
        idor_doc = await ac.get(f"/api/patients/{pid_b}/documents", headers={"Authorization": f"Bearer {token_a}"})
        assert idor_doc.status_code == 403

        # Cleanup
        users_col = get_users_collection()
        patients_col = get_patients_collection()
        await users_col.delete_one({"username": f"usera_{unique}"})
        from bson import ObjectId
        await patients_col.delete_one({"_id": ObjectId(pid_a)})
        await patients_col.delete_one({"_id": ObjectId(pid_b)})
