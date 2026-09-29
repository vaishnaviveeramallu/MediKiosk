import logging
from typing import Optional, List, Dict, Any, Callable
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

import asyncio
from app.services.auth_service import auth_service
from app.services.audit_service import audit_service
from app.models.audit import AuditEventType

logger = logging.getLogger("medikiosk.auth_deps")

security_bearer = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> Optional[Dict[str, Any]]:
    """
    Extracts and validates JWT from Authorization header or cookie.
    Returns user dict if valid; returns None if no token or token invalid.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif "Authorization" in request.headers:
        auth_header = request.headers["Authorization"]
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    elif "access_token" in request.cookies:
        token = request.cookies["access_token"]

    if not token:
        return None

    try:
        payload = auth_service.decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None

        user = await auth_service.get_user_by_id(user_id)
        if not user or not user.get("is_active", True):
            return None

        return user
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired")
        return None
    except jwt.PyJWTError as e:
        logger.debug(f"Invalid token: {e}")
        return None


async def get_current_user(
    user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
) -> Dict[str, Any]:
    """
    Mandatory authentication dependency.
    Raises HTTP 401 Unauthorized if request is unauthenticated.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(allowed_roles: List[str]) -> Callable:
    """
    Factory for role-based access control (RBAC).
    Enforces that current user belongs to one of allowed_roles.
    Raises HTTP 403 Forbidden if user lacks the required role.
    """
    async def role_checker(
        current_user: Dict[str, Any] = Depends(get_current_user),
    ) -> Dict[str, Any]:
        user_role = current_user.get("role", "")
        if user_role not in allowed_roles:
            try:
                await audit_service.log_event(
                    action=AuditEventType.SECURITY_UNAUTHORIZED_ACCESS.value,
                    actor_user_id=current_user.get("user_id"),
                    actor_role=user_role,
                    status="blocked",
                    details={
                        "required_roles": allowed_roles,
                        "user_role": user_role,
                    },
                )
            except Exception:
                pass

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Role '{user_role}' is not authorized. Requires one of: {allowed_roles}",
            )
        return current_user

    return role_checker


def verify_patient_ownership(
    target_patient_id: str,
    current_user: Dict[str, Any],
) -> None:
    """
    Enforces strict IDOR (Insecure Direct Object Reference) prevention.
    A user with role 'patient' can ONLY view or modify their own linked patient record.
    Doctors and triage staff are authorized for cross-patient clinical access.
    Automatically logs a security audit event on IDOR violations.
    """
    role = current_user.get("role", "")
    if role == "patient":
        user_pat_id = current_user.get("patient_id")
        if not user_pat_id or str(user_pat_id) != str(target_patient_id):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    audit_service.log_event(
                        action=AuditEventType.SECURITY_IDOR_BLOCKED.value,
                        actor_user_id=current_user.get("user_id"),
                        actor_role=role,
                        patient_id=str(target_patient_id),
                        status="blocked",
                        details={
                            "attempted_patient_id": str(target_patient_id),
                            "user_linked_patient_id": str(user_pat_id) if user_pat_id else None,
                            "reason": "Unauthorized access to different patient resource",
                        },
                    )
                )
            except RuntimeError:
                pass

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are only authorized to access your own patient records (IDOR protection).",
            )
