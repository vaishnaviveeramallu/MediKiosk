import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
import bcrypt
import jwt
from bson import ObjectId

from app.config import settings
from app.database import get_users_collection
from app.models.auth import UserCreate, UserLogin, UserRole

logger = logging.getLogger("medikiosk.auth_service")


class AuthService:
    """
    Core authentication service managing bcrypt password hashing,
    JWT generation and verification, and user collection operations in MongoDB.
    Strictly forbids plaintext passwords.
    """

    @staticmethod
    def hash_password(plain_password: str) -> str:
        """Hash plaintext password with bcrypt and salt."""
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify plaintext password against bcrypt hash."""
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except Exception as e:
            logger.warning(f"Password verification error: {e}")
            return False

    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create signed JWT access token with role and subject claims."""
        to_encode = data.copy()
        now = datetime.now(timezone.utc)
        if expires_delta:
            expire = now + expires_delta
        else:
            expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({
            "exp": expire,
            "iat": now,
        })
        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM,
        )
        return encoded_jwt

    @staticmethod
    def decode_access_token(token: str) -> Dict[str, Any]:
        """Decode and validate JWT access token signature and expiry."""
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )

    async def create_user(self, payload: UserCreate) -> Dict[str, Any]:
        """Register a new user in the MongoDB users collection."""
        users_col = get_users_collection()
        clean_username = payload.username.strip().lower()

        existing = await users_col.find_one({"username": clean_username})
        if existing:
            raise ValueError(f"Username '{payload.username}' is already taken.")

        now = datetime.now(timezone.utc)
        user_id = f"usr_{uuid.uuid4().hex[:10]}"
        password_hash = self.hash_password(payload.password)

        user_doc = {
            "user_id": user_id,
            "username": clean_username,
            "full_name": payload.full_name.strip(),
            "role": payload.role.value if isinstance(payload.role, UserRole) else str(payload.role),
            "password_hash": password_hash,
            "email_or_phone": payload.email_or_phone.strip() if payload.email_or_phone else None,
            "patient_id": payload.patient_id,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        await users_col.insert_one(user_doc)
        logger.info(f"Created new user '{clean_username}' with role '{user_doc['role']}'")

        # Return safe representation
        safe_doc = dict(user_doc)
        safe_doc.pop("password_hash", None)
        return safe_doc

    async def authenticate_user(self, payload: UserLogin) -> Optional[Dict[str, Any]]:
        """Authenticate user by username/phone and password."""
        users_col = get_users_collection()
        identifier = payload.username.strip().lower()

        # Search by username or email_or_phone
        user = await users_col.find_one({
            "$or": [
                {"username": identifier},
                {"email_or_phone": identifier},
            ]
        })

        if not user:
            return None

        if not user.get("is_active", True):
            return None

        if not self.verify_password(payload.password, user.get("password_hash", "")):
            return None

        return user

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve user by canonical user_id string."""
        users_col = get_users_collection()
        return await users_col.find_one({"user_id": user_id})

    async def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """Retrieve user by username."""
        users_col = get_users_collection()
        return await users_col.find_one({"username": username.strip().lower()})


auth_service = AuthService()
