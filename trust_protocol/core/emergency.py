"""
Emergency controls for the TRUST Protocol.

Provides three granularity levels of instant access revocation:

1. **Global** -- stop ALL agent access immediately.
2. **Per-agent** -- stop a specific agent by ``agent_id``.
3. **Per-credential** -- stop access to a specific credential by name.

Each brake is represented by a JSON file whose mere *existence* signals that
access is blocked.  This file-based approach means that even if the Python
process crashes or restarts, the brake remains engaged until a human
explicitly clears it.

Clearing the global brake requires a deliberate confirmation string
(``"CONFIRM_RESTORE_ACCESS"``) to prevent accidental re-enablement.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GLOBAL_CONFIRMATION = "CONFIRM_RESTORE_ACCESS"


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class EmergencyController:
    """File-based emergency brake system.

    Parameters
    ----------
    data_dir:
        Root data directory for the TRUST Protocol instance.  Emergency
        files are stored under ``<data_dir>/emergency/``.
    """

    def __init__(self, data_dir: Path) -> None:
        self._base = Path(data_dir) / "emergency"
        self._agents_dir = self._base / "agents"
        self._credentials_dir = self._base / "credentials"

        # Ensure directory structure exists
        self._base.mkdir(parents=True, exist_ok=True)
        self._agents_dir.mkdir(parents=True, exist_ok=True)
        self._credentials_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # File-path helpers
    # ------------------------------------------------------------------

    @property
    def _global_file(self) -> Path:
        return self._base / "GLOBAL_BRAKE.json"

    def _agent_file(self, agent_id: str) -> Path:
        # Sanitise to prevent directory traversal
        safe_name = agent_id.replace("/", "_").replace("..", "_")
        return self._agents_dir / f"{safe_name}.json"

    def _credential_file(self, credential_name: str) -> Path:
        safe_name = credential_name.replace("/", "_").replace("..", "_")
        return self._credentials_dir / f"{safe_name}.json"

    # ------------------------------------------------------------------
    # Global brake
    # ------------------------------------------------------------------

    def activate_global(self, reason: str) -> bool:
        """Engage the global brake.  Blocks ALL credential access.

        Returns ``True`` on success (always succeeds unless an I/O error
        occurs, in which case the exception propagates).
        """
        payload = self._brake_payload(reason, scope="global")
        self._global_file.write_text(json.dumps(payload, indent=2))
        return True

    def clear_global(self, confirmation: str) -> bool:
        """Disengage the global brake.

        Requires *confirmation* to equal ``"CONFIRM_RESTORE_ACCESS"`` to
        guard against accidental clearing.  Returns ``True`` if the brake
        existed and was removed, ``False`` if the confirmation was wrong
        or no brake was active.
        """
        if confirmation != _GLOBAL_CONFIRMATION:
            return False
        if not self._global_file.exists():
            return False
        self._global_file.unlink()
        return True

    # ------------------------------------------------------------------
    # Per-agent brake
    # ------------------------------------------------------------------

    def activate_agent(self, agent_id: str, reason: str) -> bool:
        """Block a specific agent from accessing any credential."""
        payload = self._brake_payload(reason, scope="agent", agent_id=agent_id)
        self._agent_file(agent_id).write_text(json.dumps(payload, indent=2))
        return True

    def clear_agent(self, agent_id: str) -> bool:
        """Restore access for a specific agent.

        Returns ``True`` if the brake existed and was removed.
        """
        path = self._agent_file(agent_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    # ------------------------------------------------------------------
    # Per-credential brake
    # ------------------------------------------------------------------

    def activate_credential(self, credential_name: str, reason: str) -> bool:
        """Block all access to a specific credential."""
        payload = self._brake_payload(
            reason, scope="credential", credential_name=credential_name,
        )
        self._credential_file(credential_name).write_text(
            json.dumps(payload, indent=2),
        )
        return True

    def clear_credential(self, credential_name: str) -> bool:
        """Restore access to a specific credential.

        Returns ``True`` if the brake existed and was removed.
        """
        path = self._credential_file(credential_name)
        if not path.exists():
            return False
        path.unlink()
        return True

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_blocked(
        self,
        agent_id: Optional[str] = None,
        credential_name: Optional[str] = None,
    ) -> bool:
        """Return ``True`` if access should be denied.

        Checks are evaluated in order of severity:

        1. Global brake (blocks everything).
        2. Agent brake (blocks the given *agent_id*).
        3. Credential brake (blocks the given *credential_name*).

        If called with no arguments, only the global brake is checked.
        """
        # Global
        if self._global_file.exists():
            return True

        # Per-agent
        if agent_id is not None and self._agent_file(agent_id).exists():
            return True

        # Per-credential
        if credential_name is not None and self._credential_file(credential_name).exists():
            return True

        return False

    def status(self) -> Dict[str, Any]:
        """Return a snapshot of every active brake.

        The returned dictionary has three keys:

        - ``global_active`` (bool): whether the global brake is engaged.
        - ``blocked_agents`` (list[dict]): info for each blocked agent.
        - ``blocked_credentials`` (list[dict]): info for each blocked credential.
        """
        result: Dict[str, Any] = {
            "global_active": self._global_file.exists(),
            "global_details": None,
            "blocked_agents": [],
            "blocked_credentials": [],
        }

        # Global details
        if self._global_file.exists():
            result["global_details"] = self._read_brake(self._global_file)

        # Per-agent brakes
        result["blocked_agents"] = self._collect_brakes(self._agents_dir)

        # Per-credential brakes
        result["blocked_credentials"] = self._collect_brakes(self._credentials_dir)

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _brake_payload(
        reason: str,
        scope: str,
        agent_id: Optional[str] = None,
        credential_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build the JSON payload written to a brake file."""
        payload: Dict[str, Any] = {
            "activated": datetime.now(timezone.utc).isoformat(),
            "scope": scope,
            "reason": reason,
        }
        if agent_id is not None:
            payload["agent_id"] = agent_id
        if credential_name is not None:
            payload["credential_name"] = credential_name
        return payload

    @staticmethod
    def _read_brake(path: Path) -> Optional[Dict[str, Any]]:
        """Read and parse a brake JSON file, returning ``None`` on failure."""
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

    def _collect_brakes(self, directory: Path) -> List[Dict[str, Any]]:
        """Gather info from every ``.json`` file in *directory*."""
        brakes: List[Dict[str, Any]] = []
        if not directory.exists():
            return brakes
        for path in sorted(directory.glob("*.json")):
            data = self._read_brake(path)
            if data is not None:
                brakes.append(data)
        return brakes
