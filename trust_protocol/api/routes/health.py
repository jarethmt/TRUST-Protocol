"""Health check endpoint."""

from __future__ import annotations

import time

from fastapi import APIRouter

from trust_protocol import __version__
from trust_protocol.api.middleware import get_start_time
from trust_protocol.api.schemas import HealthResponse

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    start = get_start_time()
    return HealthResponse(
        status="ok",
        version=__version__,
        uptime_seconds=round(time.time() - start, 2),
    )
