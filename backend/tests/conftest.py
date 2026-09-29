import pytest
import os

# Configure environment before any app modules or database connections are initialized
os.environ["DATABASE_NAME"] = "medikiosk_test"

from app.config import settings
settings.DATABASE_NAME = "medikiosk_test"

from app.database import db_manager


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def manage_db_connection():
    """Ensure db connection is fresh on the active event loop for each test using isolated test db."""
    settings.DATABASE_NAME = "medikiosk_test"
    await db_manager.connect()
    yield
    await db_manager.disconnect()


@pytest.fixture(scope="session", autouse=True)
async def cleanup_test_database():
    """Clean up medikiosk_test database before and after the full test session."""
    settings.DATABASE_NAME = "medikiosk_test"
    await db_manager.connect()
    if db_manager.db is not None:
        await db_manager.db.patients.drop()
        await db_manager.db.counters.drop()
        await db_manager.db.interview_sessions.drop()
        await db_manager.db.triage_alerts.drop()
        await db_manager.db.medical_documents.drop()
        await db_manager.db.audit_logs.drop()
        await db_manager.db.consent_records.drop()
    await db_manager.disconnect()
    yield
    settings.DATABASE_NAME = "medikiosk_test"
    await db_manager.connect()
    if db_manager.db is not None:
        await db_manager.db.patients.drop()
        await db_manager.db.counters.drop()
        await db_manager.db.interview_sessions.drop()
        await db_manager.db.triage_alerts.drop()
        await db_manager.db.medical_documents.drop()
        await db_manager.db.audit_logs.drop()
        await db_manager.db.consent_records.drop()
    await db_manager.disconnect()
