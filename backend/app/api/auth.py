from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import JWT_ALGORITHM, JWT_ISSUER, create_access_token, verify_password
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead, VerificationResponse, VerifyEmailRequest
from app.services.users import DuplicateEmailError, authenticate_user, register_user
from app.services.email_verification import issue_code, verify_code


router = APIRouter(prefix="/auth", tags=["authentication"])
bearer_scheme = HTTPBearer(auto_error=False)
SessionDep = Annotated[Session, Depends(get_session)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        claims = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[JWT_ALGORITHM],
            issuer=JWT_ISSUER,
            options={"require": ["exp", "iat", "iss", "sub"]},
        )
        user_id = UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise unauthorized from None

    user = session.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise unauthorized
    if settings.email_verification_required and not user.email_verified:
        raise HTTPException(403, detail={"code": "email_verification_required", "message": "Verify your email before signing in."})
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/register", response_model=VerificationResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]) -> VerificationResponse:
    try:
        user = register_user(session, str(payload.email), payload.password)
        if settings.email_verification_required:
            issue_code(session, user, settings)
        else:
            session.commit()
    except DuplicateEmailError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.") from None
    except Exception:
        session.rollback()
        raise
    if not settings.email_verification_required:
        return VerificationResponse(message="Account created. You can now sign in.", verification_required=False, resend_after_seconds=0)
    return VerificationResponse(message="We sent a six-digit verification code to your email. It expires in 10 minutes.")


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    session: SessionDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    user = authenticate_user(session, str(payload.email), payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if settings.email_verification_required and not user.email_verified:
        raise HTTPException(403, detail={"code": "email_verification_required", "message": "Verify your email before signing in."})
    return TokenResponse(
        access_token=create_access_token(user.id, settings),
        expires_in=settings.access_token_expire_minutes * 60,
    )


def verification_user(payload: LoginRequest, session: Session) -> User:
    # Serialize code issuance and attempts across API workers for this account.
    user = session.scalar(select(User).where(User.email == str(payload.email).strip().lower()).with_for_update())
    if user is None or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email or password is incorrect.")
    return user


@router.post("/resend-verification", response_model=VerificationResponse)
def resend_verification(payload: LoginRequest, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]) -> VerificationResponse:
    if not settings.email_verification_required:
        raise HTTPException(503, "Email verification is currently paused.")
    user = verification_user(payload, session)
    if user.email_verified:
        raise HTTPException(400, "Email is already verified. Please sign in.")
    try:
        issue_code(session, user, settings)
    except Exception:
        session.rollback()
        raise
    return VerificationResponse(message="We sent a new verification code. It expires in 10 minutes.")


@router.post("/verify-email", response_model=TokenResponse)
def verify_email(payload: VerifyEmailRequest, session: SessionDep, settings: Annotated[Settings, Depends(get_settings)]) -> TokenResponse:
    if not settings.email_verification_required:
        raise HTTPException(503, "Email verification is currently paused.")
    user = verification_user(payload, session)
    verify_code(session, user, payload.code, settings)
    return TokenResponse(access_token=create_access_token(user.id, settings), expires_in=settings.access_token_expire_minutes * 60)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> User:
    return current_user


@router.delete("/me", status_code=204)
def delete_account(current_user: CurrentUser, session: SessionDep):
    """Permanently remove the account and its owned records via FK cascades."""
    session.delete(current_user)
    session.commit()
