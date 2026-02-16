# Quick Start

This walkthrough takes you from zero to a working TRUST Protocol setup: running server, registered agent, stored credential, and a proxied API call where the agent never sees the secret.

## 1. Start the Server

```bash
trust-protocol serve
```

The server starts on port 9500. On first run, it generates and saves an admin key to `./data/.admin_key`.

```bash
# Read your admin key
ADMIN_KEY=$(cat data/.admin_key)
```

## 2. Register an Agent

```bash
curl -X POST http://localhost:9500/v1/agents \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-agent",
    "agent_type": "executor",
    "description": "My first AI agent"
  }'
```

Response includes a one-time `api_key`. **Save it** -- it cannot be recovered.

```json
{
  "agent_id": "agt_abc123",
  "name": "my-agent",
  "trust_tier": "NOVICE",
  "api_key": "ak_xyz789..."
}
```

## 3. Store a Credential

```bash
curl -X POST http://localhost:9500/v1/credentials \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "openai_key",
    "credential_data": {"value": "sk-your-real-api-key"},
    "minimum_trust": "COMPANION"
  }'
```

## 4. Promote the Agent

New agents start at NOVICE. To access a COMPANION-level credential, promote first:

```bash
curl -X PATCH http://localhost:9500/v1/agents/agt_abc123/trust-level \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"trust_tier": "COMPANION"}'
```

## 5. Execute Through the Credential Proxy

The agent sends a request template with `{{CREDENTIAL}}` placeholders. The server substitutes the real value, makes the HTTP call, and returns only the response.

```bash
AGENT_KEY="ak_xyz789..."

curl -X POST http://localhost:9500/v1/credentials/openai_key/proxy-execute \
  -H "X-Agent-Key: $AGENT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "purpose": "GPT-4 completion",
    "method": "POST",
    "url": "https://api.openai.com/v1/chat/completions",
    "headers": {"Authorization": "Bearer {{CREDENTIAL}}"},
    "body": {
      "model": "gpt-4",
      "messages": [{"role": "user", "content": "Hello"}]
    }
  }'
```

The agent receives the upstream API response. It never sees `sk-your-real-api-key`.

## 6. Check the Audit Trail

```bash
curl http://localhost:9500/v1/audit \
  -H "X-Admin-Key: $ADMIN_KEY"
```

Every action is logged with HMAC-signed hash chaining. Verify the chain hasn't been tampered with:

```bash
curl http://localhost:9500/v1/audit/verify \
  -H "X-Admin-Key: $ADMIN_KEY"
# {"valid": true, "message": "OK: 5 entries verified"}
```

## Next Steps

- [Credential Proxy](../guides/credential-proxy.md) -- deep dive on zero-knowledge execution
- [Skill Signing](../guides/skill-signing.md) -- sign and verify agent skills
- [Trust Tiers](../guides/trust-tiers.md) -- understand the graduated trust system
- [Python SDK](../reference/sdk.md) -- use the SDK instead of raw HTTP
- [CLI Reference](../reference/cli.md) -- all CLI commands
