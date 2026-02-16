"""Tests for TRUST Protocol core modules.

Covers trust tiers, emergency controller, audit chain, agent identity,
token authority, skill signing, and behavior analysis.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest


# =========================================================================
# Trust Tiers
# =========================================================================


class TestTrustTiers:
    """Tests for the TrustTier enum and helper functions."""

    def test_tier_names(self):
        from trust_protocol.core.trust_tiers import TrustTier

        assert TrustTier.NOVICE.name == "NOVICE"
        assert TrustTier.COMPANION.name == "COMPANION"
        assert TrustTier.PARTNER.name == "PARTNER"
        assert TrustTier.GUARDIAN.name == "GUARDIAN"
        assert TrustTier.SACRED.name == "SACRED"

    def test_tier_properties(self):
        from trust_protocol.core.trust_tiers import TrustTier

        assert TrustTier.NOVICE.token_duration_hours == 1
        assert TrustTier.SACRED.token_duration_hours == 24
        assert TrustTier.SACRED.requires_human_approval is True
        assert TrustTier.NOVICE.requires_human_approval is False
        assert TrustTier.GUARDIAN.max_credentials is None
        assert TrustTier.NOVICE.max_credentials == 1

    def test_can_access(self):
        from trust_protocol.core.trust_tiers import TrustTier, can_access

        # NOVICE can only execute
        assert can_access(TrustTier.NOVICE, "execute") is True
        assert can_access(TrustTier.NOVICE, "proxy_value") is False

        # PARTNER can execute and proxy_value
        assert can_access(TrustTier.PARTNER, "execute") is True
        assert can_access(TrustTier.PARTNER, "proxy_value") is True

        # COMPANION can only execute (like NOVICE)
        assert can_access(TrustTier.COMPANION, "proxy_value") is False

    def test_tier_ordering(self):
        from trust_protocol.core.trust_tiers import TrustTier

        tiers = list(TrustTier)
        assert tiers[0] == TrustTier.NOVICE
        assert tiers[-1] == TrustTier.SACRED
        assert len(tiers) == 5

    def test_get_token_duration(self):
        from trust_protocol.core.trust_tiers import TrustTier, get_token_duration
        from datetime import timedelta

        assert get_token_duration(TrustTier.NOVICE) == timedelta(hours=1)
        assert get_token_duration(TrustTier.SACRED) == timedelta(hours=24)


# =========================================================================
# Emergency Controller
# =========================================================================


class TestEmergency:
    """Tests for the file-based emergency brake system."""

    def test_global_brake(self, tmp_path):
        from trust_protocol.core.emergency import EmergencyController

        ec = EmergencyController(tmp_path)

        assert ec.is_blocked() is False
        ec.activate_global("test emergency")
        assert ec.is_blocked() is True

        # Wrong confirmation string should fail
        assert ec.clear_global("wrong") is False
        assert ec.is_blocked() is True

        # Correct confirmation string clears the brake
        assert ec.clear_global("CONFIRM_RESTORE_ACCESS") is True
        assert ec.is_blocked() is False

    def test_agent_brake(self, tmp_path):
        from trust_protocol.core.emergency import EmergencyController

        ec = EmergencyController(tmp_path)

        ec.activate_agent("agt_123", "suspicious activity")
        assert ec.is_blocked(agent_id="agt_123") is True
        assert ec.is_blocked(agent_id="agt_other") is False
        # Global check is not blocked
        assert ec.is_blocked() is False

        ec.clear_agent("agt_123")
        assert ec.is_blocked(agent_id="agt_123") is False

    def test_credential_brake(self, tmp_path):
        from trust_protocol.core.emergency import EmergencyController

        ec = EmergencyController(tmp_path)

        ec.activate_credential("secret_key", "compromised")
        assert ec.is_blocked(credential_name="secret_key") is True
        assert ec.is_blocked(credential_name="other_key") is False

        ec.clear_credential("secret_key")
        assert ec.is_blocked(credential_name="secret_key") is False

    def test_global_blocks_everything(self, tmp_path):
        from trust_protocol.core.emergency import EmergencyController

        ec = EmergencyController(tmp_path)

        ec.activate_global("total lockdown")
        # Global brake blocks agent-specific and credential-specific checks too
        assert ec.is_blocked(agent_id="agt_any") is True
        assert ec.is_blocked(credential_name="any_cred") is True

        ec.clear_global("CONFIRM_RESTORE_ACCESS")

    def test_status(self, tmp_path):
        from trust_protocol.core.emergency import EmergencyController

        ec = EmergencyController(tmp_path)

        status = ec.status()
        assert status["global_active"] is False
        assert status["blocked_agents"] == []
        assert status["blocked_credentials"] == []

        ec.activate_agent("agt_test", "test")
        status = ec.status()
        assert len(status["blocked_agents"]) == 1

    def test_clear_nonexistent_returns_false(self, tmp_path):
        from trust_protocol.core.emergency import EmergencyController

        ec = EmergencyController(tmp_path)
        assert ec.clear_agent("agt_nonexistent") is False
        assert ec.clear_credential("no_such_cred") is False
        assert ec.clear_global("CONFIRM_RESTORE_ACCESS") is False


# =========================================================================
# Audit Chain
# =========================================================================


class TestAuditChain:
    """Tests for the HMAC-signed, hash-chained audit log."""

    def test_log_and_query(self, tmp_path):
        from trust_protocol.core.audit_chain import AuditChain, AGENT_REGISTERED

        chain = AuditChain(tmp_path, b"test-secret")

        chain.log(AGENT_REGISTERED, "agt_1", {"name": "test"})
        chain.log(AGENT_REGISTERED, "agt_2", {"name": "test2"})

        entries = chain.query()
        assert len(entries) == 2
        assert entries[0]["agent_id"] == "agt_1"
        assert entries[1]["agent_id"] == "agt_2"

    def test_query_with_filters(self, tmp_path):
        from trust_protocol.core.audit_chain import (
            AuditChain, AGENT_REGISTERED, TOKEN_ISSUED,
        )

        chain = AuditChain(tmp_path, b"test-secret")
        chain.log(AGENT_REGISTERED, "agt_1")
        chain.log(TOKEN_ISSUED, "agt_1")
        chain.log(AGENT_REGISTERED, "agt_2")

        # Filter by event_type
        entries = chain.query(event_type=TOKEN_ISSUED)
        assert len(entries) == 1
        assert entries[0]["event_type"] == TOKEN_ISSUED

        # Filter by agent_id
        entries = chain.query(agent_id="agt_2")
        assert len(entries) == 1

    def test_verify_chain(self, tmp_path):
        from trust_protocol.core.audit_chain import AuditChain, TOKEN_ISSUED

        chain = AuditChain(tmp_path, b"test-secret")

        chain.log(TOKEN_ISSUED, "agt_1")
        chain.log(TOKEN_ISSUED, "agt_2")
        chain.log(TOKEN_ISSUED, "agt_3")

        valid, msg = chain.verify_chain()
        assert valid is True
        assert "3 entries" in msg

    def test_tamper_detection(self, tmp_path):
        from trust_protocol.core.audit_chain import AuditChain, TOKEN_ISSUED

        chain = AuditChain(tmp_path, b"test-secret")
        chain.log(TOKEN_ISSUED, "agt_1")

        # Tamper with the log file
        log_path = tmp_path / "audit.jsonl"
        content = log_path.read_text()
        content = content.replace('"agt_1"', '"agt_HACKED"')
        log_path.write_text(content)

        # Reload from tampered file
        chain2 = AuditChain(tmp_path, b"test-secret")
        valid, msg = chain2.verify_chain()
        assert valid is False

    def test_count(self, tmp_path):
        from trust_protocol.core.audit_chain import AuditChain, AGENT_REGISTERED

        chain = AuditChain(tmp_path, b"test-secret")
        assert chain.count() == 0

        chain.log(AGENT_REGISTERED, "agt_1")
        chain.log(AGENT_REGISTERED, "agt_2")
        assert chain.count() == 2

    def test_export(self, tmp_path):
        from trust_protocol.core.audit_chain import AuditChain, AGENT_REGISTERED

        chain = AuditChain(tmp_path, b"test-secret")
        chain.log(AGENT_REGISTERED, "agt_1")

        content = chain.export()
        assert "agt_1" in content
        assert "AGENT_REGISTERED" in content

    def test_chain_recovery_on_restart(self, tmp_path):
        """Chain state should survive a new AuditChain instance (simulating restart)."""
        from trust_protocol.core.audit_chain import AuditChain, TOKEN_ISSUED

        chain1 = AuditChain(tmp_path, b"test-secret")
        chain1.log(TOKEN_ISSUED, "agt_1")
        chain1.log(TOKEN_ISSUED, "agt_2")

        # Simulate restart: new instance from same directory
        chain2 = AuditChain(tmp_path, b"test-secret")
        chain2.log(TOKEN_ISSUED, "agt_3")

        valid, msg = chain2.verify_chain()
        assert valid is True
        assert "3 entries" in msg


# =========================================================================
# Agent Identity
# =========================================================================


class TestAgentIdentity:
    """Tests for agent registration, lookup, and lifecycle."""

    def test_register_and_lookup(self, tmp_path):
        from trust_protocol.core.agent_identity import AgentDefinition, AgentRegistry

        registry = AgentRegistry(tmp_path)

        defn = AgentDefinition(
            name="test",
            agent_type="executor",
            description="test agent",
            required_credentials=["cred1"],
            capabilities=["http_request"],
        )
        identity = registry.register(defn)

        assert identity.agent_id.startswith("agt_")
        assert identity.api_key.startswith("tp_")
        assert identity.status == "active"

        # Lookup by ID
        found = registry.get(identity.agent_id)
        assert found is not None
        assert found.agent_id == identity.agent_id

    def test_api_key_verification(self, tmp_path):
        from trust_protocol.core.agent_identity import AgentDefinition, AgentRegistry

        registry = AgentRegistry(tmp_path)

        defn = AgentDefinition(
            name="test",
            agent_type="executor",
            description="test",
        )
        identity = registry.register(defn)
        api_key = identity.api_key

        found = registry.get_by_api_key(api_key)
        assert found is not None
        assert found.agent_id == identity.agent_id

        # Wrong key returns None
        assert registry.get_by_api_key("tp_wrong") is None

    def test_duplicate_name_rejected(self, tmp_path):
        from trust_protocol.core.agent_identity import AgentDefinition, AgentRegistry

        registry = AgentRegistry(tmp_path)

        defn = AgentDefinition(
            name="unique",
            agent_type="executor",
            description="test",
        )
        registry.register(defn)

        with pytest.raises(ValueError, match="already exists"):
            registry.register(defn)

    def test_list_agents(self, tmp_path):
        from trust_protocol.core.agent_identity import AgentDefinition, AgentRegistry

        registry = AgentRegistry(tmp_path)
        for i in range(3):
            defn = AgentDefinition(
                name=f"agent-{i}",
                agent_type="executor",
                description="test",
            )
            registry.register(defn)

        agents = registry.list_agents()
        assert len(agents) == 3

        agents = registry.list_agents(status="active")
        assert len(agents) == 3

    def test_suspend_and_status(self, tmp_path):
        from trust_protocol.core.agent_identity import AgentDefinition, AgentRegistry

        registry = AgentRegistry(tmp_path)
        defn = AgentDefinition(
            name="test",
            agent_type="executor",
            description="test",
        )
        identity = registry.register(defn)

        assert registry.update_status(identity.agent_id, "suspended") is True
        found = registry.get(identity.agent_id)
        assert found.status == "suspended"

        # Suspended agent should not be returned by get_by_api_key
        assert registry.get_by_api_key(identity.api_key) is None

    def test_trust_assessment_companion(self, tmp_path):
        """Agent with minimal surface area should get COMPANION tier."""
        from trust_protocol.core.agent_identity import AgentDefinition, AgentRegistry
        from trust_protocol.core.trust_tiers import TrustTier

        registry = AgentRegistry(tmp_path)
        defn = AgentDefinition(
            name="safe-agent",
            agent_type="executor",
            description="minimal agent",
            required_credentials=[],  # zero creds
            capabilities=["read_only"],  # no high-risk caps
        )
        identity = registry.register(defn)
        assert identity.trust_tier == TrustTier.COMPANION

    def test_trust_assessment_novice_shell(self, tmp_path):
        """Agent with shell_execute should get NOVICE tier."""
        from trust_protocol.core.agent_identity import AgentDefinition, AgentRegistry
        from trust_protocol.core.trust_tiers import TrustTier

        registry = AgentRegistry(tmp_path)
        defn = AgentDefinition(
            name="risky-agent",
            agent_type="executor",
            description="risky",
            capabilities=["shell_execute"],
        )
        identity = registry.register(defn)
        assert identity.trust_tier == TrustTier.NOVICE

    def test_promote(self, tmp_path):
        from trust_protocol.core.agent_identity import AgentDefinition, AgentRegistry
        from trust_protocol.core.trust_tiers import TrustTier

        registry = AgentRegistry(tmp_path)
        defn = AgentDefinition(
            name="test",
            agent_type="executor",
            description="test",
        )
        identity = registry.register(defn)

        assert registry.promote(identity.agent_id, TrustTier.PARTNER) is True
        found = registry.get(identity.agent_id)
        assert found.trust_tier == TrustTier.PARTNER

    def test_delete(self, tmp_path):
        from trust_protocol.core.agent_identity import AgentDefinition, AgentRegistry

        registry = AgentRegistry(tmp_path)
        defn = AgentDefinition(
            name="test",
            agent_type="executor",
            description="test",
        )
        identity = registry.register(defn)

        assert registry.delete(identity.agent_id) is True
        assert registry.get(identity.agent_id) is None
        assert registry.delete(identity.agent_id) is False  # already gone


# =========================================================================
# Token Authority
# =========================================================================


class TestTokenAuthority:
    """Tests for token issuance, validation, renewal, and revocation."""

    def test_issue_and_validate(self, tmp_path):
        from trust_protocol.core.token_authority import TokenAuthority
        from trust_protocol.core.trust_tiers import TrustTier

        ta = TokenAuthority(b"test-secret", tmp_path)
        token = ta.issue("agt_1", TrustTier.COMPANION, ["openai_*"])

        assert token.token_id.startswith("tok_")
        assert token.agent_id == "agt_1"
        assert token.renewal_count == 0

        validated = ta.validate(token.token_id)
        assert validated is not None
        assert validated.can_access_credential("openai_key") is True
        assert validated.can_access_credential("other_key") is False

    def test_wildcard_pattern(self, tmp_path):
        from trust_protocol.core.token_authority import TokenAuthority
        from trust_protocol.core.trust_tiers import TrustTier

        ta = TokenAuthority(b"test-secret", tmp_path)
        token = ta.issue("agt_1", TrustTier.COMPANION, ["*"])

        assert token.can_access_credential("anything") is True
        assert token.can_access_credential("openai_key") is True

    def test_renewal(self, tmp_path):
        from trust_protocol.core.token_authority import TokenAuthority
        from trust_protocol.core.trust_tiers import TrustTier

        ta = TokenAuthority(b"test-secret", tmp_path)
        token = ta.issue("agt_1", TrustTier.COMPANION, ["*"])

        new_token = ta.renew(token.token_id, behavior_score=0.9)
        assert new_token is not None
        assert new_token.renewal_count == 1
        assert new_token.token_id != token.token_id

        # Old token should be invalidated
        assert ta.validate(token.token_id) is None

    def test_renewal_denied_low_score(self, tmp_path):
        from trust_protocol.core.token_authority import TokenAuthority
        from trust_protocol.core.trust_tiers import TrustTier

        ta = TokenAuthority(b"test-secret", tmp_path)
        token = ta.issue("agt_1", TrustTier.NOVICE, ["*"])

        # NOVICE threshold is 0.9; score of 0.5 should be denied
        result = ta.renew(token.token_id, behavior_score=0.5)
        assert result is None

        # Original token should still be valid (renewal failed, not revoked)
        assert ta.validate(token.token_id) is not None

    def test_revoke(self, tmp_path):
        from trust_protocol.core.token_authority import TokenAuthority
        from trust_protocol.core.trust_tiers import TrustTier

        ta = TokenAuthority(b"test-secret", tmp_path)
        token = ta.issue("agt_1", TrustTier.COMPANION, ["*"])

        assert ta.revoke(token.token_id) is True
        assert ta.validate(token.token_id) is None
        assert ta.revoke(token.token_id) is False  # already gone

    def test_revoke_all_for_agent(self, tmp_path):
        from trust_protocol.core.token_authority import TokenAuthority
        from trust_protocol.core.trust_tiers import TrustTier

        ta = TokenAuthority(b"test-secret", tmp_path)
        ta.issue("agt_1", TrustTier.COMPANION, ["*"])
        ta.issue("agt_1", TrustTier.COMPANION, ["openai_*"])
        ta.issue("agt_2", TrustTier.COMPANION, ["*"])

        count = ta.revoke_all_for_agent("agt_1")
        assert count == 2
        assert len(ta.list_tokens(agent_id="agt_1")) == 0
        assert len(ta.list_tokens(agent_id="agt_2")) == 1

    def test_list_tokens(self, tmp_path):
        from trust_protocol.core.token_authority import TokenAuthority
        from trust_protocol.core.trust_tiers import TrustTier

        ta = TokenAuthority(b"test-secret", tmp_path)
        ta.issue("agt_1", TrustTier.COMPANION, ["*"])
        ta.issue("agt_2", TrustTier.COMPANION, ["*"])

        all_tokens = ta.list_tokens()
        assert len(all_tokens) == 2

        filtered = ta.list_tokens(agent_id="agt_1")
        assert len(filtered) == 1


# =========================================================================
# Skill Signer
# =========================================================================


class TestSkillSigner:
    """Tests for Ed25519 skill signing and verification."""

    def test_sign_and_verify(self):
        from trust_protocol.core.skill_signer import (
            SkillManifest, generate_keypair, hash_code,
            sign_manifest, verify_manifest,
        )

        priv, pub = generate_keypair()
        manifest = SkillManifest(
            name="test-skill",
            version="1.0.0",
            publisher_id="pub_test",
            code_hash=hash_code("print('hello')"),
        )

        signed = sign_manifest(manifest, priv)
        assert verify_manifest(signed, pub) is True

    def test_wrong_key_fails(self):
        from trust_protocol.core.skill_signer import (
            SkillManifest, generate_keypair, hash_code,
            sign_manifest, verify_manifest,
        )

        priv1, pub1 = generate_keypair()
        _priv2, pub2 = generate_keypair()

        manifest = SkillManifest(
            name="test-skill",
            version="1.0.0",
            publisher_id="pub_test",
            code_hash=hash_code("code"),
        )

        signed = sign_manifest(manifest, priv1)
        assert verify_manifest(signed, pub2) is False

    def test_tampered_manifest_fails(self):
        from trust_protocol.core.skill_signer import (
            SkillManifest, generate_keypair, hash_code,
            sign_manifest, verify_manifest,
        )

        priv, pub = generate_keypair()
        manifest = SkillManifest(
            name="test-skill",
            version="1.0.0",
            publisher_id="pub_test",
            code_hash=hash_code("original_code"),
        )

        signed = sign_manifest(manifest, priv)

        # Tamper with the manifest after signing
        signed.manifest.code_hash = hash_code("tampered_code")

        assert verify_manifest(signed, pub) is False

    def test_hash_code_deterministic(self):
        from trust_protocol.core.skill_signer import hash_code

        h1 = hash_code("test")
        h2 = hash_code("test")
        assert h1 == h2
        assert h1.startswith("sha256:")

    def test_hash_code_bytes(self):
        from trust_protocol.core.skill_signer import hash_code

        h1 = hash_code("test")
        h2 = hash_code(b"test")
        assert h1 == h2

    def test_publisher_registry(self, tmp_path):
        from trust_protocol.core.skill_signer import (
            PublisherRegistry, generate_keypair,
        )

        _priv, pub = generate_keypair()
        registry = PublisherRegistry(tmp_path)

        publisher = registry.register(
            name="test-pub",
            organization="Test Org",
            public_key_pem=pub.decode(),
        )
        assert publisher.publisher_id.startswith("pub_")
        assert publisher.status == "active"

        # Lookup
        found = registry.get(publisher.publisher_id)
        assert found is not None
        assert found.name == "test-pub"

        # Duplicate name rejected
        with pytest.raises(ValueError, match="already exists"):
            registry.register(
                name="test-pub",
                organization="Test Org",
                public_key_pem=pub.decode(),
            )

    def test_publisher_revoke(self, tmp_path):
        from trust_protocol.core.skill_signer import (
            PublisherRegistry, generate_keypair,
        )

        _priv, pub = generate_keypair()
        registry = PublisherRegistry(tmp_path)

        publisher = registry.register(
            name="revoke-test",
            organization="Test",
            public_key_pem=pub.decode(),
        )

        assert registry.revoke_key(publisher.publisher_id, "testing") is True

        # Reload and check
        registry2 = PublisherRegistry(tmp_path)
        found = registry2.get(publisher.publisher_id)
        assert found.status == "revoked"


# =========================================================================
# Behavior Analyzer
# =========================================================================


class TestBehaviorAnalyzer:
    """Tests for behavioral monitoring and anomaly detection."""

    def test_default_score(self, tmp_path):
        from trust_protocol.core.behavior_analyzer import BehaviorAnalyzer

        analyzer = BehaviorAnalyzer(tmp_path)
        assert analyzer.get_score("unknown_agent") == 1.0

    def test_score_after_metrics(self, tmp_path):
        from trust_protocol.core.behavior_analyzer import (
            BehaviorAnalyzer, BehaviorMetrics,
        )

        analyzer = BehaviorAnalyzer(tmp_path)
        now = datetime.now(timezone.utc)

        # Submit normal metrics
        analyzer.submit_metrics(BehaviorMetrics(
            agent_id="agt_1",
            timestamp=now,
            api_calls=100,
            api_errors=1,
            requests_per_minute=5.0,
        ))

        score = analyzer.get_score("agt_1")
        # With very low error rate, score should be high
        assert score > 0.8

    def test_anomaly_detection_error_spike(self, tmp_path):
        from trust_protocol.core.behavior_analyzer import (
            BehaviorAnalyzer, BehaviorMetrics,
        )

        analyzer = BehaviorAnalyzer(tmp_path)
        now = datetime.now(timezone.utc)

        # Build baseline (need at least 3 entries before anomaly detection kicks in)
        for i in range(5):
            analyzer.submit_metrics(BehaviorMetrics(
                agent_id="agt_1",
                timestamp=now,
                api_calls=100,
                api_errors=2,
                requests_per_minute=5.0,
            ))

        # Submit anomalous metrics with high error rate
        anomalies = analyzer.submit_metrics(BehaviorMetrics(
            agent_id="agt_1",
            timestamp=now,
            api_calls=100,
            api_errors=50,
            requests_per_minute=50.0,
        ))

        assert len(anomalies) >= 1
        types = [a.anomaly_type for a in anomalies]
        assert "error_spike" in types

    def test_anomaly_detection_rate_spike(self, tmp_path):
        from trust_protocol.core.behavior_analyzer import (
            BehaviorAnalyzer, BehaviorMetrics,
        )

        analyzer = BehaviorAnalyzer(tmp_path)
        now = datetime.now(timezone.utc)

        # Build baseline
        for i in range(5):
            analyzer.submit_metrics(BehaviorMetrics(
                agent_id="agt_1",
                timestamp=now,
                api_calls=100,
                api_errors=0,
                requests_per_minute=5.0,
            ))

        # Submit rate spike (3x threshold = 15+, well above baseline of 5)
        anomalies = analyzer.submit_metrics(BehaviorMetrics(
            agent_id="agt_1",
            timestamp=now,
            api_calls=100,
            api_errors=0,
            requests_per_minute=50.0,
        ))

        types = [a.anomaly_type for a in anomalies]
        assert "rate_spike" in types

    def test_get_summary(self, tmp_path):
        from trust_protocol.core.behavior_analyzer import (
            BehaviorAnalyzer, BehaviorMetrics,
        )

        analyzer = BehaviorAnalyzer(tmp_path)
        now = datetime.now(timezone.utc)

        analyzer.submit_metrics(BehaviorMetrics(
            agent_id="agt_1",
            timestamp=now,
            api_calls=50,
            api_errors=5,
        ))

        summary = analyzer.get_summary("agt_1")
        assert summary["agent_id"] == "agt_1"
        assert summary["metrics_count"] == 1
        assert summary["total_api_calls"] == 50
        assert summary["total_api_errors"] == 5
        assert "behavior_score" in summary


# =========================================================================
# Credential Vault
# =========================================================================


class TestCredentialVault:
    """Tests for the encrypted credential vault."""

    def test_initialize_and_store(self, tmp_path):
        from trust_protocol.core.vault import CredentialVault
        from trust_protocol.core.trust_tiers import TrustLevel

        vault = CredentialVault(tmp_path)
        assert vault.initialize("test-password") is True

        result = vault.store_credential(
            "test_key",
            {"value": "secret123"},
            TrustLevel.NOVICE,
        )
        assert result is True

        creds = vault.list_credentials()
        assert len(creds) == 1
        assert creds[0]["name"] == "test_key"

    def test_request_credential_granted(self, tmp_path):
        from trust_protocol.core.vault import CredentialVault
        from trust_protocol.core.trust_tiers import TrustLevel

        vault = CredentialVault(tmp_path)
        vault.initialize("test-password")
        vault.store_credential("test_key", {"value": "secret"}, TrustLevel.NOVICE)
        vault.set_trust_level(TrustLevel.COMPANION)

        result = vault.request_credential(
            name="test_key",
            agent_id="agt_1",
            purpose="testing",
        )
        assert result is not None
        cred_data, record = result
        assert cred_data == {"value": "secret"}
        assert record.granted is True

    def test_request_credential_denied_trust(self, tmp_path):
        from trust_protocol.core.vault import CredentialVault
        from trust_protocol.core.trust_tiers import TrustLevel

        vault = CredentialVault(tmp_path)
        vault.initialize("test-password")
        vault.store_credential("high_cred", {"value": "secret"}, TrustLevel.PARTNER)
        vault.set_trust_level(TrustLevel.NOVICE)

        result = vault.request_credential(
            name="high_cred",
            agent_id="agt_1",
            purpose="testing",
        )
        assert result is None

    def test_emergency_blocks_access(self, tmp_path):
        from trust_protocol.core.vault import CredentialVault
        from trust_protocol.core.trust_tiers import TrustLevel

        vault = CredentialVault(tmp_path)
        vault.initialize("test-password")
        vault.store_credential("test_key", {"value": "secret"}, TrustLevel.NOVICE)

        vault.emergency.activate_global("emergency test")

        result = vault.request_credential(
            name="test_key",
            agent_id="agt_1",
            purpose="testing",
        )
        assert result is None

        vault.emergency.clear_global("CONFIRM_RESTORE_ACCESS")
