"""
Token Authority -- lifecycle management for agent access tokens.

Refactored from the service-trust-poc ``ServiceTokenAuthority`` to use the
open-source TRUST Protocol primitives.  Key improvements over the original:

- HMAC-SHA256 signatures give every token cryptographic integrity.
- Token duration and renewal limits are derived from ``TrustTier``.
- Credential access is checked via glob-style pattern matching.
- Tokens are held in memory with periodic persistence to disk (they are
  ephemeral by nature; persistence is a convenience, not a guarantee).
"""

from __future__ import annotations

import fnmatch
import hashlib
import hmac
import json
import logging
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from trust_protocol.core.trust_tiers import TrustTier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Renewal behaviour-score thresholds per tier
# ---------------------------------------------------------------------------

_RENEWAL_SCORE_THRESHOLDS: Dict[TrustTier, float] = {
    TrustTier.NOVICE: 0.9,
    TrustTier.COMPANION: 0.8,
    TrustTier.PARTNER: 0.7,
    TrustTier.GUARDIAN: 0.6,
    TrustTier.SACRED: 0.5,
}


# ---------------------------------------------------------------------------
# Agent token
# ---------------------------------------------------------------------------

@dataclass
class AgentToken:
    """A time-locked, HMAC-signed token granting an agent access to a set of
    credentials determined by glob patterns."""

    token_id: str
    agent_id: str
    trust_tier: TrustTier
    credential_patterns: List[str]
    issued_at: datetime
    expires_at: datetime
    hmac_signature: str
    renewal_count: int = 0
    max_renewals: int = 0

    # -- queries -----------------------------------------------------------

    def is_valid(self) -> bool:
        """Return ``True`` if the token has not expired and has not exceeded
        its renewal limit."""
        return (
            datetime.now(timezone.utc) < self.expires_at
            and self.renewal_count <= self.max_renewals
        )

    def can_access_credential(self, name: str) -> bool:
        """Check whether *name* is covered by at least one credential
        pattern.

        Matching rules:
        - ``"*"`` matches everything.
        - ``"cloudflare_*"`` matches any name starting with ``cloudflare_``.
        - An exact string matches only itself.
        """
        for pattern in self.credential_patterns:
            if pattern == name:
                return True
            if fnmatch.fnmatch(name, pattern):
                return True
        return False

    # -- serialisation -----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-serialisable dictionary."""
        return {
            "token_id": self.token_id,
            "agent_id": self.agent_id,
            "trust_tier": self.trust_tier.name,
            "credential_patterns": self.credential_patterns,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "hmac_signature": self.hmac_signature,
            "renewal_count": self.renewal_count,
            "max_renewals": self.max_renewals,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentToken:
        """Reconstruct an ``AgentToken`` from a dictionary (e.g. loaded from
        disk)."""
        return cls(
            token_id=data["token_id"],
            agent_id=data["agent_id"],
            trust_tier=TrustTier[data["trust_tier"]],
            credential_patterns=data["credential_patterns"],
            issued_at=datetime.fromisoformat(data["issued_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            hmac_signature=data["hmac_signature"],
            renewal_count=data.get("renewal_count", 0),
            max_renewals=data.get("max_renewals", 0),
        )


# ---------------------------------------------------------------------------
# Token authority
# ---------------------------------------------------------------------------

class TokenAuthority:
    """Manages the full token lifecycle: issue, validate, renew, revoke.

    Parameters
    ----------
    secret_key:
        Server-side secret used for HMAC-SHA256 token signatures.  Must be
        kept confidential; if it leaks, all outstanding tokens should be
        considered compromised.
    data_dir:
        Directory for optional on-disk persistence of active tokens.  Created
        automatically if it does not exist.
    """

    def __init__(self, secret_key: bytes, data_dir: Path) -> None:
        self._secret_key = secret_key
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._tokens_file = self._data_dir / "agent_tokens.json"

        # Primary in-memory store keyed by token_id.
        self._active: Dict[str, AgentToken] = {}

        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def issue(
        self,
        agent_id: str,
        trust_tier: TrustTier,
        credential_patterns: List[str],
    ) -> AgentToken:
        """Create a new signed token for *agent_id* at the given tier.

        Token duration and maximum renewal count are taken directly from the
        tier definition.
        """
        token_id = f"tok_{secrets.token_urlsafe(24)}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=trust_tier.token_duration_hours)

        signature = self._sign(token_id, agent_id, expires_at)

        token = AgentToken(
            token_id=token_id,
            agent_id=agent_id,
            trust_tier=trust_tier,
            credential_patterns=credential_patterns,
            issued_at=now,
            expires_at=expires_at,
            hmac_signature=signature,
            renewal_count=0,
            max_renewals=trust_tier.max_renewals,
        )

        self._active[token_id] = token
        self._persist()

        logger.info(
            "Issued token %s for agent %s (tier=%s, expires=%s)",
            token_id,
            agent_id,
            trust_tier.name,
            expires_at.isoformat(),
        )
        return token

    def validate(self, token_id: str) -> Optional[AgentToken]:
        """Return the token if it exists, has not expired, and its HMAC is
        intact.  Returns ``None`` otherwise."""
        token = self._active.get(token_id)
        if token is None:
            return None

        if not token.is_valid():
            return None

        expected = self._sign(token.token_id, token.agent_id, token.expires_at)
        if not hmac.compare_digest(expected, token.hmac_signature):
            logger.warning(
                "HMAC mismatch for token %s (agent %s) -- possible tampering",
                token_id,
                token.agent_id,
            )
            return None

        return token

    def renew(
        self,
        token_id: str,
        behavior_score: float = 1.0,
    ) -> Optional[AgentToken]:
        """Attempt to renew a token.

        Renewal succeeds only if:
        1. The token exists and is currently valid.
        2. ``renewal_count < max_renewals``.
        3. ``behavior_score`` meets or exceeds the tier-specific threshold.

        On success the old token is invalidated and a fresh one is returned.
        On failure ``None`` is returned and the old token remains active.
        """
        current = self.validate(token_id)
        if current is None:
            logger.info("Renewal denied for %s: token invalid or not found", token_id)
            return None

        if current.renewal_count >= current.max_renewals:
            logger.info(
                "Renewal denied for %s: max renewals reached (%d/%d)",
                token_id,
                current.renewal_count,
                current.max_renewals,
            )
            return None

        threshold = _RENEWAL_SCORE_THRESHOLDS.get(current.trust_tier, 0.8)
        if behavior_score < threshold:
            logger.info(
                "Renewal denied for %s: behavior_score %.2f < threshold %.2f "
                "(tier %s)",
                token_id,
                behavior_score,
                threshold,
                current.trust_tier.name,
            )
            return None

        # Invalidate old token, then issue a replacement.
        self._remove(token_id)

        new_token_id = f"tok_{secrets.token_urlsafe(24)}"
        now = datetime.now(timezone.utc)
        new_expires = now + timedelta(
            hours=current.trust_tier.token_duration_hours,
        )
        signature = self._sign(new_token_id, current.agent_id, new_expires)

        new_token = AgentToken(
            token_id=new_token_id,
            agent_id=current.agent_id,
            trust_tier=current.trust_tier,
            credential_patterns=current.credential_patterns,
            issued_at=now,
            expires_at=new_expires,
            hmac_signature=signature,
            renewal_count=current.renewal_count + 1,
            max_renewals=current.max_renewals,
        )

        self._active[new_token_id] = new_token
        self._persist()

        logger.info(
            "Renewed token for agent %s: %s -> %s (renewal %d/%d)",
            current.agent_id,
            token_id,
            new_token_id,
            new_token.renewal_count,
            new_token.max_renewals,
        )
        return new_token

    def revoke(self, token_id: str) -> bool:
        """Revoke a single token.  Returns ``True`` if it existed."""
        if token_id not in self._active:
            return False

        agent_id = self._active[token_id].agent_id
        self._remove(token_id)
        self._persist()

        logger.info("Revoked token %s (agent %s)", token_id, agent_id)
        return True

    def revoke_all_for_agent(self, agent_id: str) -> int:
        """Revoke every active token belonging to *agent_id*.

        Returns the number of tokens revoked.
        """
        to_revoke = [
            tid for tid, tok in self._active.items()
            if tok.agent_id == agent_id
        ]
        for tid in to_revoke:
            self._remove(tid)

        if to_revoke:
            self._persist()
            logger.info(
                "Revoked %d token(s) for agent %s", len(to_revoke), agent_id,
            )

        return len(to_revoke)

    def list_tokens(self, agent_id: Optional[str] = None) -> List[AgentToken]:
        """Return active tokens, optionally filtered by *agent_id*."""
        if agent_id is None:
            return list(self._active.values())
        return [
            tok for tok in self._active.values()
            if tok.agent_id == agent_id
        ]

    def cleanup_expired(self) -> int:
        """Remove all expired tokens from the in-memory store.

        Returns the number of tokens removed.
        """
        expired = [
            tid for tid, tok in self._active.items()
            if not tok.is_valid()
        ]
        for tid in expired:
            self._remove(tid)

        if expired:
            self._persist()
            logger.info("Cleaned up %d expired token(s)", len(expired))

        return len(expired)

    # ------------------------------------------------------------------
    # HMAC signing
    # ------------------------------------------------------------------

    def _sign(
        self,
        token_id: str,
        agent_id: str,
        expires_at: datetime,
    ) -> str:
        """Compute HMAC-SHA256 over the canonical token identity string."""
        message = f"{token_id}:{agent_id}:{expires_at.isoformat()}"
        return hmac.new(
            self._secret_key,
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        """Atomically write active tokens to disk."""
        data = {
            "version": "1.0",
            "updated": datetime.now(timezone.utc).isoformat(),
            "tokens": [tok.to_dict() for tok in self._active.values()],
        }
        tmp = self._tokens_file.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2))
            tmp.replace(self._tokens_file)
        except OSError:
            logger.exception("Failed to persist tokens to %s", self._tokens_file)

    def _load(self) -> None:
        """Load previously-persisted tokens from disk."""
        if not self._tokens_file.exists():
            return

        try:
            data = json.loads(self._tokens_file.read_text())
            for tok_data in data.get("tokens", []):
                token = AgentToken.from_dict(tok_data)
                self._active[token.token_id] = token
            logger.info("Loaded %d token(s) from disk", len(self._active))
        except (json.JSONDecodeError, KeyError, OSError):
            logger.exception(
                "Failed to load tokens from %s -- starting with empty store",
                self._tokens_file,
            )
            self._active = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _remove(self, token_id: str) -> None:
        """Remove a token from the in-memory store (no persist)."""
        self._active.pop(token_id, None)
