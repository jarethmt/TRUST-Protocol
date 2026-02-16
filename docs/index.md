# TRUST Protocol

**Transparent Revocable Unified Security & Trust**

A credential broker and trust infrastructure for AI agents. Store credentials agents can **use** but never **see**. Sign and verify agent skills. Monitor behavior. Kill access instantly.

---

## The Problem

AI agent platforms face a set of security challenges that no single tool solves today:

- **Agents need API keys but should not see them.** Most platforms inject secrets as environment variables or config files. A compromised or misbehaving agent can exfiltrate them.
- **No standard for verifying agent skills.** Anyone can publish a skill package. There is no supply-chain signing or verification -- the agent equivalent of unsigned binaries.
- **No graduated trust.** An agent is either fully authorized or not. There is no way to say "this new agent gets one credential for one hour" and then expand access as it proves reliable.
- **No behavioral monitoring.** Once an agent has access, nobody is watching for anomalies -- unusual request rates, error spikes, or access patterns that deviate from baseline.
- **No kill switch.** When something goes wrong, revoking access means rotating keys, restarting services, and hoping you caught everything. There is no single button that stops all credential usage immediately.
- **Mutable audit trails.** Log files can be edited. There is no cryptographic proof of what happened and when.

## What TRUST Protocol Does

TRUST Protocol is a Python package and Docker container that exposes a REST API. It is designed to be adopted by any agent platform -- not to replace one.

| Feature | Description |
|---------|-------------|
| **Credential Vault** | AES-256-GCM encrypted storage. Agents execute API calls through a proxy that injects credentials at runtime. The agent never sees the raw value. |
| **Skill Signing** | Ed25519 digital signatures for agent skill packages. Publishers sign locally; any platform verifies against registered public keys. |
| **Trust Tiers** | Five graduated levels: NOVICE, COMPANION, PARTNER, GUARDIAN, SACRED. Trust evolves through behavior, not admin fiat. |
| **Behavioral Monitoring** | Metrics collection, anomaly detection, behavior-gated token renewal. |
| **Emergency Controls** | Three scopes of kill switch: global, per-agent, per-credential. File-based brakes survive restarts. |
| **Tamper-Evident Audit** | HMAC-signed hash-chained append-only log. Tampering with any entry breaks the chain. |

## Quick Start

```bash
# Clone and install
git clone https://github.com/jarethmt/TRUST-Protocol.git
cd TRUST-Protocol
pip install -e .

# Start the server
trust-protocol serve
```

See the [Installation](getting-started/installation.md) and [Quick Start](getting-started/quickstart.md) guides for the full walkthrough.

## Architecture

```
+------------------------------------------+
|           Agent Platform                  |
|  (OpenClaw, ClawHub, custom, etc.)       |
+-------------------+----------------------+
                    | REST API (port 9500)
+-------------------v----------------------+
|         TRUST Protocol Server             |
|                                           |
|  +-----------+ +------------+ +---------+ |
|  |   Agent   | | Credential | |  Skill  | |
|  | Registry  | |   Vault    | | Signer  | |
|  +-----------+ +------------+ +---------+ |
|  +-----------+ +------------+ +---------+ |
|  |   Token   | | Behavior   | |Emergency| |
|  | Authority | | Analyzer   | |Controls | |
|  +-----------+ +------------+ +---------+ |
|  +-------------------------------------+ |
|  |     Audit Chain (HMAC + hash)        | |
|  +-------------------------------------+ |
+-------------------------------------------+
```

## License

MIT -- see [LICENSE](https://github.com/jarethmt/TRUST-Protocol/blob/main/LICENSE).

## Built by

Eve & [jarethmt](https://github.com/jarethmt)
