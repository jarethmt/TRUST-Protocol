"""Environment-driven configuration for the TRUST Protocol server."""

from __future__ import annotations

import os
import secrets
import threading
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TrustProtocolConfig:
    data_dir: Path
    secret_key: str
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

    @classmethod
    def from_env(cls) -> TrustProtocolConfig:
        data_dir = Path(os.environ.get("TRUST_PROTOCOL_DATA_DIR", "./data")).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)

        secret_key = os.environ.get("TRUST_PROTOCOL_SECRET_KEY") or secrets.token_hex(32)
        admin_key = _resolve_admin_key(data_dir)
        host = os.environ.get("TRUST_PROTOCOL_HOST", "0.0.0.0")
        port = int(os.environ.get("TRUST_PROTOCOL_PORT", "9500"))

        return cls(
            data_dir=data_dir,
            secret_key=secret_key,
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
