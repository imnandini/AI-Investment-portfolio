from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import Settings


password_hasher = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "ai-investment-copilot"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: UUID, settings: Settings) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    claims = {
        "sub": str(user_id),
        "iss": JWT_ISSUER,
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(claims, settings.secret_key, algorithm=JWT_ALGORITHM)
