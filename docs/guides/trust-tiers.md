# Trust Tiers

TRUST Protocol uses five graduated levels of access. Trust evolves through demonstrated behavior, not administrative fiat.

## The Five Tiers

| Tier | Token Duration | Max Credentials | Credential Modes | Human Approval | Description |
|------|---------------|-----------------|------------------|----------------|-------------|
| **NOVICE** | 1 hour | 1 | execute | No | New and untested agents. Minimal access, short-lived tokens. First contact. |
| **COMPANION** | 4 hours | 5 | execute | No | Proven reliable across several interactions. Expanded access. |
| **PARTNER** | 8 hours | 20 | execute, proxy_value | No | Deep collaboration. Can request single-use tokens for raw credential values. |
| **GUARDIAN** | 12 hours | Unlimited | execute, proxy_value | No | Infrastructure-level agents. Stewards of the system. |
| **SACRED** | 24 hours | Unlimited | execute, proxy_value | **Yes** | Highest trust. Cannot be auto-assigned. Each session is deliberate. |

## Credential Modes

- **execute** -- Agent provides a request template with `{{CREDENTIAL}}` placeholders. The server injects the real value and executes the request. The agent never sees the credential.
- **proxy_value** -- Agent can request a single-use, 60-second token to exchange for the raw credential value. Only available at PARTNER tier and above.

## How Trust Evolves

### Promotion

An admin promotes an agent after observing reliable behavior:

```bash
curl -X PATCH http://localhost:9500/v1/agents/{agent_id}/trust-level \
  -H "X-Admin-Key: YOUR_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"trust_tier": "COMPANION"}'
```

### Behavioral Gating

Token renewal is conditioned on behavior scores. An agent with declining scores (error spikes, unusual patterns) may be denied renewal:

- The agent submits metrics (API calls, errors, response times)
- The server computes a behavior score
- When the agent tries to renew its token, the score is checked against tier thresholds
- A low score results in renewal denial

### SACRED Tier

The highest tier requires explicit human approval. It cannot be auto-assigned through behavior alone. This represents the deepest level of trust -- deliberately granted by a human for agents that have earned it.

## Per-Credential Minimum Trust

Each stored credential has a `minimum_trust` setting:

```json
{
  "name": "stripe_key",
  "credential_data": {"value": "sk_live_..."},
  "minimum_trust": "GUARDIAN"
}
```

An agent at PARTNER tier trying to access a GUARDIAN-level credential will receive a 403 response, even though PARTNER agents have broad access in other respects.

## The Naming Convention

The tier names -- NOVICE, COMPANION, PARTNER, GUARDIAN, SACRED -- are deliberate. They describe the depth of a relationship, not a security clearance level. A NOVICE is not "low security"; it is an agent you have not yet learned to trust. A SACRED agent is not "high privilege"; it is one whose trust was earned through sustained reliability and explicitly granted by a human.

This framing matters. Security systems that treat access as purely mechanical ("level 1, level 2, level 3") invite gaming. Systems that treat access as relational ("prove yourself, and the relationship deepens") encourage genuine accountability.
