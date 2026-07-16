# KMS — Envelope Encryption

The KMS is the **complement** to the [Credential Proxy](credential-proxy.md). Where the proxy lets an
agent **use** a credential without **seeing** it (the server makes the outbound call), the KMS is for
the opposite need: keys a caller **must use itself** — encrypting data at rest.

Reach for the proxy for API keys the agent should never touch. Reach for the KMS when a platform needs
to encrypt its own data stores (files, backups, databases, per-field secrets) locally, so the storage
backend only ever holds ciphertext.

## Prerequisites

The server must be **unsealed** (same as the credential vault — see the
[Credential Proxy](credential-proxy.md) prerequisites). KMS endpoints return HTTP 503 while sealed.

## How it works — envelope encryption

The KMS never stores your data keys. It holds a single **master key**, and hands out **wrapped** (and
unwrapped) data keys on demand:

1. A caller asks the KMS to **generate** a data key. It returns the **plaintext** key (used once, then
   discarded) *and* a **wrapped** blob.
2. The caller encrypts its data locally with the plaintext key, then keeps **only the wrapped blob** at
   rest (e.g. next to the data).
3. To decrypt later, the caller sends the wrapped blob to **unwrap** and gets the plaintext key back.

```
generate ─▶ { plaintext, wrapped }     caller: encrypt locally, store `wrapped`
unwrap(wrapped) ─▶ { plaintext }        caller: decrypt locally, then discard the key
```

The **master key never leaves the server** — it is derived from the unsealed vault password
(`HKDF(PBKDF2(vault_password, kms_salt))`, a distinct HKDF context from the credential-encryption key).
A caller at rest holds only wrapped blobs; a compromised backend or backup yields nothing without the
KMS. This is the same pattern as AWS KMS `GenerateDataKey` and Google Cloud KMS.

## What the caller sees vs. what the model sees

The plaintext data key **is** returned to the caller — that is unavoidable for local encryption. The
important boundary is *who* the caller is: it should be the platform's **runtime** (its crypto layer),
**not** an LLM's context window. Keep the key out of prompts, tool outputs, and logs, and zero it after
use, and it never reaches anything that could be collected or trained on. (The proxy remains the choice
when even the runtime should never hold the value.)

## Operations

All KMS endpoints require a **PARTNER+** agent (the same bar as credential `proxy-value`) and are
recorded in the tamper-evident audit chain (`KMS_GENERATE`, `KMS_WRAP`, `KMS_UNWRAP`).

### Generate a data key

```bash
curl -X POST http://localhost:9500/v1/kms/generate \
  -H "X-Agent-Key: $AGENT_KEY" -H "Content-Type: application/json" \
  -d '{"bytes": 32}'
# { "plaintext": "<base64 data key>", "wrapped": "<base64 wrapped blob>" }
```

### Wrap / unwrap an existing key

```bash
curl -X POST http://localhost:9500/v1/kms/wrap \
  -H "X-Agent-Key: $AGENT_KEY" -H "Content-Type: application/json" \
  -d '{"plaintext": "<base64 data key>"}'
# { "wrapped": "<base64 wrapped blob>" }

curl -X POST http://localhost:9500/v1/kms/unwrap \
  -H "X-Agent-Key: $AGENT_KEY" -H "Content-Type: application/json" \
  -d '{"wrapped": "<base64 wrapped blob>"}'
# { "plaintext": "<base64 data key>" }
```

### Binding to context (AAD)

All three accept an optional base64 `aad` (additional authenticated data) — a context string bound into
the AES-256-GCM tag. A blob wrapped with an `aad` only unwraps with the *same* `aad`, so you can tie a
data key to, say, a specific silo id or record id and reject a blob replayed elsewhere.

## Blob format

`version(1) | nonce(12) | AES-256-GCM ciphertext+tag`, base64-encoded for transport. Versioned so the
wrapping scheme can evolve without breaking existing blobs. A tampered blob (or wrong key/AAD) fails to
unwrap with HTTP 400.

## Durability

Wrapped blobs stay recoverable as long as **the vault password** and **the KMS salt** (`.kms_salt` in
the data dir, created once) both survive. Back both up with the rest of your server state — losing
either makes every wrapped blob unrecoverable by design.
