"""Agent management routes for the TRUST Protocol API.

Provides CRUD operations and lifecycle management (suspend, revoke, trust
tier promotion) for registered agents.  All endpoints require admin
authentication.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from trust_protocol.api.middleware import get_services, require_admin
from trust_protocol.api.schemas import (
    AgentRegisterRequest,
    AgentRegisterResponse,
    AgentResponse,
    TrustLevelUpdateRequest,
)
from trust_protocol.core.agent_identity import (
    AgentDefinition,
    AgentIdentity,
    AgentRegistry,
)
from trust_protocol.core.audit_chain import (
    AGENT_REGISTERED,
    AGENT_REVOKED,
    AGENT_SUSPENDED,
    AuditChain,
)
from trust_protocol.core.token_authority import TokenAuthority
from trust_protocol.core.trust_tiers import TrustTier

router = APIRouter(prefix="/v1/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _identity_to_response(identity: AgentIdentity) -> dict:
    """Convert an AgentIdentity to a dict matching AgentResponse fields."""
    return {
        "agent_id": identity.agent_id,
        "name": identity.definition.name,
        "agent_type": identity.definition.agent_type,
        "description": identity.definition.description,
        "trust_tier": identity.trust_tier.name,
        "status": identity.status,
        "created_at": identity.created_at.isoformat(),
        "last_active": identity.last_active.isoformat(),
        "required_credentials": identity.definition.required_credentials,
        "capabilities": identity.definition.capabilities,
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=AgentRegisterResponse, status_code=201)
async def register_agent(
    body: AgentRegisterRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Register a new agent and return its identity including the API key.

    The API key is only returned once at registration time.  If the caller
    loses it, the agent must be re-registered.
    """
    registry: AgentRegistry = services["registry"]
    audit: AuditChain = services["audit_chain"]

    definition = AgentDefinition(
        name=body.name,
        agent_type=body.agent_type,
        description=body.description,
        required_credentials=body.required_credentials,
        network_access=body.network_access,
        capabilities=body.capabilities,
        executable_path=body.executable_path,
        executable_hash=body.executable_hash,
        metadata=body.metadata,
    )

    try:
        identity = registry.register(definition)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    audit.log(
        AGENT_REGISTERED,
        identity.agent_id,
        {
            "name": definition.name,
            "agent_type": definition.agent_type,
            "trust_tier": identity.trust_tier.name,
        },
    )

    response_data = _identity_to_response(identity)
    response_data["api_key"] = identity.api_key
    return AgentRegisterResponse(**response_data)


@router.get("", response_model=List[AgentResponse])
async def list_agents(
    status: Optional[str] = Query(None, description="Filter by agent status"),
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """List all registered agents, optionally filtered by status."""
    registry: AgentRegistry = services["registry"]
    agents = registry.list_agents(status=status)
    return [AgentResponse(**_identity_to_response(a)) for a in agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: str,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Get a single agent by ID."""
    registry: AgentRegistry = services["registry"]
    identity = registry.get(agent_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentResponse(**_identity_to_response(identity))


@router.patch("/{agent_id}/trust-level", response_model=AgentResponse)
async def update_trust_level(
    agent_id: str,
    body: TrustLevelUpdateRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Promote or demote an agent to a new trust tier."""
    registry: AgentRegistry = services["registry"]
    audit: AuditChain = services["audit_chain"]

    identity = registry.get(agent_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    old_tier = identity.trust_tier.name
    new_tier = TrustTier[body.trust_tier]

    success = registry.promote(agent_id, new_tier)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")

    audit.log(
        "TRUST_LEVEL_CHANGED",
        agent_id,
        {"old_tier": old_tier, "new_tier": new_tier.name},
    )

    # Re-fetch to get the updated state.
    updated = registry.get(agent_id)
    return AgentResponse(**_identity_to_response(updated))


@router.post("/{agent_id}/suspend", response_model=AgentResponse)
async def suspend_agent(
    agent_id: str,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Suspend an agent and revoke all its active tokens."""
    registry: AgentRegistry = services["registry"]
    audit: AuditChain = services["audit_chain"]
    ta: TokenAuthority = services["token_authority"]

    identity = registry.get(agent_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    success = registry.update_status(agent_id, "suspended")
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")

    revoked_count = ta.revoke_all_for_agent(agent_id)

    audit.log(
        AGENT_SUSPENDED,
        agent_id,
        {"tokens_revoked": revoked_count},
    )

    updated = registry.get(agent_id)
    return AgentResponse(**_identity_to_response(updated))


@router.post("/{agent_id}/revoke", response_model=AgentResponse)
async def revoke_agent(
    agent_id: str,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Revoke an agent and revoke all its active tokens.

    A revoked agent cannot be reactivated; a new agent must be registered.
    """
    registry: AgentRegistry = services["registry"]
    audit: AuditChain = services["audit_chain"]
    ta: TokenAuthority = services["token_authority"]

    identity = registry.get(agent_id)
    if identity is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    success = registry.update_status(agent_id, "revoked")
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")

    revoked_count = ta.revoke_all_for_agent(agent_id)

    audit.log(
        AGENT_REVOKED,
        agent_id,
        {"tokens_revoked": revoked_count},
    )

    updated = registry.get(agent_id)
    return AgentResponse(**_identity_to_response(updated))
