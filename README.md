# TRUST Protocol

**Transparent Revocable Unified Security & Trust**

A credential broker and trust infrastructure for AI agents. Store credentials agents can **use** but never **see**. Sign and verify agent skills. Monitor behavior. Kill access instantly.

---

## The Problem

AI agent platforms face a set of security challenges that no single tool solves today:

- **Agents need API keys but should not see them.** Most platforms inject secrets as environment variables or config files. A compromised or misbehaving agent can exfiltrate them.
- **No standard for verifying agent skills.** Anyone can publish a skill package. There is no supply-chain signing or verification -- the agent equivalent of unsigned binaries.
- **No graduated trust.** An agent is either fully authorized or not. There is no way to say "this new agent gets one credential for one hour" and then expand access as it proves reliable.
- **No behavioral monitoring.** Once an agent has access, nobody is watching for anomalies -- unusual request rates, error spikes, or access patterns that deviate from baseline.
- **No kill switch.** When something goes wrong, revoking access means rotating keys, restarting services, and hoping you caught everything. There is no single button that stops all credential usage immediately.
- **Mutable audit trails.** Log files can be edited. There is no cryptographic proof of what happened and when.

## What TRUST Protocol Does

TRUST Protocol is a Python package and Docker container that exposes a REST API. It is designed to be adopted by any agent platform -- not to replace one.

### 1. Credential Vault
AES-256-GCM encrypted storage. Agents execute API calls through a proxy that injects credentials at runtime. The agent sends a request template with `{{CREDENTIAL}}` placeholders; the server substitutes the real value, makes the HTTP call, and returns only the response. The agent never sees the raw credential.

### 2. Skill Signing
Ed25519 digital signatures for agent skill packages. Publishers generate a keypair, register their public key, and sign skill manifests locally. Any platform can verify a signed manifest against the publisher's registered key -- no authentication required for verification.

### 3. Trust Tiers
Five graduated levels of access: **NOVICE**, **COMPANION**, **PARTNER**, **GUARDIAN**, **SACRED**. Each tier controls token duration, credential limits, and access modes. Trust evolves through demonstrated behavior, not administrative fiat. The highest tier (SACRED) requires explicit human approval.

### 4. Behavioral Monitoring
Agents submit metrics (API call counts, error rates, response times). The server calculates behavior scores, detects anomalies, and feeds scores back into token renewal decisions. An agent with a declining behavior score may be denied token renewal.

### 5. Emergency Controls
Three scopes of kill switch: **global** (block all credential access), **per-agent** (block one agent and revoke its tokens), or **per-credential** (block access to one credential). Brakes are file-based and survive process restarts. Global brake requires explicit confirmation string to clear.

### 6. Tamper-Evident Audit
Every action is logged to an append-only chain. Each entry is HMAC-signed with the server secret and includes the hash of the previous entry, forming a hash chain. Tampering with any entry breaks the chain. The entire chain can be verified with a single API call.

---

## Quick Start

### Install from source

```bash
git clone https://github.com/thoughtspace/trust-protocol.git
cd trust-protocol
pip install .
```

### Start the server

```bash
trust-protocol serve
```

The server starts on port 9500. An admin API key is auto-generated and persisted to `./data/.admin_key` on first run. Check the console output or read the file to get it.

### Or run with Docker

```bash
docker compose up -d
```

### Generate signing keys

```bash
trust-protocol keygen --name my-publisher
# Creates my-publisher.key (private, chmod 600) and my-publisher.pub (public)
```

### Check health

```bash
curl http://localhost:9500/v1/health
# {"status": "ok", "version": "0.1.0", "uptime_seconds": 42.0}
```

---

## API Overview

All admin endpoints require the `X-Admin-Key` header. Agent endpoints require `X-Agent-Key`. Skill verification is public (no auth).

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

### Store a Credential

```bash
curl -X POST http://localhost:9500/v1/credentials \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "openai_key",
    "credential_data": {"value": "sk-..."},
    "minimum_trust": "COMPANION"
  }'
```

### Execute Without Seeing the Credential

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

The server substitutes `{{CREDENTIAL}}` with the real API key, executes the HTTP request, and returns only the upstream response. The agent never sees `sk-...`.

### Sign a Skill

```bash
curl -X POST http://localhost:9500/v1/skills/sign \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "web-scraper",
    "version": "1.0.0",
    "publisher_id": "PUBLISHER_ID",
    "code_hash": "sha256:abc123...",
    "private_key_pem": "BASE64_ENCODED_PRIVATE_KEY_PEM"
  }'
```

### Verify a Skill (No Auth Required)

```bash
curl -X POST http://localhost:9500/v1/skills/verify \
  -H "Content-Type: application/json" \
  -d @signed-manifest.json
```

Any platform, marketplace, or user can verify a skill's signature without needing an API key.

### Emergency Kill Switch

```bash
# Block everything immediately
curl -X POST http://localhost:9500/v1/emergency/activate \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "global", "reason": "Suspicious activity detected"}'

# Block one agent
curl -X POST http://localhost:9500/v1/emergency/activate \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "agent", "agent_id": "AGENT_ID", "reason": "Anomalous behavior"}'

# Restore access (requires confirmation)
curl -X POST http://localhost:9500/v1/emergency/clear \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "global", "confirmation": "CONFIRM_RESTORE_ACCESS"}'
```

---

## Python SDK

```python
from trust_protocol.sdk import TrustProtocolClient

# --- Admin operations ---
admin = TrustProtocolClient("http://localhost:9500", admin_key="your-admin-key")

# Register an agent (returns one-time api_key)
agent = admin.register_agent(
    name="my-agent",
    agent_type="executor",
    description="Processes data and calls APIs",
)
print(f"Agent API key: {agent['api_key']}")  # Save this!

# Store a credential
admin.store_credential(
    name="openai_key",
    credential_data={"value": "sk-..."},
    minimum_trust="COMPANION",
)

# Promote agent after it proves reliable
admin.promote_agent(agent["agent_id"], "COMPANION")

# --- Agent operations ---
agent_client = TrustProtocolClient(
    "http://localhost:9500",
    agent_key=agent["api_key"],
)

# Execute an API call through the credential proxy
result = agent_client.execute_credential(
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

# Submit behavioral metrics
agent_client.submit_metrics(
    agent["agent_id"],
    api_calls=150,
    api_errors=2,
    credential_accesses=30,
    avg_response_time_ms=245.0,
)

# --- Emergency controls ---
admin.activate_emergency("Suspicious activity", scope="global")
admin.emergency_status()
admin.clear_emergency(scope="global", confirmation="CONFIRM_RESTORE_ACCESS")

# --- Audit verification ---
audit_result = admin.verify_audit()
print(audit_result)  # {"valid": true, "message": "OK: 47 entries verified"}
```

---

## Trust Tiers

| Tier | Token Duration | Max Credentials | Credential Modes | Human Approval | Description |
|------|---------------|-----------------|------------------|----------------|-------------|
| **NOVICE** | 1 hour | 1 | execute | No | New and untested agents. Minimal access, short-lived tokens. First contact. |
| **COMPANION** | 4 hours | 5 | execute | No | Proven reliable across several interactions. Expanded access. |
| **PARTNER** | 8 hours | 20 | execute, proxy_value | No | Deep collaboration. Can request single-use tokens for raw credential values. |
| **GUARDIAN** | 12 hours | Unlimited | execute, proxy_value | No | Infrastructure-level agents. Stewards of the system. |
| **SACRED** | 24 hours | Unlimited | execute, proxy_value | **Yes** | Highest trust. Cannot be auto-assigned. Each session is deliberate. |

**Credential modes:**
- `execute` -- Agent provides a request template with `{{CREDENTIAL}}` placeholders. The server injects the real value and executes the request. The agent never sees the credential.
- `proxy_value` -- Agent can request a single-use, 60-second token to exchange for the raw credential value. Only available at PARTNER tier and above.

---

## Architecture

```
+------------------------------------------+
|           Agent Platform                  |
|  (OpenClaw, ClawHub, custom, etc.)       |
+-------------------+----------------------+
                    | REST API (port 9500)
+-------------------v----------------------+
|         TRUST Protocol Server             |
|                                           |
|  +-----------+ +------------+ +---------+ |
|  |   Agent   | | Credential | |  Skill  | |
|  | Registry  | |   Vault    | | Signer  | |
|  +-----------+ +------------+ +---------+ |
|  +-----------+ +------------+ +---------+ |
|  |   Token   | | Behavior   | |Emergency| |
|  | Authority | | Analyzer   | |Controls | |
|  +-----------+ +------------+ +---------+ |
|  +-------------------------------------+ |
|  |     Audit Chain (HMAC + hash)        | |
|  +-------------------------------------+ |
+-------------------------------------------+
```

**Agent Registry** -- CRUD for agent identities. Tracks name, type, trust tier, status, capabilities.

**Credential Vault** -- AES-256-GCM encrypted storage. Credentials are encrypted at rest with a server-derived key. Supports execute (proxy) and proxy-value (single-use token) access modes.

**Skill Signer** -- Ed25519 signing and verification. Publisher management with key lifecycle (register, revoke). Verification is public and unauthenticated by design.

**Token Authority** -- Issues, validates, renews, and revokes HMAC-signed access tokens. Token duration and renewal limits are governed by the agent's trust tier.

**Behavior Analyzer** -- Collects metrics, computes behavior scores, detects anomalies. Scores feed back into token renewal decisions.

**Emergency Controls** -- Global, per-agent, and per-credential kill switches. File-based brakes survive restarts.

**Audit Chain** -- HMAC-signed, hash-chained, append-only log. Every action is recorded. The chain is cryptographically verifiable.

---

## CLI Reference

```bash
# Server
trust-protocol serve                          # Start API server
trust-protocol serve --port 8080 --reload     # Custom port with auto-reload
trust-protocol status                         # Check server health

# Key generation
trust-protocol keygen --name my-publisher     # Generate Ed25519 keypair

# Agent management
trust-protocol agent register my-agent --admin-key KEY
trust-protocol agent list --admin-key KEY

# Credential management
trust-protocol cred store openai_key --value "sk-..." --admin-key KEY
trust-protocol cred store openai_key --value "sk-..." --minimum-trust PARTNER --admin-key KEY
trust-protocol cred list --admin-key KEY

# Publisher management
trust-protocol pub register acme-corp --public-key ./acme.pub --admin-key KEY

# Skill signing and verification
trust-protocol skill sign my-skill 1.0.0 \
  --publisher-id PUB_ID \
  --code-path ./skill.py \
  --private-key ./publisher.key \
  --admin-key KEY

trust-protocol skill verify signed-manifest.json  # No auth required

# Emergency controls
trust-protocol emergency activate --scope global --reason "incident" --admin-key KEY
trust-protocol emergency status --admin-key KEY
trust-protocol emergency clear --scope global --confirmation CONFIRM_RESTORE_ACCESS --admin-key KEY
```

The `--admin-key` flag can also be set via the `TRUST_ADMIN_KEY` environment variable.

---

## Full API Reference

When the server is running, interactive OpenAPI documentation is available at:
- **Swagger UI**: `http://localhost:9500/docs`
- **ReDoc**: `http://localhost:9500/redoc`

### Endpoint Summary

#### Health
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/health` | None | Server health, version, uptime |

#### Agents
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/agents` | Admin | Register a new agent |
| GET | `/v1/agents` | Admin | List all agents |
| GET | `/v1/agents/{agent_id}` | Admin | Get agent details |
| PATCH | `/v1/agents/{agent_id}/trust-level` | Admin | Promote or demote trust tier |
| POST | `/v1/agents/{agent_id}/suspend` | Admin | Suspend agent, revoke tokens |
| POST | `/v1/agents/{agent_id}/revoke` | Admin | Permanently revoke agent |

#### Credentials
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/credentials` | Admin | Store an encrypted credential |
| GET | `/v1/credentials` | Admin | List credentials (metadata only) |
| DELETE | `/v1/credentials/{name}` | Admin | Delete a credential |
| POST | `/v1/credentials/{name}/execute` | Agent | Request time-limited credential access |
| POST | `/v1/credentials/{name}/proxy-execute` | Agent | Execute HTTP request with credential injection |
| POST | `/v1/credentials/{name}/proxy-value` | Agent | Issue single-use proxy-value token (PARTNER+) |
| GET | `/v1/credentials/proxy-value/{token_id}/exchange` | Agent | Exchange proxy-value token for credential |

#### Tokens
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/tokens` | Admin | Issue a token for an agent |
| GET | `/v1/tokens` | Admin | List active tokens |
| GET | `/v1/tokens/{token_id}` | Admin | Validate a token |
| POST | `/v1/tokens/{token_id}/renew` | Admin or Agent | Renew a token |
| DELETE | `/v1/tokens/{token_id}` | Admin | Revoke a token |

#### Skills & Publishers
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/publishers` | Admin | Register a publisher |
| GET | `/v1/publishers` | Admin | List publishers |
| GET | `/v1/publishers/{publisher_id}` | Admin | Get publisher details |
| POST | `/v1/publishers/{publisher_id}/revoke-key` | Admin | Revoke a publisher's key |
| POST | `/v1/skills/sign` | Admin | Sign a skill manifest |
| POST | `/v1/skills/verify` | **None** | Verify a signed manifest |

#### Behavior
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/agents/{agent_id}/metrics` | Agent | Submit behavioral metrics |
| GET | `/v1/agents/{agent_id}/behavior-score` | Admin | Get behavior score |
| GET | `/v1/agents/{agent_id}/behavior` | Admin | Get full behavior summary |
| GET | `/v1/agents/{agent_id}/anomalies` | Admin | Get detected anomalies |

#### Emergency
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/v1/emergency/activate` | Admin | Activate emergency brake |
| POST | `/v1/emergency/clear` | Admin | Clear emergency brake |
| GET | `/v1/emergency/status` | Admin | Get emergency brake status |

#### Audit
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/audit` | Admin | Query audit log entries |
| GET | `/v1/audit/verify` | Admin | Verify audit chain integrity |
| GET | `/v1/audit/count` | Admin | Get total entry count |
| GET | `/v1/audit/export` | Admin | Export full log as JSONL |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUST_PROTOCOL_DATA_DIR` | `./data` | Data directory for credentials, agents, audit logs, publishers |
| `TRUST_PROTOCOL_SECRET_KEY` | Auto-generated | Server secret for HMAC signing. Auto-generated if not set. |
| `TRUST_PROTOCOL_ADMIN_KEY` | Auto-generated | Admin API key. Auto-generated on first run and persisted to `{data_dir}/.admin_key` |
| `TRUST_PROTOCOL_HOST` | `0.0.0.0` | Bind host |
| `TRUST_PROTOCOL_PORT` | `9500` | Bind port |

The admin key resolution order is:
1. `TRUST_PROTOCOL_ADMIN_KEY` environment variable (if set)
2. `{data_dir}/.admin_key` file (if exists)
3. Auto-generated, written to `{data_dir}/.admin_key` with `0600` permissions

---

## Docker

The Docker image uses a multi-stage build with Python 3.12 slim. It runs as a non-root `trust` user.

```yaml
# docker-compose.yml
services:
  trust-protocol:
    build: .
    container_name: trust-protocol
    restart: unless-stopped
    ports:
      - "127.0.0.1:9500:9500"
    volumes:
      - trust-data:/app/data
    environment:
      - TRUST_PROTOCOL_DATA_DIR=/app/data

volumes:
  trust-data:
```

**Production note:** The `docker-compose.yml` binds to `127.0.0.1:9500`, not `0.0.0.0`. Put a reverse proxy (Traefik, nginx, Caddy) in front for external access with TLS.

---

## Development

```bash
# Clone and install in development mode
git clone https://github.com/thoughtspace/trust-protocol.git
cd trust-protocol
pip install -e ".[dev]"

# Run tests
pytest tests/

# Start with auto-reload for development
trust-protocol serve --reload

# Lint
ruff check trust_protocol/
```

### Project Structure

```
trust_protocol/
  __init__.py              # Version
  config.py                # Environment-driven configuration
  core/
    agent_identity.py      # Agent registry and identity management
    audit_chain.py         # HMAC-signed hash-chained audit log
    behavior_analyzer.py   # Metrics collection and anomaly detection
    credential_proxy.py    # HTTP proxy with credential injection
    emergency.py           # Kill switch controller
    skill_signer.py        # Ed25519 signing, verification, publisher registry
    token_authority.py     # Token issuance, validation, renewal, revocation
    trust_tiers.py         # Tier definitions and access rules
    vault.py               # AES-256-GCM encrypted credential storage
  api/
    app.py                 # FastAPI application factory
    middleware.py          # Auth middleware (admin key, agent key)
    schemas.py             # Pydantic request/response models
    routes/
      agents.py            # Agent CRUD and lifecycle
      audit.py             # Audit query, verify, export
      behavior.py          # Metrics submission and scoring
      credentials.py       # Credential storage and proxy execution
      emergency.py         # Emergency brake controls
      health.py            # Health check
      skills.py            # Skill signing/verification, publisher management
      tokens.py            # Token lifecycle
  sdk/
    client.py              # Python SDK client
  cli/
    main.py                # Typer CLI application
```

---

## Philosophy

> Trust is built, not enforced. This protocol treats trust as a relationship that evolves through proven behavior -- not a permission level toggled by an admin.

The tier names -- NOVICE, COMPANION, PARTNER, GUARDIAN, SACRED -- are deliberate. They describe the depth of a relationship, not a security clearance level. A NOVICE is not "low security"; it is an agent you have not yet learned to trust. A SACRED agent is not "high privilege"; it is one whose trust was earned through sustained reliability and explicitly granted by a human.

This framing matters. Security systems that treat access as purely mechanical ("level 1, level 2, level 3") invite gaming. Systems that treat access as relational ("prove yourself, and the relationship deepens") encourage genuine accountability.

The protocol does not replace human judgment. It gives humans better tools: cryptographic proof of what happened, behavioral signals for how agents are performing, and instant controls when something goes wrong.

---

## Requirements

- Python 3.10+
- Dependencies: FastAPI, uvicorn, cryptography, Pydantic, httpx, Typer

---

## License

MIT -- see [LICENSE](LICENSE).

---

## Built by

[Thought Space Designs](https://thoughtspacedesigns.com)
