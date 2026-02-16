# Credential Proxy

The credential proxy is the core innovation of TRUST Protocol. It lets agents **use** credentials without **seeing** them.

## How It Works

1. An admin stores a credential in the vault (AES-256-GCM encrypted at rest)
2. An agent sends a **request template** containing `{{CREDENTIAL}}` placeholders
3. The server substitutes the real credential value into the template
4. The server executes the HTTP request
5. The server returns only the upstream response to the agent

The agent never sees the raw credential. The credential exists in server memory only for the duration of the HTTP call.

## Request Template

The template is a standard HTTP request with placeholder injection:

```json
{
  "purpose": "GPT-4 completion",
  "method": "POST",
  "url": "https://api.openai.com/v1/chat/completions",
  "headers": {
    "Authorization": "Bearer {{CREDENTIAL}}",
    "Content-Type": "application/json"
  },
  "body": {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}]
  },
  "timeout_seconds": 30
}
```

The `{{CREDENTIAL}}` placeholder can appear in:

- Headers (most common -- `Authorization: Bearer {{CREDENTIAL}}`)
- URL (for services that use query parameter auth)
- Request body (for services that accept keys in the payload)

## Access Modes

### Execute Mode (all tiers)

The standard proxy execution described above. The agent provides a template, the server executes it.

```bash
POST /v1/credentials/{name}/proxy-execute
```

### Proxy-Value Mode (PARTNER tier and above)

For cases where proxy execution doesn't work (e.g., the agent needs to pass the credential to a local SDK), PARTNER+ agents can request a **single-use, time-limited token** that can be exchanged for the raw credential value.

```bash
# Step 1: Request a proxy-value token
POST /v1/credentials/{name}/proxy-value
# Returns: {"token_id": "pvt_abc123", "expires_at": "..."}

# Step 2: Exchange token for credential (within 60 seconds)
GET /v1/credentials/proxy-value/{token_id}/exchange
# Returns: {"credential_name": "openai_key", "value": {"value": "sk-..."}}
```

The token is:

- **Single-use** -- consumed on first exchange
- **Time-limited** -- expires after 60 seconds
- **Audited** -- every issuance and exchange is logged

!!! warning "Proxy-value exposes the raw credential"
    Use execute mode whenever possible. Proxy-value mode exists for cases where direct HTTP proxying isn't feasible (e.g., SDKs that require a local credential). It requires PARTNER tier or above.

## Trust Tier Enforcement

Each credential has a `minimum_trust` setting. An agent's trust tier must meet or exceed this level:

```json
{
  "name": "openai_key",
  "credential_data": {"value": "sk-..."},
  "minimum_trust": "COMPANION"
}
```

A NOVICE agent trying to access a COMPANION-level credential will receive a 403 response.

## Using the Python SDK

```python
from trust_protocol.sdk import TrustProtocolClient

# Agent client
agent = TrustProtocolClient("http://localhost:9500", agent_key="ak_...")

# Execute through proxy
result = agent.execute_credential(
    "openai_key",
    purpose="GPT-4 completion",
    method="POST",
    url="https://api.openai.com/v1/chat/completions",
    headers={"Authorization": "Bearer {{CREDENTIAL}}"},
    body={"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]},
)

print(result["status_code"])  # 200
print(result["body"])         # The upstream API response
```

## Audit Trail

Every credential access is logged to the audit chain:

```json
{
  "event_type": "credential.execute",
  "agent_id": "agt_abc123",
  "details": {
    "name": "openai_key",
    "granted": true,
    "purpose": "GPT-4 completion",
    "method": "POST",
    "url_host": "api.openai.com",
    "status_code": 200,
    "execution_time_ms": 1234
  }
}
```
