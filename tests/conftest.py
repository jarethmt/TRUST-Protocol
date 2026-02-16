"""Shared test fixtures for the TRUST Protocol test suite."""

import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Force test data directory before any imports that read config at module level.
_test_dir = tempfile.mkdtemp(prefix="trust-test-")
os.environ["TRUST_PROTOCOL_DATA_DIR"] = _test_dir

from trust_protocol.config import get_config, reset_config
from trust_protocol.api.app import create_app
from trust_protocol.api.middleware import reset_services


@pytest.fixture(autouse=True)
def clean_state(tmp_path):
    """Reset config and services for each test, pointing at a fresh tmp_path."""
    os.environ["TRUST_PROTOCOL_DATA_DIR"] = str(tmp_path)
    reset_config()
    reset_services()

    # The behavior route keeps a module-level _analyzer singleton that must
    # also be cleared between tests so it picks up the new data directory.
    import trust_protocol.api.routes.behavior as _bmod
    _bmod._analyzer = None

    yield

    reset_config()
    reset_services()
    _bmod._analyzer = None


@pytest.fixture
def config(tmp_path):
    """Return a fresh TrustProtocolConfig rooted at tmp_path."""
    os.environ["TRUST_PROTOCOL_DATA_DIR"] = str(tmp_path)
    reset_config()
    return get_config()


@pytest.fixture
def client(config):
    """FastAPI TestClient wired to a clean application instance."""
    reset_services()
    app = create_app()
    return TestClient(app)


@pytest.fixture
def admin_key(config):
    """The auto-generated admin key for this test run."""
    return config.admin_key


@pytest.fixture
def admin_headers(admin_key):
    """Headers dict with the admin key for authenticated requests."""
    return {"X-Admin-Key": admin_key}


@pytest.fixture
def registered_agent(client, admin_headers):
    """Register a test agent and return the full response dict (includes api_key)."""
    r = client.post("/v1/agents", headers=admin_headers, json={
        "name": "test-agent",
        "agent_type": "executor",
        "description": "Test agent for the test suite",
        "required_credentials": ["test_cred"],
        "capabilities": ["http_request"],
    })
    assert r.status_code == 201, f"Agent registration failed: {r.text}"
    return r.json()


@pytest.fixture
def agent_headers(registered_agent):
    """Headers dict with the agent API key for agent-authenticated requests."""
    return {"X-Agent-Key": registered_agent["api_key"]}
