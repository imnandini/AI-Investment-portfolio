"""Short-lived, single-use email codes. Never return or log codes."""
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
import secrets
import smtplib
import ssl

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.user import User

CODE_LIFETIME_MINUTES = 10
RESEND_SECONDS = 60
MAX_ATTEMPTS = 5


def utc(value: datetime) -> datetime:
    # SQLite returns naive datetimes; PostgreSQL preserves the timezone.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def code_hash(user: User, code: str, settings: Settings) -> str:
    return hmac.new(settings.secret_key.encode(), f"email-verification:{user.id}:{code}".encode(), hashlib.sha256).hexdigest()


def send_verification_email(email: str, code: str, settings: Settings) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise HTTPException(503, "Email delivery is not configured. Ask the administrator to configure SMTP and try again.")
    message = EmailMessage()
    message["Subject"] = "Verify your Northstar email"
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message.set_content(
        f"Your Northstar verification code is: {code}\n\n"
        f"This code expires in {CODE_LIFETIME_MINUTES} minutes and can be used once.\n"
        "Enter it in the app to verify your email. Never share this code.\n"
        "If you did not request this, you can ignore this email."
    )
    context = ssl.create_default_context()
    try:
        connection = (smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10, context=context)
                      if settings.smtp_security == "ssl" else smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10))
        with connection as smtp:
            if settings.smtp_security == "starttls":
                smtp.starttls(context=context)
            if settings.smtp_username:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise HTTPException(503, "Could not send the verification email. Please try again later.") from None


def issue_code(session: Session, user: User, settings: Settings) -> None:
    now = datetime.now(timezone.utc)
    if user.verification_sent_at:
        remaining = RESEND_SECONDS - (now - utc(user.verification_sent_at)).total_seconds()
        if remaining > 0:
            raise HTTPException(429, "Please wait one minute before requesting another code.", headers={"Retry-After": str(max(1, int(remaining) + 1))})
    code = f"{secrets.randbelow(1_000_000):06d}"
    user.verification_code_hash = code_hash(user, code, settings)
    user.verification_expires_at = now + timedelta(minutes=CODE_LIFETIME_MINUTES)
    user.verification_sent_at = now
    user.verification_attempts = 0
    # Keep state transactional: an unsuccessful email leaves the previous code valid.
    send_verification_email(user.email, code, settings)
    session.commit()


def verify_code(session: Session, user: User, code: str, settings: Settings) -> None:
    if (user.email_verified or not user.verification_code_hash or not user.verification_expires_at
            or utc(user.verification_expires_at) <= datetime.now(timezone.utc)
            or user.verification_attempts >= MAX_ATTEMPTS):
        raise HTTPException(400, "Code is invalid or expired. Request a new code.")
    if not hmac.compare_digest(user.verification_code_hash, code_hash(user, code, settings)):
        user.verification_attempts += 1
        session.commit()
        raise HTTPException(400, "Code is invalid or expired. Check the code or request a new one.")
    user.email_verified = True
    user.verification_code_hash = None
    user.verification_expires_at = None
    user.verification_attempts = 0
    session.commit()
