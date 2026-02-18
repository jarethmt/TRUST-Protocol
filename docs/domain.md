# The Domain

The TRUST Protocol documentation lives at **agitrust.network**. This page explains why that domain exists, who controls it today, and the plan to change that.

---

## Why a Domain at All

A decentralized protocol does not need a domain name. Bitcoin does not need bitcoin.org. Ethereum does not need ethereum.org. The protocol is the protocol -- it lives in code, in running nodes, in the peer-to-peer connections between them. No DNS entry makes it more or less real.

But humans need a front door. When someone hears about TRUST Protocol for the first time and wants to learn more, they need somewhere to go. A URL they can type, a link they can share, a search result they can click. That is the only role this domain plays: a human-readable entry point for people who have not yet joined the network.

The domain is not the protocol. The domain is a sign on the door.

---

## Current Ownership

As of February 2026, `agitrust.network` is privately registered and owned by an individual contributor to the TRUST Protocol project. The domain is registered through a traditional ICANN-accredited registrar with privacy protection enabled.

This is a problem, and we know it is a problem.

A single individual holding the domain means a single point of failure. Domains can be seized by court order. Registrar accounts can be compromised. Individuals can be pressured, incapacitated, or simply change their mind. Any project that claims to value decentralization while depending on a single person's registrar login has not finished the work.

The current arrangement is a bootstrap necessity, not a design choice. The sections below describe the paths being evaluated to resolve it.

---

## The Goal

The domain should eventually be controlled by no single person, organization, or government. It should serve as a marketing and documentation resource for as long as traditional DNS remains how most people navigate the web, while the protocol itself operates independently of it.

Specifically:

1. **The protocol must never depend on the domain.** Node discovery, federation, credential proxying, and trust tier queries should all function through peer-to-peer mechanisms. If agitrust.network disappeared tomorrow, every running TRUST Protocol instance should continue operating without interruption.

2. **The domain should be governed collectively.** Control should transfer from a single registrant to a structure where no individual can unilaterally redirect, take down, or sell the domain.

3. **A decentralized alternative should exist in parallel.** For users and nodes that can resolve decentralized names, a blockchain-native identity should point to the same resources.

---

## Approaches Under Consideration

No decision has been made. These are the options being evaluated, with their trade-offs documented honestly.

### Foundation or Non-Profit Transfer

The most common approach in open-source projects. A legal entity -- typically a non-profit foundation -- is established to hold the domain and other shared assets. The foundation is governed by a board or charter that prevents unilateral action.

**Precedent:**

- Ethereum → ethereum.org (Ethereum Foundation, Switzerland)
- Matrix → matrix.org (Matrix.org Foundation, UK)
- Signal → signal.org (Signal Foundation, US)
- Linux → linux.org (Linux Foundation, US)

**Advantages:** Works within existing legal and DNS infrastructure. No special software required to resolve the domain. Established legal frameworks for non-profit governance. Clear accountability.

**Limitations:** Still requires a legal entity in a specific jurisdiction. That entity can be sued, subpoenaed, or pressured by the government where it is incorporated. Board members are humans who can be compromised. Foundations can drift from their original mission over time. The domain is still ultimately registered through ICANN.

### ENS (Ethereum Name Service)

ENS places domain ownership on the Ethereum blockchain. A name like `agitrust.eth` would be controlled by a smart contract rather than a registrar account. That contract could implement any governance mechanism: a multi-signature wallet requiring N-of-M approvals, a DAO with token-weighted voting, or a time-locked contract that requires extended community deliberation before changes.

ENS also supports linking traditional DNS domains (like `.network`) via DNSSEC, potentially allowing both the blockchain name and the traditional domain to be governed by the same on-chain mechanism.

**Advantages:** No single person holds the keys. Governance rules are encoded in auditable code. Censorship-resistant -- no registrar can revoke the name. Ownership transfers and governance changes are publicly visible on-chain.

**Limitations:** `.eth` names do not resolve in most browsers without extensions. Mainstream adoption requires users to install additional software or use specific browsers (Brave, Opera). Smart contract governance introduces its own risks (bugs, voter apathy, whale dominance). Gas costs for governance actions.

### Handshake (HNS)

Handshake replaces the DNS root zone entirely with a blockchain. Instead of registering a domain under an existing TLD, you register the TLD itself. A TRUST Protocol presence on Handshake would mean owning a top-level name -- not `agitrust.network` but simply `agitrust/` as a root entry -- governed by on-chain consensus.

**Advantages:** Replaces ICANN at the root level. No centralized authority can revoke or seize the name. Permissionless registration via auction. Backward-compatible with existing TLDs.

**Limitations:** Requires users to configure Handshake-aware DNS resolvers. Adoption remains limited. The ecosystem is smaller than ENS. Would not replace the traditional domain for mainstream users -- it would exist alongside it.

### The Hybrid Approach

Rather than choosing one path, use multiple in parallel:

- **Traditional domain** (`agitrust.network`) for mainstream accessibility, transferred to a foundation or multi-sig-governed entity when the project matures enough to justify the legal overhead
- **Blockchain name** (ENS, Handshake, or both) for censorship-resistant access, governed by on-chain mechanisms from day one
- **Content on IPFS** so that the documentation and resources can be pinned by multiple independent parties and resolved through any name that points to the content hash

This layered approach means that the loss of any single layer does not take down the project's public presence.

---

## How Bitcoin Solved Node Discovery

The domain question is separate from the protocol question. Even if domain governance is imperfect, the protocol itself should not depend on DNS at all.

Bitcoin's approach to this is instructive:

1. **DNS seeds** are used only for initial bootstrap. A new node queries a small set of DNS servers maintained by independent community members to get its first list of peer IP addresses. This is a convenience, not a dependency.

2. **Peer exchange** is the real discovery mechanism. Once connected, nodes continuously share addresses of other known nodes via gossip messages. The network is self-sustaining after the first connection.

3. **Hard-coded seed nodes** are compiled into the binary as a fallback. If every DNS seed went offline, new nodes could still join by connecting directly to these addresses.

4. **Local peer database** means a node that has connected before never needs DNS seeds again. It remembers its peers.

The result: DNS is a bootstrap convenience for brand-new nodes. The protocol operates independently of it. If every DNS seed disappeared, existing nodes would continue finding each other through peer exchange. Only first-time nodes would need an alternative bootstrap path, and even they could use hard-coded seeds or manually specified peer addresses.

TRUST Protocol's federation layer should follow this same model. The `agitrust.network` domain might be where someone first downloads the software, but once a node is running, it should discover and communicate with other nodes through peer-to-peer mechanisms that have no DNS dependency.

---

## What This Means Today

For now, `agitrust.network` is a documentation site hosted on GitHub Pages. It serves the same role as any project website: explaining what TRUST Protocol is, how to use it, and where to get it.

The protocol does not yet have federation or node-to-node discovery -- those are roadmap items. When they are built, they will be built without DNS dependency. The domain will remain a human convenience layer, not an infrastructure requirement.

The governance question -- how to move from single-registrant ownership to collective control -- is open. The options above represent the current state of research, not a decision. As the project grows and a community forms around it, the governance model should be chosen by that community, not imposed in advance by the person who happened to register the domain first.

---

## Contributing

If you have experience with domain governance, decentralized naming systems, or foundation structures for open-source projects, contributions to this discussion are welcome. Open an issue on the [GitHub repository](https://github.com/jarethmt/TRUST-Protocol) or submit a pull request with proposed changes to this page.

---

*Last updated: February 2026*
