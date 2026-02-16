# Configuration

TRUST Protocol is configured via environment variables.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TRUST_PROTOCOL_DATA_DIR` | `./data` | Data directory for credentials, agents, audit logs, publishers |
| `TRUST_PROTOCOL_SECRET_KEY` | Auto-generated | Server secret for HMAC signing. Auto-generated if not set. |
| `TRUST_PROTOCOL_ADMIN_KEY` | Auto-generated | Admin API key. Auto-generated on first run and persisted. |
| `TRUST_PROTOCOL_HOST` | `0.0.0.0` | Bind host |
| `TRUST_PROTOCOL_PORT` | `9500` | Bind port |

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

## Secret Key

The `TRUST_PROTOCOL_SECRET_KEY` is used for:

- HMAC signing of access tokens
- HMAC signing of audit chain entries
- Key derivation for AES-256-GCM credential encryption

If not set, a random secret is generated and persisted to `{data_dir}/.server_secret`. For production deployments with multiple instances, set this explicitly so all instances share the same key.
