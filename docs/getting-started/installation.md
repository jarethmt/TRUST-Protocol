# Installation

## One-Line Install

```bash
curl -fsSL https://agitrust.network/install.sh | bash
```

This checks for Python 3.10+, pip, and git, then installs the `trust-protocol` CLI and library.

## From Source

```bash
git clone https://github.com/jarethmt/TRUST-Protocol.git
cd TRUST-Protocol
pip install -e .
```

For development (includes test and lint tools):

```bash
pip install -e ".[dev]"
```

## With Docker

```bash
git clone https://github.com/jarethmt/TRUST-Protocol.git
cd TRUST-Protocol
docker compose up -d
```

The Docker image uses a multi-stage build with Python 3.12 slim and runs as a non-root `trust` user.

## From PyPI (coming soon)

```bash
# Not yet published -- will be available as:
# pip install trust-protocol
```

## Requirements

- Python 3.10+
- Dependencies (installed automatically): FastAPI, uvicorn, cryptography, Pydantic, httpx, Typer, Rich

## Verify Installation

```bash
# Start the server
trust-protocol serve

# In another terminal
curl http://localhost:9500/v1/health
# {"status": "ok", "version": "0.1.0", "uptime_seconds": ...}
```

The admin API key is auto-generated on first run and saved to `./data/.admin_key`. You'll need this key for management operations.
