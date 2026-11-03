from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import JWT_ALGORITHM, JWT_ISSUER, create_access_token
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserCreate, UserRead
from app.services.users import DuplicateEmailError, authenticate_user, register_user


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
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, session: SessionDep) -> User:
    try:
        return register_user(session, str(payload.email), payload.password)
    except DuplicateEmailError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.") from None


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
    return TokenResponse(
        access_token=create_access_token(user.id, settings),
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> User:
    return current_user
