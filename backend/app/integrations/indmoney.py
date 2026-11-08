"""Official INDmoney OAuth + Streamable HTTP. Only networth_holdings is callable.

Endpoints are discovered from INDmoney's public metadata, never from user input.
Credentials stay encrypted in the backend; mobile numbers, OTPs and MPINs never
pass through this application.
"""
import asyncio
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
from urllib.parse import urlencode, urlsplit

from cryptography.fernet import Fernet, InvalidToken
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy import delete, select, update

from app.models.indmoney import IndmoneyConnection, IndmoneyPreview

ORIGIN = "https://mcp.indmoney.com"
RESOURCE = ORIGIN + "/mcp"
SCOPE = "portfolio:read"


class IndmoneyError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc)


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def cipher(settings):
    if not settings.indmoney_token_key:
        raise IndmoneyError("Set INDMONEY_TOKEN_KEY before connecting INDmoney. See docs/indmoney.md.", 503)
    try:
        return Fernet(settings.indmoney_token_key.encode())
    except (ValueError, TypeError):
        raise IndmoneyError("INDMONEY_TOKEN_KEY must be a valid Fernet key.", 503) from None


def seal(settings, payload):
    return cipher(settings).encrypt(json.dumps(payload).encode()).decode()


def unseal(settings, value):
    try:
        return json.loads(cipher(settings).decrypt(value.encode()))
    except (InvalidToken, ValueError, TypeError):
        raise IndmoneyError("Stored INDmoney connection cannot be decrypted. Disconnect and reconnect.", 409) from None


def trusted_url(value):
    if not isinstance(value, str):
        raise IndmoneyError("INDmoney returned incomplete OAuth metadata.")
    parsed = urlsplit(value)
    if (parsed.scheme, parsed.netloc) != ("https", "mcp.indmoney.com") or parsed.fragment or parsed.username:
        raise IndmoneyError("INDmoney returned an unexpected OAuth endpoint.")
    return value


def http_client():
    return httpx.AsyncClient(timeout=15, follow_redirects=False)


async def request_json(client, method, url, **kwargs):
    try:
        response = await client.request(method, trusted_url(url), **kwargs)
        if response.status_code == 429:
            raise IndmoneyError("INDmoney rate limit reached. Try again shortly.", 429)
        if response.status_code in (400, 401, 403):
            raise IndmoneyError("INDmoney rejected this authorization. Reconnect, or check client registration.", 409)
        if not response.is_success or len(response.content) > 2_000_000:
            raise IndmoneyError("INDmoney is unavailable or returned an oversized response.")
        result = response.json()
        if not isinstance(result, dict) or result.get("error"):
            raise IndmoneyError("INDmoney returned an invalid response.")
        return result
    except (httpx.HTTPError, ValueError):
        raise IndmoneyError("Could not reach INDmoney. Try again shortly.") from None


async def metadata(client):
    resource = await request_json(client, "GET", ORIGIN + "/.well-known/oauth-protected-resource/mcp")
    if resource.get("resource") != RESOURCE or ORIGIN + "/" not in resource.get("authorization_servers", []):
        raise IndmoneyError("INDmoney resource metadata did not match the configured server.")
    meta = await request_json(client, "GET", ORIGIN + "/.well-known/oauth-authorization-server")
    if meta.get("issuer", "").rstrip("/") != ORIGIN or "S256" not in meta.get("code_challenge_methods_supported", []):
        raise IndmoneyError("INDmoney must advertise its issuer and PKCE S256 support.")
    for key in ("authorization_endpoint", "token_endpoint"):
        trusted_url(meta.get(key))
    return meta


def redirect_uri(settings):
    uri = settings.indmoney_redirect_uri
    parsed = urlsplit(uri)
    if parsed.query or parsed.fragment or parsed.username or not parsed.hostname or not parsed.path:
        raise IndmoneyError("INDMONEY_REDIRECT_URI must be an absolute portfolio page URL without a query.", 503)
    if parsed.scheme != "https" and not (settings.environment != "production" and parsed.scheme == "http" and parsed.hostname in ("localhost", "127.0.0.1")):
        raise IndmoneyError("INDMONEY_REDIRECT_URI requires HTTPS, except for local development.", 503)
    return uri


async def begin_connection(session, user_id, settings):
    cipher(settings)
    uri = redirect_uri(settings)
    async with http_client() as client:
        meta = await metadata(client)
        methods = meta.get("token_endpoint_auth_methods_supported", [])
        method = "client_secret_post" if "client_secret_post" in methods else "client_secret_basic" if "client_secret_basic" in methods else "none"
        client_info = {"client_id": settings.indmoney_client_id, "client_secret": settings.indmoney_client_secret,
                       "token_endpoint_auth_method": method}
        if not client_info["client_id"]:
            endpoint = meta.get("registration_endpoint")
            if not endpoint:
                raise IndmoneyError("INDmoney requires a registered INDMONEY_CLIENT_ID and client secret.", 503)
            client_info = await request_json(client, "POST", endpoint, json={
                "client_name": "Investment Research Copilot", "redirect_uris": [uri],
                "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
                "scope": SCOPE, "token_endpoint_auth_method": method})
            client_info.setdefault("token_endpoint_auth_method", method)
        if not client_info.get("client_id") or (method != "none" and not client_info.get("client_secret")):
            raise IndmoneyError("INDmoney did not provide the required client registration credentials.", 503)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    connection = session.get(IndmoneyConnection, user_id)
    if connection is None:
        connection = IndmoneyConnection(user_id=user_id)
        session.add(connection)
    connection.pending = seal(settings, {"verifier": verifier, "client": client_info, "redirect_uri": uri, "metadata": meta})
    connection.state_hash = hashlib.sha256(state.encode()).hexdigest()
    connection.state_expires_at = now() + timedelta(minutes=10)
    session.commit()
    params = {"response_type": "code", "client_id": client_info["client_id"], "redirect_uri": uri,
              "scope": SCOPE, "resource": RESOURCE, "state": state, "code_challenge": challenge, "code_challenge_method": "S256"}
    return {"authorization_url": meta["authorization_endpoint"] + "?" + urlencode(params), "state": state}


async def token_request(client, metadata, client_info, data):
    data = {**data, "client_id": client_info["client_id"], "resource": RESOURCE}
    method = client_info.get("token_endpoint_auth_method", "client_secret_post")
    kwargs = {}
    if method == "client_secret_basic":
        kwargs["auth"] = httpx.BasicAuth(client_info["client_id"], client_info["client_secret"])
    elif method == "client_secret_post":
        data["client_secret"] = client_info["client_secret"]
    elif method != "none":
        raise IndmoneyError("Unsupported INDmoney client authentication method.")
    token = await request_json(client, "POST", metadata["token_endpoint"], data=data, **kwargs)
    if not isinstance(token.get("access_token"), str) or str(token.get("token_type", "")).lower() != "bearer":
        raise IndmoneyError("INDmoney did not issue a bearer access token.")
    scopes = set(token.get("scope", SCOPE).split())
    if SCOPE not in scopes or scopes - {SCOPE}:
        raise IndmoneyError("INDmoney returned unexpected scopes; only portfolio:read is accepted.")
    try:
        # Missing expiry is conservative: refresh or reauthenticate after five minutes.
        token["expires_at"] = (now() + timedelta(seconds=max(0, int(token.get("expires_in", 300))))).isoformat()
    except (TypeError, ValueError, OverflowError):
        raise IndmoneyError("INDmoney returned an invalid token lifetime.") from None
    return token


async def finish_connection(session, user_id, settings, code, state):
    digest = hashlib.sha256(state.encode()).hexdigest()
    exchanging = hashlib.sha256(("exchange:" + state).encode()).hexdigest()
    connection = session.get(IndmoneyConnection, user_id)
    if not connection or not connection.pending or connection.state_hash != digest or not connection.state_expires_at or aware(connection.state_expires_at) <= now():
        raise IndmoneyError("INDmoney sign-in expired or state did not match. Start Connect again.", 400)
    pending = unseal(settings, connection.pending)
    # Atomically consume the state before exchanging a one-use code.
    used = session.execute(update(IndmoneyConnection).where(
        IndmoneyConnection.user_id == user_id, IndmoneyConnection.state_hash == digest,
        IndmoneyConnection.state_expires_at > now()).values(pending=None, state_hash=exchanging)
        .execution_options(synchronize_session=False))
    if used.rowcount != 1:
        session.rollback()
        raise IndmoneyError("INDmoney sign-in has already been used or expired.", 400)
    session.commit()
    session.expire_all()
    async with http_client() as client:
        token = await token_request(client, pending["metadata"], pending["client"], {
            "grant_type": "authorization_code", "code": code, "code_verifier": pending["verifier"], "redirect_uri": pending["redirect_uri"]})
    stored = session.execute(update(IndmoneyConnection).where(IndmoneyConnection.user_id == user_id,
        IndmoneyConnection.state_hash == exchanging).values(
        credentials=seal(settings, {"client": pending["client"], "metadata": pending["metadata"], "token": token}),
        connected_at=now(), state_hash=None, state_expires_at=None).execution_options(synchronize_session=False))
    if stored.rowcount != 1:
        session.rollback()
        raise IndmoneyError("This sign-in was cancelled or replaced by another connection. Connect again.", 409)
    session.execute(delete(IndmoneyPreview).where(IndmoneyPreview.user_id == user_id))
    session.commit()
    session.expire_all()


async def access_token(session, user_id, settings):
    connection = session.scalar(select(IndmoneyConnection).where(IndmoneyConnection.user_id == user_id).with_for_update())
    if not connection or not connection.credentials:
        raise IndmoneyError("Connect your INDmoney account first.", 409)
    credentials = unseal(settings, connection.credentials)
    token = credentials["token"]
    if datetime.fromisoformat(token["expires_at"]) <= now() + timedelta(seconds=30):
        if not token.get("refresh_token"):
            raise IndmoneyError("Your INDmoney session expired. Connect again.", 409)
        async with http_client() as client:
            refreshed = await token_request(client, credentials["metadata"], credentials["client"], {
                "grant_type": "refresh_token", "refresh_token": token["refresh_token"]})
        refreshed.setdefault("refresh_token", token["refresh_token"])
        credentials["token"] = refreshed
        connection.credentials = seal(settings, credentials)
        token = refreshed
        session.commit()
    return token["access_token"]


def result_json(result):
    if result.isError:
        raise IndmoneyError("INDmoney could not read holdings. Check consent and reconnect if needed.")
    if result.structuredContent is not None:
        value = result.structuredContent
    else:
        texts = [item.text for item in result.content if item.type == "text"]
        try:
            value = json.loads("\n".join(texts))
        except (ValueError, TypeError):
            raise IndmoneyError("INDmoney returned holdings in an unsupported format. No holdings were changed.") from None
    if len(json.dumps(value)) > 2_000_000:
        raise IndmoneyError("INDmoney holdings exceeded the import limit.")
    return value


async def read_holdings(token, asset_type=None):
    """Discover the real input schema. Never guess additional required arguments."""
    try:
        async with asyncio.timeout(45):
            async with httpx.AsyncClient(headers={"Authorization": "Bearer " + token}, timeout=20, follow_redirects=False) as client:
                async with streamable_http_client(RESOURCE, http_client=client) as (read, write, _):
                    async with ClientSession(read, write) as mcp:
                        await mcp.initialize()
                        tools = await mcp.list_tools()
                        tool = next((item for item in tools.tools if item.name == "networth_holdings"), None)
                        if tool is None:
                            raise IndmoneyError("INDmoney did not expose networth_holdings for this account.")
                        schema = tool.inputSchema
                        properties = schema.get("properties", {})
                        field = "asset_type" if "asset_type" in properties else "assetType" if "assetType" in properties else None
                        options = []
                        if field:
                            prop = properties[field]
                            if "$ref" in prop:
                                prop = schema.get("$defs", {}).get(prop["$ref"].split("/")[-1], prop)
                            options = prop.get("enum", [])
                            for variant in prop.get("anyOf", []):
                                options.extend(variant.get("enum", []))
                            options = [v for v in options if isinstance(v, str)]
                        if asset_type is None:
                            return {"asset_types": options or (["IND_STOCK", "MF", "US_STOCK"] if field else ["ALL"]), "asset_field": field}
                        if options and asset_type not in options:
                            raise IndmoneyError("Choose an asset type supported by INDmoney.", 422)
                        args = {field: asset_type} if field else {}
                        if set(schema.get("required", [])) - set(args):
                            raise IndmoneyError("INDmoney holdings requires unsupported parameters. No holdings were changed.", 422)
                        return result_json(await mcp.call_tool("networth_holdings", args))
    except IndmoneyError:
        raise
    except Exception:
        # SDK exception groups can contain upstream response text or tokens.
        raise IndmoneyError("INDmoney MCP could not read holdings. Reconnect if your session expired, then retry.") from None
