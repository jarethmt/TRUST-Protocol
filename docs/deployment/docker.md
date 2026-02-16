# Docker Deployment

The Docker image uses a multi-stage build with Python 3.12 slim. It runs as a non-root `trust` user.

## Quick Start

```bash
docker compose up -d
```

## docker-compose.yml

```yaml
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

## Production Notes

### Port Binding

The default `docker-compose.yml` binds to `127.0.0.1:9500`, not `0.0.0.0`. This means the server is only accessible from localhost. Put a reverse proxy (Traefik, nginx, Caddy) in front for external access with TLS.

### Persistent Data

The `trust-data` volume stores all credentials, agent registries, audit logs, and server keys. Back this up regularly.

### Environment Variables

```yaml
environment:
  - TRUST_PROTOCOL_DATA_DIR=/app/data
  - TRUST_PROTOCOL_SECRET_KEY=your-secret-here  # Optional: set for multi-instance
  - TRUST_PROTOCOL_ADMIN_KEY=your-admin-key      # Optional: set to control admin key
```

See [Configuration](../reference/configuration.md) for all options.

### Health Check

The Docker image includes a built-in health check:

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:9500/v1/health || exit 1
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
