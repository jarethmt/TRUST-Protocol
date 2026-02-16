"""Behavioral monitoring routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from trust_protocol.api.middleware import get_services, require_admin, require_agent
from trust_protocol.core.agent_identity import AgentIdentity
from trust_protocol.core.audit_chain import ANOMALY_DETECTED, AuditChain
from trust_protocol.core.behavior_analyzer import BehaviorAnalyzer, BehaviorMetrics

router = APIRouter(prefix="/v1", tags=["behavior"])

# Module-level analyzer (lazy init)
_analyzer: Optional[BehaviorAnalyzer] = None

def _get_analyzer(services: dict) -> BehaviorAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = BehaviorAnalyzer(services["config"].data_dir)
    return _analyzer


# --- Schemas ---

class MetricsSubmitRequest(BaseModel):
    api_calls: int = Field(default=0, ge=0)
    api_errors: int = Field(default=0, ge=0)
    credential_accesses: int = Field(default=0, ge=0)
    credential_denials: int = Field(default=0, ge=0)
    avg_response_time_ms: float = Field(default=0.0, ge=0.0)
    max_response_time_ms: float = Field(default=0.0, ge=0.0)
    requests_per_minute: float = Field(default=0.0, ge=0.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BehaviorScoreResponse(BaseModel):
    agent_id: str
    behavior_score: float
    metrics_count: int
    anomaly_count: int


# --- Routes ---

@router.post("/agents/{agent_id}/metrics")
async def submit_metrics(
    agent_id: str,
    body: MetricsSubmitRequest,
    agent: AgentIdentity = Depends(require_agent),
    services: dict = Depends(get_services),
):
    """Submit behavioral metrics for an agent. Agent auth required.
    The agent_id in the path must match the authenticated agent."""
    if agent.agent_id != agent_id:
        raise HTTPException(403, "Cannot submit metrics for another agent")

    analyzer = _get_analyzer(services)
    audit: AuditChain = services["audit_chain"]

    from datetime import datetime, timezone
    metrics = BehaviorMetrics(
        agent_id=agent_id,
        timestamp=datetime.now(timezone.utc),
        api_calls=body.api_calls,
        api_errors=body.api_errors,
        credential_accesses=body.credential_accesses,
        credential_denials=body.credential_denials,
        avg_response_time_ms=body.avg_response_time_ms,
        max_response_time_ms=body.max_response_time_ms,
        requests_per_minute=body.requests_per_minute,
        metadata=body.metadata,
    )

    anomalies = analyzer.submit_metrics(metrics)

    # Log anomalies to audit chain
    for anomaly in anomalies:
        audit.log(ANOMALY_DETECTED, agent_id, anomaly.to_dict())

    score = analyzer.get_score(agent_id)

    return {
        "agent_id": agent_id,
        "behavior_score": score,
        "anomalies_detected": len(anomalies),
        "anomalies": [a.to_dict() for a in anomalies],
    }


@router.get("/agents/{agent_id}/behavior-score", response_model=BehaviorScoreResponse)
async def get_behavior_score(
    agent_id: str,
    services: dict = Depends(get_services),
    _admin=Depends(require_admin),
):
    """Get the current behavior score for an agent. Admin auth required."""
    analyzer = _get_analyzer(services)
    summary = analyzer.get_summary(agent_id)

    return BehaviorScoreResponse(
        agent_id=agent_id,
        behavior_score=summary["behavior_score"],
        metrics_count=summary["metrics_count"],
        anomaly_count=summary["anomaly_count"],
    )


@router.get("/agents/{agent_id}/behavior")
async def get_behavior_summary(
    agent_id: str,
    services: dict = Depends(get_services),
    _admin=Depends(require_admin),
):
    """Get full behavior summary including metrics history and anomalies. Admin auth."""
    analyzer = _get_analyzer(services)
    return analyzer.get_summary(agent_id)


@router.get("/agents/{agent_id}/anomalies")
async def get_anomalies(
    agent_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    services: dict = Depends(get_services),
    _admin=Depends(require_admin),
):
    """Get recent anomalies for an agent. Admin auth."""
    analyzer = _get_analyzer(services)
    return {"agent_id": agent_id, "anomalies": analyzer.get_anomalies(agent_id, limit)}
