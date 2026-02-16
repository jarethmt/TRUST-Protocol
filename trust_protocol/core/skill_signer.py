"""Ed25519 skill signing and verification for the TRUST Protocol.

This module implements the supply-chain security layer for AI agent skills.
Every skill published through the protocol is cryptographically signed by
its publisher using Ed25519.  Any consumer -- agent platform, marketplace,
or end user -- can verify a skill's authenticity and integrity without
needing any special access or credentials.

The design addresses a specific threat model: a compromised skill
marketplace that serves tampered packages to AI agents.  Because each
skill carries an Ed25519 signature from the original publisher, a tampered
skill will fail verification even if the marketplace itself is malicious.

Key concepts:

* **Publisher** -- an entity (person or organisation) that publishes skills.
  Each publisher has a registered Ed25519 public key.  The private key is
  held exclusively by the publisher and never transmitted to the server.

* **SkillManifest** -- a declaration of what a skill *is* (name, version,
  code hash, capabilities, credential requirements).  The security-relevant
  fields are serialised to canonical JSON for signing.

* **SignedManifest** -- a SkillManifest plus an Ed25519 signature.  This is
  the artefact that travels with the skill and can be verified anywhere.

* **PublisherRegistry** -- file-backed registry of known publishers.  One
  JSON file per publisher, same atomic-write pattern as AgentRegistry.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from trust_protocol.core.trust_tiers import TrustTier

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Key generation
# ---------------------------------------------------------------------------


def generate_keypair() -> tuple[bytes, bytes]:
    """Generate an Ed25519 private/public key pair.

    Returns a ``(private_key_pem, public_key_pem)`` tuple where both
    values are PEM-encoded bytes.  The private key uses PKCS8 format with
    no encryption -- callers are responsible for storing it securely.
    """
    private_key = Ed25519PrivateKey.generate()
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


# ---------------------------------------------------------------------------
# Code hashing
# ---------------------------------------------------------------------------


def hash_code(code: str | bytes) -> str:
    """Return a ``sha256:<hex>`` hash of *code*.

    Accepts either a string (which will be UTF-8 encoded) or raw bytes.
    The returned format matches the code_hash field in SkillManifest.
    """
    if isinstance(code, str):
        code = code.encode("utf-8")
    return f"sha256:{hashlib.sha256(code).hexdigest()}"


# ---------------------------------------------------------------------------
# Publisher
# ---------------------------------------------------------------------------


@dataclass
class Publisher:
    """A registered skill publisher.

    Each publisher owns an Ed25519 key pair.  Only the public key is stored
    in the registry -- the private key remains with the publisher.
    """

    publisher_id: str
    name: str
    organization: str
    public_key_pem: str  # PEM-encoded Ed25519 public key
    trust_tier: TrustTier
    status: str = "active"  # "active" | "revoked"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict suitable for JSON persistence."""
        return {
            "publisher_id": self.publisher_id,
            "name": self.name,
            "organization": self.organization,
            "public_key_pem": self.public_key_pem,
            "trust_tier": self.trust_tier.name,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Publisher:
        """Reconstruct from a persisted dict."""
        return cls(
            publisher_id=data["publisher_id"],
            name=data["name"],
            organization=data.get("organization", ""),
            public_key_pem=data["public_key_pem"],
            trust_tier=TrustTier[data["trust_tier"]],
            status=data.get("status", "active"),
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Skill manifest
# ---------------------------------------------------------------------------


@dataclass
class SkillManifest:
    """Declaration of a skill's identity and security properties.

    The ``to_signable_bytes`` method produces a deterministic byte sequence
    from the security-relevant fields.  This is what gets signed and later
    verified.  Cosmetic fields (description, created_at) are excluded from
    the signature so that documentation updates do not invalidate it.
    """

    name: str
    version: str
    publisher_id: str
    code_hash: str  # "sha256:<hex>"
    capabilities: List[str] = field(default_factory=list)
    credentials_required: List[str] = field(default_factory=list)
    description: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_signable_bytes(self) -> bytes:
        """Canonical JSON of security-relevant fields, encoded as UTF-8.

        Fields are sorted by key to ensure determinism across platforms and
        Python versions.  Only fields that affect trust decisions are
        included -- changing the description does not invalidate a
        signature.
        """
        canonical = {
            "name": self.name,
            "version": self.version,
            "publisher_id": self.publisher_id,
            "code_hash": self.code_hash,
            "capabilities": sorted(self.capabilities),
            "credentials_required": sorted(self.credentials_required),
        }
        return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "name": self.name,
            "version": self.version,
            "publisher_id": self.publisher_id,
            "code_hash": self.code_hash,
            "capabilities": self.capabilities,
            "credentials_required": self.credentials_required,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SkillManifest:
        """Reconstruct from a plain dict."""
        return cls(
            name=data["name"],
            version=data["version"],
            publisher_id=data["publisher_id"],
            code_hash=data["code_hash"],
            capabilities=data.get("capabilities", []),
            credentials_required=data.get("credentials_required", []),
            description=data.get("description", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Signed manifest
# ---------------------------------------------------------------------------


@dataclass
class SignedManifest:
    """A SkillManifest together with its Ed25519 signature.

    The signature is stored base64-encoded.  The ``signed_at`` timestamp
    records when the signature was created but is *not* part of the
    signed data (the manifest bytes are self-contained).
    """

    manifest: SkillManifest
    signature: str  # base64-encoded Ed25519 signature
    signed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Serialise to a plain dict."""
        return {
            "manifest": self.manifest.to_dict(),
            "signature": self.signature,
            "signed_at": self.signed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SignedManifest:
        """Reconstruct from a plain dict."""
        return cls(
            manifest=SkillManifest.from_dict(data["manifest"]),
            signature=data["signature"],
            signed_at=datetime.fromisoformat(data["signed_at"]) if "signed_at" in data else datetime.now(timezone.utc),
        )


# ---------------------------------------------------------------------------
# Signing and verification
# ---------------------------------------------------------------------------


def sign_manifest(manifest: SkillManifest, private_key_pem: bytes) -> SignedManifest:
    """Sign a SkillManifest with an Ed25519 private key.

    Parameters
    ----------
    manifest:
        The skill manifest to sign.
    private_key_pem:
        PEM-encoded Ed25519 private key (PKCS8, no encryption).

    Returns
    -------
    SignedManifest
        The manifest plus its base64-encoded signature and signing timestamp.
    """
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    signature = private_key.sign(manifest.to_signable_bytes())
    return SignedManifest(
        manifest=manifest,
        signature=base64.b64encode(signature).decode("ascii"),
        signed_at=datetime.now(timezone.utc),
    )


def verify_manifest(signed_manifest: SignedManifest, public_key_pem: bytes) -> bool:
    """Verify a SignedManifest against an Ed25519 public key.

    Parameters
    ----------
    signed_manifest:
        The signed manifest to verify.
    public_key_pem:
        PEM-encoded Ed25519 public key (SubjectPublicKeyInfo format).

    Returns
    -------
    bool
        ``True`` if the signature is valid, ``False`` otherwise.
        Returns ``False`` (rather than raising) on any cryptographic
        failure, making it safe to use in conditional checks.
    """
    try:
        public_key = serialization.load_pem_public_key(public_key_pem)
        sig_bytes = base64.b64decode(signed_manifest.signature)
        public_key.verify(sig_bytes, signed_manifest.manifest.to_signable_bytes())
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Publisher registry
# ---------------------------------------------------------------------------


class PublisherRegistry:
    """File-backed registry of skill publishers.

    Publishers are stored as individual JSON files (``{publisher_id}.json``)
    inside *publishers_dir*.  The same atomic-write pattern used by
    ``AgentRegistry`` is employed here to prevent partial writes from
    corrupting the registry.

    Parameters
    ----------
    publishers_dir:
        Directory where publisher JSON files are stored.  Created if absent.
    """

    def __init__(self, publishers_dir: Path) -> None:
        self._publishers_dir = Path(publishers_dir)
        self._publishers_dir.mkdir(parents=True, exist_ok=True)

        # publisher_id -> Publisher
        self._publishers: Dict[str, Publisher] = {}

        self._load_all()

    # -- public API ----------------------------------------------------------

    def register(
        self,
        name: str,
        organization: str,
        public_key_pem: str,
        trust_tier: TrustTier = TrustTier.NOVICE,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Publisher:
        """Register a new publisher.

        Parameters
        ----------
        name:
            Human-readable publisher name.  Must be unique among active
            publishers.
        organization:
            Organisation the publisher belongs to (may be empty).
        public_key_pem:
            PEM-encoded Ed25519 public key as a string.
        trust_tier:
            Initial trust tier.  Defaults to ``NOVICE``.
        metadata:
            Arbitrary metadata (e.g. website, contact email).

        Returns
        -------
        Publisher
            The newly created publisher record.

        Raises
        ------
        ValueError
            If an active publisher with the same name already exists.
        """
        # Reject duplicate active names.
        for existing in self._publishers.values():
            if existing.name == name and existing.status == "active":
                raise ValueError(
                    f"An active publisher with name '{name}' already exists"
                )

        publisher_id = f"pub_{uuid.uuid4().hex[:8]}"
        publisher = Publisher(
            publisher_id=publisher_id,
            name=name,
            organization=organization,
            public_key_pem=public_key_pem,
            trust_tier=trust_tier,
            metadata=metadata or {},
        )

        self._publishers[publisher_id] = publisher
        self._save(publisher)

        logger.info(
            "Registered publisher %s (%s) at trust tier %s",
            publisher_id,
            name,
            trust_tier.name,
        )
        return publisher

    def get(self, publisher_id: str) -> Optional[Publisher]:
        """Return the publisher with *publisher_id*, or ``None``."""
        return self._publishers.get(publisher_id)

    def get_by_name(self, name: str) -> Optional[Publisher]:
        """Return the first active publisher matching *name*, or ``None``."""
        for publisher in self._publishers.values():
            if publisher.name == name and publisher.status == "active":
                return publisher
        return None

    def list_publishers(self, status: Optional[str] = None) -> List[Publisher]:
        """Return all publishers, optionally filtered by *status*."""
        publishers = list(self._publishers.values())
        if status is not None:
            publishers = [p for p in publishers if p.status == status]
        return publishers

    def revoke_key(self, publisher_id: str, reason: str = "") -> bool:
        """Revoke a publisher's key, preventing further skill verification.

        A revoked publisher's skills will fail verification checks because
        the publisher status is checked before the cryptographic signature.

        Parameters
        ----------
        publisher_id:
            The publisher to revoke.
        reason:
            Human-readable reason for revocation (stored in metadata).

        Returns
        -------
        bool
            ``True`` if the publisher was found and revoked, ``False``
            if the publisher_id does not exist.
        """
        publisher = self._publishers.get(publisher_id)
        if publisher is None:
            return False

        publisher.status = "revoked"
        if reason:
            publisher.metadata["revocation_reason"] = reason
            publisher.metadata["revoked_at"] = datetime.now(timezone.utc).isoformat()
        self._save(publisher)

        logger.info("Revoked publisher %s: %s", publisher_id, reason)
        return True

    def promote(self, publisher_id: str, new_tier: TrustTier) -> bool:
        """Promote (or demote) a publisher to *new_tier*.

        Returns ``True`` on success, ``False`` if the publisher was not
        found.
        """
        publisher = self._publishers.get(publisher_id)
        if publisher is None:
            return False

        old_tier = publisher.trust_tier
        publisher.trust_tier = new_tier
        self._save(publisher)

        logger.info(
            "Publisher %s trust tier changed from %s to %s",
            publisher_id,
            old_tier.name,
            new_tier.name,
        )
        return True

    # -- persistence helpers -------------------------------------------------

    def _publisher_path(self, publisher_id: str) -> Path:
        """Return the on-disk path for *publisher_id*."""
        return self._publishers_dir / f"{publisher_id}.json"

    def _save(self, publisher: Publisher) -> None:
        """Atomically write *publisher* to its JSON file."""
        path = self._publisher_path(publisher.publisher_id)
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(publisher.to_dict(), indent=2))
            tmp.replace(path)
        except Exception:
            logger.exception("Failed to save publisher %s", publisher.publisher_id)
            if tmp.exists():
                tmp.unlink()
            raise

    def _load_all(self) -> None:
        """Load every ``*.json`` file in *publishers_dir* into memory."""
        for path in sorted(self._publishers_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                publisher = Publisher.from_dict(data)
                self._publishers[publisher.publisher_id] = publisher
            except Exception:
                logger.exception("Failed to load publisher file %s", path)
                continue

        logger.info(
            "Loaded %d publisher(s) from %s",
            len(self._publishers),
            self._publishers_dir,
        )

    # -- serialisation helpers -----------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the entire registry as a dict (for export/backup)."""
        return {
            pid: p.to_dict() for pid, p in self._publishers.items()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], publishers_dir: Path) -> PublisherRegistry:
        """Reconstruct a registry from a previously exported dict.

        This creates publisher files in *publishers_dir* for each entry
        in *data* and then loads them normally.
        """
        publishers_dir = Path(publishers_dir)
        publishers_dir.mkdir(parents=True, exist_ok=True)

        for publisher_id, publisher_data in data.items():
            path = publishers_dir / f"{publisher_id}.json"
            path.write_text(json.dumps(publisher_data, indent=2))

        return cls(publishers_dir)
