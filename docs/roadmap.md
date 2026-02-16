# Roadmap

## What's Built Today (v0.1.0)

- Encrypted credential vault with zero-knowledge proxy execution
- **Sealed/unsealed vault architecture** (HashiCorp Vault-style human-only master password)
- Ed25519 skill signing and public verification
- Five-tier graduated trust system
- Behavioral monitoring with anomaly detection
- Three-level emergency controls
- HMAC-signed hash-chained audit trail
- Python SDK and CLI
- Docker packaging
- 110 tests passing

## What's Coming Next

### v0.2 -- Credential Proxy Hardening

- Subprocess-isolated credential execution (the proxy runs in a forked process so the credential never exists in the main process memory)
- URL allowlisting per credential (credential X can only be used against api.openai.com)
- Rate limiting per credential and per agent
- Response filtering (strip credentials that accidentally appear in upstream responses)
- Process memory hardening (`prctl(PR_SET_DUMPABLE, 0)`, `mlock()`, explicit zeroing on seal)
- PyPI publication (`pip install trust-protocol`)

### v0.3 -- Multi-User & RBAC

- Multiple admin users with role-based access control
- Organizational boundaries (agents and credentials belong to organizations)
- Delegated administration (org admins manage their own agents/credentials)
- OAuth2 / OIDC integration for human authentication
- Optional database backend (PostgreSQL or SQLite)

### v0.4 -- Distributed Trust Network

- Federation between TRUST Protocol instances (org A trusts publisher keys registered with org B)
- Publisher reputation scores based on aggregated verification data across instances
- Revocation propagation across federated instances
- Trust anchors (root publishers that bootstrap the network)

### v0.5 -- Advanced Behavioral Intelligence

- ML-based anomaly detection (replacing threshold-based heuristics)
- Behavioral fingerprinting (each agent develops a unique behavioral signature)
- Automatic trust tier recommendations based on behavior history
- Cross-agent correlation (detect coordinated anomalous behavior)

### v0.6 -- SDK Ecosystem

- TypeScript/JavaScript SDK
- Go SDK
- Rust SDK
- OpenAPI client generation for any language
- MCP (Model Context Protocol) integration adapter

## Future Exploration

- Hardware security module (HSM) integration for credential storage
- Secure enclaves (SGX/TrustZone) for credential proxy execution
- Verifiable computation proofs (prove the proxy executed what it claimed without revealing the credential)
- Cross-chain audit anchoring (periodic hash commitments to a public blockchain for independent verifiability)
