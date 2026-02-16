# Python SDK

The `TrustProtocolClient` provides a synchronous Python interface to the TRUST Protocol REST API.

## Installation

```bash
pip install -e .  # From the repository root
```

## Client Setup

```python
from trust_protocol.sdk import TrustProtocolClient

# Admin client (for management operations)
admin = TrustProtocolClient("http://localhost:9500", admin_key="your-admin-key")

# Agent client (for agent operations)
agent = TrustProtocolClient("http://localhost:9500", agent_key="agent-api-key")

# Context manager (auto-closes HTTP client)
with TrustProtocolClient("http://localhost:9500", admin_key="key") as client:
    agents = client.list_agents()
```

## Admin Operations

### Agent Management

```python
# Register an agent (returns one-time api_key)
agent = admin.register_agent(
    name="my-agent",
    agent_type="executor",
    description="Processes data and calls APIs",
)
print(f"Agent API key: {agent['api_key']}")  # Save this!

# List agents
agents = admin.list_agents()
agents = admin.list_agents(status="active")

# Get agent details
agent = admin.get_agent("agt_abc123")

# Promote agent
admin.promote_agent("agt_abc123", "COMPANION")

# Suspend agent
admin.suspend_agent("agt_abc123")

# Permanently revoke agent
admin.revoke_agent("agt_abc123")
```

### Credential Management

```python
# Store a credential
admin.store_credential(
    name="openai_key",
    credential_data={"value": "sk-..."},
    minimum_trust="COMPANION",
)

# List credentials (metadata only, never secret values)
creds = admin.list_credentials()

# Delete a credential
admin.delete_credential("openai_key")
```

### Token Management

```python
# Issue a token
token = admin.issue_token("agt_abc123", credential_patterns=["openai_*"])

# Validate a token
token = admin.validate_token("tok_xyz")

# List tokens
tokens = admin.list_tokens()
tokens = admin.list_tokens(agent_id="agt_abc123")

# Revoke a token
admin.revoke_token("tok_xyz")
```

### Publisher Management

```python
# Register a publisher
pub = admin.register_publisher(
    name="acme-corp",
    organization="Acme Inc.",
    public_key_pem=open("acme.pub").read(),
)

# List publishers
pubs = admin.list_publishers()

# Revoke a publisher's key
admin.revoke_publisher("pub_abc123", reason="Key compromised")
```

## Agent Operations

### Credential Proxy Execution

```python
agent = TrustProtocolClient("http://localhost:9500", agent_key="ak_...")

# Execute through proxy (agent never sees the credential)
result = agent.execute_credential(
    "openai_key",
    purpose="GPT-4 completion",
    method="POST",
    url="https://api.openai.com/v1/chat/completions",
    headers={"Authorization": "Bearer {{CREDENTIAL}}"},
    body={
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
    },
)
print(result["status_code"])  # 200
print(result["body"])         # The upstream API response
```

### Proxy-Value Mode (PARTNER+ only)

```python
# Get a single-use token
token = agent.get_proxy_value("openai_key", purpose="Local SDK usage")

# Exchange for raw credential (within 60 seconds)
credential = agent.exchange_proxy_value(token["token_id"])
print(credential["value"])
```

### Behavioral Metrics

```python
agent.submit_metrics(
    "agt_abc123",
    api_calls=150,
    api_errors=2,
    credential_accesses=30,
    avg_response_time_ms=245.0,
)
```

### Token Renewal

```python
# Renew a token (works with agent key)
agent.renew_token("tok_xyz", behavior_score=0.95)
```

## Skill Signing (Local)

```python
from trust_protocol.core.skill_signer import hash_code

# Sign locally (no server call, private key stays on your machine)
signed_manifest = TrustProtocolClient.sign_locally(
    name="my-skill",
    version="1.0.0",
    publisher_id="pub_abc123",
    code_hash=hash_code(open("skill.py", "rb").read()),
    private_key_pem=open("publisher.key", "rb").read(),
)

# Publish to registry
admin.publish_skill(signed_manifest)

# Verify (no auth needed)
client = TrustProtocolClient("http://localhost:9500")
result = client.verify_skill(signed_manifest)
print(result["verified"])  # True
```

## Emergency Controls

```python
# Activate global brake
admin.activate_emergency("Suspicious activity", scope="global")

# Check status
status = admin.emergency_status()
print(status["global_active"])  # True

# Clear global brake (requires confirmation)
admin.clear_emergency(scope="global", confirmation="CONFIRM_RESTORE_ACCESS")
```

## Audit

```python
# Query audit log
entries = admin.query_audit(event_type="credential.execute", limit=50)

# Verify chain integrity
result = admin.verify_audit()
print(result)  # {"valid": true, "message": "OK: 47 entries verified"}
```

## Error Handling

```python
from trust_protocol.sdk.client import TrustProtocolError

try:
    admin.get_agent("nonexistent")
except TrustProtocolError as e:
    print(e.status_code)  # 404
    print(e.detail)       # "Agent not found"
```
