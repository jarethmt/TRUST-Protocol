# Brand Identity Guide

This document defines the visual identity of TRUST Protocol. Use it as a reference when creating documentation, presentations, integrations, marketing materials, or any visual asset associated with the project.

---

## Brand Essence

TRUST Protocol sits at the intersection of security engineering and philosophy. The brand should reflect both: technically credible, but not afraid of depth. Security and trust are esoteric by nature -- the visual identity leans into this rather than sanitizing it away.

**Brand attributes:**

- **Deliberate** -- Nothing is accidental. Every incomplete circle, every color shift, every hidden element exists for a reason.
- **Earned** -- Warmth, access, and trust are not given freely. They are demonstrated through behavior over time.
- **Human-anchored** -- No matter how sophisticated the system, a human completes the circuit.
- **Honest** -- We document what we don't do well (known gaps) alongside what we do. The brand reflects transparency, not false confidence.

---

## Logo

### The Five Rings

The primary logo mark is five concentric arcs of ascending completeness, representing the five trust tiers. Source files live in `assets/`.

| File | Format | Use |
|------|--------|-----|
| `assets/logo.svg` | Vector SVG | Source of truth. Use for editing and re-rendering. |
| `assets/logo.png` | 1024x1024 PNG | README, documentation, social previews. |

### Logo Elements

**The arcs**: Five concentric arcs, each longer than the last, all opening at the crown (12 o'clock). They represent the trust tiers: NOVICE (innermost, shortest) through SACRED (outermost, nearly complete). None fully closes.

**The eye/fingerprint**: At the crown gap of the outermost ring. Originally designed as a fingerprint (concentric ridges), it naturally formed an eye shape -- representing the agent that sees everything except the credential at the center. Both readings are intentional.

**The hidden keyhole**: At the dead center of the rings, at 8% opacity. Only visible on close inspection of the full-size render. This is what the entire system protects.

**The typography**: "TRUST" in light weight with wide letter-spacing. "PROTOCOL" smaller and muted beneath. The text labels what the viewer has already started thinking about.

### Clear Space

Maintain clear space around the logo mark equal to at least the radius of the innermost ring. The logo should breathe -- it is about space and incompleteness.

### Logo Don'ts

- Don't close any of the rings
- Don't remove the gap at the crown
- Don't add elements inside the rings (the center void is intentional)
- Don't rotate the logo (the gap must remain at the top)
- Don't use the logo on busy or patterned backgrounds
- Don't add drop shadows, bevels, or 3D effects beyond the existing glow

---

## Color Palette

### Primary Palette

The core palette progresses from cool to warm, mirroring the trust journey.

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Slate** | `#64748b` | 100, 116, 139 | NOVICE tier, muted/secondary text, inactive states |
| **Steel Blue** | `#5b8dc9` | 91, 141, 201 | COMPANION tier, secondary interactive elements |
| **Bright Blue** | `#4a7af7` | 74, 122, 247 | PARTNER tier, primary interactive elements, links |
| **Amber** | `#c98b4a` | 201, 139, 74 | GUARDIAN tier, warm accents, important states |
| **Gold** | `#dba843` | 219, 168, 67 | SACRED tier, highest emphasis, human elements |

The progression from cool to warm is not decorative. It reflects the core philosophy: trust begins cold and uncertain, and warms through demonstrated behavior. When using tier colors in UI or documentation, respect this progression.

### Accent Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Fingerprint Gold** | `#f5d86a` | 245, 216, 106 | Human-element highlights, the eye/fingerprint mark |
| **Warm Gold** | `#f0cc50` | 240, 204, 80 | Glow effects, emphasis on human agency |
| **Soft Amber** | `#e8c040` | 232, 192, 64 | Secondary warm accents |

### Background Colors

| Name | Hex | RGB | Usage |
|------|-----|-----|-------|
| **Deep Navy** | `#060a14` | 6, 10, 20 | Darkest background, logo outer edge |
| **Dark Navy** | `#111827` | 17, 24, 39 | Primary dark background, logo center |
| **Ink** | `#0a0f1e` | 10, 15, 30 | Alternative dark background |
| **Charcoal Blue** | `#1a1a2e` | 26, 26, 46 | Documentation site background (dark mode) |
| **Sidebar Dark** | `#14142a` | 20, 20, 42 | Navigation panels |
| **Header Dark** | `#12121f` | 18, 18, 31 | Header bar, footer |

### UI Colors (Documentation Site)

The documentation site uses colors derived exclusively from the primary palette above. No additional UI-specific colors are introduced.

| Role | Source | Hex | Usage |
|------|--------|-----|-------|
| **Primary** | Bright Blue | `#4a7af7` | Navigation highlights, buttons, primary interactive |
| **Accent** | Gold | `#dba843` | Focus indicators, emphasis states |
| **Links** | Steel Blue | `#5b8dc9` | Inline links (dark mode) |
| **Link Hover** | Bright Blue | `#4a7af7` | Link hover state (warms on interaction) |
| **Code Background** | -- | `#16162a` | Code blocks (dark mode) |

### Semantic Colors

| Name | Hex | Usage |
|------|-----|-------|
| **Success** | `#4a7af7` | Verified, unsealed, active states |
| **Warning** | `#c98b4a` | Caution, elevated trust required |
| **Danger** | `#dc4444` | Emergency brake, revocation, sealed |
| **Muted** | `#64748b` | Disabled, inactive, placeholder |
| **Light Text** | `#e2e8f4` | Primary text on dark backgrounds |
| **Muted Text** | `#7888a4` | Secondary text, captions |

---

## Typography

### Logo Typeface

The logo uses a geometric sans-serif at light weight (300) with generous letter-spacing.

**Font stack**: `'Helvetica Neue', 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif`

| Element | Weight | Size | Letter-spacing | Color |
|---------|--------|------|----------------|-------|
| "TRUST" | 300 (Light) | 72px (at 1024px canvas) | 24px | `#e2e8f4` at 92% opacity |
| "PROTOCOL" | 300 (Light) | 28px (at 1024px canvas) | 14px | `#64748b` at 70% opacity |

The wide letter-spacing is essential. It creates breathing room that echoes the gaps in the rings. Do not use tight or default spacing for the wordmark.

### Documentation Typeface

The documentation site inherits Material for MkDocs defaults:

- **Body**: System font stack (Roboto on most systems)
- **Code**: Roboto Mono or system monospace
- **Headings**: Same as body, varied by weight

### Typography Principles

- **Light over bold.** The brand favors light weights and open spacing. Heaviness implies force; lightness implies confidence.
- **Let text breathe.** Generous margins, padding, and line-height. Dense text contradicts the brand's emphasis on deliberate space.
- **Uppercase sparingly.** "TRUST" and "PROTOCOL" are uppercase in the logo. Elsewhere, use sentence case. All-caps body text feels like shouting.

---

## Voice & Tone

### How TRUST Protocol Communicates

**Technical but not sterile.** We describe cryptographic operations precisely, but we also acknowledge the philosophical dimensions of what we're building. "The vault master password is held in process memory only after a human provides it" is a technical statement that carries philosophical weight.

**Honest about limitations.** The Known Gaps page is part of the brand. We document what isn't hardened alongside what is. False confidence is a security liability.

**Relational, not authoritarian.** The tier names -- NOVICE, COMPANION, PARTNER, GUARDIAN, SACRED -- describe relationships, not clearance levels. The documentation should reflect this: trust is earned through behavior, not granted by fiat.

**Deliberately incomplete.** Like the rings in the logo, the project acknowledges that it is not finished. The roadmap is part of the identity. Completeness is not the goal; honest progression is.

### Vocabulary

| Prefer | Avoid |
|--------|-------|
| Trust tier | Permission level |
| Earned | Granted |
| Sealed / Unsealed | Locked / Unlocked |
| Credential proxy | Secret injection |
| Behavior score | Compliance score |
| Emergency brake | Killswitch (in formal docs) |
| Known gaps | Vulnerabilities |
| Human-anchored | Human-controlled |

---

## Iconography & Visual Language

### The Incomplete Circle

The incomplete circle is the foundational visual motif. Use it:

- As a loading/progress indicator (the arc grows as trust grows)
- As a section divider (a thin arc, not a horizontal line)
- As a bullet point alternative (small arcs instead of dots)

The circle must never close. Even at 95% completion, the gap remains. This is the visual representation of the project's philosophy.

### Cool-to-Warm Gradient

When illustrating progression (trust tiers, onboarding flows, behavioral scoring), use the cool-to-warm color progression:

`#64748b` → `#5b8dc9` → `#4a7af7` → `#c98b4a` → `#dba843`

This progression should always flow in one direction: cold to warm, uncertainty to earned trust. Never reverse it.

### Dark-First Design

All primary brand materials should be designed dark-first. The logo was designed for dark backgrounds and loses impact on white. The documentation site defaults to dark mode.

Light mode variants should be available for print and contexts that require it, but dark is the primary expression.

### Glow, Not Shadow

The brand uses soft light emission (glow effects) rather than drop shadows or heavy borders. Elements radiate outward rather than casting downward. This implies transparency and emanation rather than weight and opacity.

---

## Usage Examples

### GitHub README Header

```markdown
<p align="center">
  <img src="assets/logo.png" alt="TRUST Protocol" width="280"/>
</p>
```

Width of 280px is the recommended size for a GitHub README header. The logo is legible at this size while leaving room for the title and description below.

### Social Preview / Open Graph

Use the full 1024x1024 logo PNG as the social preview image. The dark background, centered rings, and typography create a complete composition at any preview crop.

### Favicon

For favicon use, crop to the rings only (no typography). The five arcs remain recognizable at 32x32 and 16x16 with the gold outermost ring providing warmth and the gap at the crown providing the distinctive silhouette.

### Documentation Headers

When creating section header images or diagrams, use the tier colors to indicate the trust level being discussed. Example: a guide about PARTNER-tier features should use `#4a7af7` as the accent color.

---

## File Locations

```
assets/
├── logo.svg              # Vector source (editable)
└── logo.png              # 1024x1024 raster render
docs/
├── brand-identity.md     # This file
├── design-story.md       # The collaborative design process
└── stylesheets/
    └── extra.css         # Documentation site theme
```

---

*This guide is a living document. As the project evolves, the brand evolves with it -- but the core principles remain: deliberate, earned, human-anchored, honest.*
