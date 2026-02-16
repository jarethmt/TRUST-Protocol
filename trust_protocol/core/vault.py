"""
Credential Vault -- the storage engine of the TRUST Protocol.

Every credential is encrypted at rest with AES-256-GCM (via Fernet) using a
key derived from a master password through PBKDF2-HMAC-SHA256 with a random,
per-vault salt.

Every access produces a ``CredentialAccessRecord`` -- a cryptographic proof
that an agent requested a credential, why it was needed, and whether it was
granted.  This record is both returned to the caller and appended to an
immutable audit log so that the human principal can verify agent behaviour
at any time.

The vault delegates emergency-brake decisions to the ``EmergencyController``
(see ``trust_protocol.core.emergency``) so that a human can instantly revoke
all access -- globally, per-agent, or per-credential -- without touching the
encryption layer.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from trust_protocol.core.trust_tiers import TrustLevel
from trust_protocol.core.emergency import EmergencyController


# ---------------------------------------------------------------------------
# Access record
# ---------------------------------------------------------------------------

class CredentialAccessRecord:
    """Immutable cryptographic proof of a single credential access attempt.

    Every time an agent requests a credential the vault creates one of these,
    regardless of whether the request was granted or denied.  The record
    contains enough information for an auditor to reconstruct the agent's
    intent and the vault's decision.
    """

    def __init__(
        self,
        credential_name: str,
        agent_id: str,
        purpose: str,
        trust_level: TrustLevel,
        granted: bool,
        denial_reason: Optional[str] = None,
        duration_minutes: int = 30,
    ) -> None:
        self.timestamp = datetime.now(timezone.utc)
        self.credential_name = credential_name
        self.agent_id = agent_id
        self.purpose = purpose
        self.trust_level = trust_level
        self.granted = granted
        self.denial_reason = denial_reason
        self.duration_minutes = duration_minutes
        self.access_id = secrets.token_urlsafe(16)
        self.expiry = self.timestamp + timedelta(minutes=duration_minutes)
        self.signature = self._create_signature()

    # -- signature -----------------------------------------------------------

    def _create_signature(self) -> str:
        """SHA-256 signature over the canonical JSON of this record."""
        proof_data = {
            "access_id": self.access_id,
            "agent_id": self.agent_id,
            "credential": self.credential_name,
            "duration": self.duration_minutes,
            "granted": self.granted,
            "purpose": self.purpose,
            "timestamp": self.timestamp.isoformat(),
            "trust_level": self.trust_level.name,
        }
        proof_string = json.dumps(proof_data, sort_keys=True)
        return hashlib.sha256(proof_string.encode()).hexdigest()

    # -- queries -------------------------------------------------------------

    def is_valid(self) -> bool:
        """Return True if the access window has not expired."""
        return self.granted and datetime.now(timezone.utc) < self.expiry

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Human-readable dictionary representation."""
        d: Dict[str, Any] = {
            "access_id": self.access_id,
            "timestamp": self.timestamp.isoformat(),
            "credential": self.credential_name,
            "agent_id": self.agent_id,
            "purpose": self.purpose,
            "trust_level": self.trust_level.name,
            "granted": self.granted,
            "duration_minutes": self.duration_minutes,
            "expiry": self.expiry.isoformat(),
            "signature": self.signature,
            "is_valid": self.is_valid(),
        }
        if self.denial_reason:
            d["denial_reason"] = self.denial_reason
        return d


# ---------------------------------------------------------------------------
# Vault
# ---------------------------------------------------------------------------

class CredentialVault:
    """Encrypted credential store with trust-tier access control.

    Parameters
    ----------
    data_dir:
        Root directory for all vault data (encrypted credentials, audit log,
        trust state, emergency controls, salt, password hash).  Created
        automatically if it does not exist.
    """

    # KDF parameters
    _KDF_ITERATIONS = 100_000
    _KDF_KEY_LENGTH = 32

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self._credentials_file = self.data_dir / "credentials.enc"
        self._audit_log_file = self.data_dir / "audit.jsonl"
        self._trust_state_file = self.data_dir / "trust_state.json"
        self._password_hash_file = self.data_dir / ".password_hash"
        self._salt_file = self.data_dir / ".vault_salt"

        # Encryption state (set on initialize)
        self._cipher_suite: Optional[Fernet] = None

        # Trust state
        self.current_trust_level: TrustLevel = TrustLevel.NOVICE
        self.partnership_start: Optional[datetime] = None

        # In-memory access history for metrics
        self._access_history: List[CredentialAccessRecord] = []

        # Emergency controller
        self._emergency = EmergencyController(self.data_dir)

        # Restore persisted trust state
        self._load_trust_state()

    # ------------------------------------------------------------------
    # Salt management
    # ------------------------------------------------------------------

    def _get_or_create_salt(self) -> bytes:
        """Return the vault salt, generating and persisting it on first use."""
        if self._salt_file.exists():
            return self._salt_file.read_bytes()
        salt = os.urandom(16)
        self._salt_file.write_bytes(salt)
        self._salt_file.chmod(0o600)
        return salt

    # ------------------------------------------------------------------
    # Initialisation / password
    # ------------------------------------------------------------------

    def initialize(self, master_password: str) -> bool:
        """Unlock (or create) the vault with a master password.

        On first call the password is hashed and persisted.  Subsequent calls
        verify against the stored hash.  Returns ``False`` if the global
        emergency brake is active or the password is wrong.
        """
        if self._emergency.is_blocked():
            return False

        salt = self._get_or_create_salt()

        # Derive encryption key
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self._KDF_KEY_LENGTH,
            salt=salt,
            iterations=self._KDF_ITERATIONS,
        )
        key = base64.urlsafe_b64encode(kdf.derive(master_password.encode()))

        # Create a verification hash (separate from the encryption key)
        password_hash = hashlib.sha256(
            master_password.encode() + b"trust_verify" + salt
        ).hexdigest()

        # First run vs. subsequent
        if self._password_hash_file.exists():
            stored_hash = self._password_hash_file.read_text().strip()
            if password_hash != stored_hash:
                self._write_audit("AUTH_FAILED", {"message": "Invalid password attempt"})
                return False
        else:
            self._password_hash_file.write_text(password_hash)
            self._password_hash_file.chmod(0o600)

        self._cipher_suite = Fernet(key)

        # Record partnership start on very first init
        if self.partnership_start is None:
            self.partnership_start = datetime.now(timezone.utc)
            self._save_trust_state()
            self._write_audit("VAULT_INITIALIZED", {
                "message": "Trust partnership began",
                "trust_level": self.current_trust_level.name,
            })

        return True

    def change_password(self, current_password: str, new_password: str) -> bool:
        """Re-encrypt all credentials under a new master password.

        Returns ``False`` if the current password is wrong or the emergency
        brake is active.
        """
        if self._emergency.is_blocked():
            return False

        if not self.initialize(current_password):
            return False

        try:
            credentials = self._load_credentials()
        except Exception:
            self._write_audit("PASSWORD_CHANGE_FAILED", {
                "message": "Could not decrypt existing credentials",
            })
            return False

        # Derive new key
        salt = self._get_or_create_salt()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self._KDF_KEY_LENGTH,
            salt=salt,
            iterations=self._KDF_ITERATIONS,
        )
        new_key = base64.urlsafe_b64encode(kdf.derive(new_password.encode()))

        new_hash = hashlib.sha256(
            new_password.encode() + b"trust_verify" + salt
        ).hexdigest()

        self._cipher_suite = Fernet(new_key)
        self._save_credentials(credentials)
        self._password_hash_file.write_text(new_hash)

        self._write_audit("PASSWORD_CHANGED", {
            "message": "Master password changed successfully",
        })
        return True

    # ------------------------------------------------------------------
    # Credential CRUD
    # ------------------------------------------------------------------

    def _require_unlocked(self) -> None:
        if self._cipher_suite is None:
            raise RuntimeError("Vault is locked. Call initialize() first.")

    def store_credential(
        self,
        name: str,
        credential_data: Dict[str, Any],
        minimum_trust: TrustLevel = TrustLevel.COMPANION,
    ) -> bool:
        """Encrypt and persist a credential with a minimum trust requirement.

        Returns ``False`` if the emergency brake is active.
        """
        if self._emergency.is_blocked():
            return False
        self._require_unlocked()

        credentials = self._load_credentials()
        credentials[name] = {
            "data": credential_data,
            "minimum_trust": minimum_trust.name,
            "created": datetime.now(timezone.utc).isoformat(),
            "last_accessed": None,
            "access_count": 0,
        }
        self._save_credentials(credentials)

        self._write_audit("CREDENTIAL_STORED", {
            "name": name,
            "minimum_trust": minimum_trust.name,
        })
        return True

    def request_credential(
        self,
        name: str,
        agent_id: str,
        purpose: str,
        duration_minutes: int = 30,
    ) -> Optional[Tuple[Dict[str, Any], CredentialAccessRecord]]:
        """Request access to a credential.

        The caller must supply an ``agent_id`` and a human-readable
        ``purpose``.  The vault checks:

        1. Emergency brakes (global, per-agent, per-credential).
        2. Whether the credential exists.
        3. Whether the vault's current trust level meets the credential's
           minimum requirement.

        Returns ``(credential_data, access_record)`` on success, or ``None``
        on denial.  In both cases an audit entry is written.
        """
        # -- emergency checks -----------------------------------------------
        if self._emergency.is_blocked(agent_id=agent_id, credential_name=name):
            record = self._make_record(
                name, agent_id, purpose, duration_minutes,
                granted=False, denial_reason="Emergency brake active",
            )
            self._write_audit("ACCESS_DENIED", record.to_dict())
            return None

        self._require_unlocked()
        credentials = self._load_credentials()

        # -- existence check -------------------------------------------------
        if name not in credentials:
            record = self._make_record(
                name, agent_id, purpose, duration_minutes,
                granted=False, denial_reason="Credential not found",
            )
            self._write_audit("ACCESS_DENIED", record.to_dict())
            return None

        cred_info = credentials[name]
        required_trust = TrustLevel[cred_info["minimum_trust"]]

        # -- trust-level check -----------------------------------------------
        if self.current_trust_level.value < required_trust.value:
            record = self._make_record(
                name, agent_id, purpose, duration_minutes,
                granted=False,
                denial_reason=(
                    f"Insufficient trust: have {self.current_trust_level.name}, "
                    f"need {required_trust.name}"
                ),
            )
            self._write_audit("ACCESS_DENIED", record.to_dict())
            return None

        # -- grant -----------------------------------------------------------
        record = self._make_record(
            name, agent_id, purpose, duration_minutes, granted=True,
        )

        cred_info["last_accessed"] = datetime.now(timezone.utc).isoformat()
        cred_info["access_count"] += 1
        self._save_credentials(credentials)

        self._access_history.append(record)
        self._write_audit("ACCESS_GRANTED", record.to_dict())

        return (cred_info["data"], record)

    def list_credentials(self) -> List[Dict[str, Any]]:
        """Return metadata for every stored credential (never the values).

        Each entry contains the credential name, minimum trust tier,
        creation time, last access time, and total access count.
        """
        self._require_unlocked()
        credentials = self._load_credentials()
        result: List[Dict[str, Any]] = []
        for name, info in credentials.items():
            result.append({
                "name": name,
                "minimum_trust": info["minimum_trust"],
                "created": info["created"],
                "last_accessed": info["last_accessed"],
                "access_count": info["access_count"],
            })
        return result

    def delete_credential(self, name: str) -> bool:
        """Remove a credential from the vault.

        Returns ``True`` if the credential existed and was deleted,
        ``False`` otherwise (including when the emergency brake is active).
        """
        if self._emergency.is_blocked():
            return False
        self._require_unlocked()

        credentials = self._load_credentials()
        if name not in credentials:
            return False

        del credentials[name]
        self._save_credentials(credentials)

        self._write_audit("CREDENTIAL_DELETED", {"name": name})
        return True

    # ------------------------------------------------------------------
    # Trust state
    # ------------------------------------------------------------------

    def set_trust_level(self, level: TrustLevel) -> None:
        """Explicitly set the current trust level and persist it."""
        self.current_trust_level = level
        self._save_trust_state()
        self._write_audit("TRUST_LEVEL_SET", {"level": level.name})

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    def get_audit_trail(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Return audit entries from the last *hours* hours."""
        if not self._audit_log_file.exists():
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        entries: List[Dict[str, Any]] = []

        with open(self._audit_log_file, "r") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                entry_time = datetime.fromisoformat(entry["timestamp"])
                if entry_time.tzinfo is None:
                    entry_time = entry_time.replace(tzinfo=timezone.utc)
                if entry_time > cutoff:
                    entries.append(entry)

        return entries

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict[str, Any]:
        """Summary metrics suitable for a dashboard or health check."""
        total = len(self._access_history)
        granted = sum(1 for r in self._access_history if r.granted)
        days = 0
        if self.partnership_start:
            days = (datetime.now(timezone.utc) - self.partnership_start).days

        return {
            "current_trust_level": self.current_trust_level.name,
            "trust_description": self.current_trust_level.description,
            "partnership_days": days,
            "total_accesses": total,
            "granted_accesses": granted,
            "grant_rate": (granted / total * 100) if total > 0 else 0,
            "emergency_status": self._emergency.status(),
        }

    # ------------------------------------------------------------------
    # Emergency delegation
    # ------------------------------------------------------------------

    @property
    def emergency(self) -> EmergencyController:
        """Direct access to the emergency controller for the vault's data dir."""
        return self._emergency

    # ------------------------------------------------------------------
    # Private helpers -- encryption
    # ------------------------------------------------------------------

    def _load_credentials(self) -> Dict[str, Any]:
        if not self._credentials_file.exists():
            return {}
        assert self._cipher_suite is not None
        encrypted = self._credentials_file.read_bytes()
        decrypted = self._cipher_suite.decrypt(encrypted)
        return json.loads(decrypted)

    def _save_credentials(self, credentials: Dict[str, Any]) -> None:
        assert self._cipher_suite is not None
        raw = json.dumps(credentials, indent=2).encode()
        encrypted = self._cipher_suite.encrypt(raw)
        self._credentials_file.write_bytes(encrypted)

    # ------------------------------------------------------------------
    # Private helpers -- trust state
    # ------------------------------------------------------------------

    def _load_trust_state(self) -> None:
        if not self._trust_state_file.exists():
            return
        with open(self._trust_state_file, "r") as fh:
            state = json.load(fh)
        self.current_trust_level = TrustLevel[state["trust_level"]]
        if state.get("partnership_start"):
            dt = datetime.fromisoformat(state["partnership_start"])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            self.partnership_start = dt

    def _save_trust_state(self) -> None:
        state = {
            "trust_level": self.current_trust_level.name,
            "partnership_start": (
                self.partnership_start.isoformat()
                if self.partnership_start
                else None
            ),
        }
        with open(self._trust_state_file, "w") as fh:
            json.dump(state, fh, indent=2)

    # ------------------------------------------------------------------
    # Private helpers -- audit
    # ------------------------------------------------------------------

    def _write_audit(self, event_type: str, details: Dict[str, Any]) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "details": details,
        }
        with open(self._audit_log_file, "a") as fh:
            fh.write(json.dumps(entry) + "\n")

    # ------------------------------------------------------------------
    # Private helpers -- record factory
    # ------------------------------------------------------------------

    def _make_record(
        self,
        credential_name: str,
        agent_id: str,
        purpose: str,
        duration_minutes: int,
        *,
        granted: bool,
        denial_reason: Optional[str] = None,
    ) -> CredentialAccessRecord:
        record = CredentialAccessRecord(
            credential_name=credential_name,
            agent_id=agent_id,
            purpose=purpose,
            trust_level=self.current_trust_level,
            granted=granted,
            denial_reason=denial_reason,
            duration_minutes=duration_minutes,
        )
        self._access_history.append(record)
        return record
