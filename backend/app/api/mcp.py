from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from app.api.auth import CurrentUser, bearer_scheme
from app.integrations.mcp_client import ALLOWED_TOOLS, local_mcp
from app.core.config import Settings, get_settings

router = APIRouter(prefix="/mcp", tags=["local MCP"])
Credentials = Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)]
Config = Annotated[Settings, Depends(get_settings)]


class ToolRequest(BaseModel):
    name: str = Field(max_length=80)
    arguments: dict = Field(default_factory=dict)


@router.get("/tools")
async def discover(user: CurrentUser, credentials: Credentials, settings: Config):
    try:
        return await local_mcp(credentials.credentials, settings.internal_api_url)
    except Exception:
        raise HTTPException(503, "Local MCP server is unavailable.") from None


@router.post("/invoke")
async def invoke(payload: ToolRequest, user: CurrentUser, credentials: Credentials, settings: Config):
    if payload.name not in ALLOWED_TOOLS:
        raise HTTPException(422, "Only the documented read-only tools may be called.")
    try:
        return await local_mcp(credentials.credentials, settings.internal_api_url, payload.name, payload.arguments)
    except Exception:
        raise HTTPException(503, "Local MCP call failed or exceeded its timeout.") from None
