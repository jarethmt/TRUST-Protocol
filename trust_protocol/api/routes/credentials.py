"""Credential management routes for the TRUST Protocol API.

Provides endpoints for storing, listing, deleting, and executing with
encrypted credentials.  Storage and management operations require admin
authentication; the execute endpoint uses agent authentication so that
the requesting agent's trust tier can be evaluated against the credential's
minimum trust requirement.
"""

from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from trust_protocol.api.middleware import get_services, require_admin, require_agent
from trust_protocol.api.schemas import (
    CredentialExecuteRequest,
    CredentialResponse,
    CredentialStoreRequest,
)
from trust_protocol.core.agent_identity import AgentIdentity
from trust_protocol.core.audit_chain import (
    CREDENTIAL_ACCESSED,
    CREDENTIAL_DELETED,
    CREDENTIAL_STORED,
    AuditChain,
)
from trust_protocol.core.trust_tiers import TrustTier
from trust_protocol.core.vault import CredentialVault

router = APIRouter(prefix="/v1/credentials", tags=["credentials"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_vault(services: Dict[str, Any]) -> CredentialVault:
    """Unlock the vault using the server secret key.

    The vault must be initialised before every operation because it may
    have been locked by an emergency brake clearing or a process restart.
    """
    vault: CredentialVault = services["vault"]
    cfg = services["config"]
    vault.initialize(cfg.secret_key)
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
