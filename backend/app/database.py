from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import logging
from app.config import settings

logger = logging.getLogger("medikiosk.database")


class DatabaseManager:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None

    async def connect(self):
        logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI}...")
        self.client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,
        )
        self.db = self.client[settings.DATABASE_NAME]

        # Verify connectivity
        await self.client.admin.command("ping")
        logger.info(f"Connected successfully to MongoDB database: '{settings.DATABASE_NAME}'")

        # Create essential collections and indexes
        await self._setup_indexes()

    async def _setup_indexes(self):
        if self.db is None:
            return

        patients_collection = self.db["patients"]

        # Ensure index on token_number (unique)
        await patients_collection.create_index("token_number", unique=True)
        # Ensure index on phone_number for quick lookup
        await patients_collection.create_index("phone_number")
        # Ensure index on created_at for queue ordering
        await patients_collection.create_index([("created_at", -1)])
        # Ensure index on registration_status
        await patients_collection.create_index("registration_status")

        # Triage alerts collection indexes
        triage_collection = self.db["triage_alerts"]
        await triage_collection.create_index("alert_id", unique=True)
        await triage_collection.create_index("patient_id")
        await triage_collection.create_index("status")
        await triage_collection.create_index("priority")
        await triage_collection.create_index([("detected_at", -1)])

        # Medical documents collection indexes (Phase 7)
        docs_collection = self.db["medical_documents"]
        await docs_collection.create_index("document_id", unique=True)
        await docs_collection.create_index("patient_id")
        await docs_collection.create_index([("patient_id", 1), ("file_hash", 1)])
        await docs_collection.create_index([("uploaded_at", -1)])

        # Users collection indexes (Phase 11)
        users_collection = self.db["users"]
        await users_collection.create_index("username", unique=True)
        await users_collection.create_index("user_id", unique=True)
        await users_collection.create_index("role")
        await users_collection.create_index("patient_id")

        # Audit logs collection indexes (Phase 12)
        audit_collection = self.db["audit_logs"]
        await audit_collection.create_index("event_id", unique=True)
        await audit_collection.create_index("actor_user_id")
        await audit_collection.create_index("patient_id")
        await audit_collection.create_index("action")
        await audit_collection.create_index([("timestamp", -1)])

        # Consent records collection indexes (Phase 12)
        consent_collection = self.db["consent_records"]
        await consent_collection.create_index("consent_id", unique=True)
        await consent_collection.create_index("patient_id")
        await consent_collection.create_index("status")
        await consent_collection.create_index([("timestamp", -1)])

        logger.info("Database indexes configured successfully.")

    async def disconnect(self):
        if self.client:
            logger.info("Closing MongoDB connection...")
            self.client.close()
            self.client = None
            self.db = None
            logger.info("MongoDB connection closed.")

    async def ping(self) -> bool:
        if not self.client:
            return False
        try:
            await self.client.admin.command("ping")
            return True
        except Exception as e:
            logger.error(f"MongoDB ping failed: {e}")
            return False


db_manager = DatabaseManager()


def get_database() -> AsyncIOMotorDatabase:
    if db_manager.db is None:
        raise RuntimeError("Database not initialized. Please ensure server startup completed.")
    return db_manager.db


def get_patients_collection():
    return get_database()["patients"]


def get_documents_collection():
    return get_database()["medical_documents"]


def get_interview_sessions_collection():
    return get_database()["interview_sessions"]


def get_triage_alerts_collection():
    return get_database()["triage_alerts"]


def get_users_collection():
    return get_database()["users"]


def get_audit_logs_collection():
    return get_database()["audit_logs"]


def get_consent_records_collection():
    return get_database()["consent_records"]

