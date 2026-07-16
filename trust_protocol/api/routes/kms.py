"""KMS routes -- envelope encryption for data keys the caller must use itself.

``generate`` (KMS GenerateDataKey), ``wrap``, and ``unwrap``. All require an unsealed server and a
PARTNER+ agent (same bar as credential proxy-value); every operation is recorded in the audit chain.
"""
from __future__ import annotations

import base64
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from trust_protocol.api.middleware import get_services, require_agent
from trust_protocol.config import get_config
from trust_protocol.core.agent_identity import AgentIdentity
from trust_protocol.core.audit_chain import AuditChain, KMS_GENERATE, KMS_UNWRAP, KMS_WRAP
from trust_protocol.core.kms import KMS
from trust_protocol.core.seal import get_seal_manager
from trust_protocol.core.trust_tiers import can_access

router = APIRouter(prefix="/v1/kms", tags=["kms"])


def _kms() -> KMS:
    seal = get_seal_manager()
    if seal.is_sealed:
        raise HTTPException(status_code=503, detail="Server is sealed. Run 'trust-protocol unseal'.")
    # KMS keeps its own persistent salt (independent of the credential vault's lazy init). Created once,
    # then stable — wrapped blobs stay recoverable across restarts as long as this + the password hold.
    salt_file = get_config().data_dir / ".kms_salt"
    if salt_file.exists():
        salt = salt_file.read_bytes()
    else:
        salt = os.urandom(16)
        salt_file.write_bytes(salt)
        salt_file.chmod(0o600)
    return KMS(seal.get_vault_password(), salt)


def _require_partner(agent: AgentIdentity) -> None:
    if not can_access(agent.trust_tier, "proxy_value"):
        raise HTTPException(status_code=403, detail="PARTNER tier or above required for KMS")


def _aad(b64: str) -> bytes:
    return base64.b64decode(b64) if b64 else b""


class GenerateRequest(BaseModel):
    bytes: int = Field(default=32, ge=16, le=64, description="data key length")
    aad: str = Field(default="", description="optional base64 additional authenticated data")


class WrapRequest(BaseModel):
    plaintext: str = Field(..., description="base64 data key to wrap")
    aad: str = Field(default="")


class UnwrapRequest(BaseModel):
    wrapped: str = Field(..., description="base64 wrapped blob")
    aad: str = Field(default="")


@router.post("/generate")
async def generate(
    body: GenerateRequest,
    agent: AgentIdentity = Depends(require_agent),
    services: dict = Depends(get_services),
):
    """Generate a fresh data key; return the plaintext (use once) + the wrapped blob (store at rest)."""
    _require_partner(agent)
    dk, wrapped = _kms().generate_data_key(body.bytes, _aad(body.aad))
    audit: AuditChain = services["audit_chain"]
    audit.log(KMS_GENERATE, agent.agent_id, {"bytes": body.bytes})
    return {"plaintext": base64.b64encode(dk).decode(), "wrapped": base64.b64encode(wrapped).decode()}


@router.post("/wrap")
async def wrap(
    body: WrapRequest,
    agent: AgentIdentity = Depends(require_agent),
    services: dict = Depends(get_services),
):
    _require_partner(agent)
    wrapped = _kms().wrap(base64.b64decode(body.plaintext), _aad(body.aad))
    services["audit_chain"].log(KMS_WRAP, agent.agent_id, {})
    return {"wrapped": base64.b64encode(wrapped).decode()}


@router.post("/unwrap")
async def unwrap(
    body: UnwrapRequest,
    agent: AgentIdentity = Depends(require_agent),
    services: dict = Depends(get_services),
):
    _require_partner(agent)
    audit: AuditChain = services["audit_chain"]
    try:
        pt = _kms().unwrap(base64.b64decode(body.wrapped), _aad(body.aad))
    except Exception:
        audit.log(KMS_UNWRAP, agent.agent_id, {"granted": False})
        raise HTTPException(status_code=400, detail="unwrap failed (bad blob, wrong key, or AAD mismatch)")
    audit.log(KMS_UNWRAP, agent.agent_id, {"granted": True})
    return {"plaintext": base64.b64encode(pt).decode()}
