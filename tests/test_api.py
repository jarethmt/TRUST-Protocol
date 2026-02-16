"""Tests for the TRUST Protocol REST API.

Tests the FastAPI application through the TestClient, covering all
route groups: health, agents, tokens, credentials, audit, emergency,
skills/publishers, and behavior.
"""

import base64

import pytest


# =========================================================================
# Health
# =========================================================================


class TestHealth:
    """Health endpoint should be publicly accessible."""

    def test_health(self, client):
        r = client.get("/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data


# =========================================================================
# Agents
# =========================================================================


class TestAgents:
    """Agent registration and lifecycle management."""

    def test_register(self, client, admin_headers):
        r = client.post("/v1/agents", headers=admin_headers, json={
            "name": "my-agent",
            "agent_type": "executor",
            "description": "test",
        })
        assert r.status_code == 201
        data = r.json()
        assert "agent_id" in data
        assert "api_key" in data
        assert data["api_key"].startswith("tp_")
        assert data["agent_id"].startswith("agt_")
        assert data["status"] == "active"

    def test_register_duplicate_name(self, client, admin_headers):
        body = {
            "name": "dup-agent",
            "agent_type": "executor",
            "description": "test",
        }
        r = client.post("/v1/agents", headers=admin_headers, json=body)
        assert r.status_code == 201

        r = client.post("/v1/agents", headers=admin_headers, json=body)
        assert r.status_code == 409

    def test_list(self, client, admin_headers, registered_agent):
        r = client.get("/v1/agents", headers=admin_headers)
        assert r.status_code == 200
        agents = r.json()
        assert len(agents) >= 1
        assert any(a["agent_id"] == registered_agent["agent_id"] for a in agents)

    def test_get(self, client, admin_headers, registered_agent):
        r = client.get(
            f"/v1/agents/{registered_agent['agent_id']}",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "test-agent"

    def test_promote(self, client, admin_headers, registered_agent):
        r = client.patch(
            f"/v1/agents/{registered_agent['agent_id']}/trust-level",
            headers=admin_headers,
            json={"trust_tier": "PARTNER"},
        )
        assert r.status_code == 200
        assert r.json()["trust_tier"] == "PARTNER"

    def test_suspend(self, client, admin_headers, registered_agent):
        r = client.post(
            f"/v1/agents/{registered_agent['agent_id']}/suspend",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "suspended"

    def test_revoke(self, client, admin_headers, registered_agent):
        r = client.post(
            f"/v1/agents/{registered_agent['agent_id']}/revoke",
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "revoked"

    def test_not_found(self, client, admin_headers):
        r = client.get("/v1/agents/agt_nonexistent", headers=admin_headers)
        assert r.status_code == 404

    def test_auth_required(self, client):
        r = client.get("/v1/agents")
        assert r.status_code == 401

    def test_wrong_admin_key(self, client):
        r = client.get("/v1/agents", headers={"X-Admin-Key": "wrong"})
        assert r.status_code == 401


# =========================================================================
# Tokens
# =========================================================================


class TestTokens:
    """Token issuance, validation, renewal, and revocation."""

    def test_issue_and_validate(self, client, admin_headers, registered_agent):
        r = client.post("/v1/tokens", headers=admin_headers, json={
            "agent_id": registered_agent["agent_id"],
            "credential_patterns": ["test_*"],
        })
        assert r.status_code == 201
        data = r.json()
        token_id = data["token_id"]
        assert token_id.startswith("tok_")
        assert data["agent_id"] == registered_agent["agent_id"]

        # Validate by fetching the token
        r = client.get(f"/v1/tokens/{token_id}", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["token_id"] == token_id

    def test_issue_for_nonexistent_agent(self, client, admin_headers):
        r = client.post("/v1/tokens", headers=admin_headers, json={
            "agent_id": "agt_nonexistent",
        })
        assert r.status_code == 404

    def test_renew_with_agent_key(self, client, admin_headers, registered_agent, agent_headers):
        # Issue a token
        r = client.post("/v1/tokens", headers=admin_headers, json={
            "agent_id": registered_agent["agent_id"],
        })
        assert r.status_code == 201
        token_id = r.json()["token_id"]

        # Renew with agent key
        r = client.post(
            f"/v1/tokens/{token_id}/renew",
            headers=agent_headers,
            json={"behavior_score": 0.95},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["renewal_count"] == 1
        assert data["token_id"] != token_id  # New token issued

    def test_renew_with_admin_key(self, client, admin_headers, registered_agent):
        r = client.post("/v1/tokens", headers=admin_headers, json={
            "agent_id": registered_agent["agent_id"],
        })
        token_id = r.json()["token_id"]

        r = client.post(
            f"/v1/tokens/{token_id}/renew",
            headers=admin_headers,
            json={"behavior_score": 0.95},
        )
        assert r.status_code == 200

    def test_renew_denied_low_score(self, client, admin_headers, registered_agent):
        r = client.post("/v1/tokens", headers=admin_headers, json={
            "agent_id": registered_agent["agent_id"],
        })
        token_id = r.json()["token_id"]

        r = client.post(
            f"/v1/tokens/{token_id}/renew",
            headers=admin_headers,
            json={"behavior_score": 0.1},
        )
        assert r.status_code == 400

    def test_list_tokens(self, client, admin_headers, registered_agent):
        # Issue a token
        client.post("/v1/tokens", headers=admin_headers, json={
            "agent_id": registered_agent["agent_id"],
        })

        r = client.get("/v1/tokens", headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_revoke_token(self, client, admin_headers, registered_agent):
        r = client.post("/v1/tokens", headers=admin_headers, json={
            "agent_id": registered_agent["agent_id"],
        })
        token_id = r.json()["token_id"]

        r = client.delete(f"/v1/tokens/{token_id}", headers=admin_headers)
        assert r.status_code == 204

        # Token should no longer be valid
        r = client.get(f"/v1/tokens/{token_id}", headers=admin_headers)
        assert r.status_code == 404


# =========================================================================
# Credentials
# =========================================================================


class TestCredentials:
    """Credential storage, listing, and execution."""

    def test_store_and_list(self, client, admin_headers):
        r = client.post("/v1/credentials", headers=admin_headers, json={
            "name": "test_key",
            "credential_data": {"value": "secret"},
            "minimum_trust": "NOVICE",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "test_key"
        assert data["minimum_trust"] == "NOVICE"

        r = client.get("/v1/credentials", headers=admin_headers)
        assert r.status_code == 200
        creds = r.json()
        assert len(creds) >= 1
        assert any(c["name"] == "test_key" for c in creds)

    def test_delete_credential(self, client, admin_headers):
        client.post("/v1/credentials", headers=admin_headers, json={
            "name": "to_delete",
            "credential_data": {"value": "secret"},
            "minimum_trust": "NOVICE",
        })

        r = client.delete("/v1/credentials/to_delete", headers=admin_headers)
        assert r.status_code == 204

        # Should be gone
        r = client.delete("/v1/credentials/to_delete", headers=admin_headers)
        assert r.status_code == 404

    def test_execute(self, client, admin_headers, registered_agent, agent_headers):
        # Store credential
        client.post("/v1/credentials", headers=admin_headers, json={
            "name": "exec_test",
            "credential_data": {"value": "secret"},
            "minimum_trust": "NOVICE",
        })

        # Execute with agent auth -- the agent needs an agent_id in the body too
        r = client.post(
            "/v1/credentials/exec_test/execute",
            headers=agent_headers,
            json={
                "agent_id": registered_agent["agent_id"],
                "purpose": "testing credential access",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["granted"] is True
        assert "access_id" in data
        assert "expires" in data

    def test_execute_denied_trust(self, client, admin_headers, registered_agent, agent_headers):
        """Agent at NOVICE/COMPANION cannot access a SACRED-level credential."""
        client.post("/v1/credentials", headers=admin_headers, json={
            "name": "sacred_cred",
            "credential_data": {"value": "top-secret"},
            "minimum_trust": "SACRED",
        })

        r = client.post(
            "/v1/credentials/sacred_cred/execute",
            headers=agent_headers,
            json={
                "agent_id": registered_agent["agent_id"],
                "purpose": "testing denial",
            },
        )
        assert r.status_code == 403

    def test_execute_nonexistent_credential(self, client, admin_headers, registered_agent, agent_headers):
        r = client.post(
            "/v1/credentials/no_such_cred/execute",
            headers=agent_headers,
            json={
                "agent_id": registered_agent["agent_id"],
                "purpose": "testing",
            },
        )
        assert r.status_code == 403


# =========================================================================
# Audit
# =========================================================================


class TestAudit:
    """Audit trail query, verification, and counting."""

    def test_query(self, client, admin_headers, registered_agent):
        r = client.get("/v1/audit", headers=admin_headers)
        assert r.status_code == 200
        entries = r.json()
        # Agent registration should have been logged
        assert len(entries) >= 1
        event_types = [e["event_type"] for e in entries]
        assert "AGENT_REGISTERED" in event_types

    def test_verify(self, client, admin_headers, registered_agent):
        r = client.get("/v1/audit/verify", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert "OK" in data["message"]

    def test_count(self, client, admin_headers, registered_agent):
        r = client.get("/v1/audit/count", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["count"] >= 1

    def test_export(self, client, admin_headers, registered_agent):
        r = client.get("/v1/audit/export", headers=admin_headers)
        assert r.status_code == 200
        assert "AGENT_REGISTERED" in r.text

    def test_query_with_filter(self, client, admin_headers, registered_agent):
        r = client.get(
            "/v1/audit",
            headers=admin_headers,
            params={"event_type": "AGENT_REGISTERED"},
        )
        assert r.status_code == 200
        entries = r.json()
        assert all(e["event_type"] == "AGENT_REGISTERED" for e in entries)

    def test_auth_required(self, client):
        r = client.get("/v1/audit")
        assert r.status_code == 401


# =========================================================================
# Emergency
# =========================================================================


class TestEmergency:
    """Emergency brake activation, clearing, and status."""

    def test_activate_and_clear_global(self, client, admin_headers):
        r = client.post("/v1/emergency/activate", headers=admin_headers, json={
            "reason": "test emergency",
            "scope": "global",
        })
        assert r.status_code == 200
        assert r.json()["global_active"] is True

        r = client.post("/v1/emergency/clear", headers=admin_headers, json={
            "scope": "global",
            "confirmation": "CONFIRM_RESTORE_ACCESS",
        })
        assert r.status_code == 200
        assert r.json()["global_active"] is False

    def test_activate_agent_scope(self, client, admin_headers, registered_agent):
        r = client.post("/v1/emergency/activate", headers=admin_headers, json={
            "reason": "suspicious agent",
            "scope": "agent",
            "agent_id": registered_agent["agent_id"],
        })
        assert r.status_code == 200
        assert len(r.json()["blocked_agents"]) >= 1

    def test_activate_credential_scope(self, client, admin_headers):
        r = client.post("/v1/emergency/activate", headers=admin_headers, json={
            "reason": "compromised credential",
            "scope": "credential",
            "credential_name": "api_key_123",
        })
        assert r.status_code == 200
        assert len(r.json()["blocked_credentials"]) >= 1

    def test_clear_wrong_confirmation(self, client, admin_headers):
        # Activate first
        client.post("/v1/emergency/activate", headers=admin_headers, json={
            "reason": "test",
            "scope": "global",
        })

        r = client.post("/v1/emergency/clear", headers=admin_headers, json={
            "scope": "global",
            "confirmation": "WRONG",
        })
        assert r.status_code == 400

        # Clean up
        client.post("/v1/emergency/clear", headers=admin_headers, json={
            "scope": "global",
            "confirmation": "CONFIRM_RESTORE_ACCESS",
        })

    def test_status(self, client, admin_headers):
        r = client.get("/v1/emergency/status", headers=admin_headers)
        assert r.status_code == 200
        data = r.json()
        assert "global_active" in data
        assert "blocked_agents" in data
        assert "blocked_credentials" in data

    def test_auth_required(self, client):
        r = client.get("/v1/emergency/status")
        assert r.status_code == 401


# =========================================================================
# Skills & Publishers
# =========================================================================


class TestSkills:
    """Skill signing, verification, and publisher management."""

    def test_register_publisher(self, client, admin_headers):
        from trust_protocol.core.skill_signer import generate_keypair

        _priv, pub = generate_keypair()

        r = client.post("/v1/publishers", headers=admin_headers, json={
            "name": "test-pub",
            "organization": "Test Org",
            "public_key_pem": pub.decode(),
        })
        assert r.status_code == 201
        data = r.json()
        assert "publisher_id" in data
        assert data["name"] == "test-pub"
        assert data["status"] == "active"

    def test_list_publishers(self, client, admin_headers):
        from trust_protocol.core.skill_signer import generate_keypair

        _priv, pub = generate_keypair()
        client.post("/v1/publishers", headers=admin_headers, json={
            "name": "list-test-pub",
            "organization": "Test",
            "public_key_pem": pub.decode(),
        })

        r = client.get("/v1/publishers", headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_full_local_signing_flow(self, client, admin_headers):
        """End-to-end: register publisher, sign locally, publish, verify, revoke, re-verify."""
        from trust_protocol.core.skill_signer import generate_keypair, hash_code
        from trust_protocol.sdk import TrustProtocolClient

        priv, pub = generate_keypair()

        # 1. Register publisher
        r = client.post("/v1/publishers", headers=admin_headers, json={
            "name": "signing-flow-pub",
            "organization": "Test",
            "public_key_pem": pub.decode(),
        })
        assert r.status_code == 201
        pub_id = r.json()["publisher_id"]

        # 2. Sign locally (no server call)
        signed = TrustProtocolClient.sign_locally(
            name="test-skill",
            version="1.0.0",
            publisher_id=pub_id,
            code_hash=hash_code("print('hello')"),
            private_key_pem=priv,
        )
        assert "manifest" in signed
        assert "signature" in signed

        # 3. Publish to registry
        r = client.post("/v1/skills/publish", headers=admin_headers, json=signed)
        assert r.status_code == 200
        assert r.json()["published"] is True
        assert r.json()["publisher_name"] == "signing-flow-pub"

        # 4. Verify (no auth required)
        r = client.post("/v1/skills/verify", json=signed)
        assert r.status_code == 200
        assert r.json()["verified"] is True
        assert r.json()["publisher_name"] == "signing-flow-pub"

        # 5. Revoke publisher
        r = client.post(
            f"/v1/publishers/{pub_id}/revoke-key",
            headers=admin_headers,
            json={"reason": "testing revocation"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "revoked"

        # 6. Verify fails after revocation
        r = client.post("/v1/skills/verify", json=signed)
        assert r.status_code == 200
        assert r.json()["verified"] is False
        assert "revoked" in r.json().get("reason", "").lower()

    def test_verify_unknown_publisher(self, client):
        """Verification with a non-existent publisher should fail gracefully."""
        r = client.post("/v1/skills/verify", json={
            "manifest": {
                "name": "ghost-skill",
                "version": "1.0.0",
                "publisher_id": "pub_nonexistent",
                "code_hash": "sha256:abc",
                "capabilities": [],
                "credentials_required": [],
                "description": "",
                "created_at": "2025-01-01T00:00:00+00:00",
            },
            "signature": "dGVzdA==",
            "signed_at": "2025-01-01T00:00:00+00:00",
        })
        assert r.status_code == 200
        assert r.json()["verified"] is False

    def test_publish_revoked_publisher(self, client, admin_headers):
        """Publishing a locally-signed manifest from a revoked publisher should fail."""
        from trust_protocol.core.skill_signer import generate_keypair, hash_code
        from trust_protocol.sdk import TrustProtocolClient

        priv, pub = generate_keypair()

        r = client.post("/v1/publishers", headers=admin_headers, json={
            "name": "revoked-pub",
            "organization": "Test",
            "public_key_pem": pub.decode(),
        })
        pub_id = r.json()["publisher_id"]

        client.post(
            f"/v1/publishers/{pub_id}/revoke-key",
            headers=admin_headers,
            json={"reason": "test"},
        )

        # Sign locally (this works fine -- signing is just math)
        signed = TrustProtocolClient.sign_locally(
            name="test-skill",
            version="1.0.0",
            publisher_id=pub_id,
            code_hash=hash_code("code"),
            private_key_pem=priv,
        )

        # But publishing to the registry should fail
        r = client.post("/v1/skills/publish", headers=admin_headers, json=signed)
        assert r.status_code == 400  # Publisher is revoked


# =========================================================================
# Behavior
# =========================================================================


class TestBehavior:
    """Behavioral metrics submission and scoring."""

    def test_submit_and_score(self, client, admin_headers, registered_agent, agent_headers):
        agent_id = registered_agent["agent_id"]

        r = client.post(
            f"/v1/agents/{agent_id}/metrics",
            headers=agent_headers,
            json={"api_calls": 100, "api_errors": 2},
        )
        assert r.status_code == 200
        data = r.json()
        assert "behavior_score" in data
        assert data["agent_id"] == agent_id

        # Get score via admin endpoint
        r = client.get(
            f"/v1/agents/{agent_id}/behavior-score",
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["behavior_score"] > 0
        assert data["agent_id"] == agent_id

    def test_submit_wrong_agent_forbidden(self, client, admin_headers, registered_agent, agent_headers):
        """Agent cannot submit metrics for a different agent_id."""
        r = client.post(
            "/v1/agents/agt_someone_else/metrics",
            headers=agent_headers,
            json={"api_calls": 100, "api_errors": 0},
        )
        assert r.status_code == 403

    def test_behavior_summary(self, client, admin_headers, registered_agent, agent_headers):
        agent_id = registered_agent["agent_id"]

        # Submit some metrics first
        client.post(
            f"/v1/agents/{agent_id}/metrics",
            headers=agent_headers,
            json={"api_calls": 50, "api_errors": 1},
        )

        r = client.get(
            f"/v1/agents/{agent_id}/behavior",
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["agent_id"] == agent_id
        assert data["metrics_count"] >= 1

    def test_anomalies_endpoint(self, client, admin_headers, registered_agent):
        agent_id = registered_agent["agent_id"]

        r = client.get(
            f"/v1/agents/{agent_id}/anomalies",
            headers=admin_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["agent_id"] == agent_id
        assert "anomalies" in data


# =========================================================================
# Seal / Unseal
# =========================================================================


class TestSeal:
    """Tests for the seal/unseal workflow."""

    def test_seal_status_unsealed(self, client):
        """Default test env is auto-unsealed via TRUST_PROTOCOL_VAULT_PASSWORD."""
        r = client.get("/v1/seal-status")
        assert r.status_code == 200
        assert r.json()["sealed"] is False

    def test_health_includes_seal_status(self, client):
        r = client.get("/v1/health")
        assert r.status_code == 200
        assert "sealed" in r.json()
        assert r.json()["sealed"] is False

    def test_credential_ops_fail_when_sealed(self, client, admin_headers):
        """Credential endpoints should return 503 when server is sealed."""
        from trust_protocol.core.seal import get_seal_manager
        get_seal_manager().seal()

        r = client.get("/v1/credentials", headers=admin_headers)
        assert r.status_code == 503

    def test_non_credential_ops_work_when_sealed(self, client, admin_headers):
        """Health, agents, audit should work even when sealed."""
        from trust_protocol.core.seal import get_seal_manager
        get_seal_manager().seal()

        r = client.get("/v1/health")
        assert r.status_code == 200
        assert r.json()["sealed"] is True

        r = client.get("/v1/agents", headers=admin_headers)
        assert r.status_code == 200

    def test_unseal_with_correct_password(self, client, admin_headers):
        """Unseal with the correct password should work."""
        from trust_protocol.core.seal import get_seal_manager
        get_seal_manager().seal()

        r = client.post("/v1/unseal", headers=admin_headers, json={
            "password": "test-vault-password",
        })
        assert r.status_code == 200
        assert r.json()["sealed"] is False

        # Verify credentials work again
        r = client.get("/v1/seal-status")
        assert r.json()["sealed"] is False

    def test_unseal_with_wrong_password(self, client, admin_headers):
        """Wrong password after vault has been established should fail."""
        # Store a credential to establish the password hash
        client.post("/v1/credentials", headers=admin_headers, json={
            "name": "test_cred",
            "credential_data": {"value": "secret"},
            "minimum_trust": "NOVICE",
        })

        from trust_protocol.core.seal import get_seal_manager
        get_seal_manager().seal()

        r = client.post("/v1/unseal", headers=admin_headers, json={
            "password": "wrong-password",
        })
        assert r.status_code == 400

    def test_seal_clears_access(self, client, admin_headers):
        """Full cycle: store → seal → 503 → unseal → 200."""
        # Store credential while unsealed
        r = client.post("/v1/credentials", headers=admin_headers, json={
            "name": "seal_test",
            "credential_data": {"value": "secret"},
            "minimum_trust": "NOVICE",
        })
        assert r.status_code == 201

        # Seal
        r = client.post("/v1/seal", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["sealed"] is True

        # Try to list credentials
        r = client.get("/v1/credentials", headers=admin_headers)
        assert r.status_code == 503

        # Unseal
        r = client.post("/v1/unseal", headers=admin_headers, json={
            "password": "test-vault-password",
        })
        assert r.status_code == 200

        # Now credentials work again
        r = client.get("/v1/credentials", headers=admin_headers)
        assert r.status_code == 200
        creds = r.json()
        assert any(c["name"] == "seal_test" for c in creds)

    def test_unseal_requires_admin(self, client):
        """Unseal without admin key should return 401."""
        r = client.post("/v1/unseal", json={"password": "test"})
        assert r.status_code == 401

    def test_seal_requires_admin(self, client):
        """Seal without admin key should return 401."""
        r = client.post("/v1/seal")
        assert r.status_code == 401

    def test_seal_status_no_auth_required(self, client):
        """Seal status should be accessible without authentication."""
        r = client.get("/v1/seal-status")
        assert r.status_code == 200
        assert "sealed" in r.json()


# =========================================================================
# Integration: Cross-Cutting Concerns
# =========================================================================


class TestIntegration:
    """Tests that span multiple API areas."""

    def test_suspend_revokes_tokens(self, client, admin_headers, registered_agent):
        """Suspending an agent should revoke all its tokens."""
        agent_id = registered_agent["agent_id"]

        # Issue a token
        r = client.post("/v1/tokens", headers=admin_headers, json={
            "agent_id": agent_id,
        })
        assert r.status_code == 201
        token_id = r.json()["token_id"]

        # Suspend the agent
        r = client.post(
            f"/v1/agents/{agent_id}/suspend",
            headers=admin_headers,
        )
        assert r.status_code == 200

        # Token should be invalid
        r = client.get(f"/v1/tokens/{token_id}", headers=admin_headers)
        assert r.status_code == 404

    def test_full_lifecycle(self, client, admin_headers):
        """Full agent lifecycle: register, issue token, use credential, audit."""
        # 1. Register agent
        r = client.post("/v1/agents", headers=admin_headers, json={
            "name": "lifecycle-agent",
            "agent_type": "service",
            "description": "End-to-end test",
        })
        assert r.status_code == 201
        agent_id = r.json()["agent_id"]
        api_key = r.json()["api_key"]
        agent_hdrs = {"X-Agent-Key": api_key}

        # 2. Store a credential
        r = client.post("/v1/credentials", headers=admin_headers, json={
            "name": "lifecycle_cred",
            "credential_data": {"value": "lifecycle-secret"},
            "minimum_trust": "NOVICE",
        })
        assert r.status_code == 201

        # 3. Issue a token
        r = client.post("/v1/tokens", headers=admin_headers, json={
            "agent_id": agent_id,
        })
        assert r.status_code == 201

        # 4. Agent executes with credential
        r = client.post(
            "/v1/credentials/lifecycle_cred/execute",
            headers=agent_hdrs,
            json={"agent_id": agent_id, "purpose": "lifecycle test"},
        )
        assert r.status_code == 200
        assert r.json()["granted"] is True

        # 5. Audit trail should capture everything
        r = client.get("/v1/audit", headers=admin_headers)
        assert r.status_code == 200
        event_types = [e["event_type"] for e in r.json()]
        assert "AGENT_REGISTERED" in event_types

        # 6. Verify chain integrity
        r = client.get("/v1/audit/verify", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["valid"] is True
