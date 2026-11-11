from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import Settings
from app.core.config import get_settings
from app.main import app
from app.core.security import create_access_token
from app.models.user import User
from app.services.email_verification import send_verification_email

EMAIL = "verify@example.com"
PASSWORD = "a-long-test-password"
CREDENTIALS = {"email": EMAIL, "password": PASSWORD}
REGISTRATION = {**CREDENTIALS, "confirm_password": PASSWORD}


def test_registration_and_login_work_without_smtp_when_verification_is_paused(api_context, inbox):
    client, _, _, _, session = api_context
    settings = app.dependency_overrides[get_settings]()
    settings.email_verification_required = False
    response = client.post("/auth/register", json=REGISTRATION)
    assert response.status_code == 201
    assert response.json()["verification_required"] is False
    user = session.scalar(select(User).where(User.email == EMAIL))
    assert not user.email_verified and user.verification_code_hash is None
    assert not inbox
    login = client.post("/auth/login", json=CREDENTIALS)
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert client.get("/portfolios", headers=headers).status_code == 200
    assert client.post("/auth/resend-verification", json=CREDENTIALS).status_code == 503
    assert client.post("/auth/verify-email", json={**CREDENTIALS, "code": "123456"}).status_code == 503
    assert not inbox
    settings.email_verification_required = True
    assert client.post("/auth/login", json=CREDENTIALS).status_code == 403
    assert client.get("/auth/me", headers=headers).status_code == 403


@pytest.fixture
def inbox(monkeypatch):
    messages = []
    monkeypatch.setattr("app.services.email_verification.send_verification_email", lambda email, code, settings: messages.append((email, code)))
    return messages


def pending(api_context):
    client, _, _, _, session = api_context
    response = client.post("/auth/register", json=REGISTRATION)
    assert response.status_code == 201, response.text
    return session.scalar(select(User).where(User.email == EMAIL))


@pytest.mark.parametrize("confirmation", [None, "another-long-password"])
def test_password_confirmation_required(api_context, inbox, confirmation):
    client, _, _, _, session = api_context
    payload = {**CREDENTIALS}
    if confirmation is not None:
        payload["confirm_password"] = confirmation
    assert client.post("/auth/register", json=payload).status_code == 422
    assert session.scalar(select(User).where(User.email == EMAIL)) is None
    assert not inbox


def test_code_gates_login_and_existing_tokens_then_is_single_use(api_context, inbox):
    client, _, _, _, session = api_context
    user = pending(api_context)
    assert user.email_verified is False
    code = inbox[-1][1]
    assert len(code) == 6 and code.isdigit()
    assert code != user.verification_code_hash
    assert PASSWORD != user.password_hash
    response = client.post("/auth/login", json=CREDENTIALS)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "email_verification_required"
    settings = Settings(secret_key="test-secret-key-with-more-than-32-characters")
    old_token = create_access_token(user.id, settings)
    headers = {"Authorization": f"Bearer {old_token}"}
    assert client.get("/auth/me", headers=headers).status_code == 403
    assert client.get("/portfolios", headers=headers).status_code == 403
    response = client.post("/auth/verify-email", json={**CREDENTIALS, "code": code})
    assert response.status_code == 200
    headers = {"Authorization": "Bearer " + response.json()["access_token"]}
    assert client.get("/auth/me", headers=headers).json()["email_verified"] is True
    assert user.verification_code_hash is None
    assert client.post("/auth/verify-email", json={**CREDENTIALS, "code": code}).status_code == 400
    assert client.post("/auth/login", json=CREDENTIALS).status_code == 200


def test_expired_code_and_attempt_limit(api_context, inbox):
    client, _, _, _, session = api_context
    user = pending(api_context)
    code = inbox[-1][1]
    user.verification_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    session.commit()
    assert client.post("/auth/verify-email", json={**CREDENTIALS, "code": code}).status_code == 400
    user.verification_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    session.commit()
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert client.post("/auth/verify-email", json={**CREDENTIALS, "code": wrong}).status_code == 400
    assert user.verification_attempts == 5
    assert client.post("/auth/verify-email", json={**CREDENTIALS, "code": code}).status_code == 400
    assert not user.email_verified


def test_resend_cooldown_replaces_old_code_and_requires_password(api_context, inbox, monkeypatch):
    client, _, _, _, session = api_context
    monkeypatch.setattr("app.services.email_verification.secrets.randbelow", lambda _: 123456)
    user = pending(api_context)
    response = client.post("/auth/resend-verification", json=CREDENTIALS)
    assert response.status_code == 429 and int(response.headers["Retry-After"]) > 0
    assert len(inbox) == 1
    user.verification_sent_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    session.commit()
    monkeypatch.setattr("app.services.email_verification.secrets.randbelow", lambda _: 654321)
    assert client.post("/auth/resend-verification", json={**CREDENTIALS, "password": "incorrect"}).status_code == 401
    assert client.post("/auth/resend-verification", json=CREDENTIALS).status_code == 200
    assert len(inbox) == 2
    assert client.post("/auth/verify-email", json={**CREDENTIALS, "code": "123456"}).status_code == 400
    assert client.post("/auth/verify-email", json={**CREDENTIALS, "password": "incorrect", "code": "654321"}).status_code == 401
    assert client.post("/auth/verify-email", json={**CREDENTIALS, "code": "654321"}).status_code == 200


def test_delivery_failure_rolls_back_registration_and_resend(api_context, inbox, monkeypatch):
    client, _, _, _, session = api_context
    user = pending(api_context)
    original_hash = user.verification_code_hash
    user.verification_sent_at = datetime.now(timezone.utc) - timedelta(seconds=61)
    session.commit()

    def fail(*args):
        raise HTTPException(503, "Could not send the verification email.")

    monkeypatch.setattr("app.services.email_verification.send_verification_email", fail)
    assert client.post("/auth/resend-verification", json=CREDENTIALS).status_code == 503
    session.refresh(user)
    assert user.verification_code_hash == original_hash
    assert client.post("/auth/register", json={**REGISTRATION, "email": "failed@example.com"}).status_code == 503
    assert session.scalar(select(User).where(User.email == "failed@example.com")) is None


def test_duplicate_registration_does_not_change_password_or_send(api_context, inbox):
    client, _, _, _, _ = api_context
    user = pending(api_context)
    original_hash = user.password_hash
    assert client.post("/auth/register", json=REGISTRATION).status_code == 409
    assert user.password_hash == original_hash and len(inbox) == 1


@pytest.mark.parametrize("security", ["starttls", "ssl"])
def test_smtp_uses_encryption_and_sends_code(security):
    settings = Settings(smtp_host="smtp.example.com", smtp_from_email="no-reply@example.com", smtp_username="sender", smtp_password="private-password", smtp_security=security)
    with patch("app.services.email_verification.smtplib.SMTP") as plain, patch("app.services.email_verification.smtplib.SMTP_SSL") as encrypted:
        send_verification_email(EMAIL, "123456", settings)
        connection = plain if security == "starttls" else encrypted
        smtp = connection.return_value.__enter__.return_value
        smtp.login.assert_called_once_with("sender", "private-password")
        if security == "starttls":
            smtp.starttls.assert_called_once()
        message = smtp.send_message.call_args.args[0]
        assert message["To"] == EMAIL and "123456" in message.get_content()


def test_missing_smtp_and_delivery_errors_are_actionable():
    with pytest.raises(HTTPException) as failure:
        send_verification_email(EMAIL, "123456", Settings(smtp_host="", smtp_from_email=""))
    assert failure.value.status_code == 503
    with patch("app.services.email_verification.smtplib.SMTP", side_effect=OSError("sensitive-provider-error")):
        with pytest.raises(HTTPException) as failure:
            send_verification_email(EMAIL, "123456", Settings(smtp_host="smtp.example.com", smtp_from_email="no-reply@example.com"))
    assert "sensitive-provider-error" not in failure.value.detail


def test_migration_requires_existing_users_to_verify_and_preserves_accounts():
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy import create_engine, text

    path = Path(__file__).resolve().parents[1] / "migrations/versions/0007_email_verification.py"
    spec = importlib.util.spec_from_file_location("email_verification_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY, email VARCHAR(320) NOT NULL)"))
        connection.execute(text("INSERT INTO users (id, email) VALUES (1, 'existing@example.com')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        existing = connection.execute(text("SELECT email, email_verified, verification_attempts, verification_code_hash FROM users")).one()
        assert tuple(existing) == ("existing@example.com", 0, 0, None)
        with Operations.context(MigrationContext.configure(connection)):
            migration.downgrade()
        assert connection.execute(text("SELECT email FROM users")).scalar_one() == "existing@example.com"
    engine.dispose()
