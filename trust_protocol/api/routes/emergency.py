"""Emergency control routes for the TRUST Protocol API.

Provides endpoints for activating, clearing, and inspecting the
emergency brake system.  All endpoints require admin authentication.

The emergency brake operates at three granularity levels:

- **Global** -- immediately blocks ALL credential access.
- **Per-agent** -- blocks a specific agent and revokes its tokens.
- **Per-credential** -- blocks access to a specific credential.

Brakes are file-based and survive process restarts.  The global brake
requires a deliberate confirmation string to clear, preventing
accidental re-enablement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from trust_protocol.api.middleware import get_services, require_admin
from trust_protocol.api.schemas import (
    EmergencyActivateRequest,
    EmergencyClearRequest,
    EmergencyStatusResponse,
)
from trust_protocol.core.audit_chain import (
    EMERGENCY_ACTIVATED,
    EMERGENCY_CLEARED,
    AuditChain,
)
from trust_protocol.core.emergency import EmergencyController
from trust_protocol.core.token_authority import TokenAuthority

router = APIRouter(prefix="/v1/emergency", tags=["emergency"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/activate")
async def activate_emergency(
    body: EmergencyActivateRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Activate an emergency brake at the specified scope.

    Scopes:

    - ``"global"`` -- blocks all credential access immediately.
    - ``"agent"`` -- blocks a specific agent (requires ``agent_id``)
      and revokes all of its active tokens.
    - ``"credential"`` -- blocks a specific credential (requires
      ``credential_name``).

    Returns the current emergency status after activation.
    """
    emergency: EmergencyController = services["emergency"]
    audit: AuditChain = services["audit_chain"]
    ta: TokenAuthority = services["token_authority"]

    if body.scope == "global":
        emergency.activate_global(body.reason)
        audit.log(
            EMERGENCY_ACTIVATED,
            details={"scope": "global", "reason": body.reason},
        )

    elif body.scope == "agent":
        if not body.agent_id:
            raise HTTPException(
                status_code=400,
                detail="agent_id is required for agent-scope emergency brake",
            )
        emergency.activate_agent(body.agent_id, body.reason)
        ta.revoke_all_for_agent(body.agent_id)
        audit.log(
            EMERGENCY_ACTIVATED,
            body.agent_id,
            {"scope": "agent", "reason": body.reason},
        )

    elif body.scope == "credential":
        if not body.credential_name:
            raise HTTPException(
                status_code=400,
                detail="credential_name is required for credential-scope emergency brake",
            )
        emergency.activate_credential(body.credential_name, body.reason)
        audit.log(
            EMERGENCY_ACTIVATED,
            details={
                "scope": "credential",
                "credential_name": body.credential_name,
                "reason": body.reason,
            },
        )

    return emergency.status()


@router.post("/clear")
async def clear_emergency(
    body: EmergencyClearRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Clear an emergency brake at the specified scope.

    For global scope, the ``confirmation`` field must be set to
    ``"CONFIRM_RESTORE_ACCESS"`` to prevent accidental clearing.

    Returns the current emergency status after clearing.
    """
    emergency: EmergencyController = services["emergency"]
    audit: AuditChain = services["audit_chain"]

    if body.scope == "global":
        success = emergency.clear_global(body.confirmation)
        if not success:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Failed to clear global brake. Either no global brake is "
                    "active or confirmation is invalid. Use 'CONFIRM_RESTORE_ACCESS'."
                ),
            )
        audit.log(EMERGENCY_CLEARED, details={"scope": "global"})

    elif body.scope == "agent":
        if not body.agent_id:
            raise HTTPException(
                status_code=400,
                detail="agent_id is required for agent-scope emergency clear",
            )
        success = emergency.clear_agent(body.agent_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"No emergency brake active for agent '{body.agent_id}'",
            )
        audit.log(
            EMERGENCY_CLEARED,
            body.agent_id,
            {"scope": "agent"},
        )

    elif body.scope == "credential":
        if not body.credential_name:
            raise HTTPException(
                status_code=400,
                detail="credential_name is required for credential-scope emergency clear",
            )
        success = emergency.clear_credential(body.credential_name)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"No emergency brake active for credential '{body.credential_name}'",
            )
        audit.log(
            EMERGENCY_CLEARED,
            details={
                "scope": "credential",
                "credential_name": body.credential_name,
            },
        )

    return emergency.status()


@router.get("/status", response_model=EmergencyStatusResponse)
async def emergency_status(
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Return the current state of all emergency brakes.

    The response includes:

    - ``global_active`` -- whether the global brake is engaged.
    - ``global_details`` -- activation metadata (reason, timestamp) if active.
    - ``blocked_agents`` -- list of per-agent brakes.
    - ``blocked_credentials`` -- list of per-credential brakes.
    """
    emergency: EmergencyController = services["emergency"]
    return EmergencyStatusResponse(**emergency.status())
