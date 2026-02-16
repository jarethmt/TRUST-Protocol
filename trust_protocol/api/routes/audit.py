"""Audit trail routes for the TRUST Protocol API.

Provides read-only access to the HMAC-signed, hash-chained audit log.
All endpoints require admin authentication.  The audit chain is
append-only and cryptographically verifiable -- these routes expose
query, verification, counting, and export capabilities.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

from trust_protocol.api.middleware import get_services, require_admin
from trust_protocol.api.schemas import AuditEntryResponse, AuditVerifyResponse
from trust_protocol.core.audit_chain import AuditChain

router = APIRouter(prefix="/v1/audit", tags=["audit"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("", response_model=list[AuditEntryResponse])
async def query_audit(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    agent_id: Optional[str] = Query(None, description="Filter by agent ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum entries to return"),
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Query audit log entries with optional filtering.

    Results are ordered oldest-first (ascending sequence number).  Use
    ``event_type`` and ``agent_id`` to narrow the results, and ``limit``
    to cap the number of entries returned (default 100, maximum 1000).
    """
    audit: AuditChain = services["audit_chain"]
    entries = audit.query(event_type=event_type, agent_id=agent_id, limit=limit)
    return entries


@router.get("/verify", response_model=AuditVerifyResponse)
async def verify_audit(
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Verify the integrity of the entire audit chain.

    Walks every entry in the log and checks:
    1. Sequence continuity (no gaps).
    2. Hash-chain linkage (each entry references the previous hash).
    3. Entry hash integrity (recomputed vs. stored).
    4. HMAC authenticity (proves entries were written by this server).

    Returns ``{"valid": true, "message": "OK: N entries verified"}`` on
    success, or ``{"valid": false, "message": "<description>"}`` on the
    first violation found.
    """
    audit: AuditChain = services["audit_chain"]
    valid, message = audit.verify_chain()
    return AuditVerifyResponse(valid=valid, message=message)


@router.get("/count")
async def audit_count(
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Return the total number of entries in the audit chain."""
    audit: AuditChain = services["audit_chain"]
    return {"count": audit.count()}


@router.get("/export")
async def export_audit(
    _admin: None = Depends(require_admin),
    services: dict = Depends(get_services),
):
    """Export the full audit log as JSONL plain text.

    Each line is a self-contained JSON object representing one audit
    entry.  The output can be saved to a file and verified offline
    using the ``verify_chain`` method with the server secret key.
    """
    audit: AuditChain = services["audit_chain"]
    content = audit.export()
    return PlainTextResponse(content=content, media_type="text/plain")
