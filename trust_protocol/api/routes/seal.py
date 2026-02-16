"""Seal/unseal endpoints for the TRUST Protocol API.

The server starts in a sealed state.  A human operator must provide the
vault master password via the unseal endpoint (or CLI) before credential
operations become available.  Non-credential endpoints (health, agents,
skills, audit) continue to function while sealed.

For development and CI, set ``TRUST_PROTOCOL_VAULT_PASSWORD`` to auto-unseal
at startup.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from trust_protocol.api.middleware import get_services, require_admin
from trust_protocol.core.seal import get_seal_manager
from trust_protocol.core.vault import CredentialVault

router = APIRouter(prefix="/v1", tags=["seal"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class UnsealRequest(BaseModel):
    """Request body for the unseal endpoint."""

    password: str = Field(..., min_length=1)


class SealStatusResponse(BaseModel):
    """Response from the seal-status endpoint."""

    sealed: bool
    vault_initialized: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/unseal")
async def unseal_server(
    body: UnsealRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Unseal the server by providing the vault master password.

    The password is verified against the vault's stored password hash
    (or becomes the vault's master password on first run).  On success
    the password is held only in server process memory -- never written
    to disk or config files.

    Requires admin authentication.
    """
    seal_mgr = get_seal_manager()
    vault: CredentialVault = services["vault"]

    # Verify the password by attempting vault initialization.
    success = vault.initialize(body.password)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Invalid password or emergency brake is active",
        )

    seal_mgr.unseal(body.password)

    return {"sealed": False, "message": "Server unsealed successfully"}


@router.post("/seal")
async def seal_server(
    _admin: None = Depends(require_admin),
):
    """Re-seal the server, clearing the vault password from memory.

    After sealing, all credential operations return 503 until the server
    is unsealed again.  Non-credential endpoints continue to function.

    Requires admin authentication.
    """
    seal_mgr = get_seal_manager()
    seal_mgr.seal()
    return {"sealed": True, "message": "Server sealed. Credential operations disabled."}


@router.get("/seal-status", response_model=SealStatusResponse)
async def seal_status(
    services: dict = Depends(get_services),
):
    """Check whether the server is sealed or unsealed.

    This endpoint does not require authentication so that monitoring
    systems and CLI tools can detect seal state.
    """
    seal_mgr = get_seal_manager()
    vault: CredentialVault = services["vault"]
    return SealStatusResponse(
        sealed=seal_mgr.is_sealed,
        vault_initialized=vault._cipher_suite is not None,
    )
