# Docker Deployment

The Docker image uses a multi-stage build with Python 3.12 slim. It runs as a non-root `trust` user.

## Quick Start

```bash
docker compose up -d
```

## Operating Modes

### Production (Sealed Start -- Recommended)

The server starts sealed. Credential operations return 503 until a human unseals it. The vault password never touches disk.

```yaml
# docker-compose.yml (production)
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

After starting, unseal the server:

```bash
# Using the CLI
trust-protocol unseal --admin-key $(docker exec trust-protocol cat /app/data/.admin_key)

# Or via the API
curl -X POST http://localhost:9500/v1/unseal \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"password": "your-vault-password"}'
```

If the container restarts, you must unseal again. This is by design -- the vault password is held only in process memory.

### Development (Auto-Unseal)

Set `TRUST_PROTOCOL_VAULT_PASSWORD` for automatic unsealing at startup:

```yaml
# docker-compose.yml (development)
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
      - TRUST_PROTOCOL_VAULT_PASSWORD=dev-password  # Auto-unseal

volumes:
  trust-data:
```

!!! warning "Dev mode only"
    `TRUST_PROTOCOL_VAULT_PASSWORD` in the environment means the password is visible via `docker inspect` and `/proc/<pid>/environ`. Never use this in production.

## Production Notes

### Port Binding

The default `docker-compose.yml` binds to `127.0.0.1:9500`, not `0.0.0.0`. This means the server is only accessible from localhost. Put a reverse proxy (Traefik, nginx, Caddy) in front for external access with TLS.

### Persistent Data

The `trust-data` volume stores all credentials, agent registries, audit logs, and server keys. Back this up regularly.

Note: The vault master password is **not** stored in the data volume. It exists only in server process memory after unseal.

### Environment Variables

```yaml
environment:
  - TRUST_PROTOCOL_DATA_DIR=/app/data
  - TRUST_PROTOCOL_SECRET_KEY=your-hmac-key     # Optional: HMAC key for multi-instance
  - TRUST_PROTOCOL_ADMIN_KEY=your-admin-key      # Optional: set to control admin key
  # Do NOT set TRUST_PROTOCOL_VAULT_PASSWORD in production
```

See [Configuration](../reference/configuration.md) for all options.

### Health Check

The Docker image includes a built-in health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:9500/v1/health || exit 1
```

The health endpoint returns a `sealed` field so monitoring tools can alert when the server needs unsealing:

```bash
curl -s http://localhost:9500/v1/health | jq '.sealed'
# false (unsealed, credential ops working)
# true (sealed, needs human unseal)
```

### Behind a Reverse Proxy (Traefik example)

```yaml
services:
  trust-protocol:
    build: .
    container_name: trust-protocol
    restart: unless-stopped
    volumes:
      - trust-data:/app/data
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.trust.rule=Host(`trust.yourdomain.com`)"
      - "traefik.http.routers.trust.tls.certresolver=letsencrypt"
      - "traefik.http.services.trust.loadbalancer.server.port=9500"
    networks:
      - proxy

volumes:
  trust-data:

networks:
  proxy:
    external: true
```

### Reading the Admin Key

The admin key is auto-generated on first run:

```bash
# From host
docker exec trust-protocol cat /app/data/.admin_key

# Or check logs on first startup
docker logs trust-protocol 2>&1 | head
```
