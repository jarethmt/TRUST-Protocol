"""Server seal state management.

The SealManager holds the vault master password in process memory after
an unseal operation.  The password is never written to disk, environment
variables, or configuration files.

Operating modes:
- **Production (sealed start)**: Server starts sealed.  A human runs
  ``trust-protocol unseal`` to provide the master password interactively.
- **Development (auto-unseal)**: Set ``TRUST_PROTOCOL_VAULT_PASSWORD`` in the
  environment and the server unseals automatically at startup.
"""

from __future__ import annotations

import threading
from typing import Optional


class SealManager:
    """Thread-safe manager for the server's sealed/unsealed state.

    The vault master password is held only in this object's memory after
    unseal.  It is cleared on seal or process exit.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._vault_password: Optional[str] = None
        self._sealed: bool = True

    @property
    def is_sealed(self) -> bool:
        """True if the server is sealed (credential operations disabled)."""
        return self._sealed

    def unseal(self, password: str) -> None:
        """Unseal the server by providing the vault master password.

        The password is stored in process memory only.
        """
        with self._lock:
            self._vault_password = password
            self._sealed = False

    def seal(self) -> None:
        """Re-seal the server, clearing the password from memory."""
        with self._lock:
            self._vault_password = None
            self._sealed = True

    def get_vault_password(self) -> Optional[str]:
        """Return the vault password if unsealed, None if sealed."""
        with self._lock:
            return self._vault_password


# ---------------------------------------------------------------------------
# Thread-safe singleton
# ---------------------------------------------------------------------------

_instance: Optional[SealManager] = None
_lock = threading.Lock()


def get_seal_manager() -> SealManager:
    """Return the global SealManager singleton.

    On first creation, if ``TRUST_PROTOCOL_VAULT_PASSWORD`` is set the
    manager auto-unseals so the server is immediately usable in dev/CI
    mode.
    """
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                import os
                mgr = SealManager()
                vault_password = os.environ.get("TRUST_PROTOCOL_VAULT_PASSWORD")
                if vault_password:
                    mgr.unseal(vault_password)
                _instance = mgr
    return _instance


def reset_seal_manager() -> None:
    """Reset the singleton.  Used in tests."""
    global _instance
    with _lock:
        _instance = None
