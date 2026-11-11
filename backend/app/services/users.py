from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.user import User


class DuplicateEmailError(Exception):
    pass


def register_user(session: Session, email: str, password: str) -> User:
    """Stage an unverified account; the caller commits after email delivery."""
    normalized_email = email.strip().lower()
    if session.scalar(select(User.id).where(User.email == normalized_email)) is not None:
        raise DuplicateEmailError

    user = User(email=normalized_email, password_hash=hash_password(password))
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise DuplicateEmailError from exc
    return user


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = session.scalar(select(User).where(User.email == normalized_email))
    if user is None or not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user
