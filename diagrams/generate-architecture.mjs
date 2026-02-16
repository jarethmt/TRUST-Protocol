#!/usr/bin/env node
/**
 * Generates the TRUST Protocol architecture diagram as Excalidraw JSON.
 * Run: node generate-architecture.mjs > trust-protocol-architecture.excalidraw.json
 */

let seedCounter = 100000000;
function nextSeed() { return seedCounter++; }
const now = Date.now();

function rect(id, x, y, w, h, opts = {}) {
  return {
    id, type: "rectangle", x, y, width: w, height: h, angle: 0,
    strokeColor: opts.stroke || "#000000",
    backgroundColor: opts.fill || "transparent",
    fillStyle: opts.fillStyle || "solid",
    strokeWidth: opts.strokeWidth || 2,
    strokeStyle: opts.strokeStyle || "solid",
    roughness: 0, opacity: 100,
    groupIds: opts.groupIds || [], frameId: null,
    roundness: opts.roundness !== undefined ? opts.roundness : { type: 3 },
    seed: nextSeed(), version: 1, versionNonce: nextSeed(),
    isDeleted: false, boundElements: opts.boundElements || null,
    updated: now, link: null, locked: false
  };
}

function text(id, x, y, w, h, label, opts = {}) {
  return {
    id, type: "text", x, y, width: w, height: h, angle: 0,
    strokeColor: opts.color || "#1e1e1e",
    backgroundColor: "transparent",
    fillStyle: "solid", strokeWidth: 2, strokeStyle: "solid",
    roughness: 0, opacity: 100,
    groupIds: opts.groupIds || [], frameId: null,
    roundness: null,
    seed: nextSeed(), version: 1, versionNonce: nextSeed(),
    isDeleted: false, boundElements: null,
    updated: now, link: null, locked: false,
    text: label, fontSize: opts.fontSize || 16,
    fontFamily: opts.fontFamily || 2,
    textAlign: opts.textAlign || "center",
    verticalAlign: opts.verticalAlign || "middle",
    containerId: opts.containerId || null,
    originalText: label, lineHeight: 1.25
  };
}

function arrow(id, x, y, points, opts = {}) {
  const dx = points[points.length - 1][0] - points[0][0];
  const dy = points[points.length - 1][1] - points[0][1];
  return {
    id, type: "arrow", x, y,
    width: Math.abs(dx), height: Math.abs(dy), angle: 0,
    strokeColor: opts.stroke || "#6b7280",
    backgroundColor: "transparent",
    fillStyle: "solid",
    strokeWidth: opts.strokeWidth || 2,
    strokeStyle: opts.strokeStyle || "solid",
    roughness: 0, opacity: 100,
    groupIds: [], frameId: null,
    roundness: { type: 2 },
    seed: nextSeed(), version: 1, versionNonce: nextSeed(),
    isDeleted: false, boundElements: null,
    updated: now, link: null, locked: false,
    points,
    lastCommittedPoint: null,
    startBinding: null, endBinding: null,
    startArrowhead: opts.startArrowhead || null,
    endArrowhead: opts.endArrowhead !== undefined ? opts.endArrowhead : "arrow"
  };
}

function ellipse(id, x, y, w, h, opts = {}) {
  return {
    id, type: "ellipse", x, y, width: w, height: h, angle: 0,
    strokeColor: opts.stroke || "#000000",
    backgroundColor: opts.fill || "transparent",
    fillStyle: opts.fillStyle || "solid",
    strokeWidth: opts.strokeWidth || 2,
    strokeStyle: opts.strokeStyle || "solid",
    roughness: 0, opacity: 100,
    groupIds: opts.groupIds || [], frameId: null,
    roundness: { type: 2 },
    seed: nextSeed(), version: 1, versionNonce: nextSeed(),
    isDeleted: false, boundElements: null,
    updated: now, link: null, locked: false
  };
}

function diamond(id, x, y, w, h, opts = {}) {
  return {
    id, type: "diamond", x, y, width: w, height: h, angle: 0,
    strokeColor: opts.stroke || "#000000",
    backgroundColor: opts.fill || "transparent",
    fillStyle: opts.fillStyle || "solid",
    strokeWidth: 2, strokeStyle: "solid",
    roughness: 0, opacity: 100,
    groupIds: opts.groupIds || [], frameId: null,
    roundness: { type: 2 },
    seed: nextSeed(), version: 1, versionNonce: nextSeed(),
    isDeleted: false, boundElements: null,
    updated: now, link: null, locked: false
  };
}

function line(id, x, y, points, opts = {}) {
  return {
    id, type: "line", x, y,
    width: 0, height: 0, angle: 0,
    strokeColor: opts.stroke || "#6b7280",
    backgroundColor: "transparent",
    fillStyle: "solid",
    strokeWidth: opts.strokeWidth || 1,
    strokeStyle: opts.strokeStyle || "solid",
    roughness: 0, opacity: opts.opacity || 100,
    groupIds: [], frameId: null,
    roundness: { type: 2 },
    seed: nextSeed(), version: 1, versionNonce: nextSeed(),
    isDeleted: false, boundElements: null,
    updated: now, link: null, locked: false,
    points,
    lastCommittedPoint: null,
    startBinding: null, endBinding: null,
    startArrowhead: null, endArrowhead: null
  };
}

// ============================================================
// LAYOUT CONSTANTS
// ============================================================

const elements = [];

// Colors
const NAVY = "#1e3a5f";
const NAVY_LIGHT = "#e8f0fe";
const BLUE = "#3b82f6";
const BLUE_LIGHT = "#dbeafe";
const BLUE_MED = "#93c5fd";
const GREEN = "#059669";
const GREEN_LIGHT = "#d1fae5";
const GREEN_FILL = "#a7f3d0";
const RED = "#dc2626";
const RED_LIGHT = "#fee2e2";
const RED_FILL = "#fecaca";
const ORANGE = "#d97706";
const ORANGE_LIGHT = "#fef3c7";
const ORANGE_FILL = "#fde68a";
const PURPLE = "#7c3aed";
const PURPLE_LIGHT = "#ede9fe";
const GRAY = "#6b7280";
const GRAY_LIGHT = "#f3f4f6";
const GRAY_BORDER = "#d1d5db";
const BLACK = "#1e1e1e";
const WHITE = "#ffffff";

// ============================================================
// TITLE
// ============================================================

elements.push(text("title", 460, 20, 680, 40, "TRUST Protocol — Agent Security Infrastructure", {
  fontSize: 28, fontFamily: 2, color: NAVY
}));
elements.push(text("subtitle", 520, 62, 560, 24, "How AI agents use credentials without seeing them", {
  fontSize: 16, fontFamily: 2, color: GRAY
}));

// ============================================================
// LEFT ZONE: Agent Platforms & Users
// ============================================================

const LZ_X = 30;
const LZ_Y = 110;
const LZ_W = 340;
const LZ_H = 780;

// Zone background
elements.push(rect("zone-left", LZ_X, LZ_Y, LZ_W, LZ_H, {
  stroke: GRAY_BORDER, fill: GRAY_LIGHT, strokeWidth: 1, roundness: { type: 3 }
}));
elements.push(text("zone-left-label", LZ_X + 40, LZ_Y + 10, 260, 24, "AGENT PLATFORMS & USERS", {
  fontSize: 14, fontFamily: 2, color: GRAY
}));

// Human Operator
const HO_X = LZ_X + 30;
const HO_Y = LZ_Y + 55;
const BOX_W = 280;
const BOX_H = 65;
elements.push(rect("human-op", HO_X, HO_Y, BOX_W, BOX_H, {
  stroke: "#4b5563", fill: "#e5e7eb"
}));
elements.push(text("human-op-t1", HO_X + 40, HO_Y + 8, 200, 22, "Human Operator", {
  fontSize: 16, fontFamily: 2, color: BLACK
}));
elements.push(text("human-op-t2", HO_X + 55, HO_Y + 34, 170, 18, "Admin / DevOps", {
  fontSize: 12, fontFamily: 2, color: GRAY
}));

// OpenClaw Platform
const OC_Y = HO_Y + 100;
elements.push(rect("openclaw", HO_X, OC_Y, BOX_W, BOX_H, {
  stroke: BLUE, fill: BLUE_LIGHT
}));
elements.push(text("openclaw-t1", HO_X + 55, OC_Y + 8, 170, 22, "OpenClaw", {
  fontSize: 16, fontFamily: 2, color: BLUE
}));
elements.push(text("openclaw-t2", HO_X + 45, OC_Y + 34, 190, 18, "Agent Platform", {
  fontSize: 12, fontFamily: 2, color: GRAY
}));

// ClawHub Marketplace
const CH_Y = OC_Y + 100;
elements.push(rect("clawhub", HO_X, CH_Y, BOX_W, BOX_H, {
  stroke: BLUE, fill: BLUE_LIGHT
}));
elements.push(text("clawhub-t1", HO_X + 40, CH_Y + 8, 200, 22, "ClawHub Marketplace", {
  fontSize: 16, fontFamily: 2, color: BLUE
}));
elements.push(text("clawhub-t2", HO_X + 55, CH_Y + 34, 170, 18, "Skill Registry", {
  fontSize: 12, fontFamily: 2, color: GRAY
}));

// Custom Agent Framework
const CF_Y = CH_Y + 100;
elements.push(rect("custom-fw", HO_X, CF_Y, BOX_W, BOX_H, {
  stroke: BLUE, fill: BLUE_LIGHT
}));
elements.push(text("custom-fw-t1", HO_X + 15, CF_Y + 8, 250, 22, "Custom Agent Framework", {
  fontSize: 16, fontFamily: 2, color: BLUE
}));
elements.push(text("custom-fw-t2", HO_X + 40, CF_Y + 34, 200, 18, "MCP, LangChain, etc.", {
  fontSize: 12, fontFamily: 2, color: GRAY
}));

// Skill Developer
const SD_Y = CF_Y + 120;
elements.push(rect("skill-dev", HO_X, SD_Y, BOX_W, BOX_H, {
  stroke: PURPLE, fill: PURPLE_LIGHT
}));
elements.push(text("skill-dev-t1", HO_X + 50, SD_Y + 8, 180, 22, "Skill Developer", {
  fontSize: 16, fontFamily: 2, color: PURPLE
}));
elements.push(text("skill-dev-t2", HO_X + 30, SD_Y + 34, 220, 18, "Signs with Ed25519 key", {
  fontSize: 12, fontFamily: 2, color: GRAY
}));

// ============================================================
// CENTER ZONE: TRUST Protocol Server
// ============================================================

const CZ_X = 440;
const CZ_Y = 110;
const CZ_W = 700;
const CZ_H = 780;

// Main server box
elements.push(rect("zone-center", CZ_X, CZ_Y, CZ_W, CZ_H, {
  stroke: NAVY, fill: "#f0f4fa", strokeWidth: 3, roundness: { type: 3 }
}));
elements.push(text("zone-center-label", CZ_X + 180, CZ_Y + 12, 340, 28, "TRUST PROTOCOL SERVER", {
  fontSize: 18, fontFamily: 2, color: NAVY
}));
elements.push(text("zone-center-sub", CZ_X + 230, CZ_Y + 40, 240, 20, "REST API · Port 9500", {
  fontSize: 13, fontFamily: 3, color: GRAY
}));

// Internal component grid: 2 cols x 4 rows
const COMP_W = 300;
const COMP_H = 70;
const COL1_X = CZ_X + 30;
const COL2_X = CZ_X + 370;
const ROW_START = CZ_Y + 80;
const ROW_GAP = 95;

function componentBox(id, col, row, label, sublabel, opts = {}) {
  const x = col === 0 ? COL1_X : COL2_X;
  const y = ROW_START + row * ROW_GAP;
  const stroke = opts.stroke || BLUE;
  const fill = opts.fill || BLUE_LIGHT;
  const labelColor = opts.labelColor || NAVY;

  elements.push(rect(id, x, y, COMP_W, COMP_H, { stroke, fill }));
  elements.push(text(id + "-t1", x + 20, y + 10, COMP_W - 40, 22, label, {
    fontSize: 15, fontFamily: 2, color: labelColor
  }));
  elements.push(text(id + "-t2", x + 20, y + 38, COMP_W - 40, 18, sublabel, {
    fontSize: 11, fontFamily: 2, color: GRAY
  }));
}

// Row 0
componentBox("agent-reg", 0, 0, "Agent Registry", "Identity, API keys, trust tiers");
componentBox("token-auth", 1, 0, "Token Authority", "HMAC tokens, behavior-gated renewal");

// Row 1
componentBox("cred-vault", 0, 1, "Credential Vault", "AES-256-GCM encrypted storage", {
  stroke: GREEN, fill: GREEN_LIGHT, labelColor: "#065f46"
});
componentBox("cred-proxy", 1, 1, "Credential Proxy", "Zero-knowledge execution engine", {
  stroke: GREEN, fill: GREEN_LIGHT, labelColor: "#065f46"
});

// Row 2
componentBox("skill-sign", 0, 2, "Skill Signer", "Ed25519 signing & verification", {
  stroke: PURPLE, fill: PURPLE_LIGHT, labelColor: PURPLE
});
componentBox("behavior", 1, 2, "Behavior Analyzer", "Anomaly detection & scoring", {
  stroke: ORANGE, fill: ORANGE_LIGHT, labelColor: "#92400e"
});

// Row 3
componentBox("audit", 0, 3, "Audit Chain", "HMAC-signed, hash-chained log", {
  stroke: "#4b5563", fill: "#e5e7eb", labelColor: "#374151"
});
componentBox("emergency", 1, 3, "Emergency Controls", "Global / Agent / Credential kill switch", {
  stroke: RED, fill: RED_LIGHT, labelColor: RED
});

// --- Trust Tier Progression Bar ---
const TIER_Y = ROW_START + 4 * ROW_GAP + 20;
const TIER_BOX_W = 108;
const TIER_BOX_H = 44;
const TIER_GAP = 32;
const TIER_START_X = CZ_X + 42;
const tiers = [
  { name: "NOVICE", sub: "1h / 1 cred", fill: "#fef3c7", stroke: "#d97706" },
  { name: "COMPANION", sub: "4h / 5 cred", fill: "#fde68a", stroke: "#b45309" },
  { name: "PARTNER", sub: "8h / 20 cred", fill: "#fdba74", stroke: "#c2410c" },
  { name: "GUARDIAN", sub: "12h / unlim", fill: "#fb923c", stroke: "#9a3412" },
  { name: "SACRED", sub: "24h / human", fill: "#f97316", stroke: "#7c2d12" },
];

elements.push(text("tier-label", TIER_START_X, TIER_Y - 28, 300, 22, "Trust Evolution (earned through behavior)", {
  fontSize: 13, fontFamily: 2, color: ORANGE, textAlign: "left"
}));

tiers.forEach((tier, i) => {
  const tx = TIER_START_X + i * (TIER_BOX_W + TIER_GAP);
  elements.push(rect(`tier-${i}`, tx, TIER_Y, TIER_BOX_W, TIER_BOX_H, {
    stroke: tier.stroke, fill: tier.fill, roundness: { type: 3 }
  }));
  elements.push(text(`tier-${i}-name`, tx + 6, TIER_Y + 4, TIER_BOX_W - 12, 18, tier.name, {
    fontSize: 12, fontFamily: 2, color: "#1e1e1e"
  }));
  elements.push(text(`tier-${i}-sub`, tx + 6, TIER_Y + 24, TIER_BOX_W - 12, 14, tier.sub, {
    fontSize: 10, fontFamily: 3, color: GRAY
  }));
  // Arrow between tiers
  if (i < tiers.length - 1) {
    const arrowX = tx + TIER_BOX_W + 2;
    const arrowY2 = TIER_Y + TIER_BOX_H / 2;
    elements.push(arrow(`tier-arrow-${i}`, arrowX, arrowY2, [[0, 0], [TIER_GAP - 4, 0]], {
      stroke: ORANGE, strokeWidth: 2
    }));
  }
});

// --- Flow description boxes at bottom of center ---
const FLOW_Y = TIER_Y + TIER_BOX_H + 30;
const FLOW_BOX_W = CZ_W - 60;

elements.push(rect("flow-legend-bg", CZ_X + 30, FLOW_Y, FLOW_BOX_W, 110, {
  stroke: GRAY_BORDER, fill: WHITE, strokeWidth: 1
}));
elements.push(text("flow-legend-title", CZ_X + 50, FLOW_Y + 8, 200, 18, "Key Flows:", {
  fontSize: 13, fontFamily: 2, color: BLACK, textAlign: "left"
}));

// Green dot
elements.push(ellipse("legend-green", CZ_X + 50, FLOW_Y + 33, 10, 10, {
  stroke: GREEN, fill: GREEN_FILL
}));
elements.push(text("legend-green-t", CZ_X + 68, FLOW_Y + 28, 300, 18,
  "Credential Proxy: Agent sends {{CREDENTIAL}} template, gets response only", {
  fontSize: 11, fontFamily: 2, color: BLACK, textAlign: "left"
}));

// Purple dot
elements.push(ellipse("legend-purple", CZ_X + 50, FLOW_Y + 55, 10, 10, {
  stroke: PURPLE, fill: PURPLE_LIGHT
}));
elements.push(text("legend-purple-t", CZ_X + 68, FLOW_Y + 50, 400, 18,
  "Skill Verification: Publisher signs manifest, marketplace verifies (no auth)", {
  fontSize: 11, fontFamily: 2, color: BLACK, textAlign: "left"
}));

// Red dot
elements.push(ellipse("legend-red", CZ_X + 50, FLOW_Y + 77, 10, 10, {
  stroke: RED, fill: RED_FILL
}));
elements.push(text("legend-red-t", CZ_X + 68, FLOW_Y + 72, 400, 18,
  "Emergency Brake: One call blocks all access globally, per-agent, or per-credential", {
  fontSize: 11, fontFamily: 2, color: BLACK, textAlign: "left"
}));

// ============================================================
// RIGHT ZONE: External Services
// ============================================================

const RZ_X = 1210;
const RZ_Y = 110;
const RZ_W = 300;
const RZ_H = 480;

elements.push(rect("zone-right", RZ_X, RZ_Y, RZ_W, RZ_H, {
  stroke: GRAY_BORDER, fill: GRAY_LIGHT, strokeWidth: 1, roundness: { type: 3 }
}));
elements.push(text("zone-right-label", RZ_X + 55, RZ_Y + 10, 190, 24, "EXTERNAL SERVICES", {
  fontSize: 14, fontFamily: 2, color: GRAY
}));

// API ellipses
const API_W = 220;
const API_H = 65;
const API_X = RZ_X + 40;

function apiEllipse(id, y, label, sublabel) {
  elements.push(ellipse(id, API_X, y, API_W, API_H, {
    stroke: GREEN, fill: GREEN_LIGHT
  }));
  elements.push(text(id + "-t1", API_X + 30, y + 12, API_W - 60, 22, label, {
    fontSize: 15, fontFamily: 2, color: "#065f46"
  }));
  elements.push(text(id + "-t2", API_X + 30, y + 36, API_W - 60, 16, sublabel, {
    fontSize: 11, fontFamily: 2, color: GRAY
  }));
}

apiEllipse("api-openai", RZ_Y + 55, "OpenAI API", "api.openai.com");
apiEllipse("api-github", RZ_Y + 165, "GitHub API", "api.github.com");
apiEllipse("api-stripe", RZ_Y + 275, "Stripe API", "api.stripe.com");

// "Agent never sees" callout
elements.push(rect("callout-nosee", RZ_X + 15, RZ_Y + 400, 270, 55, {
  stroke: RED, fill: RED_LIGHT, strokeWidth: 1, strokeStyle: "dashed"
}));
elements.push(text("callout-nosee-t", RZ_X + 30, RZ_Y + 410, 240, 36,
  "Agent NEVER sees raw\ncredentials — only responses", {
  fontSize: 12, fontFamily: 2, color: RED
}));

// ============================================================
// FLOW ARROWS
// ============================================================

// 1. OpenClaw → Agent Registry (register agent)
const arrowOC_startX = HO_X + BOX_W;
const arrowOC_startY = OC_Y + BOX_H / 2;
const arrowOC_endX = COL1_X;
const arrowOC_endY = ROW_START + COMP_H / 2;
elements.push(arrow("flow-register", arrowOC_startX, arrowOC_startY,
  [[0, 0], [(arrowOC_endX - arrowOC_startX), arrowOC_endY - arrowOC_startY]], {
  stroke: BLUE, strokeWidth: 2
}));
elements.push(text("flow-register-label", arrowOC_startX + 10, arrowOC_startY - 28, 130, 16,
  "Register Agent", { fontSize: 11, fontFamily: 2, color: BLUE, textAlign: "left" }));

// 2. Custom Framework → Token Authority (get token)
const arrowCF_startX = HO_X + BOX_W;
const arrowCF_startY = CF_Y + BOX_H / 2;
const arrowCF_endX = COL2_X;
const arrowCF_endY = ROW_START + COMP_H / 2;
elements.push(arrow("flow-token", arrowCF_startX, arrowCF_startY,
  [[0, 0], [(arrowCF_endX - arrowCF_startX), arrowCF_endY - arrowCF_startY]], {
  stroke: BLUE, strokeWidth: 2, strokeStyle: "dashed"
}));
elements.push(text("flow-token-label", arrowCF_startX + 10, arrowCF_startY + 8, 100, 16,
  "Get Token", { fontSize: 11, fontFamily: 2, color: BLUE, textAlign: "left" }));

// 3. OpenClaw → Credential Proxy (proxy-execute)
const arrowProxy_startX = HO_X + BOX_W;
const arrowProxy_startY = OC_Y + BOX_H - 8;
const arrowProxy_endX = COL2_X;
const arrowProxy_endY = ROW_START + ROW_GAP + COMP_H / 2;
elements.push(arrow("flow-proxy", arrowProxy_startX, arrowProxy_startY,
  [[0, 0], [(arrowProxy_endX - arrowProxy_startX), arrowProxy_endY - arrowProxy_startY]], {
  stroke: GREEN, strokeWidth: 3
}));
elements.push(text("flow-proxy-label", arrowProxy_startX + 5, arrowProxy_startY + 15, 170, 16,
  "{{CREDENTIAL}} template", { fontSize: 11, fontFamily: 3, color: GREEN, textAlign: "left" }));

// 4. Credential Proxy → External APIs
const arrowExt_startX = COL2_X + COMP_W;
const arrowExt_startY = ROW_START + ROW_GAP + COMP_H / 2;
const arrowExt_endX = API_X;
elements.push(arrow("flow-external", arrowExt_startX, arrowExt_startY,
  [[0, 0], [(arrowExt_endX - arrowExt_startX), -10]], {
  stroke: GREEN, strokeWidth: 3
}));
elements.push(text("flow-ext-label", arrowExt_startX + 8, arrowExt_startY - 26, 150, 16,
  "Injects real credential", { fontSize: 11, fontFamily: 2, color: GREEN, textAlign: "left" }));

// 5. Response arrow back (dashed)
elements.push(arrow("flow-response", arrowExt_endX - 5, arrowExt_startY + 20,
  [[0, 0], [-(arrowExt_endX - arrowExt_startX - 10), 15]], {
  stroke: GREEN, strokeWidth: 2, strokeStyle: "dashed"
}));
elements.push(text("flow-resp-label", arrowExt_startX + 8, arrowExt_startY + 22, 140, 16,
  "Response only", { fontSize: 11, fontFamily: 2, color: GREEN, textAlign: "left" }));

// 6. Skill Developer → Skill Signer (sign)
const arrowSD_startX = HO_X + BOX_W;
const arrowSD_startY = SD_Y + BOX_H / 2;
const arrowSD_endX = COL1_X;
const arrowSD_endY = ROW_START + 2 * ROW_GAP + COMP_H / 2;
elements.push(arrow("flow-sign", arrowSD_startX, arrowSD_startY,
  [[0, 0], [(arrowSD_endX - arrowSD_startX), arrowSD_endY - arrowSD_startY]], {
  stroke: PURPLE, strokeWidth: 2
}));
elements.push(text("flow-sign-label", arrowSD_startX + 10, arrowSD_startY - 18, 120, 16,
  "Sign Manifest", { fontSize: 11, fontFamily: 2, color: PURPLE, textAlign: "left" }));

// 7. ClawHub → Skill Signer (verify, no auth)
const arrowCH_startX = HO_X + BOX_W;
const arrowCH_startY = CH_Y + BOX_H / 2;
elements.push(arrow("flow-verify", arrowCH_startX, arrowCH_startY,
  [[0, 0], [(arrowSD_endX - arrowCH_startX), arrowSD_endY - arrowCH_startY]], {
  stroke: PURPLE, strokeWidth: 2, strokeStyle: "dashed"
}));
elements.push(text("flow-verify-label", arrowCH_startX + 10, arrowCH_startY + 10, 140, 16,
  "Verify (no auth!)", { fontSize: 11, fontFamily: 2, color: PURPLE, textAlign: "left" }));

// 8. Human → Emergency Controls (red kill switch)
const arrowEM_startX = HO_X + BOX_W;
const arrowEM_startY = HO_Y + BOX_H / 2;
const arrowEM_endX = COL2_X;
const arrowEM_endY = ROW_START + 3 * ROW_GAP + COMP_H / 2;
elements.push(arrow("flow-emergency", arrowEM_startX, arrowEM_startY,
  [[0, 0], [(arrowEM_endX - arrowEM_startX), arrowEM_endY - arrowEM_startY]], {
  stroke: RED, strokeWidth: 3
}));
elements.push(text("flow-em-label", arrowEM_startX + 45, arrowEM_startY + 35, 100, 16,
  "Kill Switch", { fontSize: 12, fontFamily: 2, color: RED, textAlign: "left" }));

// 9. Internal: Behavior → Token Authority (score feeds renewal)
const arrowBT_startX = COL2_X + COMP_W / 2;
const arrowBT_startY = ROW_START + 2 * ROW_GAP;
const arrowBT_endY = ROW_START + ROW_GAP - 5 + COMP_H;
elements.push(arrow("flow-behavior-token", arrowBT_startX + 50, arrowBT_startY,
  [[0, 0], [0, -(arrowBT_startY - arrowBT_endY)]], {
  stroke: ORANGE, strokeWidth: 2, strokeStyle: "dashed"
}));
elements.push(text("flow-bt-label", arrowBT_startX + 56, arrowBT_startY - 42, 110, 14,
  "Score gates renewal", { fontSize: 10, fontFamily: 2, color: ORANGE, textAlign: "left" }));

// 10. Internal: All actions → Audit Chain
const arrowAudit_startX = COL1_X + COMP_W / 2;
const arrowAudit_startY = ROW_START + 2 * ROW_GAP + COMP_H;
const arrowAudit_endY = ROW_START + 3 * ROW_GAP;
elements.push(arrow("flow-audit", arrowAudit_startX, arrowAudit_startY + 5,
  [[0, 0], [0, arrowAudit_endY - arrowAudit_startY - 5]], {
  stroke: "#4b5563", strokeWidth: 1, strokeStyle: "dashed"
}));
elements.push(text("flow-audit-label", arrowAudit_startX + 6, arrowAudit_startY + 2, 80, 14,
  "Logs all", { fontSize: 10, fontFamily: 2, color: GRAY, textAlign: "left" }));

// ============================================================
// ASSEMBLE SCENE
// ============================================================

const scene = {
  type: "excalidraw",
  version: 2,
  source: "https://draw.thoughtspacedesigns.com",
  elements,
  appState: {
    gridSize: null,
    viewBackgroundColor: "#ffffff"
  },
  files: {}
};

process.stdout.write(JSON.stringify(scene, null, 2));
