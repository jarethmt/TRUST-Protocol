# Skill Signing

TRUST Protocol provides Ed25519 digital signatures for agent skill packages. Publishers sign skills locally (the private key never leaves their machine), and any platform can verify signatures against registered public keys.

## Why Skill Signing Matters

Agent skill marketplaces (like ClawHub) face the same supply-chain risk as npm or Docker Hub: anyone can upload a package. Without signing, there's no way to verify that a skill hasn't been tampered with or that it comes from a trusted publisher.

TRUST Protocol solves this with:

- **Ed25519 signatures** -- fast, compact, no configuration complexity
- **Publisher registry** -- public keys registered with trust tiers
- **Public verification** -- no authentication required to verify a signature
- **Instant revocation** -- one call revokes a publisher's key globally

## Publisher Workflow

### 1. One-Time Setup

```bash
trust-protocol setup
```

This interactive wizard:

1. Generates an Ed25519 keypair
2. Registers your public key with a TRUST Protocol registry
3. Saves everything to `~/.trust-protocol/`

Or manually:

```bash
# Generate keypair
trust-protocol keygen --name my-publisher

# Register with the registry
trust-protocol pub register my-publisher \
  --public-key ./my-publisher.pub \
  --admin-key YOUR_ADMIN_KEY
```

### 2. Sign a Skill

Signing happens **locally**. The private key never leaves your machine and no server call is made.

```bash
trust-protocol skill sign my-skill 1.0.0 \
  --publisher-id YOUR_PUBLISHER_ID \
  --code-path ./skill.py \
  --private-key ~/.trust-protocol/publisher.key
```

This creates `signed-manifest.json` containing:

- Skill metadata (name, version, description)
- SHA-256 hash of the skill code
- Ed25519 signature over the canonical manifest
- Publisher ID for verification lookup

### 3. Publish to Registry

```bash
trust-protocol skill publish signed-manifest.json --admin-key YOUR_ADMIN_KEY
```

The server validates the signature before accepting. If the signature doesn't match the publisher's registered public key, the publish is rejected.

### 4. Verification (No Auth Required)

Anyone can verify a signed manifest:

```bash
trust-protocol skill verify signed-manifest.json
# VERIFIED
#   Publisher: my-publisher
#   Tier:      NOVICE
#   Since:     2026-02-16T...
```

Or via the API:

```bash
curl -X POST http://localhost:9500/v1/skills/verify \
  -H "Content-Type: application/json" \
  -d @signed-manifest.json
```

Verification is **unauthenticated by design** so any marketplace, CI/CD pipeline, or user can verify without an account.

## Key Revocation

If a private key is compromised:

```bash
curl -X POST http://localhost:9500/v1/publishers/{publisher_id}/revoke-key \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Key compromised"}'
```

All subsequent verification calls for that publisher will return `verified: false`.

## Using the Python SDK

```python
from trust_protocol.sdk import TrustProtocolClient
from trust_protocol.core.skill_signer import hash_code

# Sign locally (no server call)
signed_manifest = TrustProtocolClient.sign_locally(
    name="my-skill",
    version="1.0.0",
    publisher_id="pub_abc123",
    code_hash=hash_code(open("skill.py", "rb").read()),
    private_key_pem=open("~/.trust-protocol/publisher.key", "rb").read(),
)

# Publish to registry
admin = TrustProtocolClient("http://localhost:9500", admin_key="your-admin-key")
admin.publish_skill(signed_manifest)

# Verify (no auth needed)
client = TrustProtocolClient("http://localhost:9500")
result = client.verify_skill(signed_manifest)
print(result["verified"])  # True
```

## How Marketplaces Integrate

```
SKILL DEVELOPER                MARKETPLACE                     TRUST PROTOCOL
(publisher)                    (ClawHub, registry, etc.)       (verification server)
     |                              |                                |
     |  1. Generate keypair         |                                |
     |  (trust-protocol keygen)     |                                |
     |                              |                                |
     |  2. Register public key      |                                |
     |-------------------------------------------------------------->|
     |                              |                                |
     |  3. Build & sign skill       |                                |
     |  (trust-protocol skill sign) |                                |
     |                              |                                |
     |  4. Upload signed package    |                                |
     |---------------------------->|                                |
     |                              |                                |
     |                              |  5. On install: verify sig     |
     |                              |------------------------------->|
     |                              |  POST /skills/verify           |
     |                              |  (no auth needed!)             |
     |                              |                                |
     |                              |  <-- {verified: true,          |
     |                              |       publisher: "Acme",       |
     |                              |       trust_tier: "COMPANION"} |
     |                              |                                |
     |                              |  6. Enforce policy:            |
     |                              |  "only install from PARTNER+"  |
```
