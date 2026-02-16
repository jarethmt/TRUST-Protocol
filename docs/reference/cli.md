# CLI Reference

The `trust-protocol` CLI provides commands for server management, agent administration, credential storage, skill signing, and emergency controls.

The `--admin-key` flag can also be set via the `TRUST_ADMIN_KEY` environment variable.

## Server

```bash
# Start the API server
trust-protocol serve

# Custom port with auto-reload
trust-protocol serve --port 8080 --reload

# Check server health
trust-protocol status
trust-protocol status --url http://remote-server:9500
```

## Setup Wizard

```bash
# Interactive setup (generates keypair, registers publisher)
trust-protocol setup

# Non-interactive
trust-protocol setup \
  --registry-url http://localhost:9500 \
  --admin-key YOUR_KEY \
  --name my-publisher \
  --organization "My Org"
```

Saves configuration to `~/.trust-protocol/`:

- `config.json` -- publisher ID, registry URL, key paths
- `publisher.key` -- Ed25519 private key (chmod 600)
- `publisher.pub` -- Ed25519 public key

## Key Generation

```bash
# Generate Ed25519 keypair
trust-protocol keygen --name my-publisher

# Specify output directory
trust-protocol keygen --name my-publisher --output-dir ./keys
```

## Agent Management

```bash
# Register a new agent
trust-protocol agent register my-agent --admin-key KEY
trust-protocol agent register my-agent \
  --agent-type executor \
  --description "My agent" \
  --credentials "openai_key,stripe_key" \
  --capabilities "web-search,code-gen" \
  --admin-key KEY

# List all agents
trust-protocol agent list --admin-key KEY
```

## Credential Management

```bash
# Store a credential
trust-protocol cred store openai_key --value "sk-..." --admin-key KEY

# Store with minimum trust requirement
trust-protocol cred store stripe_key \
  --value "sk_live_..." \
  --minimum-trust PARTNER \
  --admin-key KEY

# Store JSON credential data
trust-protocol cred store complex_cred \
  --value '{"client_id": "abc", "client_secret": "xyz"}' \
  --admin-key KEY

# List credentials (metadata only)
trust-protocol cred list --admin-key KEY
```

## Publisher Management

```bash
# Register a publisher
trust-protocol pub register acme-corp \
  --public-key ./acme.pub \
  --organization "Acme Inc." \
  --admin-key KEY
```

## Skill Signing

```bash
# Sign a skill locally (private key never leaves your machine)
trust-protocol skill sign my-skill 1.0.0 \
  --publisher-id PUB_ID \
  --code-path ./skill.py \
  --private-key ~/.trust-protocol/publisher.key

# Sign with metadata
trust-protocol skill sign my-skill 1.0.0 \
  --publisher-id PUB_ID \
  --code-path ./skill.py \
  --private-key ~/.trust-protocol/publisher.key \
  --capabilities "web-search,data-analysis" \
  --credentials "openai_key" \
  --description "A web search skill" \
  --output my-skill-signed.json

# Publish signed manifest to registry
trust-protocol skill publish signed-manifest.json --admin-key KEY

# Verify a signed manifest (no auth required)
trust-protocol skill verify signed-manifest.json
trust-protocol skill verify signed-manifest.json --url http://remote-registry:9500
```

## Emergency Controls

```bash
# Activate global brake
trust-protocol emergency activate \
  --scope global \
  --reason "incident" \
  --admin-key KEY

# Activate per-agent brake
trust-protocol emergency activate \
  --scope agent \
  --agent-id agt_abc123 \
  --reason "anomalous behavior" \
  --admin-key KEY

# Activate per-credential brake
trust-protocol emergency activate \
  --scope credential \
  --credential-name openai_key \
  --reason "possible compromise" \
  --admin-key KEY

# Check status
trust-protocol emergency status --admin-key KEY

# Clear global brake (requires confirmation)
trust-protocol emergency clear \
  --scope global \
  --confirmation CONFIRM_RESTORE_ACCESS \
  --admin-key KEY

# Clear agent brake
trust-protocol emergency clear \
  --scope agent \
  --agent-id agt_abc123 \
  --admin-key KEY
```
