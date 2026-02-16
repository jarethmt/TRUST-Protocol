"""Pydantic request/response schemas for the TRUST Protocol API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# --- Health ---

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    uptime_seconds: float


# --- Agents ---

class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    agent_type: str = Field(..., min_length=1, max_length=64)
    description: str = Field(default="")
    required_credentials: List[str] = Field(default_factory=list)
    network_access: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)
    executable_path: Optional[str] = None
    executable_hash: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    agent_id: str
    name: str
    agent_type: str
    description: str
    trust_tier: str
    status: str
    created_at: str
    last_active: str
    required_credentials: List[str] = Field(default_factory=list)
    capabilities: List[str] = Field(default_factory=list)


class AgentRegisterResponse(AgentResponse):
    api_key: str  # Only returned once at registration


class TrustLevelUpdateRequest(BaseModel):
    trust_tier: str = Field(..., pattern="^(NOVICE|COMPANION|PARTNER|GUARDIAN|SACRED)$")


# --- Tokens ---

class TokenIssueRequest(BaseModel):
    agent_id: str
    credential_patterns: List[str] = Field(default_factory=lambda: ["*"])


class TokenResponse(BaseModel):
    token_id: str
    agent_id: str
    trust_tier: str
    credential_patterns: List[str]
    issued_at: str
    expires_at: str
    renewal_count: int
    max_renewals: int


class TokenRenewRequest(BaseModel):
    behavior_score: float = Field(default=1.0, ge=0.0, le=1.0)


# --- Credentials ---

class CredentialStoreRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    credential_data: Dict[str, Any]
    minimum_trust: str = Field(default="COMPANION", pattern="^(NOVICE|COMPANION|PARTNER|GUARDIAN|SACRED)$")


class CredentialResponse(BaseModel):
    name: str
    minimum_trust: str
    created: str
    last_accessed: Optional[str] = None
    access_count: int = 0


class CredentialExecuteRequest(BaseModel):
    agent_id: str
    purpose: str = Field(..., min_length=1)
    duration_minutes: int = Field(default=30, ge=1, le=1440)


# --- Emergency ---

class EmergencyActivateRequest(BaseModel):
    reason: str = Field(..., min_length=1)
    scope: str = Field(default="global", pattern="^(global|agent|credential)$")
    agent_id: Optional[str] = None
    credential_name: Optional[str] = None


class EmergencyClearRequest(BaseModel):
    scope: str = Field(default="global", pattern="^(global|agent|credential)$")
    confirmation: str = Field(default="")
    agent_id: Optional[str] = None
    credential_name: Optional[str] = None


class EmergencyStatusResponse(BaseModel):
    global_active: bool
    global_details: Optional[Dict[str, Any]] = None
    blocked_agents: List[Dict[str, Any]] = Field(default_factory=list)
    blocked_credentials: List[Dict[str, Any]] = Field(default_factory=list)


# --- Audit ---

class AuditEntryResponse(BaseModel):
    seq: int
    timestamp: str
    event_type: str
    agent_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    previous_hash: str
    hash: str
    hmac: str


class AuditVerifyResponse(BaseModel):
    valid: bool
    message: str


# --- Generic ---

class ErrorResponse(BaseModel):
    detail: str
