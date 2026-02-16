"""
Agent Identity Management for the TRUST Protocol.

Every agent that participates in the protocol receives a cryptographically
unique identity on registration.  The identity binds the agent's declared
capabilities, network requirements, and credential needs to a trust tier
that governs what the agent is allowed to do.

An API key is generated once at registration and returned to the caller.
Subsequent requests authenticate with this key.  The key is *never*
persisted to disk -- only a salted SHA-256 hash is stored -- so if the
caller loses it, the agent must be re-registered.

Agents are persisted as individual JSON files inside a configurable
directory (one file per agent: ``{agent_id}.json``).  This keeps the
storage model simple, auditable, and merge-friendly.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from trust_protocol.core.trust_tiers import TrustTier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent definition
# ---------------------------------------------------------------------------

@dataclass
class AgentDefinition:
    """Complete definition of an agent submitted at registration time.

    The definition captures *what the agent is* and *what it needs*.  It is
    immutable after registration -- changing capabilities requires
    re-registration so that the trust assessment is re-evaluated.
    """

    name: str
    agent_type: str  # e.g. "skill_executor", "service", "assistant"
    description: str
    required_credentials: List[str] = field(default_factory=list)
    network_access: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    executable_path: Optional[str] = None
    executable_hash: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Return a plain-dict representation suitable for JSON."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentDefinition:
        """Reconstruct from a plain dict (e.g. loaded from JSON)."""
        return cls(**data)

    # -- hashing -------------------------------------------------------------

    def calculate_hash(self) -> str:
        """Deterministic SHA-256 hash of the security-relevant fields.

        Only fields that affect the trust assessment are included so that
        cosmetic changes (description, metadata) do not alter the hash.
        """
        normalised = {
            "name": self.name,
            "agent_type": self.agent_type,
            "capabilities": sorted(self.capabilities),
            "required_credentials": sorted(self.required_credentials),
            "network_access": sorted(self.network_access),
            "executable_hash": self.executable_hash,
        }
        payload = json.dumps(normalised, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Agent identity
# ---------------------------------------------------------------------------

@dataclass
class AgentIdentity:
    """Cryptographically unique identity assigned to a registered agent.

    The ``api_key`` is generated once during registration and must be
    returned to the caller immediately.  It is **not** written to the
    on-disk JSON -- only a salted hash is stored.  If the key is lost the
    agent must be re-registered.
    """

    agent_id: str
    definition: AgentDefinition
    trust_tier: TrustTier
    api_key: str
    created_at: datetime
    last_active: datetime
    status: str = "active"  # "active" | "suspended" | "revoked"

    # The salted hash that is persisted instead of the raw key.
    _api_key_hash: str = field(default="", repr=False)

    # -- factory -------------------------------------------------------------

    @classmethod
    def create(cls, definition: AgentDefinition) -> AgentIdentity:
        """Create a brand-new identity for *definition*.

        Generates the ``agent_id``, ``api_key``, and determines the initial
        trust tier via a risk-based assessment of the definition.
        """
        agent_uuid = uuid.uuid4().hex[:8]
        def_hash = definition.calculate_hash()[:8]
        agent_id = f"agt_{agent_uuid}_{def_hash}"

        api_key = f"tp_{secrets.token_urlsafe(32)}"

        trust_tier = cls._assess_initial_trust(definition)

        now = datetime.now(timezone.utc)

        identity = cls(
            agent_id=agent_id,
            definition=definition,
            trust_tier=trust_tier,
            api_key=api_key,
            created_at=now,
            last_active=now,
        )
        identity._api_key_hash = identity._hash_api_key(api_key)
        return identity

    # -- trust assessment ----------------------------------------------------

    @staticmethod
    def _assess_initial_trust(definition: AgentDefinition) -> TrustTier:
        """Determine the starting trust tier from the agent's definition.

        The logic is deliberately conservative -- most agents start at
        ``NOVICE``.  Only agents with a very limited surface area are
        promoted to ``COMPANION``.  ``SACRED`` is **never** auto-assigned.

        Rules (evaluated in order, first match wins):
        1. ``shell_execute`` in capabilities              -> NOVICE
        2. Any wildcard (``*``) in network_access entries -> NOVICE
        3. More than three required credentials           -> NOVICE
        4. Limited capabilities AND at most one credential -> COMPANION
        5. Everything else                                 -> NOVICE
        """
        caps = set(definition.capabilities)
        net = definition.network_access
        creds = definition.required_credentials

        # High-risk signals -> NOVICE immediately.
        if "shell_execute" in caps:
            return TrustTier.NOVICE

        if any("*" in entry for entry in net):
            return TrustTier.NOVICE

        if len(creds) > 3:
            return TrustTier.NOVICE

        # Low-risk surface -> COMPANION.
        high_risk_caps = {"shell_execute", "file_write", "network", "sudo"}
        if not caps.intersection(high_risk_caps) and len(creds) <= 1:
            return TrustTier.COMPANION

        return TrustTier.NOVICE

    # -- api key hashing -----------------------------------------------------

    @staticmethod
    def _hash_api_key(api_key: str) -> str:
        """Return a salted SHA-256 hex digest of *api_key*.

        A per-key random salt is prepended so that identical keys never
        produce the same hash.  The stored format is ``salt$hash``.
        """
        salt = secrets.token_hex(16)
        digest = hashlib.sha256(f"{salt}{api_key}".encode()).hexdigest()
        return f"{salt}${digest}"

    @staticmethod
    def _verify_api_key(api_key: str, stored_hash: str) -> bool:
        """Check *api_key* against a ``salt$hash`` string."""
        if "$" not in stored_hash:
            return False
        salt, expected = stored_hash.split("$", 1)
        digest = hashlib.sha256(f"{salt}{api_key}".encode()).hexdigest()
        return secrets.compare_digest(digest, expected)

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise for persistence / API responses.

        The raw ``api_key`` is **excluded** for safety.  Only the salted
        hash is included so the key can be verified on future requests.
        """
        return {
            "agent_id": self.agent_id,
            "definition": self.definition.to_dict(),
            "trust_tier": self.trust_tier.name,
            "api_key_hash": self._api_key_hash,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "status": self.status,
        }

    def to_dict_with_key(self) -> Dict[str, Any]:
        """Serialise **including** the raw API key.

        Only used in the registration response so the caller can store
        the key.  Must never be persisted to disk.
        """
        data = self.to_dict()
        data["api_key"] = self.api_key
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentIdentity:
        """Reconstruct from a persisted dict (JSON file).

        Because the raw ``api_key`` is never stored, we set the field to
        an empty string.  The salted hash is loaded separately for
        verification purposes.
        """
        definition = AgentDefinition.from_dict(data["definition"])

        identity = cls(
            agent_id=data["agent_id"],
            definition=definition,
            trust_tier=TrustTier[data["trust_tier"]],
            api_key="",  # never persisted
            created_at=datetime.fromisoformat(data["created_at"]),
            last_active=datetime.fromisoformat(data["last_active"]),
            status=data.get("status", "active"),
        )
        identity._api_key_hash = data.get("api_key_hash", "")
        return identity


# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

class AgentRegistry:
    """Manages the full lifecycle of agent identities.

    Agents are stored as individual JSON files (``{agent_id}.json``) inside
    *agents_dir*.  An in-memory index maps API-key hashes to agent IDs so
    that authentication look-ups are fast.
    """

    def __init__(self, agents_dir: Path) -> None:
        self._agents_dir = Path(agents_dir)
        self._agents_dir.mkdir(parents=True, exist_ok=True)

        # agent_id -> AgentIdentity
        self._agents: Dict[str, AgentIdentity] = {}

        # In-memory reverse index: api_key_hash -> agent_id.
        # Rebuilt from disk on init.  Kept in sync on every mutation.
        self._key_index: Dict[str, str] = {}

        self._load_all()

    # -- public API ----------------------------------------------------------

    def register(self, definition: AgentDefinition) -> AgentIdentity:
        """Register a new agent and return its identity.

        The returned ``AgentIdentity`` is the **only** time the raw
        ``api_key`` is available.  Callers must capture it from the
        response (via ``to_dict_with_key()``).
        """
        # Reject duplicate active names.
        for existing in self._agents.values():
            if existing.definition.name == definition.name and existing.status == "active":
                raise ValueError(
                    f"An active agent with name '{definition.name}' already exists"
                )

        identity = AgentIdentity.create(definition)

        self._agents[identity.agent_id] = identity
        self._key_index[identity._api_key_hash] = identity.agent_id
        self._save(identity)

        logger.info(
            "Registered agent %s (%s) at trust tier %s",
            identity.agent_id,
            definition.name,
            identity.trust_tier.name,
        )
        return identity

    def get(self, agent_id: str) -> Optional[AgentIdentity]:
        """Return the agent with *agent_id*, or ``None``."""
        return self._agents.get(agent_id)

    def get_by_api_key(self, api_key: str) -> Optional[AgentIdentity]:
        """Look up an agent by its raw API key.

        Iterates the key index and verifies the salted hash.  Although
        the index is keyed by hash string, verification still uses
        constant-time comparison to avoid timing leaks.
        """
        for key_hash, agent_id in self._key_index.items():
            if AgentIdentity._verify_api_key(api_key, key_hash):
                identity = self._agents.get(agent_id)
                if identity and identity.status == "active":
                    return identity
                return None
        return None

    def list_agents(self, status: Optional[str] = None) -> List[AgentIdentity]:
        """Return agents, optionally filtered by *status*."""
        agents = list(self._agents.values())
        if status is not None:
            agents = [a for a in agents if a.status == status]
        return agents

    def update_status(self, agent_id: str, status: str) -> bool:
        """Set the status of *agent_id* to *status*.

        Valid statuses: ``"active"``, ``"suspended"``, ``"revoked"``.
        Returns ``True`` on success, ``False`` if the agent was not found.
        """
        valid = {"active", "suspended", "revoked"}
        if status not in valid:
            raise ValueError(f"Invalid status '{status}'; must be one of {valid}")

        identity = self._agents.get(agent_id)
        if identity is None:
            return False

        identity.status = status
        self._save(identity)

        logger.info("Agent %s status changed to %s", agent_id, status)
        return True

    def promote(self, agent_id: str, new_tier: TrustTier) -> bool:
        """Promote (or demote) *agent_id* to *new_tier*.

        ``SACRED`` can only be assigned explicitly through this method --
        it is never auto-assigned during registration.

        Returns ``True`` on success, ``False`` if the agent was not found.
        """
        identity = self._agents.get(agent_id)
        if identity is None:
            return False

        old_tier = identity.trust_tier
        identity.trust_tier = new_tier
        self._save(identity)

        logger.info(
            "Agent %s trust tier changed from %s to %s",
            agent_id,
            old_tier.name,
            new_tier.name,
        )
        return True

    def update_last_active(self, agent_id: str) -> None:
        """Touch the ``last_active`` timestamp for *agent_id*."""
        identity = self._agents.get(agent_id)
        if identity is None:
            return

        identity.last_active = datetime.now(timezone.utc)
        self._save(identity)

    def delete(self, agent_id: str) -> bool:
        """Permanently remove the agent and its on-disk file.

        Returns ``True`` if the agent existed and was deleted.
        """
        identity = self._agents.pop(agent_id, None)
        if identity is None:
            return False

        # Remove from key index.
        self._key_index = {
            k: v for k, v in self._key_index.items() if v != agent_id
        }

        # Remove JSON file.
        path = self._agent_path(agent_id)
        if path.exists():
            path.unlink()

        logger.info("Deleted agent %s", agent_id)
        return True

    # -- persistence helpers -------------------------------------------------

    def _agent_path(self, agent_id: str) -> Path:
        """Return the on-disk path for *agent_id*."""
        return self._agents_dir / f"{agent_id}.json"

    def _save(self, identity: AgentIdentity) -> None:
        """Atomically write *identity* to its JSON file."""
        path = self._agent_path(identity.agent_id)
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(identity.to_dict(), indent=2))
            tmp.replace(path)
        except Exception:
            logger.exception("Failed to save agent %s", identity.agent_id)
            if tmp.exists():
                tmp.unlink()
            raise

    def _load_all(self) -> None:
        """Load every ``*.json`` file in *agents_dir* into memory."""
        for path in sorted(self._agents_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                identity = AgentIdentity.from_dict(data)
                self._agents[identity.agent_id] = identity

                # Rebuild key index entry.
                if identity._api_key_hash:
                    self._key_index[identity._api_key_hash] = identity.agent_id
            except Exception:
                logger.exception("Failed to load agent file %s", path)
                continue

        logger.info(
            "Loaded %d agent(s) from %s", len(self._agents), self._agents_dir
        )
