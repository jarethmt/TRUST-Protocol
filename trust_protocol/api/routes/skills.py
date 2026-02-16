"""Skill signing and publisher management routes for the TRUST Protocol API.

Provides endpoints for:

* **Publisher management** (admin-authenticated): Register publishers,
  list/query publishers, and revoke publisher keys.

* **Skill signing** (admin-authenticated): Create Ed25519-signed skill
  manifests that travel with the skill package.

* **Skill verification** (public, no auth): Verify a signed manifest
  against the publisher's registered public key.  This endpoint is
  intentionally unauthenticated so that *any* agent platform or marketplace
  can verify skills without needing a relationship with the TRUST Protocol
  server.

Two routers are exported from this module:

* ``router`` -- skill signing and verification (``/v1/skills/*``)
* ``publisher_router`` -- publisher management (``/v1/publishers/*``)

Both should be registered in the application factory.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from trust_protocol.api.middleware import get_services, require_admin
from trust_protocol.core.audit_chain import (
    PUBLISHER_REGISTERED,
    PUBLISHER_REVOKED,
    SKILL_SIGNED,
    SKILL_VERIFIED,
    AuditChain,
)
from trust_protocol.core.skill_signer import (
    PublisherRegistry,
    SignedManifest,
    SkillManifest,
    sign_manifest,
    verify_manifest,
)


# ---------------------------------------------------------------------------
# Pydantic request / response schemas
# ---------------------------------------------------------------------------


class PublisherRegisterRequest(BaseModel):
    """Request body for registering a new skill publisher."""

    name: str = Field(..., min_length=1, max_length=128)
    organization: str = Field(default="")
    public_key_pem: str = Field(
        ...,
        description="PEM-encoded Ed25519 public key",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublisherRevokeRequest(BaseModel):
    """Request body for revoking a publisher's key."""

    reason: str = Field(default="", description="Human-readable revocation reason")


class SkillSignRequest(BaseModel):
    """Request body for signing a skill manifest."""

    name: str = Field(..., min_length=1)
    version: str = Field(..., min_length=1)
    publisher_id: str = Field(..., min_length=1)
    code_hash: str = Field(
        ...,
        min_length=1,
        description='SHA-256 hash in "sha256:<hex>" format',
    )
    capabilities: List[str] = Field(default_factory=list)
    credentials_required: List[str] = Field(default_factory=list)
    description: str = ""
    private_key_pem: str = Field(
        ...,
        description="Base64-encoded PEM of the publisher's Ed25519 private key",
    )


class SkillVerifyRequest(BaseModel):
    """Request body for verifying a signed skill manifest."""

    manifest: Dict[str, Any]
    signature: str
    signed_at: str


class SkillVerifyResponse(BaseModel):
    """Response from the skill verification endpoint."""

    verified: bool
    publisher_name: Optional[str] = None
    publisher_trust_tier: Optional[str] = None
    registered_since: Optional[str] = None
    reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Publisher router
# ---------------------------------------------------------------------------

publisher_router = APIRouter(prefix="/v1/publishers", tags=["publishers"])


@publisher_router.post("", status_code=201)
async def register_publisher(
    body: PublisherRegisterRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Register a new skill publisher.

    The caller must supply a PEM-encoded Ed25519 public key.  The
    corresponding private key is never sent to the server -- it remains
    with the publisher for local signing.
    """
    registry = PublisherRegistry(services["config"].publishers_dir)
    audit: AuditChain = services["audit_chain"]

    try:
        publisher = registry.register(
            name=body.name,
            organization=body.organization,
            public_key_pem=body.public_key_pem,
            metadata=body.metadata,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    audit.log(
        PUBLISHER_REGISTERED,
        details={
            "publisher_id": publisher.publisher_id,
            "name": publisher.name,
            "organization": publisher.organization,
            "trust_tier": publisher.trust_tier.name,
        },
    )

    return publisher.to_dict()


@publisher_router.get("")
async def list_publishers(
    status: Optional[str] = Query(None, description="Filter by publisher status"),
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """List all registered publishers, optionally filtered by status."""
    registry = PublisherRegistry(services["config"].publishers_dir)
    publishers = registry.list_publishers(status=status)
    return [p.to_dict() for p in publishers]


@publisher_router.get("/{publisher_id}")
async def get_publisher(
    publisher_id: str,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Get a single publisher by ID."""
    registry = PublisherRegistry(services["config"].publishers_dir)
    publisher = registry.get(publisher_id)
    if publisher is None:
        raise HTTPException(status_code=404, detail="Publisher not found")
    return publisher.to_dict()


@publisher_router.post("/{publisher_id}/revoke-key")
async def revoke_publisher_key(
    publisher_id: str,
    body: PublisherRevokeRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Revoke a publisher's key.

    Once revoked, skills signed by this publisher will fail verification
    because the publisher status is checked before the cryptographic
    signature.  This is the primary defence against a compromised
    publisher key.
    """
    registry = PublisherRegistry(services["config"].publishers_dir)
    audit: AuditChain = services["audit_chain"]

    publisher = registry.get(publisher_id)
    if publisher is None:
        raise HTTPException(status_code=404, detail="Publisher not found")

    success = registry.revoke_key(publisher_id, reason=body.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Publisher not found")

    audit.log(
        PUBLISHER_REVOKED,
        details={
            "publisher_id": publisher_id,
            "name": publisher.name,
            "reason": body.reason,
        },
    )

    # Re-read from disk to get the updated state.
    updated_registry = PublisherRegistry(services["config"].publishers_dir)
    updated = updated_registry.get(publisher_id)
    return updated.to_dict()


# ---------------------------------------------------------------------------
# Skills router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/v1/skills", tags=["skills"])


@router.post("/sign")
async def sign_skill(
    body: SkillSignRequest,
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Sign a skill manifest with the publisher's Ed25519 private key.

    The private key is provided base64-encoded in the request body.  It is
    used only for signing and is never stored.  In production, publishers
    should prefer signing locally with the SDK rather than transmitting
    their private key over the network.
    """
    registry = PublisherRegistry(services["config"].publishers_dir)
    audit: AuditChain = services["audit_chain"]

    # Validate publisher exists and is active.
    publisher = registry.get(body.publisher_id)
    if publisher is None:
        raise HTTPException(status_code=404, detail="Publisher not found")
    if publisher.status != "active":
        raise HTTPException(
            status_code=400,
            detail=f"Publisher is {publisher.status}; cannot sign skills",
        )

    # Build manifest.
    manifest = SkillManifest(
        name=body.name,
        version=body.version,
        publisher_id=body.publisher_id,
        code_hash=body.code_hash,
        capabilities=body.capabilities,
        credentials_required=body.credentials_required,
        description=body.description,
    )

    # Decode private key from base64.
    try:
        private_key_pem = base64.b64decode(body.private_key_pem)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Invalid base64 encoding for private_key_pem",
        )

    # Sign.
    try:
        signed = sign_manifest(manifest, private_key_pem)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Signing failed: {exc}",
        )

    audit.log(
        SKILL_SIGNED,
        details={
            "skill_name": body.name,
            "skill_version": body.version,
            "publisher_id": body.publisher_id,
            "code_hash": body.code_hash,
        },
    )

    return signed.to_dict()


@router.post("/verify", response_model=SkillVerifyResponse)
async def verify_skill(
    body: SkillVerifyRequest,
    services: dict = Depends(get_services),
):
    """Verify a signed skill manifest.

    **This endpoint requires no authentication.**  Any agent platform,
    marketplace, or end user can verify a skill's signature without
    needing admin access or an API key.  This is a deliberate design
    choice: trust verification should be universally accessible.

    The endpoint checks:
    1. The publisher exists and is active.
    2. The Ed25519 signature is valid against the publisher's public key.
    """
    registry = PublisherRegistry(services["config"].publishers_dir)
    audit: AuditChain = services["audit_chain"]

    # Reconstruct the signed manifest from the request body.
    try:
        signed_manifest = SignedManifest.from_dict({
            "manifest": body.manifest,
            "signature": body.signature,
            "signed_at": body.signed_at,
        })
    except (KeyError, ValueError) as exc:
        return SkillVerifyResponse(
            verified=False,
            reason=f"Invalid manifest format: {exc}",
        )

    publisher_id = signed_manifest.manifest.publisher_id

    # Look up publisher.
    publisher = registry.get(publisher_id)
    if publisher is None:
        audit.log(
            SKILL_VERIFIED,
            details={
                "skill_name": signed_manifest.manifest.name,
                "publisher_id": publisher_id,
                "verified": False,
                "reason": "Publisher not found",
            },
        )
        return SkillVerifyResponse(
            verified=False,
            reason="Publisher not found",
        )

    if publisher.status == "revoked":
        audit.log(
            SKILL_VERIFIED,
            details={
                "skill_name": signed_manifest.manifest.name,
                "publisher_id": publisher_id,
                "verified": False,
                "reason": "Publisher revoked",
            },
        )
        return SkillVerifyResponse(
            verified=False,
            publisher_name=publisher.name,
            publisher_trust_tier=publisher.trust_tier.name,
            registered_since=publisher.created_at.isoformat(),
            reason="Publisher revoked",
        )

    # Verify the Ed25519 signature.
    public_key_pem = publisher.public_key_pem.encode("utf-8")
    verified = verify_manifest(signed_manifest, public_key_pem)

    audit.log(
        SKILL_VERIFIED,
        details={
            "skill_name": signed_manifest.manifest.name,
            "skill_version": signed_manifest.manifest.version,
            "publisher_id": publisher_id,
            "publisher_name": publisher.name,
            "verified": verified,
            "reason": None if verified else "Invalid signature",
        },
    )

    if verified:
        return SkillVerifyResponse(
            verified=True,
            publisher_name=publisher.name,
            publisher_trust_tier=publisher.trust_tier.name,
            registered_since=publisher.created_at.isoformat(),
        )
    else:
        return SkillVerifyResponse(
            verified=False,
            publisher_name=publisher.name,
            publisher_trust_tier=publisher.trust_tier.name,
            registered_since=publisher.created_at.isoformat(),
            reason="Invalid signature",
        )
