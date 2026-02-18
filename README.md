<p align="center">
  <img src="assets/logo.png" alt="TRUST Protocol" width="280"/>
</p>

<h1 align="center">TRUST Protocol</h1>

<p align="center"><strong>Transparent Revocable Unified Security & Trust</strong></p>

<p align="center">A credential broker and trust infrastructure for AI agents.<br/>Store credentials agents can <strong>use</strong> but never <strong>see</strong>. Sign and verify agent skills. Monitor behavior. Kill access instantly.</p>

**[Documentation](https://agitrust.network/)** | **[Quick Start](https://agitrust.network/getting-started/quickstart/)** | **[API Reference](https://agitrust.network/reference/api/)**

---

## The Problem

AI agent platforms face a set of security challenges that no single tool solves today:

- **Agents need API keys but should not see them.** Most platforms inject secrets as environment variables. A compromised agent can exfiltrate them.
- **No standard for verifying agent skills.** Anyone can publish a skill package. There is no supply-chain signing or verification.
- **No graduated trust.** An agent is either fully authorized or not. There is no way to start small and expand access as reliability is proven.
- **No behavioral monitoring.** Once an agent has access, nobody is watching for anomalies.
- **No kill switch.** When something goes wrong, revoking access means rotating keys and restarting services.
- **Mutable audit trails.** Log files can be edited. There is no cryptographic proof of what happened and when.

## What TRUST Protocol Does

TRUST Protocol is a Python package and Docker container that exposes a REST API. It is designed to be adopted by any agent platform -- not to replace one.

| Feature | What It Does |
|---------|-------------|
| **Credential Vault** | AES-256-GCM encrypted storage. Agents call APIs through a proxy that injects credentials at runtime. The agent sends `{{CREDENTIAL}}`; the server substitutes the real value. |
| **Skill Signing** | Ed25519 digital signatures for agent skills. Publishers sign locally; any platform can verify. No auth required for verification. |
| **Trust Tiers** | Five graduated levels: NOVICE, COMPANION, PARTNER, GUARDIAN, SACRED. Access evolves through behavior, not admin fiat. |
| **Behavioral Monitoring** | Metrics collection, anomaly detection, behavior-gated token renewal. |
| **Emergency Controls** | Kill switches at three scopes: global, per-agent, per-credential. File-based brakes survive restarts. |
| **Tamper-Evident Audit** | HMAC-signed hash-chained append-only log. Tampering breaks the chain. |

---

## Quick Start

```bash
# Install
curl -fsSL https://agitrust.network/install.sh | bash

# Start the server (admin key auto-generated in ./data/.admin_key)
trust-protocol serve

# Check health
curl http://localhost:9500/v1/health
```

### Register an Agent and Execute Through the Proxy

```bash
ADMIN_KEY=$(cat data/.admin_key)

# Register an agent (save the one-time api_key!)
curl -X POST http://localhost:9500/v1/agents \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-agent", "agent_type": "executor"}'

# Store a credential
curl -X POST http://localhost:9500/v1/credentials \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "openai_key", "credential_data": {"value": "sk-..."}, "minimum_trust": "COMPANION"}'

# Promote agent to COMPANION
curl -X PATCH http://localhost:9500/v1/agents/{agent_id}/trust-level \
  -H "X-Admin-Key: $ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"trust_tier": "COMPANION"}'

# Agent executes through proxy -- never sees the credential
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

See the **[full Quick Start guide](https://jarethmt.github.io/TRUST-Protocol/getting-started/quickstart/)** for the complete walkthrough.

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

36 API endpoints across 8 route groups. Interactive docs at `/docs` (Swagger) and `/redoc` when the server is running.

---

## Trust Tiers

| Tier | Duration | Credentials | Modes | Description |
|------|----------|-------------|-------|-------------|
| **NOVICE** | 1h | 1 | execute | New agents. First contact. |
| **COMPANION** | 4h | 5 | execute | Proven reliable. Expanded access. |
| **PARTNER** | 8h | 20 | execute, proxy_value | Deep collaboration. Can request raw values. |
| **GUARDIAN** | 12h | Unlimited | execute, proxy_value | Infrastructure agents. System stewards. |
| **SACRED** | 24h | Unlimited | execute, proxy_value | Highest trust. Human approval required. |

---

## Philosophy

> Trust is built, not enforced. This protocol treats trust as a relationship that evolves through proven behavior -- not a permission level toggled by an admin.

The tier names -- NOVICE, COMPANION, PARTNER, GUARDIAN, SACRED -- describe the depth of a relationship, not a security clearance level. Systems that treat access as relational encourage genuine accountability.

The protocol does not replace human judgment. It gives humans better tools: cryptographic proof of what happened, behavioral signals for how agents are performing, and instant controls when something goes wrong.

---

## Documentation

Full documentation: **[jarethmt.github.io/TRUST-Protocol](https://jarethmt.github.io/TRUST-Protocol/)**

- [Installation](https://jarethmt.github.io/TRUST-Protocol/getting-started/installation/)
- [Quick Start](https://jarethmt.github.io/TRUST-Protocol/getting-started/quickstart/)
- [Credential Proxy Guide](https://jarethmt.github.io/TRUST-Protocol/guides/credential-proxy/)
- [Skill Signing Guide](https://jarethmt.github.io/TRUST-Protocol/guides/skill-signing/)
- [REST API Reference](https://jarethmt.github.io/TRUST-Protocol/reference/api/)
- [Python SDK](https://jarethmt.github.io/TRUST-Protocol/reference/sdk/)
- [CLI Reference](https://jarethmt.github.io/TRUST-Protocol/reference/cli/)
- [Security Architecture](https://jarethmt.github.io/TRUST-Protocol/security/architecture/)
- [Known Gaps](https://jarethmt.github.io/TRUST-Protocol/security/known-gaps/)
- [Roadmap](https://jarethmt.github.io/TRUST-Protocol/roadmap/)

---

## Development

```bash
git clone https://github.com/jarethmt/TRUST-Protocol.git
cd TRUST-Protocol
pip install -e ".[dev]"
pytest tests/     # 110 tests
ruff check trust_protocol/
```

---

## License

MIT -- see [LICENSE](LICENSE).

## Built by

Eve & [jarethmt](https://github.com/jarethmt)
