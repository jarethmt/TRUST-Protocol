"""Token lifecycle routes for the TRUST Protocol API.

Provides endpoints for issuing, validating, renewing, revoking, and listing
agent access tokens.  Most endpoints require admin authentication; the renew
endpoint also accepts agent self-authentication via X-Agent-Key.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response

from trust_protocol.api.middleware import get_services, require_admin
from trust_protocol.api.schemas import (
    TokenIssueRequest,
    TokenRenewRequest,
    TokenResponse,
)
from trust_protocol.core.agent_identity import AgentRegistry
from trust_protocol.core.audit_chain import (
    TOKEN_ISSUED,
    TOKEN_RENEWED,
    TOKEN_REVOKED,
    AuditChain,
)
from trust_protocol.core.token_authority import TokenAuthority

router = APIRouter(prefix="/v1/tokens", tags=["tokens"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("", response_model=TokenResponse, status_code=201)
async def issue_token(
    body: TokenIssueRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Issue a new access token for an agent.

    The agent must exist and be in ``active`` status.  The token's trust tier
    and duration are derived from the agent's current tier.
    """
    registry: AgentRegistry = services["registry"]
    ta: TokenAuthority = services["token_authority"]
    audit: AuditChain = services["audit_chain"]

    agent = registry.get(body.agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Agent is not active (current status: {agent.status})",
        )

    token = ta.issue(
        agent_id=agent.agent_id,
        trust_tier=agent.trust_tier,
        credential_patterns=body.credential_patterns,
    )

    audit.log(
        TOKEN_ISSUED,
        agent.agent_id,
        {
            "token_id": token.token_id,
            "trust_tier": token.trust_tier.name,
            "credential_patterns": token.credential_patterns,
        },
    )

    return TokenResponse(**token.to_dict())


@router.get("/{token_id}", response_model=TokenResponse)
async def get_token(
    token_id: str,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Validate and return a token by ID.

    Returns the token if it exists and is still valid (not expired, HMAC
    intact).  Returns 404 otherwise.
    """
    ta: TokenAuthority = services["token_authority"]

    token = ta.validate(token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found or invalid")

    return TokenResponse(**token.to_dict())


@router.post("/{token_id}/renew", response_model=TokenResponse)
async def renew_token(
    token_id: str,
    body: TokenRenewRequest,
    request: Request,
    services: dict = Depends(get_services),
):
    """Renew a token, extending its lifetime.

    Accepts either admin authentication (X-Admin-Key / Authorization: Bearer)
    or agent self-authentication (X-Agent-Key).  When using agent auth, the
    token must belong to the requesting agent.

    Renewal may be denied if the token has expired, the maximum renewal count
    has been reached, or the behavior score is below the tier threshold.
    """
    ta: TokenAuthority = services["token_authority"]
    audit: AuditChain = services["audit_chain"]

    # --- Determine authentication method ---
    agent_key = request.headers.get("X-Agent-Key")
    if agent_key:
        # Agent self-authentication: verify the key and token ownership.
        registry: AgentRegistry = services["registry"]
        agent = registry.get_by_api_key(agent_key)
        if agent is None:
            raise HTTPException(status_code=401, detail="Invalid agent API key")

        current = ta.validate(token_id)
        if current is None:
            raise HTTPException(
                status_code=404, detail="Token not found or invalid"
            )
        if current.agent_id != agent.agent_id:
            raise HTTPException(
                status_code=403, detail="Token does not belong to this agent"
            )
    else:
        # Fall back to admin authentication.
        admin_key = request.headers.get("X-Admin-Key") or ""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            admin_key = admin_key or auth_header[7:]

        cfg = services["config"]
        if admin_key != cfg.admin_key:
            raise HTTPException(
                status_code=401, detail="Admin key or agent key required"
            )

    # --- Perform the renewal ---
    new_token = ta.renew(token_id, body.behavior_score)
    if new_token is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Renewal denied: token expired, max renewals reached, "
                "or behavior score too low"
            ),
        )

    audit.log(
        TOKEN_RENEWED,
        new_token.agent_id,
        {
            "token_id": new_token.token_id,
            "renewal_count": new_token.renewal_count,
        },
    )

    return TokenResponse(**new_token.to_dict())


@router.delete("/{token_id}", status_code=204)
async def revoke_token(
    token_id: str,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Revoke a single token by ID."""
    ta: TokenAuthority = services["token_authority"]
    audit: AuditChain = services["audit_chain"]

    # Capture agent_id before revocation for the audit log.
    existing = ta.validate(token_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Token not found or invalid")

    agent_id = existing.agent_id
    success = ta.revoke(token_id)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")

    audit.log(
        TOKEN_REVOKED,
        agent_id,
        {"token_id": token_id},
    )

    return Response(status_code=204)


@router.get("", response_model=List[TokenResponse])
async def list_tokens(
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """List all active tokens, optionally filtered by agent ID."""
    ta: TokenAuthority = services["token_authority"]
    tokens = ta.list_tokens(agent_id=agent_id)
    return [TokenResponse(**t.to_dict()) for t in tokens]
