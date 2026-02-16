# Security Architecture

This document describes the cryptographic primitives and security design of TRUST Protocol.

## Cryptographic Primitives

### Credential Encryption: AES-256-GCM

Credentials are encrypted at rest using AES-256-GCM (Authenticated Encryption with Associated Data). The encryption key is derived from the server secret using a key derivation function.

- **Algorithm**: AES-256-GCM
- **Key derivation**: From `TRUST_PROTOCOL_SECRET_KEY`
- **Nonce**: Unique per encryption operation
- **Authentication**: GCM tag prevents tampering

### Token Signing: HMAC-SHA256

Access tokens are HMAC-signed with the server secret. This is a symmetric scheme -- the same server that issues tokens validates them.

- **Algorithm**: HMAC-SHA256
- **Key**: Server secret (`TRUST_PROTOCOL_SECRET_KEY`)
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
