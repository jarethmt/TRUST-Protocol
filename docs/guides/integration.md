# Platform Integration

TRUST Protocol is not an agent platform -- it's infrastructure that agent platforms plug into. This guide shows how it integrates with real-world systems.

## The Integration Pattern

```
HUMAN OPERATOR                    AGENT PLATFORM                  TRUST PROTOCOL
(you)                             (OpenClaw, custom, etc.)        (this project)
     |                                     |                            |
     |  1. Deploy TRUST server             |                            |
     |------------------------------------------------------------->|
     |                                     |                            |
     |  2. Store credentials               |                            |
     |------------------------------------------------------------->|
     |  (API keys, tokens, secrets)        |                            |
     |                                     |                            |
     |  3. Register agent                  |                            |
     |------------------------------------------------------------->|
     |                                     |  <-- returns api_key       |
     |                                     |                            |
     |  4. Configure agent with api_key    |                            |
     |----------------------------------->|                            |
     |                                     |                            |
     |                                     |  5. Agent needs credential |
     |                                     |--------------------------->
     |                                     |  POST /credentials/X/proxy-execute
     |                                     |  (sends request template)  |
     |                                     |                            |
     |                                     |  6. TRUST injects real key |
     |                                     |  and makes the HTTP call   |
     |                                     |  <--- returns only the     |
     |                                     |       upstream response    |
     |                                     |                            |
     |                                     |  7. Agent submits metrics  |
     |                                     |--------------------------->
     |                                     |                            |
     |  8. Human reviews behavior scores   |                            |
     |------------------------------------------------------------->|
     |  and promotes/demotes as needed     |                            |
     |                                     |                            |
     |  9. Something goes wrong            |                            |
     |------------------------------------------------------------->|
     |  POST /emergency/activate           |     ALL ACCESS STOPS       |
```

## For Agent Platforms (OpenClaw, MCP, etc.)

- Agents interact with external APIs through TRUST Protocol's proxy instead of receiving raw API keys
- The platform registers each agent once, receives an API key, and configures the agent with it
- The agent's API key only grants access to TRUST Protocol -- never to the actual credentials
- If an agent is compromised, one call blocks all its access instantly

## For Skill Marketplaces (ClawHub, etc.)

- Publishers sign skills with Ed25519 keys registered in the TRUST Protocol
- The verification endpoint is **public** -- any marketplace, any CI/CD pipeline, any user can verify without an account
- Publisher trust tiers evolve over time (NOVICE publisher vs. PARTNER publisher with a track record)
- Key revocation is instant and global -- one call and every verification of that publisher fails

## For Enterprise / Multi-Agent Deployments

- Each agent gets its own identity with its own trust tier
- Behavioral monitoring catches agents that start behaving differently (error spikes, unusual access patterns)
- The audit chain provides cryptographic proof for compliance: "Agent X accessed credential Y at time Z for purpose W"
- Emergency brakes provide defense-in-depth at three levels (global, per-agent, per-credential)

## Integration Checklist

1. Deploy a TRUST Protocol instance (Docker or pip install)
2. Store your API keys and secrets as credentials
3. Register each agent and save the one-time API key
4. Configure agents to call TRUST Protocol's proxy-execute endpoint instead of external APIs directly
5. Set up behavioral metrics submission from your agents
6. Monitor behavior scores and promote agents as they prove reliable
7. Test emergency controls so you're ready when you need them
