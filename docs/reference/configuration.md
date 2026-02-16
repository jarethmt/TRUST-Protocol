# Configuration

TRUST Protocol is configured via environment variables.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUST_PROTOCOL_DATA_DIR` | `./data` | Data directory for credentials, agents, audit logs, publishers |
| `TRUST_PROTOCOL_SECRET_KEY` | Auto-generated | HMAC signing key for tokens and audit chain. Auto-generated if not set. |
| `TRUST_PROTOCOL_VAULT_PASSWORD` | *(unset)* | Vault master password for credential encryption. If set, the server auto-unseals at startup (dev/CI mode). If unset, the server starts sealed and requires interactive unseal. |
| `TRUST_PROTOCOL_ADMIN_KEY` | Auto-generated | Admin API key. Auto-generated on first run and persisted. |
| `TRUST_PROTOCOL_HOST` | `0.0.0.0` | Bind host |
| `TRUST_PROTOCOL_PORT` | `9500` | Bind port |

## Operating Modes

### Production (Sealed Start)

Do **not** set `TRUST_PROTOCOL_VAULT_PASSWORD`. The server starts sealed -- credential operations return HTTP 503 until a human unseals it:

```bash
# Start the server (sealed)
trust-protocol serve

# In another terminal, unseal interactively
trust-protocol unseal
# Enter vault password: ********
```

If the server restarts, the password is lost and a human must unseal again. This is the intended security model -- the vault password never touches disk.

### Development (Auto-Unseal)

Set `TRUST_PROTOCOL_VAULT_PASSWORD` to auto-unseal at startup:

```bash
export TRUST_PROTOCOL_VAULT_PASSWORD="my-dev-password"
trust-protocol serve
# Server starts unsealed, credential ops work immediately
```

!!! warning "Dev mode only"
    Setting `TRUST_PROTOCOL_VAULT_PASSWORD` in the environment means the password is visible in `/proc/<pid>/environ` and `ps e` output. Use this only for development and CI, never in production.

## Key Separation

TRUST Protocol uses two independent keys:

| Key | Variable | Purpose | Storage |
|-----|----------|---------|---------|
| **HMAC key** | `TRUST_PROTOCOL_SECRET_KEY` | Token signing, audit chain integrity | Auto-generated on disk or env var |
| **Vault password** | `TRUST_PROTOCOL_VAULT_PASSWORD` (dev) or interactive unseal (prod) | AES-256-GCM credential encryption | Process memory only (after unseal) |

This separation means the HMAC key (which protects integrity but not secrecy) can safely live on disk, while the vault password (which protects credential secrecy) requires human interaction in production.

## Admin Key Resolution

The admin key is resolved in this order:

1. `TRUST_PROTOCOL_ADMIN_KEY` environment variable (if set)
2. `{data_dir}/.admin_key` file (if exists)
3. Auto-generated, written to `{data_dir}/.admin_key` with `0600` permissions

## Data Directory

All persistent data is stored in `TRUST_PROTOCOL_DATA_DIR`:

```
data/
├── .admin_key              # Admin API key (auto-generated, chmod 600)
├── .server_secret          # HMAC signing secret (auto-generated)
├── credentials/            # AES-256-GCM encrypted credential files
├── agents/                 # Agent identity files (JSON)
├── publishers/             # Publisher registry files (JSON)
├── tokens/                 # Active token files (JSON)
└── audit.jsonl             # Append-only audit chain
```

Note: The vault master password is **not** stored in the data directory. It exists only in server process memory after unseal.

## Docker Environment

When running in Docker, the data directory defaults to `/app/data` and is mounted as a volume:

```yaml
services:
  trust-protocol:
    build: .
    environment:
      - TRUST_PROTOCOL_DATA_DIR=/app/data
    volumes:
      - trust-data:/app/data
```

See [Docker Deployment](../deployment/docker.md) for complete examples including sealed and auto-unseal modes.
