"""TRUST Protocol API application factory."""

from __future__ import annotations

from fastapi import FastAPI

from trust_protocol import __version__
from trust_protocol.api.routes import agents, audit, credentials, emergency, health, skills, tokens


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="TRUST Protocol",
        description="Transparent Revocable Unified Security & Trust - credential broker for AI agents",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Register route modules (each router already defines its own prefix)
    app.include_router(health.router)
    app.include_router(agents.router)
    app.include_router(tokens.router)
    app.include_router(credentials.router)
    app.include_router(audit.router)
    app.include_router(emergency.router)
    app.include_router(skills.router)
    app.include_router(skills.publisher_router)

    return app
