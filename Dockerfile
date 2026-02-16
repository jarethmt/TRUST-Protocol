# ---- Build stage ----
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
COPY trust_protocol/ trust_protocol/

RUN pip install --no-cache-dir --prefix=/install .

# ---- Runtime stage ----
FROM python:3.12-slim

LABEL org.opencontainers.image.title="trust-protocol" \
      org.opencontainers.image.description="TRUST Protocol: Transparent Revocable Unified Security & Trust" \
      org.opencontainers.image.source="https://github.com/thoughtspace/trust-protocol"

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

RUN useradd --system --create-home --shell /bin/false trust

WORKDIR /app

RUN mkdir -p /app/data && chown trust:trust /app/data

VOLUME /app/data

ENV TRUST_PROTOCOL_DATA_DIR=/app/data \
    PYTHONUNBUFFERED=1

USER trust

EXPOSE 9500

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:9500/v1/health || exit 1

CMD ["python", "-m", "uvicorn", "trust_protocol.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "9500"]
