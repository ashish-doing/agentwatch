/**
 * AgentWatch — Page Guide System
 * Drop <script src="guide.js"></script> at the end of <body> on any page.
 * Auto-detects which page it's on and renders the right guide overlay.
 *
 * Pages supported:
 *   /           → Live Brain guide
 *   /ops        → Agent Ops guide
 *   /topology   → Topology Map guide
 *   (landing)   → landing.html loading screen
 */

(function () {
  "use strict";

  /* ─── CONFIG ─────────────────────────────────────────────── */

  const GUIDES = {
    brain: {
      title: "Live Brain",
      subtitle: "Real-time agent intelligence visualizer",
      accent: "#00e5ff",
      icon: `<svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <circle cx="14" cy="14" r="12" stroke="#00e5ff" stroke-width="1.5"/>
        <circle cx="14" cy="14" r="5" fill="#00e5ff" opacity="0.3"/>
        <circle cx="14" cy="14" r="2" fill="#00e5ff"/>
        <line x1="14" y1="2" x2="14" y2="8" stroke="#00e5ff" stroke-width="1.5"/>
        <line x1="14" y1="20" x2="14" y2="26" stroke="#00e5ff" stroke-width="1.5"/>
        <line x1="2" y1="14" x2="8" y2="14" stroke="#00e5ff" stroke-width="1.5"/>
        <line x1="20" y1="14" x2="26" y2="14" stroke="#00e5ff" stroke-width="1.5"/>
      </svg>`,
      steps: [
        {
          icon: "◉",
          label: "Run an agent scenario",
          body: "Click <strong>NORMAL</strong>, <strong>LOOP</strong>, <strong>HALLUCINATE</strong>, or <strong>DRIFT</strong> at the top to fire a demo agent. Watch the 3D brain graph burst to life — each bubble is a live reasoning step.",
        },
        {
          icon: "◈",
          label: "Read the bubbles",
          body: "<strong>Green</strong> = healthy step, <strong>orange</strong> = warning, <strong>red</strong> = anomaly. Bubble size scales with token count. Lines between them are tool calls or data flows.",
        },
        {
          icon: "⬡",
          label: "Inspect any node",
          body: "Click any bubble in the brain graph. The <strong>Node Inspector</strong> panel on the right shows step name, trust score, latency, and token count for that node.",
        },
        {
          icon: "⚠",
          label: "Respond to anomaly alerts",
          body: "Red banners auto-fire when a loop, token spike, or trust collapse is detected. Hit <strong>EXPLAIN</strong> to get a Foundation-Sec AI explanation in plain English, or <strong>EXPORT PDF</strong> to save the incident.",
        },
        {
          icon: "✦",
          label: "Query Splunk naturally",
          body: "Type a question in the bottom bar — <em>\"Which tools have the lowest trust scores?\"</em> — and hit <strong>RUN</strong>. The AI Assistant converts it to SPL and returns results live. Preset chips get you started instantly.",
        },
        {
          icon: "⊙",
          label: "Watch the metric strips",
          body: "The three sparklines below the brain show <strong>Tokens / LLM Call</strong>, <strong>Step Latency</strong>, and <strong>Trust Score</strong> over the current run. Spikes here precede alerts above.",
        },
        {
          icon: "◎",
          label: "Trace timeline",
          body: "The bar at the bottom is the full trace timeline. Coloured segments map to each step. Scroll horizontally across a long run to find exactly where things went wrong.",
        },
      ],
    },

    ops: {
      title: "Agent Ops",
      subtitle: "CRM-style run history & fleet health",
      accent: "#a78bfa",
      icon: `<svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <rect x="3" y="5" width="22" height="18" rx="2" stroke="#a78bfa" stroke-width="1.5"/>
        <line x1="3" y1="10" x2="25" y2="10" stroke="#a78bfa" stroke-width="1.5"/>
        <rect x="7" y="14" width="4" height="5" fill="#a78bfa" opacity="0.4"/>
        <rect x="13" y="12" width="4" height="7" fill="#a78bfa" opacity="0.7"/>
        <rect x="19" y="15" width="3" height="4" fill="#a78bfa" opacity="0.4"/>
      </svg>`,
      steps: [
        {
          icon: "①",
          label: "Six headline metrics",
          body: "The top row gives you fleet-wide health at a glance: <strong>Total Runs</strong>, <strong>Avg Trust Score</strong>, <strong>Total Anomalies</strong>, <strong>Total Tokens</strong>, <strong>Est. Cost</strong>, and <strong>Live Events</strong>. These update in real time as agents run.",
        },
        {
          icon: "②",
          label: "Agent Run History table",
          body: "Every run is a row. Columns show mode, status (<span style='color:#4ade80'>HEALTHY</span> / <span style='color:#facc15'>WARNING</span> / <span style='color:#f87171'>CRITICAL</span>), trust bar, anomaly count, tokens, cost, and duration. Click any row to drill into that run's full trace on the Live Brain page.",
        },
        {
          icon: "③",
          label: "Filter by failure mode",
          body: "Use the <strong>ALL / NORMAL / LOOP / HALLUCINATE / DRIFT</strong> tabs above the table to narrow runs by the scenario type you care about. Good for comparing loop runs only.",
        },
        {
          icon: "④",
          label: "Trust Trend chart",
          body: "The line chart on the right shows how avg trust has moved across the last N runs. A downward trend means your agent is degrading across sessions — catch it before production.",
        },
        {
          icon: "⑤",
          label: "Anomaly Types donut",
          body: "The donut breaks down what kinds of failures occurred: loop, token spike, latency drift, error burst, trust collapse. Hover segments for counts. Use this to prioritise what to fix first.",
        },
        {
          icon: "⑥",
          label: "Run a new agent + Live View",
          body: "Click <strong>▶ RUN AGENT</strong> to kick off a fresh run from this page. Hit <strong>← LIVE VIEW</strong> to jump straight to the Live Brain for the current run without navigating manually.",
        },
        {
          icon: "⑦",
          label: "Time window selector",
          body: "The <strong>Last 30 runs / Last 10 runs / All runs</strong> dropdown controls how many runs populate the table and charts. Switch to <em>All runs</em> to see your full project history.",
        },
      ],
    },

    topology: {
      title: "Topology Map",
      subtitle: "Agent network graph — every node, every edge",
      accent: "#34d399",
      icon: `<svg width="28" height="28" viewBox="0 0 28 28" fill="none">
        <circle cx="14" cy="14" r="4" fill="#34d399" opacity="0.5"/>
        <circle cx="5"  cy="7"  r="2.5" stroke="#34d399" stroke-width="1.5"/>
        <circle cx="23" cy="7"  r="2.5" stroke="#34d399" stroke-width="1.5"/>
        <circle cx="5"  cy="21" r="2.5" stroke="#34d399" stroke-width="1.5"/>
        <circle cx="23" cy="21" r="2.5" stroke="#34d399" stroke-width="1.5"/>
        <line x1="7" y1="8"  x2="12" y2="12" stroke="#34d399" stroke-width="1"/>
        <line x1="21" y1="8"  x2="16" y2="12" stroke="#34d399" stroke-width="1"/>
        <line x1="7" y1="20" x2="12" y2="16" stroke="#34d399" stroke-width="1"/>
        <line x1="21" y1="20" x2="16" y2="16" stroke="#34d399" stroke-width="1"/>
      </svg>`,
      steps: [
        {
          icon: "◐",
          label: "What you're looking at",
          body: "This is a <strong>force-directed graph</strong> of every node and edge across all agent runs. Each node is one event — an LLM call, tool call, healthy step, warning step, anomaly, or agent hub. Edges show data flow and anomaly propagation paths.",
        },
        {
          icon: "◑",
          label: "Node colour legend",
          body: "<strong>Blue</strong> = LLM Call &nbsp;·&nbsp; <strong>Cyan</strong> = Tool Call &nbsp;·&nbsp; <strong>Green</strong> = Healthy Step &nbsp;·&nbsp; <strong>Yellow</strong> = Warning Step &nbsp;·&nbsp; <strong>Red pulsing</strong> = Anomaly/Error &nbsp;·&nbsp; <strong>Purple</strong> = Agent Hub (root)",
        },
        {
          icon: "◒",
          label: "Edge colour legend",
          body: "<strong>Cyan line</strong> = normal data flow &nbsp;·&nbsp; <strong>Red line</strong> = anomaly propagation path (follow these to trace a failure back to its source) &nbsp;·&nbsp; <strong>Green line</strong> = successful completion edge",
        },
        {
          icon: "◓",
          label: "Click any node to inspect",
          body: "The <strong>Node Inspector</strong> panel on the right shows: Node Type, Label, Agent ID, Trust Score (colour-coded bar), and connection count. Use this to see why a specific tool call was flagged.",
        },
        {
          icon: "◔",
          label: "Try the demo buttons",
          body: "<strong>▶ LOOP DEMO</strong> injects a loop failure pattern into the graph so you can see how anomaly edges cluster. <strong>▶ DRIFT DEMO</strong> shows latency degradation spreading node-to-node. Hit <strong>⊕ RESET VIEW</strong> to clear.",
        },
        {
          icon: "◕",
          label: "Navigate the graph",
          body: "<strong>Drag</strong> to pan, <strong>scroll</strong> to zoom. The graph is physics-simulated so nodes settle naturally. Dense red clusters = repeated failures at the same tool. Isolated nodes = one-off events.",
        },
        {
          icon: "●",
          label: "Bottom stat bar",
          body: "The five counters at the bottom show live totals: <strong>Agents · Nodes · Edges · Anomalies · Avg Trust</strong>. These match the aggregate across every run loaded, giving you a network-wide health score.",
        },
      ],
    },
  };

  /* ─── PAGE DETECTION ─────────────────────────────────────── */

  function detectPage() {
    const path = window.location.pathname.replace(/\/$/, "");
    if (path === "/ops") return "ops";
    if (path === "/topology") return "topology";
    return "brain"; // default: Live Brain (root or /index.html)
  }

  /* ─── STORAGE ─────────────────────────────────────────────── */

  const SEEN_KEY = "aw_guide_seen_v1";

  function hasSeenGuide(page) {
    try {
      const seen = JSON.parse(localStorage.getItem(SEEN_KEY) || "{}");
      return !!seen[page];
    } catch {
      return false;
    }
  }

  function markSeen(page) {
    try {
      const seen = JSON.parse(localStorage.getItem(SEEN_KEY) || "{}");
      seen[page] = Date.now();
      localStorage.setItem(SEEN_KEY, JSON.stringify(seen));
    } catch {}
  }

  /* ─── STYLES ─────────────────────────────────────────────── */

  function injectStyles() {
    if (document.getElementById("aw-guide-styles")) return;
    const style = document.createElement("style");
    style.id = "aw-guide-styles";
    style.textContent = `
      /* ── Guide Backdrop ── */
      #aw-guide-backdrop {
        position: fixed;
        inset: 0;
        background: rgba(0,0,0,0.72);
        backdrop-filter: blur(3px);
        z-index: 9000;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 16px;
        animation: aw-fade-in 0.25s ease;
      }

      @keyframes aw-fade-in {
        from { opacity: 0; }
        to   { opacity: 1; }
      }

      /* ── Guide Panel ── */
      #aw-guide-panel {
        position: relative;
        width: 100%;
        max-width: 560px;
        max-height: 90vh;
        overflow-y: auto;
        background: #0f1117;
        border: 1px solid var(--aw-accent, #00e5ff);
        border-radius: 10px;
        box-shadow: 0 0 48px rgba(0,0,0,0.8), 0 0 16px var(--aw-glow, rgba(0,229,255,0.12));
        font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
        color: #e2e8f0;
        animation: aw-slide-up 0.3s cubic-bezier(0.22, 1, 0.36, 1);
        scrollbar-width: thin;
        scrollbar-color: var(--aw-accent, #00e5ff) #1a1f2e;
      }

      @keyframes aw-slide-up {
        from { transform: translateY(20px); opacity: 0; }
        to   { transform: translateY(0);    opacity: 1; }
      }

      /* ── Header ── */
      .aw-guide-header {
        display: flex;
        align-items: flex-start;
        gap: 14px;
        padding: 22px 22px 16px;
        border-bottom: 1px solid #1e2540;
      }

      .aw-guide-icon-wrap {
        flex-shrink: 0;
        margin-top: 2px;
      }

      .aw-guide-header-text {
        flex: 1;
      }

      .aw-guide-eyebrow {
        font-size: 10px;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--aw-accent, #00e5ff);
        opacity: 0.7;
        margin-bottom: 4px;
      }

      .aw-guide-title {
        font-size: 18px;
        font-weight: 700;
        color: #fff;
        letter-spacing: -0.01em;
        line-height: 1.2;
      }

      .aw-guide-subtitle {
        font-size: 11px;
        color: #7a8499;
        margin-top: 3px;
        font-family: -apple-system, 'Segoe UI', sans-serif;
      }

      /* ── Close ── */
      #aw-guide-close {
        position: absolute;
        top: 14px;
        right: 14px;
        width: 26px;
        height: 26px;
        border: 1px solid #2a3050;
        border-radius: 5px;
        background: transparent;
        color: #7a8499;
        font-size: 14px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: border-color 0.15s, color 0.15s, background 0.15s;
        line-height: 1;
      }

      #aw-guide-close:hover {
        border-color: var(--aw-accent, #00e5ff);
        color: #fff;
        background: rgba(255,255,255,0.05);
      }

      /* ── Steps ── */
      .aw-guide-steps {
        padding: 18px 22px;
        display: flex;
        flex-direction: column;
        gap: 14px;
      }

      .aw-guide-step {
        display: flex;
        gap: 14px;
        align-items: flex-start;
        padding: 12px 14px;
        border-radius: 7px;
        background: #141824;
        border: 1px solid #1e2540;
        transition: border-color 0.2s, background 0.2s;
      }

      .aw-guide-step:hover {
        border-color: var(--aw-accent, #00e5ff);
        background: #161d2e;
      }

      .aw-step-glyph {
        flex-shrink: 0;
        width: 22px;
        text-align: center;
        font-size: 14px;
        color: var(--aw-accent, #00e5ff);
        opacity: 0.8;
        margin-top: 1px;
        line-height: 1.5;
      }

      .aw-step-content {
        flex: 1;
        min-width: 0;
      }

      .aw-step-label {
        font-size: 12px;
        font-weight: 600;
        color: #c9d4e8;
        letter-spacing: 0.04em;
        margin-bottom: 5px;
        text-transform: uppercase;
        font-size: 10.5px;
      }

      .aw-step-body {
        font-family: -apple-system, 'Segoe UI', sans-serif;
        font-size: 13px;
        color: #8a94ad;
        line-height: 1.6;
      }

      .aw-step-body strong {
        color: #c9d4e8;
        font-weight: 600;
      }

      .aw-step-body em {
        color: var(--aw-accent, #00e5ff);
        font-style: normal;
        opacity: 0.85;
      }

      /* ── Footer ── */
      .aw-guide-footer {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 14px 22px 18px;
        border-top: 1px solid #1e2540;
        gap: 12px;
      }

      .aw-guide-nav-links {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }

      .aw-guide-nav-link {
        font-family: 'JetBrains Mono', monospace;
        font-size: 10px;
        padding: 4px 9px;
        border: 1px solid #2a3050;
        border-radius: 4px;
        color: #7a8499;
        text-decoration: none;
        transition: border-color 0.15s, color 0.15s;
        letter-spacing: 0.04em;
      }

      .aw-guide-nav-link:hover {
        border-color: #4a5280;
        color: #c9d4e8;
      }

      .aw-guide-cta {
        flex-shrink: 0;
        padding: 8px 18px;
        background: var(--aw-accent, #00e5ff);
        color: #0a0d14;
        border: none;
        border-radius: 5px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.06em;
        cursor: pointer;
        transition: opacity 0.15s, transform 0.15s;
        text-transform: uppercase;
      }

      .aw-guide-cta:hover {
        opacity: 0.88;
        transform: translateY(-1px);
      }

      /* ── Trigger button (? badge) ── */
      #aw-guide-trigger {
        position: fixed;
        bottom: 18px;
        left: 18px;
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: #0f1117;
        border: 1px solid var(--aw-accent, #00e5ff);
        color: var(--aw-accent, #00e5ff);
        font-family: 'JetBrains Mono', monospace;
        font-size: 15px;
        font-weight: 700;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 8000;
        box-shadow: 0 0 10px var(--aw-glow, rgba(0,229,255,0.18));
        transition: transform 0.15s, box-shadow 0.15s;
        line-height: 1;
      }

      #aw-guide-trigger:hover {
        transform: scale(1.12);
        box-shadow: 0 0 18px var(--aw-glow, rgba(0,229,255,0.35));
      }

      #aw-guide-trigger-tooltip {
        position: fixed;
        bottom: 18px;
        left: 60px;
        background: #1a1f2e;
        border: 1px solid #2a3050;
        border-radius: 5px;
        padding: 5px 10px;
        font-family: -apple-system, 'Segoe UI', sans-serif;
        font-size: 11px;
        color: #7a8499;
        white-space: nowrap;
        z-index: 8000;
        pointer-events: none;
        opacity: 0;
        transform: translateX(-4px);
        transition: opacity 0.2s, transform 0.2s;
      }

      #aw-guide-trigger:hover + #aw-guide-trigger-tooltip {
        opacity: 1;
        transform: translateX(0);
      }

      /* ── Page badge ── */
      .aw-page-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 9px;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--aw-accent, #00e5ff);
        background: rgba(0,229,255,0.07);
        border: 1px solid rgba(0,229,255,0.2);
        padding: 2px 7px;
        border-radius: 3px;
        margin-bottom: 6px;
      }

      .aw-page-badge::before {
        content: '';
        width: 5px;
        height: 5px;
        border-radius: 50%;
        background: var(--aw-accent, #00e5ff);
        display: inline-block;
      }
    `;
    document.head.appendChild(style);
  }

  /* ─── BUILD GUIDE HTML ──────────────────────────────────── */

  function buildGuide(pageKey) {
    const g = GUIDES[pageKey];
    const accentHex = g.accent;

    const stepsHTML = g.steps
      .map(
        (s) => `
      <div class="aw-guide-step">
        <span class="aw-step-glyph">${s.icon}</span>
        <div class="aw-step-content">
          <div class="aw-step-label">${s.label}</div>
          <div class="aw-step-body">${s.body}</div>
        </div>
      </div>`
      )
      .join("");

    // Other pages nav links
    const allPages = [
      { key: "brain",    label: "Live Brain",  path: "/" },
      { key: "ops",      label: "Agent Ops",   path: "/ops" },
      { key: "topology", label: "Topology",    path: "/topology" },
    ];
    const otherLinks = allPages
      .filter((p) => p.key !== pageKey)
      .map(
        (p) =>
          `<a class="aw-guide-nav-link" href="${p.path}">→ ${p.label}</a>`
      )
      .join("");

    const ctaLabel =
      pageKey === "brain"
        ? "Let's go →"
        : pageKey === "ops"
        ? "View runs →"
        : "Explore graph →";

    return `
      <div id="aw-guide-panel" style="--aw-accent:${accentHex}; --aw-glow:${accentHex}22;">
        <button id="aw-guide-close" title="Close guide">✕</button>

        <div class="aw-guide-header">
          <div class="aw-guide-icon-wrap">${g.icon}</div>
          <div class="aw-guide-header-text">
            <div class="aw-page-badge" style="color:${accentHex}; background:${accentHex}12; border-color:${accentHex}33;">
              ${g.title}
            </div>
            <div class="aw-guide-title">How to use this page</div>
            <div class="aw-guide-subtitle">${g.subtitle}</div>
          </div>
        </div>

        <div class="aw-guide-steps">
          ${stepsHTML}
        </div>

        <div class="aw-guide-footer">
          <div class="aw-guide-nav-links">
            ${otherLinks}
          </div>
          <button class="aw-guide-cta" id="aw-guide-dismiss" style="background:${accentHex};">
            ${ctaLabel}
          </button>
        </div>
      </div>
    `;
  }

  /* ─── SHOW / HIDE ─────────────────────────────────────────── */

  function showGuide(pageKey, forced) {
    if (!forced && hasSeenGuide(pageKey)) return;

    const g = GUIDES[pageKey];
    injectStyles();

    const backdrop = document.createElement("div");
    backdrop.id = "aw-guide-backdrop";
    backdrop.innerHTML = buildGuide(pageKey);
    document.body.appendChild(backdrop);

    // Set CSS var on panel for accent
    const panel = backdrop.querySelector("#aw-guide-panel");
    panel.style.setProperty("--aw-accent", g.accent);

    function dismiss() {
      backdrop.style.animation = "aw-fade-in 0.18s ease reverse forwards";
      setTimeout(() => backdrop.remove(), 180);
      markSeen(pageKey);
    }

    backdrop.querySelector("#aw-guide-close").addEventListener("click", dismiss);
    backdrop.querySelector("#aw-guide-dismiss").addEventListener("click", dismiss);
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) dismiss();
    });
    document.addEventListener("keydown", function esc(e) {
      if (e.key === "Escape") { dismiss(); document.removeEventListener("keydown", esc); }
    });
  }

  /* ─── PERSISTENT ? BUTTON ─────────────────────────────────── */

  function addTriggerButton(pageKey) {
    injectStyles();
    const g = GUIDES[pageKey];

    const btn = document.createElement("button");
    btn.id = "aw-guide-trigger";
    btn.title = "Show page guide";
    btn.textContent = "?";
    btn.style.setProperty("--aw-accent", g.accent);
    btn.style.setProperty("--aw-glow", g.accent + "44");

    const tip = document.createElement("div");
    tip.id = "aw-guide-trigger-tooltip";
    tip.textContent = "Page guide";

    document.body.appendChild(btn);
    document.body.appendChild(tip);

    btn.addEventListener("click", () => showGuide(pageKey, true));
  }

  /* ─── INIT ────────────────────────────────────────────────── */

  function init() {
    const page = detectPage();

    // Show guide immediately on first visit
    // Small delay so the page itself has time to paint first
    setTimeout(() => showGuide(page, false), 420);

    // Always add the persistent ? button
    addTriggerButton(page);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();