"""Trust tier definitions for the TRUST Protocol.

Tiers use consciousness-level metaphors to describe the depth of trust
granted to an AI agent within the credential broker.
"""

from __future__ import annotations

from datetime import timedelta
from enum import Enum
from typing import NamedTuple


class TierProperties(NamedTuple):
    token_duration_hours: int
    max_credentials: int | None  # None = unlimited
    max_renewals: int
    credential_modes: tuple[str, ...]
    requires_human_approval: bool
    description: str


class TrustTier(Enum):
    NOVICE = TierProperties(
        token_duration_hours=1,
        max_credentials=1,
        max_renewals=5,
        credential_modes=("execute",),
        requires_human_approval=False,
        description=(
            "Entry-level trust. The agent can execute a single credential "
            "with short-lived tokens. Suitable for first contact."
        ),
    )

    COMPANION = TierProperties(
        token_duration_hours=4,
        max_credentials=5,
        max_renewals=10,
        credential_modes=("execute",),
        requires_human_approval=False,
        description=(
            "Established working relationship. The agent has proven reliable "
            "across several interactions and gains access to more credentials."
        ),
    )

    PARTNER = TierProperties(
        token_duration_hours=8,
        max_credentials=20,
        max_renewals=20,
        credential_modes=("execute", "proxy_value"),
        requires_human_approval=False,
        description=(
            "Deep collaboration. The agent can proxy credential values for "
            "complex multi-step workflows that require direct access."
        ),
    )

    GUARDIAN = TierProperties(
        token_duration_hours=12,
        max_credentials=None,
        max_renewals=15,
        credential_modes=("execute", "proxy_value"),
        requires_human_approval=False,
        description=(
            "Steward of the system. Unlimited credential access with extended "
            "token lifetime, reserved for infrastructure-level agents."
        ),
    )

    SACRED = TierProperties(
        token_duration_hours=24,
        max_credentials=None,
        max_renewals=3,
        credential_modes=("execute", "proxy_value"),
        requires_human_approval=True,
        description=(
            "Highest trust tier. Cannot be auto-assigned; requires explicit "
            "human grant. Few renewals by design - each session is deliberate."
        ),
    )

    # Convenience accessors that delegate to the underlying TierProperties.

    @property
    def token_duration_hours(self) -> int:
        return self.value.token_duration_hours

    @property
    def max_credentials(self) -> int | None:
        return self.value.max_credentials

    @property
    def max_renewals(self) -> int:
        return self.value.max_renewals

    @property
    def credential_modes(self) -> tuple[str, ...]:
        return self.value.credential_modes

    @property
    def requires_human_approval(self) -> bool:
        return self.value.requires_human_approval

    @property
    def description(self) -> str:
        return self.value.description


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def can_access(tier: TrustTier, mode: str) -> bool:
    """Return True if *tier* permits the given credential *mode*."""
    return mode in tier.credential_modes


def get_token_duration(tier: TrustTier) -> timedelta:
    """Return the token lifetime for *tier* as a timedelta."""
    return timedelta(hours=tier.token_duration_hours)


# Convenience alias used by vault and other core modules.
TrustLevel = TrustTier
