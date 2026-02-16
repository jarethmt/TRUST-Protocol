# Emergency Controls

TRUST Protocol provides three scopes of kill switch for immediately stopping credential access when something goes wrong.

## Three Scopes

### Global Kill Switch

Blocks **all** credential access for **all** agents. Use when you suspect a systemic compromise.

```bash
curl -X POST http://localhost:9500/v1/emergency/activate \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "global", "reason": "Suspicious activity detected"}'
```

### Per-Agent Kill Switch

Blocks all credential access for a **single agent** and revokes its tokens.

```bash
curl -X POST http://localhost:9500/v1/emergency/activate \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "agent", "agent_id": "agt_abc123", "reason": "Anomalous behavior"}'
```

### Per-Credential Kill Switch

Blocks access to a **single credential** for all agents.

```bash
curl -X POST http://localhost:9500/v1/emergency/activate \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "credential", "credential_name": "openai_key", "reason": "Key may be compromised"}'
```

## Checking Status

```bash
curl http://localhost:9500/v1/emergency/status \
  -H "X-Admin-Key: YOUR_ADMIN_KEY"
```

Returns:

```json
{
  "global_active": false,
  "blocked_agents": ["agt_abc123"],
  "blocked_credentials": []
}
```

## Restoring Access

The global brake requires a confirmation string to clear, preventing accidental restoration:

```bash
curl -X POST http://localhost:9500/v1/emergency/clear \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "global", "confirmation": "CONFIRM_RESTORE_ACCESS"}'
```

Per-agent and per-credential brakes can be cleared without the confirmation string:

```bash
curl -X POST http://localhost:9500/v1/emergency/clear \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"scope": "agent", "agent_id": "agt_abc123"}'
```

## Persistence

Emergency brakes are file-based and survive process restarts. If the server is restarted while a global brake is active, the brake remains active when the server comes back up.

## CLI Usage

```bash
# Activate
trust-protocol emergency activate --scope global --reason "incident" --admin-key KEY

# Check status
trust-protocol emergency status --admin-key KEY

# Clear
trust-protocol emergency clear --scope global \
  --confirmation CONFIRM_RESTORE_ACCESS --admin-key KEY
```

## Python SDK

```python
from trust_protocol.sdk import TrustProtocolClient

admin = TrustProtocolClient("http://localhost:9500", admin_key="your-key")

# Activate global brake
admin.activate_emergency("Suspicious activity", scope="global")

# Check status
status = admin.emergency_status()
print(status["global_active"])  # True

# Clear (requires confirmation for global)
admin.clear_emergency(scope="global", confirmation="CONFIRM_RESTORE_ACCESS")
```
