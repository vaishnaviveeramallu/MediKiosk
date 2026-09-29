import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends, Request
from app.models.auth import UserCreate, UserLogin, TokenResponse, UserProfile
from app.models.audit import AuditEventType
from app.services.auth_service import auth_service
from app.services.audit_service import audit_service
from app.utils.auth_deps import get_current_user, get_current_user_optional

logger = logging.getLogger("medikiosk.auth_routes")

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user account",
    description="Creates a new patient, doctor, or triage_staff account with bcrypt password hashing.",
)
async def register_user(payload: UserCreate, request: Request):
    client_ip = request.client.host if request.client else None
    try:
        user_doc = await auth_service.create_user(payload)
    except ValueError as e:
        await audit_service.log_event(
            action=AuditEventType.AUTH_REGISTER.value,
            status="failure",
            ip_address=client_ip,
            details={"username": payload.username, "role": payload.role, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    # Generate JWT token
    token = auth_service.create_access_token({
        "sub": user_doc["user_id"],
        "username": user_doc["username"],
        "role": user_doc["role"],
        "patient_id": user_doc.get("patient_id"),
    })

    await audit_service.log_event(
        action=AuditEventType.AUTH_REGISTER.value,
        actor_user_id=user_doc["user_id"],
        actor_role=user_doc["role"],
        patient_id=user_doc.get("patient_id"),
        status="success",
        ip_address=client_ip,
        details={"username": user_doc["username"], "role": user_doc["role"]},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserProfile(
            user_id=user_doc["user_id"],
            username=user_doc["username"],
            full_name=user_doc["full_name"],
            role=user_doc["role"],
            patient_id=user_doc.get("patient_id"),
            email_or_phone=user_doc.get("email_or_phone"),
            created_at=user_doc["created_at"],
        ),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="User login with credentials",
    description="Authenticates username/password using bcrypt and returns JWT token.",
)
async def login_user(payload: UserLogin, request: Request):
    client_ip = request.client.host if request.client else None
    user = await auth_service.authenticate_user(payload)
    if not user:
        await audit_service.log_event(
            action=AuditEventType.AUTH_LOGIN_FAILURE.value,
            status="failure",
            ip_address=client_ip,
            details={"username": payload.username, "reason": "Invalid credentials"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please check your username and password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_service.create_access_token({
        "sub": user["user_id"],
        "username": user["username"],
        "role": user["role"],
        "patient_id": user.get("patient_id"),
    })

    await audit_service.log_event(
        action=AuditEventType.AUTH_LOGIN_SUCCESS.value,
        actor_user_id=user["user_id"],
        actor_role=user["role"],
        patient_id=user.get("patient_id"),
        status="success",
        ip_address=client_ip,
        details={"username": user["username"], "role": user["role"]},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserProfile(
            user_id=user["user_id"],
            username=user["username"],
            full_name=user["full_name"],
            role=user["role"],
            patient_id=user.get("patient_id"),
            email_or_phone=user.get("email_or_phone"),
            created_at=user["created_at"],
        ),
    )


@router.get(
    "/me",
    response_model=UserProfile,
    summary="Get current user profile",
    description="Returns the profile of the currently authenticated user.",
)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserProfile(
        user_id=current_user["user_id"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        role=current_user["role"],
        patient_id=current_user.get("patient_id"),
        email_or_phone=current_user.get("email_or_phone"),
        created_at=current_user["created_at"],
    )


@router.post(
    "/logout",
    summary="Log out user",
    description="Acknowledge logout and log audit event.",
)
async def logout(
    current_user: Optional[dict] = Depends(get_current_user_optional),
    request: Request = None,
):
    client_ip = request.client.host if (request and request.client) else None
    if current_user:
        await audit_service.log_event(
            action=AuditEventType.AUTH_LOGOUT.value,
            actor_user_id=current_user.get("user_id"),
            actor_role=current_user.get("role"),
            status="success",
            ip_address=client_ip,
            details={"username": current_user.get("username")},
        )

    return {
        "status": "success",
        "message": "User successfully logged out. Local token cleared.",
    }
