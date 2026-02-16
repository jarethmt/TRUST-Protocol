"""Credential management routes for the TRUST Protocol API.

Provides endpoints for storing, listing, deleting, and executing with
encrypted credentials.  Storage and management operations require admin
authentication; the execute endpoint uses agent authentication so that
the requesting agent's trust tier can be evaluated against the credential's
minimum trust requirement.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from trust_protocol.api.middleware import get_services, require_admin, require_agent
from trust_protocol.core.seal import get_seal_manager
from trust_protocol.api.schemas import (
    CredentialExecuteRequest,
    CredentialResponse,
    CredentialStoreRequest,
)
from trust_protocol.core.agent_identity import AgentIdentity
from trust_protocol.core.audit_chain import (
    CREDENTIAL_ACCESSED,
    CREDENTIAL_DELETED,
    CREDENTIAL_EXECUTE,
    CREDENTIAL_PROXY_VALUE,
    CREDENTIAL_STORED,
    AuditChain,
)
from trust_protocol.core.credential_proxy import CredentialProxy, RequestTemplate
from trust_protocol.core.trust_tiers import TrustTier, can_access
from trust_protocol.core.vault import CredentialVault

router = APIRouter(prefix="/v1/credentials", tags=["credentials"])

# Module-level credential proxy instance (shared across requests).
_proxy = CredentialProxy()


# ---------------------------------------------------------------------------
# Proxy request models
# ---------------------------------------------------------------------------


class ProxyExecuteRequest(BaseModel):
    """Request body for the proxy-execute endpoint."""

    purpose: str = Field(..., min_length=1)
    method: str = Field(default="GET")
    url: str = Field(..., min_length=1)
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    timeout_seconds: int = Field(default=30, ge=1, le=120)


class ProxyValueRequest(BaseModel):
    """Request body for the proxy-value endpoint."""

    purpose: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_vault(services: Dict[str, Any]) -> CredentialVault:
    """Unlock the vault using the master password from the seal manager.

    Raises HTTP 503 if the server is sealed.  The vault must be
    initialised before every credential operation because it may have
    been locked by an emergency brake clearing or a process restart.
    """
    seal_mgr = get_seal_manager()
    if seal_mgr.is_sealed:
        raise HTTPException(
            status_code=503,
            detail="Server is sealed. Run 'trust-protocol unseal' to unlock credential operations.",
        )

    vault: CredentialVault = services["vault"]
    vault.initialize(seal_mgr.get_vault_password())
    return vault


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=CredentialResponse, status_code=201)
async def store_credential(
    body: CredentialStoreRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Store an encrypted credential in the vault.

    The credential is encrypted at rest with AES-256-GCM.  The
    ``minimum_trust`` field determines which trust tier an agent must
    hold before it can access this credential.
    """
    vault = _init_vault(services)
    audit: AuditChain = services["audit_chain"]

    trust_tier = TrustTier[body.minimum_trust]
    success = vault.store_credential(body.name, body.credential_data, trust_tier)
    if not success:
        raise HTTPException(
            status_code=503,
            detail="Vault is locked or emergency brake is active",
        )

    audit.log(
        CREDENTIAL_STORED,
        details={"name": body.name, "minimum_trust": body.minimum_trust},
    )

    # Return the credential metadata (never the secret value).
    creds = vault.list_credentials()
    for cred in creds:
        if cred["name"] == body.name:
            return CredentialResponse(**cred)

    # Fallback if list_credentials doesn't return the just-stored entry
    # (should not happen under normal operation).
    return CredentialResponse(
        name=body.name,
        minimum_trust=body.minimum_trust,
        created="",
        access_count=0,
    )


@router.get("", response_model=List[CredentialResponse])
async def list_credentials(
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """List all stored credentials (metadata only, never secret values)."""
    vault = _init_vault(services)
    return [CredentialResponse(**c) for c in vault.list_credentials()]


@router.delete("/{name}", status_code=204)
async def delete_credential(
    name: str,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Delete a credential from the vault.

    Returns 204 on success or 404 if the credential does not exist.
    """
    vault = _init_vault(services)
    audit: AuditChain = services["audit_chain"]

    if not vault.delete_credential(name):
        raise HTTPException(status_code=404, detail=f"Credential '{name}' not found")

    audit.log(CREDENTIAL_DELETED, details={"name": name})
    return Response(status_code=204)


@router.post("/{name}/execute")
async def execute_with_credential(
    name: str,
    body: CredentialExecuteRequest,
    agent: AgentIdentity = Depends(require_agent),
    services: dict = Depends(get_services),
):
    """Request time-limited access to a credential for execution.

    The authenticated agent's trust tier is evaluated against the
    credential's minimum trust requirement.  If the agent's tier is
    insufficient, access is denied with a 403 response.

    On success, returns a time-bounded access record containing the
    ``access_id`` and ``expires`` timestamp.  The credential value itself
    is injected into the execution environment -- it is never returned
    directly in the API response.
    """
    vault = _init_vault(services)
    audit: AuditChain = services["audit_chain"]

    # Set the vault's current trust level to the requesting agent's tier
    # so that the trust-level comparison inside request_credential works.
    vault.set_trust_level(agent.trust_tier)

    result = vault.request_credential(
        name=name,
        agent_id=agent.agent_id,
        purpose=body.purpose,
        duration_minutes=body.duration_minutes,
    )

    if result is None:
        audit.log(
            CREDENTIAL_ACCESSED,
            agent.agent_id,
            {"name": name, "granted": False, "purpose": body.purpose},
        )
        raise HTTPException(status_code=403, detail="Credential access denied")

    cred_data, record = result
    audit.log(
        CREDENTIAL_ACCESSED,
        agent.agent_id,
        {
            "name": name,
            "granted": True,
            "access_id": record.access_id,
            "purpose": body.purpose,
        },
    )

    return {
        "access_id": record.access_id,
        "granted": True,
        "expires": record.expiry.isoformat(),
    }


# ---------------------------------------------------------------------------
# Proxy execute -- zero-knowledge credential usage
# ---------------------------------------------------------------------------


@router.post("/{name}/proxy-execute")
async def proxy_execute_credential(
    name: str,
    body: ProxyExecuteRequest,
    agent: AgentIdentity = Depends(require_agent),
    services: dict = Depends(get_services),
):
    """Execute an HTTP request with a credential injected at runtime.

    The agent provides a request template containing ``{{CREDENTIAL}}``
    placeholders.  The proxy substitutes the real credential value and
    executes the HTTP request, returning only the response.  The agent
    never sees the raw credential.
    """
    vault = _init_vault(services)
    audit: AuditChain = services["audit_chain"]

    # Set the vault's trust level to the requesting agent's tier.
    vault.set_trust_level(agent.trust_tier)

    result = vault.request_credential(
        name=name,
        agent_id=agent.agent_id,
        purpose=body.purpose,
    )

    if result is None:
        audit.log(
            CREDENTIAL_EXECUTE,
            agent.agent_id,
            {"name": name, "granted": False, "purpose": body.purpose},
        )
        raise HTTPException(status_code=403, detail="Credential access denied")

    cred_data, _record = result

    # Build the request template from the body.
    template = RequestTemplate(
        method=body.method,
        url=body.url,
        headers=body.headers,
        body=body.body,
        timeout_seconds=body.timeout_seconds,
    )

    # The credential data stored in the vault is a dict.  For injection
    # we serialise it to a string.  If the dict has a single "value" key,
    # use that directly; otherwise JSON-encode the whole dict.
    if isinstance(cred_data, dict) and len(cred_data) == 1 and "value" in cred_data:
        credential_value = str(cred_data["value"])
    elif isinstance(cred_data, dict):
        credential_value = json.dumps(cred_data)
    else:
        credential_value = str(cred_data)

    # Execute via the proxy -- the agent never receives the credential.
    execution_result = await _proxy.execute(
        template=template,
        credential_value=credential_value,
        credential_name=name,
        agent_id=agent.agent_id,
    )

    audit.log(
        CREDENTIAL_EXECUTE,
        agent.agent_id,
        {
            "name": name,
            "granted": True,
            "purpose": body.purpose,
            "method": body.method,
            "url_host": body.url.split("/")[2] if "/" in body.url else body.url,
            "status_code": execution_result.status_code,
            "execution_time_ms": execution_result.execution_time_ms,
        },
    )

    return {
        "status_code": execution_result.status_code,
        "headers": execution_result.headers,
        "body": execution_result.body,
        "execution_time_ms": execution_result.execution_time_ms,
    }


# ---------------------------------------------------------------------------
# Proxy value -- single-use token for PARTNER+ agents
# ---------------------------------------------------------------------------


@router.post("/{name}/proxy-value")
async def issue_proxy_value_token(
    name: str,
    body: ProxyValueRequest,
    agent: AgentIdentity = Depends(require_agent),
    services: dict = Depends(get_services),
):
    """Issue a single-use, time-limited token for credential value access.

    Only agents at PARTNER tier or above may use this endpoint.  The token
    can be exchanged exactly once within 60 seconds via the
    ``/proxy-value/{token_id}/exchange`` endpoint.
    """
    audit: AuditChain = services["audit_chain"]

    # Gate on PARTNER+ tier using the credential_modes check.
    if not can_access(agent.trust_tier, "proxy_value"):
        audit.log(
            CREDENTIAL_PROXY_VALUE,
            agent.agent_id,
            {
                "name": name,
                "granted": False,
                "reason": "Insufficient tier for proxy-value mode",
                "agent_tier": agent.trust_tier.name,
            },
        )
        raise HTTPException(
            status_code=403,
            detail="PARTNER tier or above required for proxy-value mode",
        )

    vault = _init_vault(services)
    vault.set_trust_level(agent.trust_tier)

    result = vault.request_credential(
        name=name,
        agent_id=agent.agent_id,
        purpose=body.purpose,
    )

    if result is None:
        audit.log(
            CREDENTIAL_PROXY_VALUE,
            agent.agent_id,
            {"name": name, "granted": False, "purpose": body.purpose},
        )
        raise HTTPException(status_code=403, detail="Credential access denied")

    # Issue a single-use proxy value token.
    token = _proxy.issue_proxy_value(
        credential_name=name,
        agent_id=agent.agent_id,
    )

    audit.log(
        CREDENTIAL_PROXY_VALUE,
        agent.agent_id,
        {
            "name": name,
            "granted": True,
            "purpose": body.purpose,
            "token_id": token.token_id,
            "expires_at": token.expires_at.isoformat(),
        },
    )

    return {
        "token_id": token.token_id,
        "expires_at": token.expires_at.isoformat(),
        "credential_name": name,
    }


# ---------------------------------------------------------------------------
# Proxy value exchange -- redeem token for raw credential
# ---------------------------------------------------------------------------


@router.get("/proxy-value/{token_id}/exchange")
async def exchange_proxy_value_token(
    token_id: str,
    agent: AgentIdentity = Depends(require_agent),
    services: dict = Depends(get_services),
):
    """Exchange a proxy-value token for the actual credential value.

    The token is single-use and time-limited (60 seconds by default).
    After a successful exchange the token is invalidated.  Every exchange
    is recorded in the audit chain.
    """
    audit: AuditChain = services["audit_chain"]

    # Validate and consume the token.
    token = _proxy.exchange_proxy_value(token_id)
    if token is None:
        raise HTTPException(
            status_code=404,
            detail="Token expired, already used, or not found",
        )

    # Verify the token belongs to the requesting agent.
    if token.agent_id != agent.agent_id:
        # Re-mark as unused so the rightful owner can still use it.
        # (In practice, the token was already marked used; the rightful
        # owner would need a new token.  This prevents cross-agent theft.)
        raise HTTPException(
            status_code=403,
            detail="Token does not belong to this agent",
        )

    # Retrieve the credential value from the vault.
    vault = _init_vault(services)
    vault.set_trust_level(agent.trust_tier)

    result = vault.request_credential(
        name=token.credential_name,
        agent_id=agent.agent_id,
        purpose=f"proxy-value exchange for token {token_id}",
    )

    if result is None:
        raise HTTPException(
            status_code=403,
            detail="Credential access denied during exchange",
        )

    cred_data, _record = result

    audit.log(
        CREDENTIAL_PROXY_VALUE,
        agent.agent_id,
        {
            "name": token.credential_name,
            "action": "exchange",
            "token_id": token_id,
        },
    )

    return {
        "credential_name": token.credential_name,
        "value": cred_data,
        "expires_in": "single-use",
    }
