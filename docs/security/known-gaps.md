# Known Security Gaps

TRUST Protocol v0.1.0 is a functional MVP. This document honestly describes what is **not yet hardened**. These are planned improvements, not design flaws.

## Process Memory Reading

**Gap**: After unseal, the vault master password exists in server process memory. An attacker with root access or `ptrace` capability on the host can read `/proc/<pid>/mem` to extract the password.

**Context**: This is an inherent limitation of any in-process secret management, including HashiCorp Vault itself. Any software that holds a secret in memory is vulnerable to a sufficiently privileged attacker on the same machine.

**Current mitigations**:

- The Docker image runs as a non-root `trust` user, reducing the attack surface
- The password is held in a single `SealManager` object, not scattered across memory
- The `seal` command explicitly clears the password from memory

**Planned mitigations**:

- `prctl(PR_SET_DUMPABLE, 0)` to prevent core dumps and `/proc/<pid>/mem` reads from non-root
- Running with `ptrace_scope=2` or higher to restrict ptrace access
- Memory-safe password handling using `mlock()` and explicit zeroing on seal
- Container namespace isolation (separate PID namespace prevents `/proc` access from other containers)

**Future exploration**:

- Hardware Security Module (HSM) integration where the encryption key never enters process memory
- Secure enclave execution (SGX/TrustZone) for the credential proxy
- Subprocess isolation where the vault password exists only in a short-lived child process

**Honest framing**: If an attacker has root on the host machine, no software-only solution is fully secure. The sealed/unsealed model significantly raises the bar compared to storing the key on disk or in an environment variable, but process memory reading remains a theoretical risk that requires hardware-level solutions to fully eliminate.

## No URL Allowlisting

**Gap**: The credential proxy will execute HTTP requests to any URL. An agent could potentially use a credential against unintended targets.

**Planned fix (v0.2)**: Per-credential URL allowlists. Example: "The `openai_key` credential can only be used against `api.openai.com`."

## No Response Filtering

**Gap**: If an upstream API accidentally echoes the credential in its response body, the agent would see it.

**Planned fix (v0.2)**: Scrub the credential value from response bodies before returning to the agent.

## No Subprocess Isolation

**Gap**: The credential proxy runs in the same process as the main server. The credential value exists in server process memory during the HTTP call.

**Planned fix (v0.2)**: Fork a subprocess for each proxy execution so the credential exists only in the child process memory and is destroyed on exit.

## No Rate Limiting

**Gap**: There are no per-agent or per-credential rate limits. A misbehaving agent could make unlimited proxy-execute calls.

**Planned fix (v0.2)**: Configurable rate limits per credential and per agent, enforced at the API layer.

## In-Memory Proxy-Value Tokens

**Gap**: Proxy-value tokens (the single-use tokens for PARTNER+ raw credential access) are stored in memory. They are lost if the server restarts during their 60-second window.

**Impact**: Low. These tokens have a 60-second TTL and are single-use. The worst case is that an in-flight exchange fails and the agent needs to request a new token.

## File-Based Storage

**Gap**: All data (credentials, agents, tokens, audit) is stored as files with basic file locking. This limits throughput under high concurrency and doesn't support multi-instance deployments.

**Planned fix (v0.3+)**: Optional database backend (PostgreSQL or SQLite) with proper transactional guarantees.

## Single Admin Key

**Gap**: There is one admin key with full access to all operations. No role-based access control, no multi-user support.

**Planned fix (v0.3)**: Multi-user RBAC with organizational boundaries.

## No TLS Termination

**Gap**: The server does not handle TLS. In production, it must be placed behind a reverse proxy (Traefik, nginx, Caddy) that terminates TLS.

**This is by design**: TLS termination is better handled by purpose-built reverse proxies. The server binds to `127.0.0.1` by default.
