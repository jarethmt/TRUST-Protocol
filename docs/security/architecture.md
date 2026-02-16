# Security Architecture

This document describes the cryptographic primitives and security design of TRUST Protocol.

## Cryptographic Primitives

### Credential Encryption: AES-256-GCM

Credentials are encrypted at rest using AES-256-GCM (Authenticated Encryption with Associated Data). The encryption key is derived from the **vault master password** using PBKDF2-HMAC-SHA256.

- **Algorithm**: AES-256-GCM
- **Key derivation**: PBKDF2-HMAC-SHA256 from vault master password
- **Nonce**: Unique per encryption operation
- **Authentication**: GCM tag prevents tampering
- **Key source**: Human-provided vault password (never stored on disk)

### Token Signing: HMAC-SHA256

Access tokens are HMAC-signed with the HMAC key. This is a symmetric scheme -- the same server that issues tokens validates them.

- **Algorithm**: HMAC-SHA256
- **Key**: HMAC key (`TRUST_PROTOCOL_SECRET_KEY`)
- **Token contents**: Agent ID, trust tier, credential patterns, expiry, renewal count

### Skill Signing: Ed25519

Skill manifests are signed with Ed25519 (asymmetric). Publishers hold private keys; the server stores public keys.

- **Algorithm**: Ed25519 (RFC 8032)
- **Key format**: PEM-encoded PKCS8
- **Signed data**: Canonical JSON of skill manifest (name, version, publisher_id, code_hash, capabilities, credentials_required, description)
- **Private key location**: Publisher's machine only (never transmitted)

### Audit Chain: HMAC + Hash Chain

Each audit entry is:

1. HMAC-signed with the server secret
2. Includes the hash of the previous entry

This forms a hash chain where tampering with any entry breaks the chain. The entire chain can be verified with a single API call.

## Sealed/Unsealed Architecture

TRUST Protocol uses a **sealed/unsealed model** inspired by HashiCorp Vault. The vault master password -- the key that encrypts all stored credentials -- is never written to disk, environment variables, or configuration files. It exists only in server process memory after a human provides it.

### How It Works

```
Server starts → SEALED (credential operations return 503)
                    ↓
Human runs: trust-protocol unseal → types password → sends to /v1/unseal
                    ↓
Server validates password → holds in RAM → UNSEALED (credential ops work)
                    ↓
Server restarts → back to SEALED (password gone from memory)
```

### Key Separation

The vault master password and the HMAC signing key serve different purposes and are managed independently:

| Key | Purpose | Storage | Protects |
|-----|---------|---------|----------|
| **Vault password** | AES-256-GCM credential encryption | Process memory only (after unseal) | Credential secrecy |
| **HMAC key** | Token signing, audit chain integrity | `TRUST_PROTOCOL_SECRET_KEY` or auto-generated on disk | Token/audit integrity |

This separation means an attacker who reads the HMAC key from disk can forge tokens but **cannot decrypt credentials**. Only reading the vault password from process memory would compromise credential secrecy.

### Operating Modes

**Production (sealed start)**: The server starts sealed. A human must run `trust-protocol unseal` and provide the vault master password interactively. If the server restarts, the password is lost and a human must unseal again.

**Development (auto-unseal)**: Set `TRUST_PROTOCOL_VAULT_PASSWORD` in the environment. The server auto-unseals at startup. This is convenient for development and CI, but the password is visible in the process environment.

### What Works While Sealed

Non-credential operations continue to work while the server is sealed:

- Health checks (`GET /v1/health`)
- Agent registration and management
- Token operations
- Skill signing and verification
- Audit queries
- Emergency controls
- Seal status checks

Only credential operations (store, list, delete, execute, proxy) return HTTP 503 while sealed.

## Authentication Model

### Admin Authentication

The admin key is a shared secret. It authenticates via:

- `X-Admin-Key` header
- `Authorization: Bearer <key>` header

The admin key has full access to all endpoints.

### Agent Authentication

Each agent receives a unique API key at registration. Agents authenticate via:

- `X-Agent-Key` header

Agent keys grant access only to agent-scoped endpoints (credential execution, metrics submission, token renewal).

## Trust Enforcement

### Tier-Based Access Control

Each credential has a `minimum_trust` tier. An agent must have a trust tier equal to or higher than the credential's minimum to access it.

The tier hierarchy: NOVICE < COMPANION < PARTNER < GUARDIAN < SACRED.

### Behavioral Gating

Token renewal is conditioned on behavior scores. The behavior analyzer:

1. Collects metrics from agents (API calls, errors, response times)
2. Computes a behavior score (0.0 - 1.0)
3. Detects anomalies (deviation from baseline patterns)
4. Feeds scores into token renewal decisions

An agent with a declining score may be denied token renewal.

## Emergency Controls

Three scopes of kill switch:

| Scope | Effect | Confirmation Required |
|-------|--------|----------------------|
| Global | Blocks all credential access | Yes (`CONFIRM_RESTORE_ACCESS`) |
| Per-agent | Blocks one agent, revokes its tokens | No |
| Per-credential | Blocks access to one credential | No |

Brakes are file-based and survive process restarts.

## File-Based Storage

All data is stored as files in the data directory:

- Credentials: Individual encrypted JSON files
- Agents: Individual JSON files
- Tokens: Individual JSON files
- Audit: Single append-only JSONL file
- Publishers: Individual JSON files

This design was chosen for MVP simplicity. See [Known Gaps](known-gaps.md) for the implications and planned improvements.
