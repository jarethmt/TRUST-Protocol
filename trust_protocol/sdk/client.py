"""Python SDK client for the TRUST Protocol API.

Usage:
    from trust_protocol.sdk import TrustProtocolClient

    # Admin client
    client = TrustProtocolClient("http://localhost:9500", admin_key="your-admin-key")
    agent = client.register_agent(name="my-agent", agent_type="executor", ...)

    # Agent client (after registration)
    agent_client = TrustProtocolClient("http://localhost:9500", agent_key=agent["api_key"])
    result = agent_client.execute_credential("openai_key", purpose="API call", ...)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


class TrustProtocolClient:
    """Synchronous client for the TRUST Protocol REST API.

    Authenticate with either an admin key or an agent key.
    Admin key: full access to all endpoints.
    Agent key: access to agent-scoped endpoints (credential execution,
    token renewal, metrics submission).
    """

    def __init__(
        self,
        base_url: str = "http://localhost:9500",
        admin_key: Optional[str] = None,
        agent_key: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._admin_key = admin_key
        self._agent_key = agent_key
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout)

    def close(self) -> None:
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # -- auth helpers --

    def _admin_headers(self) -> Dict[str, str]:
        if not self._admin_key:
            raise ValueError("Admin key required for this operation")
        return {"X-Admin-Key": self._admin_key}

    def _agent_headers(self) -> Dict[str, str]:
        if not self._agent_key:
            raise ValueError("Agent key required for this operation")
        return {"X-Agent-Key": self._agent_key}

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", response.text)
            except Exception:
                detail = response.text
            raise TrustProtocolError(response.status_code, detail)

    # -- Health --

    def health(self) -> Dict[str, Any]:
        r = self._client.get("/v1/health")
        self._raise_for_status(r)
        return r.json()

    # -- Agents (admin) --

    def register_agent(
        self,
        name: str,
        agent_type: str,
        description: str = "",
        required_credentials: Optional[List[str]] = None,
        network_access: Optional[List[str]] = None,
        capabilities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a new agent. Returns agent details including one-time api_key."""
        r = self._client.post("/v1/agents", headers=self._admin_headers(), json={
            "name": name,
            "agent_type": agent_type,
            "description": description,
            "required_credentials": required_credentials or [],
            "network_access": network_access or [],
            "capabilities": capabilities or [],
            "metadata": metadata or {},
        })
        self._raise_for_status(r)
        return r.json()

    def list_agents(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if status:
            params["status"] = status
        r = self._client.get("/v1/agents", headers=self._admin_headers(), params=params)
        self._raise_for_status(r)
        return r.json()

    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        r = self._client.get(f"/v1/agents/{agent_id}", headers=self._admin_headers())
        self._raise_for_status(r)
        return r.json()

    def promote_agent(self, agent_id: str, trust_tier: str) -> Dict[str, Any]:
        r = self._client.patch(f"/v1/agents/{agent_id}/trust-level",
            headers=self._admin_headers(), json={"trust_tier": trust_tier})
        self._raise_for_status(r)
        return r.json()

    def suspend_agent(self, agent_id: str) -> Dict[str, Any]:
        r = self._client.post(f"/v1/agents/{agent_id}/suspend", headers=self._admin_headers())
        self._raise_for_status(r)
        return r.json()

    def revoke_agent(self, agent_id: str) -> Dict[str, Any]:
        r = self._client.post(f"/v1/agents/{agent_id}/revoke", headers=self._admin_headers())
        self._raise_for_status(r)
        return r.json()

    # -- Tokens (admin + agent) --

    def issue_token(self, agent_id: str, credential_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        r = self._client.post("/v1/tokens", headers=self._admin_headers(), json={
            "agent_id": agent_id,
            "credential_patterns": credential_patterns or ["*"],
        })
        self._raise_for_status(r)
        return r.json()

    def validate_token(self, token_id: str) -> Dict[str, Any]:
        r = self._client.get(f"/v1/tokens/{token_id}", headers=self._admin_headers())
        self._raise_for_status(r)
        return r.json()

    def renew_token(self, token_id: str, behavior_score: float = 1.0) -> Dict[str, Any]:
        """Renew a token. Works with either admin or agent key."""
        headers = self._agent_headers() if self._agent_key else self._admin_headers()
        r = self._client.post(f"/v1/tokens/{token_id}/renew",
            headers=headers, json={"behavior_score": behavior_score})
        self._raise_for_status(r)
        return r.json()

    def revoke_token(self, token_id: str) -> None:
        r = self._client.delete(f"/v1/tokens/{token_id}", headers=self._admin_headers())
        self._raise_for_status(r)

    def list_tokens(self, agent_id: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if agent_id:
            params["agent_id"] = agent_id
        r = self._client.get("/v1/tokens", headers=self._admin_headers(), params=params)
        self._raise_for_status(r)
        return r.json()

    # -- Credentials (admin + agent) --

    def store_credential(
        self, name: str, credential_data: Dict[str, Any], minimum_trust: str = "COMPANION",
    ) -> Dict[str, Any]:
        r = self._client.post("/v1/credentials", headers=self._admin_headers(), json={
            "name": name, "credential_data": credential_data, "minimum_trust": minimum_trust,
        })
        self._raise_for_status(r)
        return r.json()

    def list_credentials(self) -> List[Dict[str, Any]]:
        r = self._client.get("/v1/credentials", headers=self._admin_headers())
        self._raise_for_status(r)
        return r.json()

    def delete_credential(self, name: str) -> None:
        r = self._client.delete(f"/v1/credentials/{name}", headers=self._admin_headers())
        self._raise_for_status(r)

    def execute_credential(
        self,
        name: str,
        purpose: str,
        method: str = "GET",
        url: str = "",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 30,
    ) -> Dict[str, Any]:
        """Execute an HTTP request with credential injection (agent auth)."""
        r = self._client.post(f"/v1/credentials/{name}/proxy-execute",
            headers=self._agent_headers(), json={
                "purpose": purpose,
                "method": method,
                "url": url,
                "headers": headers or {},
                "body": body,
                "timeout_seconds": timeout_seconds,
            })
        self._raise_for_status(r)
        return r.json()

    def request_credential_access(self, name: str, purpose: str, duration_minutes: int = 30) -> Dict[str, Any]:
        """Request direct credential access (agent auth, basic execute mode)."""
        r = self._client.post(f"/v1/credentials/{name}/execute",
            headers=self._agent_headers(), json={
                "purpose": purpose, "duration_minutes": duration_minutes,
            })
        self._raise_for_status(r)
        return r.json()

    def get_proxy_value(self, name: str, purpose: str) -> Dict[str, Any]:
        """Get a proxy-value token (PARTNER+ only, agent auth)."""
        r = self._client.post(f"/v1/credentials/{name}/proxy-value",
            headers=self._agent_headers(), json={"purpose": purpose})
        self._raise_for_status(r)
        return r.json()

    def exchange_proxy_value(self, token_id: str) -> Dict[str, Any]:
        """Exchange a proxy-value token for the credential (agent auth)."""
        r = self._client.get(f"/v1/credentials/proxy-value/{token_id}/exchange",
            headers=self._agent_headers())
        self._raise_for_status(r)
        return r.json()

    # -- Skills --

    def register_publisher(
        self, name: str, organization: str, public_key_pem: str, metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        r = self._client.post("/v1/publishers", headers=self._admin_headers(), json={
            "name": name, "organization": organization,
            "public_key_pem": public_key_pem, "metadata": metadata or {},
        })
        self._raise_for_status(r)
        return r.json()

    def list_publishers(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {}
        if status:
            params["status"] = status
        r = self._client.get("/v1/publishers", headers=self._admin_headers(), params=params)
        self._raise_for_status(r)
        return r.json()

    def revoke_publisher(self, publisher_id: str, reason: str = "") -> Dict[str, Any]:
        r = self._client.post(f"/v1/publishers/{publisher_id}/revoke-key",
            headers=self._admin_headers(), json={"reason": reason})
        self._raise_for_status(r)
        return r.json()

    def publish_skill(self, signed_manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Publish a pre-signed skill manifest to the registry.

        The manifest must be signed locally using ``sign_locally()`` before
        calling this method.  The server validates the publisher and
        signature before accepting.
        """
        r = self._client.post("/v1/skills/publish", headers=self._admin_headers(), json=signed_manifest)
        self._raise_for_status(r)
        return r.json()

    @staticmethod
    def sign_locally(
        name: str,
        version: str,
        publisher_id: str,
        code_hash: str,
        private_key_pem: bytes,
        capabilities: Optional[List[str]] = None,
        credentials_required: Optional[List[str]] = None,
        description: str = "",
    ) -> Dict[str, Any]:
        """Sign a skill manifest locally without any server roundtrip.

        The private key never leaves this process.  Returns a dict
        suitable for passing to ``publish_skill()`` or ``verify_skill()``.

        Parameters
        ----------
        name : str
            Skill name.
        version : str
            Skill version (semver recommended).
        publisher_id : str
            The publisher ID obtained during registration.
        code_hash : str
            SHA-256 hash of the skill code in ``sha256:<hex>`` format.
            Use ``trust_protocol.core.skill_signer.hash_code()`` to generate.
        private_key_pem : bytes
            PEM-encoded Ed25519 private key (PKCS8, unencrypted).
        capabilities : list, optional
            Capabilities the skill declares.
        credentials_required : list, optional
            Credentials the skill needs to function.
        description : str, optional
            Human-readable skill description.
        """
        from trust_protocol.core.skill_signer import SkillManifest, sign_manifest

        manifest = SkillManifest(
            name=name,
            version=version,
            publisher_id=publisher_id,
            code_hash=code_hash,
            capabilities=capabilities or [],
            credentials_required=credentials_required or [],
            description=description,
        )
        signed = sign_manifest(manifest, private_key_pem)
        return signed.to_dict()

    def verify_skill(self, signed_manifest: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a signed skill manifest (no auth required)."""
        r = self._client.post("/v1/skills/verify", json=signed_manifest)
        self._raise_for_status(r)
        return r.json()

    # -- Behavior --

    def submit_metrics(self, agent_id: str, **metrics) -> Dict[str, Any]:
        """Submit behavioral metrics (agent auth)."""
        r = self._client.post(f"/v1/agents/{agent_id}/metrics",
            headers=self._agent_headers(), json=metrics)
        self._raise_for_status(r)
        return r.json()

    def get_behavior_score(self, agent_id: str) -> Dict[str, Any]:
        r = self._client.get(f"/v1/agents/{agent_id}/behavior-score", headers=self._admin_headers())
        self._raise_for_status(r)
        return r.json()

    # -- Audit (admin) --

    def query_audit(self, event_type: Optional[str] = None, agent_id: Optional[str] = None,
                    limit: int = 100) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if event_type:
            params["event_type"] = event_type
        if agent_id:
            params["agent_id"] = agent_id
        r = self._client.get("/v1/audit", headers=self._admin_headers(), params=params)
        self._raise_for_status(r)
        return r.json()

    def verify_audit(self) -> Dict[str, Any]:
        r = self._client.get("/v1/audit/verify", headers=self._admin_headers())
        self._raise_for_status(r)
        return r.json()

    # -- Emergency (admin) --

    def activate_emergency(self, reason: str, scope: str = "global",
                          agent_id: Optional[str] = None,
                          credential_name: Optional[str] = None) -> Dict[str, Any]:
        r = self._client.post("/v1/emergency/activate", headers=self._admin_headers(), json={
            "reason": reason, "scope": scope, "agent_id": agent_id,
            "credential_name": credential_name,
        })
        self._raise_for_status(r)
        return r.json()

    def clear_emergency(self, scope: str = "global", confirmation: str = "",
                       agent_id: Optional[str] = None,
                       credential_name: Optional[str] = None) -> Dict[str, Any]:
        r = self._client.post("/v1/emergency/clear", headers=self._admin_headers(), json={
            "scope": scope, "confirmation": confirmation,
            "agent_id": agent_id, "credential_name": credential_name,
        })
        self._raise_for_status(r)
        return r.json()

    def emergency_status(self) -> Dict[str, Any]:
        r = self._client.get("/v1/emergency/status", headers=self._admin_headers())
        self._raise_for_status(r)
        return r.json()


class TrustProtocolError(Exception):
    """Raised when the API returns an error response."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"HTTP {status_code}: {detail}")
