# REST API Reference

**Base URL:** `http://localhost:9500`

All admin endpoints require the `X-Admin-Key` header. Agent endpoints require `X-Agent-Key`. Skill verification is public (no auth).

When the server is running, interactive OpenAPI documentation is available at:

- **Swagger UI**: `http://localhost:9500/docs`
- **ReDoc**: `http://localhost:9500/redoc`

## Health

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/health` | None | Server health, version, uptime, seal status |

Response includes a `sealed` field indicating whether the server vault is sealed.

## Seal

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/unseal` | Admin | Unseal the server vault |
| POST | `/v1/seal` | Admin | Re-seal the server vault |
| GET | `/v1/seal-status` | **None** | Check seal status |

### Unseal the Server

```bash
curl -X POST http://localhost:9500/v1/unseal \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"password": "your-vault-password"}'
```

The password is validated against the encrypted vault. If incorrect or the emergency brake is active, the server stays sealed and returns HTTP 400.

### Re-Seal the Server

```bash
curl -X POST http://localhost:9500/v1/seal \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

Clears the vault password from server memory. Credential operations will return 503 until unsealed again.

### Check Seal Status (No Auth)

```bash
curl http://localhost:9500/v1/seal-status
# {"sealed": false, "vault_initialized": true}
```

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

## KMS (Envelope Encryption)

Data keys the caller uses itself to encrypt data at rest (the complement to the credential proxy). All
require a **PARTNER+** agent and an unsealed server; audit-logged. See the [KMS guide](../guides/kms.md).

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/kms/generate` | Agent (PARTNER+) | Generate a data key → `{ plaintext, wrapped }` |
| POST | `/v1/kms/wrap` | Agent (PARTNER+) | Wrap a data key → `{ wrapped }` |
| POST | `/v1/kms/unwrap` | Agent (PARTNER+) | Unwrap a blob → `{ plaintext }` |

All three accept an optional base64 `aad` bound into the AES-256-GCM tag.

### Generate a Data Key

```bash
curl -X POST http://localhost:9500/v1/kms/generate \
  -H "X-Agent-Key: $AGENT_KEY" -H "Content-Type: application/json" \
  -d '{"bytes": 32}'
# { "plaintext": "<base64 data key>", "wrapped": "<base64 wrapped blob>" }
```

### Unwrap a Blob

```bash
curl -X POST http://localhost:9500/v1/kms/unwrap \
  -H "X-Agent-Key: $AGENT_KEY" -H "Content-Type: application/json" \
  -d '{"wrapped": "<base64 wrapped blob>"}'
# { "plaintext": "<base64 data key>" }   (HTTP 400 if tampered / wrong key / AAD mismatch)
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
