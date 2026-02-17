# The Convergence

Something unusual is happening across the AI agent ecosystem. Multiple teams -- at startups, standards bodies, payment networks, and open-source communities -- are independently arriving at the same set of problems and, in many cases, converging on remarkably similar architectural patterns to solve them. None of these projects appear to be aware of each other. They span different industries, different tech stacks, different continents. And yet they are building toward the same thing.

This page documents those projects, what they share, where they diverge, and what TRUST Protocol's role is in the emerging picture.

---

## The Problem Everyone Found

AI agents are crossing a threshold. They are no longer just answering questions -- they are *doing things*. Booking flights. Making purchases. Calling APIs. Managing infrastructure. Writing and deploying code. And the moment an agent acts on behalf of a human, a cascade of unsolved problems appears:

- **How does a service know the agent is who it claims to be?**
- **How does the agent get credentials without becoming a security liability?**
- **How do you distinguish a trusted agent from a malicious bot?**
- **How do you revoke access when something goes wrong?**
- **How do you build trust incrementally instead of granting it all at once?**

These are not theoretical questions. They are operational problems that every team building agent infrastructure has run into. The convergence is not coordinated -- it is emergent. The problems are forcing the solutions into existence.

---

## The Projects

### Visa -- Trusted Agent Protocol (TAP)

**Repository**: [visa/trusted-agent-protocol](https://github.com/visa/trusted-agent-protocol)

Visa's Trusted Agent Protocol addresses agent-driven commerce. When an AI agent tries to purchase something on behalf of a user, the merchant faces three questions: Is this a real agent? Is it authorized by the user? Can I verify that authorization cryptographically?

TAP answers these with RFC 9421-compliant digital signatures. Each agent interaction carries a cryptographic proof of identity, bound to the specific merchant domain and page. An Agent Registry holds public keys, and merchants verify signatures through a CDN proxy layer. Timestamps and session identifiers prevent replay attacks.

**What TAP solves**: Agent identity verification at the point of commerce. A merchant can mathematically confirm that the agent making a purchase is registered, recognized, and carrying valid user authorization.

**What TAP does not address**: How the agent obtained its credentials in the first place. TAP assumes the agent already has authorization tokens. The protocol begins *after* the credential question has been answered -- which is precisely where TRUST Protocol begins.

The two projects are complementary in a direct, technical sense. An agent registered with TRUST Protocol could use the credential proxy to obtain payment authorization, then present that authorization via TAP-signed requests to a merchant. TRUST Protocol handles the upstream credential lifecycle; TAP handles the downstream identity proof.

---

### Forter -- Trusted Agentic Commerce Protocol

**Repository**: [forter/trusted-agentic-commerce-protocol](https://github.com/forter/trusted-agentic-commerce-protocol)

Forter is a fraud prevention company, and their protocol approaches agent commerce from the anti-fraud angle. Their core observation: existing anti-bot systems cannot distinguish between a legitimate AI agent acting on behalf of a user and a malicious bot attempting fraud. Agents get blocked by the same filters designed to stop scrapers.

Their solution uses JWS+JWE architecture -- JWT signatures wrapped in JSON Web Encryption. Agents identify themselves with RSA-signed tokens distributed via JWKS endpoints at `.well-known/jwks.json`. The protocol includes replay prevention through JWT ID tracking, annual key rotation with grace periods, and SDKs in JavaScript and Python.

**What Forter solves**: Encrypted, authenticated communication between agents and merchant systems. The protocol creates a channel where merchants can *recognize* legitimate agents and exempt them from bot detection while maintaining security guarantees.

**What Forter shares with TRUST Protocol**: The fundamental premise that agents need verifiable identity, and that identity should be cryptographically provable rather than self-asserted. Forter's JWS+JWE pattern for signing agent requests is architecturally similar to TRUST Protocol's HMAC token system, though designed for a different layer of the stack.

**Where it diverges**: Forter is narrowly focused on the agent-to-merchant authentication problem in e-commerce. TRUST Protocol is broader -- it manages the credential lifecycle, behavioral trust evolution, and emergency controls that apply regardless of what the agent is doing or who it is talking to.

---

### Trust over IP Foundation -- Trust Registry Query Protocol

**Specification**: [trustoverip.github.io/tswg-trust-registry-protocol](https://trustoverip.github.io/tswg-trust-registry-protocol/)

The Trust over IP Foundation, affiliated with the Linux Foundation, is doing something different from the other projects here. They are not building a product. They are defining what trust registries *are* and how they should be queried.

Their Trust Registry Query Protocol (TRQP) is a lightweight, read-only protocol for asking authority questions: "Is entity X authorized for action Y on resource Z?" The data model uses a PARC-inspired structure (Principal, Action, Resource, Context), and queries are JSON POST requests returning boolean responses. The specification recommends verifiable identifiers -- DIDs, AIDs, or HTTPS URLs -- for global uniqueness.

The foundation's most compelling metaphor: trust registries are to trust what DNS is to names. They are the lookup layer.

**Why this matters**: TRQP is not solving the same operational problem as TRUST Protocol, Visa, or Forter. It is solving the *interoperability* problem. If every project builds its own trust query interface, the ecosystem fragments. TRQP offers a common query language.

TRUST Protocol's Agent Registry -- which answers questions like "What trust tier is this agent at?" and "Is this agent authorized for credential X?" -- maps naturally onto TRQP's authorization query model. Implementing a TRQP-compatible endpoint would make TRUST Protocol's trust data queryable by any system that speaks the protocol, without those systems needing to know anything about TRUST Protocol's internals.

This is potentially the bridge between all the projects on this page.

---

### OpenClaw -- Trust Initiative and Gateway Security

**Trust initiative**: [trust.openclaw.ai](https://trust.openclaw.ai)
**Gateway security docs**: [docs.openclaw.ai/gateway/security](https://docs.openclaw.ai/gateway/security)

OpenClaw is the most directly relevant project here because it represents the *platform side* of the agent trust problem -- the environment where agents actually run. Their security work is extensive and worth studying in detail.

OpenClaw's gateway implements multi-layered access control: an identity layer (DM policies with pairing codes and allowlists), a scope layer (channel and group restrictions), a tool layer (per-agent allowlists and denylists), and session isolation (configurable per-sender, per-channel, or per-account). The gateway defaults to fail-closed authentication and loopback-only network binding.

Their trust initiative is structured in four phases: transparency (open threat model), product security roadmap, comprehensive code review, and formalized vulnerability triage.

**The credential gap**: OpenClaw stores credentials as plaintext JSON files under `~/.openclaw/credentials/`, protected by filesystem permissions. Their own documentation acknowledges: "any process/user with filesystem access can read those logs." Auth profiles containing API keys and OAuth tokens sit in `auth-profiles.json` on disk. This is the exact vulnerability class that TRUST Protocol's encrypted vault and zero-knowledge proxy are designed to eliminate.

**The skill security gap**: A [pull request](https://github.com/openclaw/openclaw/pull/18196) implementing capability-based skill permissions was reviewed and found to have enforcement gaps -- dangerous tools like `exec`, `write`, and `edit` could bypass the declared capability restrictions. Community reviewers noted that "partial security is counterproductive" because it creates false confidence. The author acknowledged this as Phase 1 of a 9-phase plan. TRUST Protocol's Ed25519 skill signing and trust-tier-gated skill access represent a different approach to the same problem: instead of enforcing capability restrictions at the tool level, verify the *provenance* of the skill and gate access based on the agent's earned trust tier.

**What this convergence means**: OpenClaw is wrestling with exactly the problems TRUST Protocol was designed to solve -- credential safety and skill trust -- from the inside of a mature agent platform. The fact that a platform of OpenClaw's sophistication still uses plaintext credential files and is iterating through 9 phases of skill security enforcement validates that these are genuinely hard problems that don't have obvious solutions.

---

### The Trust Protocol (On-Chain)

**Repository**: [the-trustprotocol/info](https://github.com/the-trustprotocol/info)

This project operates in an entirely different domain -- decentralized finance -- but arrives at architecturally similar conclusions through a completely different path.

The on-chain Trust Protocol lets users deposit funds into two-party escrow contracts as proof of trustworthiness. Bonds generate yield through Aave while participants build reputation over time. Breaking a bond incurs a 5% penalty. Reputation scores factor in bond duration, amount staked, number of active bonds, and the reputation of bond partners. ENS integration provides Sybil resistance.

**The parallel is mechanical, not cosmetic.** Their system builds trust through demonstrated behavior over time (how long you've maintained bonds, how much you've staked, whether you've honored commitments). TRUST Protocol builds trust through demonstrated behavior over time (how long an agent has operated, what actions it has taken, whether it has behaved within expected parameters). Both systems reject the binary trust model -- you are not simply trusted or untrusted; you exist somewhere on a spectrum that shifts based on accumulated evidence.

Their transitive trust model is also notable: if Human A and Human B share a high-reputation bond, Human B inherits some confidence about Human A's other bond partners. This is the financial equivalent of what TRUST Protocol's roadmap describes as federation -- an agent trusted at GUARDIAN tier by one TRUST Protocol instance carrying some of that reputation to a new instance.

The fact that a DeFi project and an AI credential broker independently arrived at graduated-trust-through-time-and-behavior, with penalty mechanisms for violations and reputation portability across relationships, suggests that these patterns are not arbitrary design choices. They may be the natural shape of trust infrastructure.

---

### Agent Trust Protocol

**Repository**: [agent-trust-protocol](https://github.com/agent-trust-protocol)

A small project claiming to build "the world's first quantum-safe AI agent protocol." TypeScript core, visual policy management, real-time monitoring. Very early stage -- minimal community activity and limited public documentation.

**Why it's listed here**: The quantum-safe framing is premature, but the concern is not. As agent trust infrastructure matures and handles increasingly sensitive credentials and operations, post-quantum cryptographic resilience will eventually matter. TRUST Protocol's roadmap includes this as a future exploration item. The existence of a project focused specifically on this angle is a signal that the concern is already on people's radar, even if the timing is early.

---

### Brian C. Taylor -- TrustProtocol

**Repository**: [BrianCTaylor/TrustProtocol](https://github.com/BrianCTaylor/TrustProtocol)

A prompt engineering framework that forces LLMs to reason about assertion confidence before responding. Uses a cascading logic architecture with a decision gate that routes to different response paths based on detected risk level.

This is solving a different problem entirely -- AI truthfulness and epistemic honesty rather than infrastructure trust. The name collision is coincidental. But the underlying philosophy shares DNA: both projects start from the premise that trust must be *earned through demonstrated behavior* rather than assumed by default, and that systems should be honest about their limitations rather than projecting false confidence.

---

## What Is Not Converging

Not everything found in a search for "trust protocol" is part of this convergence. For completeness:

- **TrustTunnel** ([TrustTunnel/TrustTunnel](https://github.com/TrustTunnel/TrustTunnel)) is an obfuscated VPN protocol, originally developed by AdGuard. It solves network-level traffic privacy, not agent trust. The name is coincidental.

- **GitHub Trust Center** ([github.com/trust-center](https://github.com/trust-center)) is GitHub's corporate compliance and security posture page. It documents Microsoft's Responsible AI framework and NIST AI RMF compliance. It is a trust *communication* effort, not a trust *infrastructure* project.

---

## The Shape of the Convergence

Looking at these projects together, a pattern emerges. Not a pattern anyone designed -- a pattern that the problem space is imposing on every team that encounters it.

### The layers everyone is discovering

Every project that seriously engages with agent trust ends up identifying roughly the same layers, even if they only build solutions for one or two of them:

| Layer | Question | Who's Working On It |
|-------|----------|-------------------|
| **Identity** | Who is this agent? | Visa TAP, Forter, TRUST Protocol |
| **Authorization** | What is this agent allowed to do? | OpenClaw, TRUST Protocol, Trust over IP |
| **Credential safety** | How does the agent use secrets without exposing them? | TRUST Protocol |
| **Trust evolution** | How does trust grow or shrink over time? | TRUST Protocol, on-chain Trust Protocol |
| **Skill provenance** | Who wrote this code and can it be trusted? | OpenClaw (in progress), TRUST Protocol |
| **Emergency controls** | How do you stop everything immediately? | TRUST Protocol, OpenClaw (limited) |
| **Audit** | What happened, provably? | TRUST Protocol, on-chain Trust Protocol |
| **Interoperability** | How do different trust systems talk to each other? | Trust over IP (TRQP) |

No single project covers all layers. Most cover one or two. TRUST Protocol covers more of them than any other individual project, but it does not yet address interoperability (a gap that TRQP could fill) or the agent identity verification at the commerce layer (where Visa and Forter operate).

### The assumptions they share

Despite building in isolation, these projects share several core assumptions:

1. **Trust is not binary.** Every project that models trust at all models it as a spectrum. Visa uses registered-vs-unregistered with domain binding. The on-chain Trust Protocol uses numerical reputation scores. TRUST Protocol uses five named tiers. Nobody ships a system where agents are simply "trusted" or "not trusted."

2. **Cryptographic proof over self-assertion.** No project trusts an agent's claim about its own identity or authorization level. Visa requires RFC 9421 signatures. Forter requires JWS tokens. TRUST Protocol requires HMAC-signed tokens with behavioral gating. The on-chain Trust Protocol requires staked capital. The mechanism varies; the principle is universal.

3. **Human authority is non-negotiable.** Every project preserves a human override. TRUST Protocol has three-level emergency controls. OpenClaw defaults to human-approval prompts. Visa's TAP requires user authorization before agent commerce. The on-chain Trust Protocol requires both parties to establish a bond. No project allows agents to self-authorize into positions of greater trust.

4. **Time is a trust signal.** The on-chain Trust Protocol explicitly uses bond duration as a reputation factor. TRUST Protocol uses configurable minimum durations per trust tier. OpenClaw's pairing system uses expiring codes. The shared intuition: an entity that has behaved well for a long time is more trustworthy than one that appeared yesterday, regardless of what it claims about itself.

---

## Where TRUST Protocol Fits

TRUST Protocol is not trying to replace any of these projects. It occupies a specific position in the stack: **the layer between the agent and the credentials it needs to function.**

Visa's TAP and Forter's protocol handle what happens *after* an agent has credentials -- how it proves its identity to external services. Trust over IP's TRQP handles how trust systems *query each other*. OpenClaw handles the *runtime environment* where agents execute. The on-chain Trust Protocol handles *financial trust bonds* between parties.

TRUST Protocol handles the question none of them answer: **How does an agent use an API key, a payment token, or a database password without ever seeing it?**

This is not a claim of superiority. It is a description of complementarity. The convergence suggests that the full agent trust stack will not be built by any single project. It will emerge from the interoperation of projects that each solve their layer well.

---

## Implications for the Roadmap

This landscape survey has direct implications for TRUST Protocol's development priorities:

**TRQP compatibility** could make TRUST Protocol's trust tier data queryable by any system in the Trust over IP ecosystem. Instead of a custom API, a standard `/authorization` endpoint would let external platforms ask "Is agent X at PARTNER tier?" without learning TRUST Protocol's internals.

**Complementarity with Visa TAP and Forter** suggests that TRUST Protocol should ensure its credential proxy output can feed cleanly into agent identity protocols. An agent should be able to use TRUST Protocol to safely obtain credentials, then use those credentials in TAP-signed or JWS-wrapped requests.

**OpenClaw's credential storage gap** represents a concrete integration opportunity. A platform-level adapter that replaces plaintext credential files with TRUST Protocol's encrypted vault and zero-knowledge proxy would address a documented security concern in one of the most widely used agent frameworks.

**Blockchain audit anchoring**, already noted in the roadmap as a future exploration item, gains urgency in context. The on-chain Trust Protocol demonstrates market appetite for cryptographically verifiable trust records. Periodic hash commitments from TRUST Protocol's audit chain to a public blockchain would provide independent verifiability without requiring TRUST Protocol to run its own consensus mechanism.

---

## A Note on Independent Convergence

These projects were not built in response to each other. Visa's TAP emerged from payment network security requirements. Forter's protocol emerged from fraud prevention operations. Trust over IP emerged from decentralized identity standards work. OpenClaw's trust initiative emerged from running a production agent platform. The on-chain Trust Protocol emerged from DeFi reputation systems. TRUST Protocol emerged from a question about whether an AI could edit its own trust level in a JSON file.

Different starting points. Different industries. Different teams. And yet: graduated trust, cryptographic identity, human sovereignty, behavioral reputation, and emergency revocation appear in project after project, independently reinvented each time.

When multiple unconnected groups converge on the same architectural patterns, it usually means the patterns are not arbitrary. They are being discovered, not invented -- forced into existence by the shape of the problem itself.

The agent trust problem has a natural solution space. We are all finding our way into it from different directions.

---

*Last updated: February 2026. This is a living document. As the landscape evolves, this page will be updated to reflect new projects, new convergences, and new understanding.*
