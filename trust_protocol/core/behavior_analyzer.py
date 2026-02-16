"""Behavioral monitoring and anomaly detection for the TRUST Protocol.

Agents submit behavioral metrics (API call counts, error rates, timing
patterns, resource usage). The analyzer computes a composite trust score
between 0.0 and 1.0 that gates token renewal.

Anomaly detection flags sudden changes in behavior patterns that may
indicate compromised or malfunctioning agents.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Metrics snapshot
# ---------------------------------------------------------------------------

@dataclass
class BehaviorMetrics:
    """A point-in-time snapshot of agent behavior."""
    agent_id: str
    timestamp: datetime
    # API usage
    api_calls: int = 0
    api_errors: int = 0
    # Credential usage
    credential_accesses: int = 0
    credential_denials: int = 0
    # Timing
    avg_response_time_ms: float = 0.0
    max_response_time_ms: float = 0.0
    # Resource
    requests_per_minute: float = 0.0
    # Custom
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "api_calls": self.api_calls,
            "api_errors": self.api_errors,
            "credential_accesses": self.credential_accesses,
            "credential_denials": self.credential_denials,
            "avg_response_time_ms": self.avg_response_time_ms,
            "max_response_time_ms": self.max_response_time_ms,
            "requests_per_minute": self.requests_per_minute,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> BehaviorMetrics:
        return cls(
            agent_id=data["agent_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            api_calls=data.get("api_calls", 0),
            api_errors=data.get("api_errors", 0),
            credential_accesses=data.get("credential_accesses", 0),
            credential_denials=data.get("credential_denials", 0),
            avg_response_time_ms=data.get("avg_response_time_ms", 0.0),
            max_response_time_ms=data.get("max_response_time_ms", 0.0),
            requests_per_minute=data.get("requests_per_minute", 0.0),
            metadata=data.get("metadata", {}),
        )


# ---------------------------------------------------------------------------
# Anomaly record
# ---------------------------------------------------------------------------

@dataclass
class Anomaly:
    """A detected behavioral anomaly."""
    agent_id: str
    timestamp: datetime
    anomaly_type: str  # "error_spike", "rate_spike", "credential_abuse", "timing_anomaly"
    severity: float  # 0.0 to 1.0
    description: str
    metrics_snapshot: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp.isoformat(),
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "description": self.description,
            "metrics_snapshot": self.metrics_snapshot,
        }


# ---------------------------------------------------------------------------
# Behavior analyzer
# ---------------------------------------------------------------------------

class BehaviorAnalyzer:
    """Analyzes agent behavior patterns and computes trust scores.

    The analyzer maintains a sliding window of metrics per agent and
    computes composite scores based on:

    1. Error rate (low errors = high score)
    2. Credential denial rate (few denials = high score)
    3. Request rate stability (consistent patterns = high score)
    4. Response time consistency (stable timing = high score)

    Scores range from 0.0 (untrusted) to 1.0 (fully trusted).
    Default score for agents with no history is 1.0 (benefit of doubt).
    """

    # Sliding window size
    _WINDOW_SIZE = 100

    # Thresholds for anomaly detection
    _ERROR_RATE_THRESHOLD = 0.3     # >30% error rate is anomalous
    _DENIAL_RATE_THRESHOLD = 0.5    # >50% denial rate is anomalous
    _RATE_SPIKE_FACTOR = 3.0        # 3x normal rate is a spike
    _TIMING_SPIKE_FACTOR = 5.0      # 5x normal timing is anomalous

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._metrics_dir = self._data_dir / "behavior"
        self._metrics_dir.mkdir(parents=True, exist_ok=True)

        # In-memory sliding windows: agent_id -> list of BehaviorMetrics
        self._windows: Dict[str, List[BehaviorMetrics]] = {}

        # Cached scores
        self._scores: Dict[str, float] = {}

        # Anomaly history
        self._anomalies: Dict[str, List[Anomaly]] = {}

    def submit_metrics(self, metrics: BehaviorMetrics) -> List[Anomaly]:
        """Submit a metrics snapshot for an agent.

        Returns any anomalies detected from this submission.
        """
        agent_id = metrics.agent_id

        # Add to sliding window
        if agent_id not in self._windows:
            self._windows[agent_id] = []

        window = self._windows[agent_id]
        window.append(metrics)

        # Trim to window size
        if len(window) > self._WINDOW_SIZE:
            self._windows[agent_id] = window[-self._WINDOW_SIZE:]

        # Detect anomalies
        anomalies = self._detect_anomalies(agent_id, metrics)

        if anomalies:
            if agent_id not in self._anomalies:
                self._anomalies[agent_id] = []
            self._anomalies[agent_id].extend(anomalies)

        # Recompute score
        self._scores[agent_id] = self._compute_score(agent_id)

        # Persist latest metrics
        self._persist_metrics(agent_id, metrics)

        return anomalies

    def get_score(self, agent_id: str) -> float:
        """Return the current behavior score for an agent.

        Returns 1.0 (full trust) if no metrics have been submitted.
        """
        return self._scores.get(agent_id, 1.0)

    def get_metrics_history(self, agent_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent metrics snapshots for an agent."""
        window = self._windows.get(agent_id, [])
        return [m.to_dict() for m in window[-limit:]]

    def get_anomalies(self, agent_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent anomalies for an agent."""
        anomalies = self._anomalies.get(agent_id, [])
        return [a.to_dict() for a in anomalies[-limit:]]

    def get_summary(self, agent_id: str) -> Dict[str, Any]:
        """Return a summary of agent behavior."""
        window = self._windows.get(agent_id, [])
        anomalies = self._anomalies.get(agent_id, [])

        total_calls = sum(m.api_calls for m in window)
        total_errors = sum(m.api_errors for m in window)
        total_cred_accesses = sum(m.credential_accesses for m in window)
        total_cred_denials = sum(m.credential_denials for m in window)

        return {
            "agent_id": agent_id,
            "behavior_score": self.get_score(agent_id),
            "metrics_count": len(window),
            "anomaly_count": len(anomalies),
            "total_api_calls": total_calls,
            "total_api_errors": total_errors,
            "error_rate": (total_errors / total_calls) if total_calls > 0 else 0.0,
            "total_credential_accesses": total_cred_accesses,
            "total_credential_denials": total_cred_denials,
            "recent_anomalies": [a.to_dict() for a in anomalies[-5:]],
        }

    # -- scoring ---------------------------------------------------------------

    def _compute_score(self, agent_id: str) -> float:
        """Compute composite behavior score from the sliding window.

        Components (weighted):
        - Error rate score (30%): lower error rate = higher score
        - Denial rate score (25%): fewer credential denials = higher
        - Rate stability score (25%): consistent request patterns = higher
        - Anomaly penalty (20%): recent anomalies reduce score
        """
        window = self._windows.get(agent_id, [])
        if not window:
            return 1.0

        # Error rate score (30%)
        total_calls = sum(m.api_calls for m in window)
        total_errors = sum(m.api_errors for m in window)
        if total_calls > 0:
            error_rate = total_errors / total_calls
            error_score = max(0.0, 1.0 - (error_rate * 2))  # 50% errors = 0 score
        else:
            error_score = 1.0

        # Denial rate score (25%)
        total_accesses = sum(m.credential_accesses for m in window)
        total_denials = sum(m.credential_denials for m in window)
        if total_accesses + total_denials > 0:
            denial_rate = total_denials / (total_accesses + total_denials)
            denial_score = max(0.0, 1.0 - (denial_rate * 2))
        else:
            denial_score = 1.0

        # Rate stability score (25%)
        rates = [m.requests_per_minute for m in window if m.requests_per_minute > 0]
        if len(rates) >= 2:
            mean_rate = sum(rates) / len(rates)
            if mean_rate > 0:
                variance = sum((r - mean_rate) ** 2 for r in rates) / len(rates)
                cv = math.sqrt(variance) / mean_rate  # coefficient of variation
                stability_score = max(0.0, 1.0 - cv)  # cv=1 means score=0
            else:
                stability_score = 1.0
        else:
            stability_score = 1.0

        # Anomaly penalty (20%)
        recent_anomalies = self._anomalies.get(agent_id, [])
        # Count anomalies in last hour
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        recent = [a for a in recent_anomalies if a.timestamp > cutoff]
        anomaly_penalty = min(1.0, len(recent) * 0.2)  # Each anomaly costs 0.2
        anomaly_score = 1.0 - anomaly_penalty

        # Weighted composite
        score = (
            error_score * 0.30
            + denial_score * 0.25
            + stability_score * 0.25
            + anomaly_score * 0.20
        )

        return round(max(0.0, min(1.0, score)), 4)

    # -- anomaly detection -----------------------------------------------------

    def _detect_anomalies(
        self, agent_id: str, current: BehaviorMetrics
    ) -> List[Anomaly]:
        """Check for anomalous behavior in the latest metrics submission."""
        anomalies: List[Anomaly] = []
        window = self._windows.get(agent_id, [])
        now = datetime.now(timezone.utc)

        if len(window) < 3:
            # Not enough history to detect anomalies
            return anomalies

        # Use all but the current entry as baseline
        baseline = window[:-1]

        # 1. Error rate spike
        if current.api_calls > 0:
            current_error_rate = current.api_errors / current.api_calls
            if current_error_rate > self._ERROR_RATE_THRESHOLD:
                anomalies.append(Anomaly(
                    agent_id=agent_id,
                    timestamp=now,
                    anomaly_type="error_spike",
                    severity=min(1.0, current_error_rate),
                    description=f"Error rate {current_error_rate:.1%} exceeds threshold {self._ERROR_RATE_THRESHOLD:.0%}",
                    metrics_snapshot=current.to_dict(),
                ))

        # 2. Credential denial spike
        total_cred = current.credential_accesses + current.credential_denials
        if total_cred > 0:
            denial_rate = current.credential_denials / total_cred
            if denial_rate > self._DENIAL_RATE_THRESHOLD:
                anomalies.append(Anomaly(
                    agent_id=agent_id,
                    timestamp=now,
                    anomaly_type="credential_abuse",
                    severity=min(1.0, denial_rate),
                    description=f"Credential denial rate {denial_rate:.1%} exceeds threshold {self._DENIAL_RATE_THRESHOLD:.0%}",
                    metrics_snapshot=current.to_dict(),
                ))

        # 3. Request rate spike
        baseline_rates = [m.requests_per_minute for m in baseline if m.requests_per_minute > 0]
        if baseline_rates and current.requests_per_minute > 0:
            avg_rate = sum(baseline_rates) / len(baseline_rates)
            if avg_rate > 0 and current.requests_per_minute > avg_rate * self._RATE_SPIKE_FACTOR:
                anomalies.append(Anomaly(
                    agent_id=agent_id,
                    timestamp=now,
                    anomaly_type="rate_spike",
                    severity=min(1.0, (current.requests_per_minute / avg_rate) / 10),
                    description=f"Request rate {current.requests_per_minute:.1f}/min is {current.requests_per_minute/avg_rate:.1f}x baseline avg {avg_rate:.1f}/min",
                    metrics_snapshot=current.to_dict(),
                ))

        # 4. Response time anomaly
        baseline_times = [m.avg_response_time_ms for m in baseline if m.avg_response_time_ms > 0]
        if baseline_times and current.avg_response_time_ms > 0:
            avg_time = sum(baseline_times) / len(baseline_times)
            if avg_time > 0 and current.avg_response_time_ms > avg_time * self._TIMING_SPIKE_FACTOR:
                anomalies.append(Anomaly(
                    agent_id=agent_id,
                    timestamp=now,
                    anomaly_type="timing_anomaly",
                    severity=min(1.0, (current.avg_response_time_ms / avg_time) / 10),
                    description=f"Avg response time {current.avg_response_time_ms:.0f}ms is {current.avg_response_time_ms/avg_time:.1f}x baseline {avg_time:.0f}ms",
                    metrics_snapshot=current.to_dict(),
                ))

        return anomalies

    # -- persistence -----------------------------------------------------------

    def _persist_metrics(self, agent_id: str, metrics: BehaviorMetrics) -> None:
        """Append metrics to agent's JSONL file."""
        safe_id = agent_id.replace("/", "_").replace("..", "_")
        path = self._metrics_dir / f"{safe_id}.jsonl"
        try:
            with open(path, "a") as f:
                f.write(json.dumps(metrics.to_dict()) + "\n")
        except OSError:
            logger.exception("Failed to persist metrics for %s", agent_id)
