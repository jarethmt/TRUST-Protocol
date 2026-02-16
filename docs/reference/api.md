# REST API Reference

**Base URL:** `http://localhost:9500`

All admin endpoints require the `X-Admin-Key` header. Agent endpoints require `X-Agent-Key`. Skill verification is public (no auth).

When the server is running, interactive OpenAPI documentation is available at:

- **Swagger UI**: `http://localhost:9500/docs`
- **ReDoc**: `http://localhost:9500/redoc`

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/health` | None | Server health, version, uptime |

## Agents

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/agents` | Admin | Register a new agent |
| GET | `/v1/agents` | Admin | List all agents |
| GET | `/v1/agents/{agent_id}` | Admin | Get agent details |
| PATCH | `/v1/agents/{agent_id}/trust-level` | Admin | Promote or demote trust tier |
| POST | `/v1/agents/{agent_id}/suspend` | Admin | Suspend agent, revoke tokens |
| POST | `/v1/agents/{agent_id}/revoke` | Admin | Permanently revoke agent |

### Register an Agent

```bash
curl -X POST http://localhost:9500/v1/agents \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-agent",
    "agent_type": "executor",
    "description": "My AI agent"
  }'
```

Response includes a one-time `api_key`. Save it -- it cannot be recovered.

## Credentials

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/credentials` | Admin | Store an encrypted credential |
| GET | `/v1/credentials` | Admin | List credentials (metadata only) |
| DELETE | `/v1/credentials/{name}` | Admin | Delete a credential |
| POST | `/v1/credentials/{name}/execute` | Agent | Request time-limited credential access |
| POST | `/v1/credentials/{name}/proxy-execute` | Agent | Execute HTTP request with credential injection |
| POST | `/v1/credentials/{name}/proxy-value` | Agent | Issue single-use proxy-value token (PARTNER+) |
| GET | `/v1/credentials/proxy-value/{token_id}/exchange` | Agent | Exchange proxy-value token for credential |

### Proxy Execute (Zero-Knowledge)

```bash
curl -X POST http://localhost:9500/v1/credentials/openai_key/proxy-execute \
  -H "X-Agent-Key: AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "purpose": "GPT-4 completion",
    "method": "POST",
    "url": "https://api.openai.com/v1/chat/completions",
    "headers": {"Authorization": "Bearer {{CREDENTIAL}}"},
    "body": {"model": "gpt-4", "messages": [{"role": "user", "content": "Hello"}]}
  }'
```

## Tokens

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/tokens` | Admin | Issue a token for an agent |
| GET | `/v1/tokens` | Admin | List active tokens |
| GET | `/v1/tokens/{token_id}` | Admin | Validate a token |
| POST | `/v1/tokens/{token_id}/renew` | Admin or Agent | Renew a token |
| DELETE | `/v1/tokens/{token_id}` | Admin | Revoke a token |

## Skills & Publishers

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/publishers` | Admin | Register a publisher |
| GET | `/v1/publishers` | Admin | List publishers |
| GET | `/v1/publishers/{publisher_id}` | Admin | Get publisher details |
| POST | `/v1/publishers/{publisher_id}/revoke-key` | Admin | Revoke a publisher's key |
| POST | `/v1/skills/publish` | Admin | Publish a locally-signed manifest |
| POST | `/v1/skills/verify` | **None** | Verify a signed manifest |

### Verify a Skill (No Auth Required)

```bash
curl -X POST http://localhost:9500/v1/skills/verify \
  -H "Content-Type: application/json" \
  -d @signed-manifest.json
```

## Behavior

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/agents/{agent_id}/metrics` | Agent | Submit behavioral metrics |
| GET | `/v1/agents/{agent_id}/behavior-score` | Admin | Get behavior score |
| GET | `/v1/agents/{agent_id}/behavior` | Admin | Get full behavior summary |
| GET | `/v1/agents/{agent_id}/anomalies` | Admin | Get detected anomalies |

## Emergency

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/emergency/activate` | Admin | Activate emergency brake |
| POST | `/v1/emergency/clear` | Admin | Clear emergency brake |
| GET | `/v1/emergency/status` | Admin | Get emergency brake status |

### Emergency Kill Switch

```bash
# Block everything
curl -X POST http://localhost:9500/v1/emergency/activate \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "global", "reason": "Suspicious activity detected"}'

# Restore (requires confirmation for global scope)
curl -X POST http://localhost:9500/v1/emergency/clear \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "global", "confirmation": "CONFIRM_RESTORE_ACCESS"}'
```

## Audit

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/audit` | Admin | Query audit log entries |
| GET | `/v1/audit/verify` | Admin | Verify audit chain integrity |
| GET | `/v1/audit/count` | Admin | Get total entry count |
| GET | `/v1/audit/export` | Admin | Export full log as JSONL |
