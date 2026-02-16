"""Authentication middleware and dependency injection for the TRUST Protocol API."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict

from fastapi import Depends, HTTPException, Request

from trust_protocol.config import get_config
from trust_protocol.core.agent_identity import AgentIdentity, AgentRegistry
from trust_protocol.core.audit_chain import AuditChain
from trust_protocol.core.emergency import EmergencyController
from trust_protocol.core.token_authority import TokenAuthority
from trust_protocol.core.vault import CredentialVault


# ---------------------------------------------------------------------------
# Service container (singleton)
# ---------------------------------------------------------------------------

_services: Dict[str, Any] | None = None
_start_time: float = time.time()


def _init_services() -> Dict[str, Any]:
    """Lazily initialize all core services."""
    global _services, _start_time
    if _services is not None:
        return _services

    _start_time = time.time()
    cfg = get_config()

    emergency = EmergencyController(cfg.data_dir)
    registry = AgentRegistry(cfg.agents_dir)
    token_authority = TokenAuthority(
        secret_key=cfg.secret_key.encode(),
        data_dir=cfg.data_dir,
    )
    audit_chain = AuditChain(
        data_dir=cfg.audit_dir,
        secret_key=cfg.secret_key.encode(),
    )
    vault = CredentialVault(cfg.credentials_dir)

    _services = {
        "config": cfg,
        "emergency": emergency,
        "registry": registry,
        "token_authority": token_authority,
        "audit_chain": audit_chain,
        "vault": vault,
        "start_time": _start_time,
    }
    return _services


def get_services() -> Dict[str, Any]:
    """FastAPI dependency that returns the service container."""
    return _init_services()


def reset_services() -> None:
    """Reset for testing."""
    global _services
    _services = None


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------

def _extract_key(request: Request, header_name: str) -> str | None:
    """Extract API key from custom header or Authorization: Bearer."""
    key = request.headers.get(header_name)
    if key:
        return key
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


async def require_admin(request: Request) -> None:
    """Dependency: require a valid admin key."""
    key = _extract_key(request, "X-Admin-Key")
    if not key:
        raise HTTPException(status_code=401, detail="Admin key required")

    cfg = get_config()
    if key != cfg.admin_key:
        raise HTTPException(status_code=401, detail="Invalid admin key")


async def require_agent(
    request: Request,
    services: Dict[str, Any] = Depends(get_services),
) -> AgentIdentity:
    """Dependency: require a valid agent API key. Returns the AgentIdentity."""
    key = _extract_key(request, "X-Agent-Key")
    if not key:
        raise HTTPException(status_code=401, detail="Agent API key required")

    registry: AgentRegistry = services["registry"]
    identity = registry.get_by_api_key(key)
    if identity is None:
        raise HTTPException(status_code=401, detail="Invalid agent API key")

    registry.update_last_active(identity.agent_id)
    return identity


def get_start_time() -> float:
    """Return the server start timestamp."""
    return _start_time
