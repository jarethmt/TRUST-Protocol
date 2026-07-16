"""HMAC-signed, hash-chained audit log for the TRUST Protocol.

Every mutation within the credential broker -- agent registration, token
issuance, credential access, emergency shutdown -- is recorded as an
append-only JSONL entry.  Entries are linked via SHA-256 hash chaining and
individually authenticated with HMAC-SHA256 using the server secret key.

This module is the single source of truth for *what happened and when*.
An external auditor can verify the full chain with nothing more than the
log file and the server secret key.
"""

from __future__ import annotations

import fcntl
import hashlib
import hmac
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

# Agent lifecycle
AGENT_REGISTERED = "AGENT_REGISTERED"
AGENT_SUSPENDED = "AGENT_SUSPENDED"
AGENT_REVOKED = "AGENT_REVOKED"

# Token lifecycle
TOKEN_ISSUED = "TOKEN_ISSUED"
TOKEN_RENEWED = "TOKEN_RENEWED"
TOKEN_REVOKED = "TOKEN_REVOKED"

# Credential operations
CREDENTIAL_STORED = "CREDENTIAL_STORED"
CREDENTIAL_ACCESSED = "CREDENTIAL_ACCESSED"

KMS_GENERATE = "KMS_GENERATE"
KMS_WRAP = "KMS_WRAP"
KMS_UNWRAP = "KMS_UNWRAP"
CREDENTIAL_DELETED = "CREDENTIAL_DELETED"
CREDENTIAL_EXECUTE = "CREDENTIAL_EXECUTE"
CREDENTIAL_PROXY_VALUE = "CREDENTIAL_PROXY_VALUE"

# Emergency operations
EMERGENCY_ACTIVATED = "EMERGENCY_ACTIVATED"
EMERGENCY_CLEARED = "EMERGENCY_CLEARED"

# Skill signing
SKILL_SIGNED = "SKILL_SIGNED"
SKILL_VERIFIED = "SKILL_VERIFIED"
PUBLISHER_REGISTERED = "PUBLISHER_REGISTERED"
PUBLISHER_REVOKED = "PUBLISHER_REVOKED"

# Anomaly detection
ANOMALY_DETECTED = "ANOMALY_DETECTED"

ALL_EVENT_TYPES: frozenset[str] = frozenset({
    AGENT_REGISTERED, AGENT_SUSPENDED, AGENT_REVOKED,
    TOKEN_ISSUED, TOKEN_RENEWED, TOKEN_REVOKED,
    CREDENTIAL_STORED, CREDENTIAL_ACCESSED, CREDENTIAL_DELETED,
    CREDENTIAL_EXECUTE, CREDENTIAL_PROXY_VALUE,
    EMERGENCY_ACTIVATED, EMERGENCY_CLEARED,
    SKILL_SIGNED, SKILL_VERIFIED, PUBLISHER_REGISTERED, PUBLISHER_REVOKED,
    ANOMALY_DETECTED,
})

GENESIS_HASH = "sha256:genesis"

_AUDIT_FILENAME = "audit.jsonl"


# ---------------------------------------------------------------------------
# AuditChain
# ---------------------------------------------------------------------------

class AuditChain:
    """Append-only, HMAC-signed, hash-chained audit log.

    Parameters
    ----------
    data_dir:
        Directory where ``audit.jsonl`` will be stored.  Created if absent.
    secret_key:
        Server secret key used for HMAC-SHA256 signatures.  Must be kept
        confidential -- anyone who possesses it can forge entries.
    """

    def __init__(self, data_dir: Path, secret_key: bytes) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._secret_key = secret_key
        self._log_path = self._data_dir / _AUDIT_FILENAME

        # Recover chain state from existing log (if any).
        self._last_hash: str = GENESIS_HASH
        self._seq: int = 0
        self._recover_chain_state()

    # -- public interface ---------------------------------------------------

    def log(
        self,
        event_type: str,
        agent_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> str:
        """Append a new entry to the audit chain.

        Returns the ``sha256:...`` hash of the newly created entry.
        """
        if details is None:
            details = {}

        seq = self._seq + 1
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        previous_hash = self._last_hash

        entry_hash = self._compute_hash(
            seq, timestamp, event_type, agent_id, details, previous_hash,
        )
        entry_hmac = self._compute_hmac(entry_hash)

        entry: dict[str, Any] = {
            "seq": seq,
            "timestamp": timestamp,
            "event_type": event_type,
            "agent_id": agent_id,
            "details": details,
            "previous_hash": previous_hash,
            "hash": entry_hash,
            "hmac": entry_hmac,
        }

        line = json.dumps(entry, separators=(",", ":")) + "\n"

        self._append_locked(line)

        # Advance internal state only after a successful write.
        self._seq = seq
        self._last_hash = entry_hash

        return entry_hash

    def query(
        self,
        event_type: str | None = None,
        agent_id: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return entries matching the given filters.

        Results are ordered oldest-first (ascending sequence number).
        """
        results: list[dict[str, Any]] = []

        for entry in self._iter_entries():
            if event_type is not None and entry.get("event_type") != event_type:
                continue
            if agent_id is not None and entry.get("agent_id") != agent_id:
                continue
            if since is not None:
                entry_dt = datetime.fromisoformat(
                    entry["timestamp"].replace("Z", "+00:00"),
                )
                if entry_dt < since:
                    continue

            results.append(entry)
            if len(results) >= limit:
                break

        return results

    def verify_chain(self) -> tuple[bool, str]:
        """Walk the full log and verify hash chain + HMAC signatures.

        Returns ``(True, "OK: N entries verified")`` on success, or
        ``(False, "<description of first violation>")`` on failure.
        """
        expected_previous = GENESIS_HASH
        count = 0

        for entry in self._iter_entries():
            seq = entry.get("seq")

            # 1. Sequence continuity.
            count += 1
            if seq != count:
                return (
                    False,
                    f"Sequence gap at position {count}: expected seq={count}, "
                    f"found seq={seq}",
                )

            # 2. Previous-hash linkage.
            if entry.get("previous_hash") != expected_previous:
                return (
                    False,
                    f"Chain broken at seq={seq}: expected previous_hash="
                    f"{expected_previous!r}, found "
                    f"{entry.get('previous_hash')!r}",
                )

            # 3. Entry hash integrity.
            computed_hash = self._compute_hash(
                entry["seq"],
                entry["timestamp"],
                entry["event_type"],
                entry.get("agent_id"),
                entry.get("details", {}),
                entry["previous_hash"],
            )
            if entry.get("hash") != computed_hash:
                return (
                    False,
                    f"Hash mismatch at seq={seq}: stored={entry.get('hash')!r}, "
                    f"computed={computed_hash!r}",
                )

            # 4. HMAC authenticity.
            computed_hmac = self._compute_hmac(computed_hash)
            if entry.get("hmac") != computed_hmac:
                return (
                    False,
                    f"HMAC mismatch at seq={seq}: entry may have been forged "
                    f"or the secret key has changed",
                )

            expected_previous = computed_hash

        return (True, f"OK: {count} entries verified")

    def export(self, output_path: Path | None = None) -> str:
        """Return the full audit log as a JSONL string.

        If *output_path* is provided the content is also written to that file.
        """
        if not self._log_path.exists():
            content = ""
        else:
            content = self._log_path.read_text(encoding="utf-8")

        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")

        return content

    def count(self) -> int:
        """Return the number of entries currently in the chain."""
        return self._seq

    # -- internal helpers ---------------------------------------------------

    def _recover_chain_state(self) -> None:
        """Read the last entry from the log file to restore seq and hash."""
        if not self._log_path.exists():
            return

        last_line: str | None = None
        with open(self._log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped:
                    last_line = stripped

        if last_line is None:
            return

        try:
            entry = json.loads(last_line)
            self._seq = entry["seq"]
            self._last_hash = entry["hash"]
        except (json.JSONDecodeError, KeyError):
            # Corrupted tail -- the caller should run verify_chain().
            pass

    def _iter_entries(self):
        """Yield parsed entries from the log file in order."""
        if not self._log_path.exists():
            return

        with open(self._log_path, "r", encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    yield json.loads(stripped)
                except json.JSONDecodeError:
                    continue

    def _append_locked(self, line: str) -> None:
        """Append *line* to the log file under an exclusive file lock."""
        with open(self._log_path, "a", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(line)
                fh.flush()
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _compute_hash(
        seq: int,
        timestamp: str,
        event_type: str,
        agent_id: str | None,
        details: dict[str, Any],
        previous_hash: str,
    ) -> str:
        """Compute the SHA-256 hash over the canonical entry fields."""
        canonical = json.dumps(
            [seq, timestamp, event_type, agent_id, details, previous_hash],
            separators=(",", ":"),
            sort_keys=True,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def _compute_hmac(self, entry_hash: str) -> str:
        """Compute HMAC-SHA256 of *entry_hash* using the server secret key."""
        digest = hmac.new(
            self._secret_key,
            entry_hash.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"hmac-sha256:{digest}"
