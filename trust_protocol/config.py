"""Environment-driven configuration for the TRUST Protocol server.

Two keys serve distinct purposes:

- **hmac_key** (``TRUST_PROTOCOL_SECRET_KEY``): Used for HMAC signing of
  tokens and audit chain entries.  Protects *integrity*.  Auto-generated
  and stored on disk if not set.

- **vault_password** (``TRUST_PROTOCOL_VAULT_PASSWORD``): Used for
  AES-256-GCM encryption of credentials.  Protects *secrecy*.  If set,
  the server auto-unseals at startup (dev/CI mode).  If not set, the
  server starts sealed and a human must run ``trust-protocol unseal``
  (production mode).
"""

from __future__ import annotations

import os
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TrustProtocolConfig:
    data_dir: Path
    hmac_key: str
    vault_password: Optional[str]
    admin_key: str
    host: str
    port: int

    # Derived subdirectories
    credentials_dir: Path = field(init=False)
    audit_dir: Path = field(init=False)
    agents_dir: Path = field(init=False)
    publishers_dir: Path = field(init=False)

    def __post_init__(self) -> None:
        self.credentials_dir = self.data_dir / "credentials"
        self.audit_dir = self.data_dir / "audit"
        self.agents_dir = self.data_dir / "agents"
        self.publishers_dir = self.data_dir / "publishers"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        for d in (self.data_dir, self.credentials_dir, self.audit_dir,
                  self.agents_dir, self.publishers_dir):
            d.mkdir(parents=True, exist_ok=True)

    # Backward-compat alias
    @property
    def secret_key(self) -> str:
        """Deprecated alias for hmac_key.  Use hmac_key directly."""
        return self.hmac_key

    @classmethod
    def from_env(cls) -> TrustProtocolConfig:
        data_dir = Path(os.environ.get("TRUST_PROTOCOL_DATA_DIR", "./data")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)

        hmac_key = os.environ.get("TRUST_PROTOCOL_SECRET_KEY") or secrets.token_hex(32)
        vault_password = os.environ.get("TRUST_PROTOCOL_VAULT_PASSWORD") or None
        admin_key = _resolve_admin_key(data_dir)
        host = os.environ.get("TRUST_PROTOCOL_HOST", "0.0.0.0")
        port = int(os.environ.get("TRUST_PROTOCOL_PORT", "9500"))

        return cls(
            data_dir=data_dir,
            hmac_key=hmac_key,
            vault_password=vault_password,
            admin_key=admin_key,
            host=host,
            port=port,
        )


def _resolve_admin_key(data_dir: Path) -> str:
    env_key = os.environ.get("TRUST_PROTOCOL_ADMIN_KEY")
    if env_key:
        return env_key

    key_file = data_dir / ".admin_key"
    if key_file.exists():
        return key_file.read_text().strip()

    generated = secrets.token_hex(32)
    key_file.write_text(generated)
    key_file.chmod(0o600)
    return generated


# ---------------------------------------------------------------------------
# Thread-safe singleton
# ---------------------------------------------------------------------------

_instance: TrustProtocolConfig | None = None
_lock = threading.Lock()


def get_config() -> TrustProtocolConfig:
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                _instance = TrustProtocolConfig.from_env()
    return _instance


def reset_config() -> None:
    """Reset the singleton. Useful in tests."""
    global _instance
    with _lock:
        _instance = None
