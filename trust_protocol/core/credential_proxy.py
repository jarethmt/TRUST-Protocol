"""Zero-knowledge credential proxy for the TRUST Protocol.

Agents can execute HTTP requests that require credentials without ever
seeing the credential values. The proxy injects credentials at runtime
and returns only the HTTP response.

Two access modes:
- **execute**: Agent provides a request template with placeholders.
  The proxy substitutes the credential and executes the request.
- **proxy_value**: For PARTNER+ agents. Issues a single-use, time-limited
  token that can be exchanged for the raw credential value. Every exchange
  is logged to the audit chain.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request template
# ---------------------------------------------------------------------------

@dataclass
class RequestTemplate:
    """HTTP request template with credential placeholders.

    Placeholders use the format ``{{CREDENTIAL}}`` and are replaced
    with the actual credential value at execution time.

    Example::

        RequestTemplate(
            method="POST",
            url="https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer {{CREDENTIAL}}"},
            body={"model": "gpt-4", "messages": [...]},
        )
    """

    method: str = "GET"
    url: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    timeout_seconds: int = 30

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "body": self.body,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RequestTemplate:
        return cls(
            method=data.get("method", "GET"),
            url=data.get("url", ""),
            headers=data.get("headers", {}),
            body=data.get("body"),
            timeout_seconds=data.get("timeout_seconds", 30),
        )


# ---------------------------------------------------------------------------
# Execution result
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    """Result of a proxied HTTP request."""

    status_code: int
    headers: Dict[str, str]
    body: str
    execution_time_ms: float
    credential_name: str
    agent_id: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
            "execution_time_ms": self.execution_time_ms,
            "credential_name": self.credential_name,
            "agent_id": self.agent_id,
        }


# ---------------------------------------------------------------------------
# Proxy value token
# ---------------------------------------------------------------------------

@dataclass
class ProxyValueToken:
    """Single-use, time-limited token for credential value access.

    PARTNER tier and above only. The token can be exchanged exactly
    once for the raw credential value within its TTL window.
    """

    token_id: str
    credential_name: str
    agent_id: str
    created_at: datetime
    expires_at: datetime
    used: bool = False
    used_at: Optional[datetime] = None

    def is_valid(self) -> bool:
        """True if token is unused and not expired."""
        return not self.used and datetime.now(timezone.utc) < self.expires_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_id": self.token_id,
            "credential_name": self.credential_name,
            "agent_id": self.agent_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "used": self.used,
            "used_at": self.used_at.isoformat() if self.used_at else None,
        }


# ---------------------------------------------------------------------------
# Credential proxy
# ---------------------------------------------------------------------------

PLACEHOLDER_PATTERN = re.compile(r"\{\{CREDENTIAL\}\}")


class CredentialProxy:
    """Executes HTTP requests with credential injection.

    The proxy never returns credential values to the caller in execute
    mode. In proxy-value mode, it issues single-use tokens with a
    configurable TTL (default 60 seconds).
    """

    def __init__(self, proxy_value_ttl_seconds: int = 60) -> None:
        self._proxy_value_ttl = proxy_value_ttl_seconds
        # In-memory store for proxy value tokens
        self._proxy_tokens: Dict[str, ProxyValueToken] = {}

    def _inject_credential(self, template_str: str, credential_value: str) -> str:
        """Replace ``{{CREDENTIAL}}`` placeholders with the actual value."""
        return PLACEHOLDER_PATTERN.sub(credential_value, template_str)

    async def execute(
        self,
        template: RequestTemplate,
        credential_value: str,
        credential_name: str,
        agent_id: str,
    ) -> ExecutionResult:
        """Execute an HTTP request with the credential injected.

        The credential value is substituted into URL, headers, and body
        wherever ``{{CREDENTIAL}}`` appears. The agent never sees the raw
        credential -- only the HTTP response is returned.
        """
        start = time.monotonic()

        # Inject credential into URL
        url = self._inject_credential(template.url, credential_value)

        # Inject into headers
        headers = {}
        for k, v in template.headers.items():
            headers[k] = self._inject_credential(v, credential_value)

        # Inject into body
        body = None
        if template.body is not None:
            body_str = json.dumps(template.body)
            body_str = self._inject_credential(body_str, credential_value)
            body = json.loads(body_str)

        # Execute the request
        async with httpx.AsyncClient(timeout=template.timeout_seconds) as client:
            response = await client.request(
                method=template.method.upper(),
                url=url,
                headers=headers,
                json=body if body else None,
            )

        elapsed_ms = (time.monotonic() - start) * 1000

        # Pass through response headers (credential should not leak here
        # because we only injected it into the *request*).
        safe_headers = dict(response.headers)

        result = ExecutionResult(
            status_code=response.status_code,
            headers=safe_headers,
            body=response.text,
            execution_time_ms=round(elapsed_ms, 2),
            credential_name=credential_name,
            agent_id=agent_id,
        )

        logger.info(
            "Proxy execute: agent=%s credential=%s status=%d time=%.1fms",
            agent_id,
            credential_name,
            response.status_code,
            elapsed_ms,
        )

        return result

    def issue_proxy_value(
        self,
        credential_name: str,
        agent_id: str,
    ) -> ProxyValueToken:
        """Issue a single-use proxy value token.

        The token can be exchanged for the raw credential value exactly
        once within the TTL window. PARTNER tier and above only.
        """
        now = datetime.now(timezone.utc)
        token = ProxyValueToken(
            token_id=f"pv_{secrets.token_urlsafe(24)}",
            credential_name=credential_name,
            agent_id=agent_id,
            created_at=now,
            expires_at=now + timedelta(seconds=self._proxy_value_ttl),
        )
        self._proxy_tokens[token.token_id] = token

        logger.info(
            "Issued proxy-value token %s for agent=%s credential=%s (TTL=%ds)",
            token.token_id,
            agent_id,
            credential_name,
            self._proxy_value_ttl,
        )

        return token

    def exchange_proxy_value(
        self,
        token_id: str,
    ) -> Optional[ProxyValueToken]:
        """Mark a proxy value token as used.

        Returns the token if valid, ``None`` if expired, already used, or
        not found.  The caller is responsible for providing the actual
        credential value after this validation succeeds.
        """
        token = self._proxy_tokens.get(token_id)
        if token is None:
            return None

        if not token.is_valid():
            return None

        # Mark as used (single-use)
        token.used = True
        token.used_at = datetime.now(timezone.utc)

        logger.info(
            "Exchanged proxy-value token %s for agent=%s credential=%s",
            token_id,
            token.agent_id,
            token.credential_name,
        )

        return token

    def cleanup_expired(self) -> int:
        """Remove expired proxy value tokens from memory.

        Returns the number of tokens purged.
        """
        now = datetime.now(timezone.utc)
        expired = [
            tid
            for tid, tok in self._proxy_tokens.items()
            if now > tok.expires_at
        ]
        for tid in expired:
            del self._proxy_tokens[tid]
        return len(expired)
