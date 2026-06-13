/**
 * agentwatch/frontend/src/websocket.js
 *
 * Connects to the FastAPI WebSocket backend.
 * Receives agent events and routes them to:
 *   - brain.js (Three.js visualization)
 *   - alerts.js (anomaly overlays)
 *   - The live event feed panel
 */

import { updateHealthScore } from './health_score.js';
import { initSparklines, pushSparklineEvent } from './sparklines.js';
import { initTimeline, pushTimelineEvent } from './trace_timeline.js';
import { checkRunComplete } from './autopsy_panel.js';
import { addOrUpdateNode } from './brain.js';
import { showAnomalyAlert } from './alerts.js';

// In production (served from the FastAPI backend itself, e.g. on
// Railway), derive the WS URL from the current page's host so it works
// on whatever domain the app is deployed to. window.__WS_URL can still
// override this for local dev (e.g. frontend on :3000, backend on :8001).
const WS_URL = window.__WS_URL || (() => {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // Local dev convenience: if running the old `python -m http.server 3000`
  // setup, fall back to localhost:8001 for the backend.
  if (window.location.port === '3000') {
    return 'ws://localhost:8001/ws/browser';
  }
  return `${proto}//${window.location.host}/ws/browser`;
})();
const connStatus = document.getElementById('conn-status');
const feedList = document.getElementById('feed-list');

let ws = null;
let reconnectDelay = 1000;
let eventCount = 0;

// ─────────────────────────────────────────────
// Connection
// ─────────────────────────────────────────────

function connect() {
  connStatus.textContent = '◌ Connecting...';
  connStatus.style.color = 'var(--text-dim)';

  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    connStatus.textContent = '⬤ Connected';
    connStatus.style.color = 'var(--green)';
    reconnectDelay = 1000;
    console.log('[AgentWatch] WebSocket connected');
    initSparklines();
    initTimeline();

    // Heartbeat
    setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, 15000);
  };

  ws.onmessage = (msg) => {
    try {
      const payload = JSON.parse(msg.data);

      if (payload.type === 'replay') {
        // Batch replay of recent events on connect
        for (const event of payload.events) {
          handleEvent(event, false);  // silent = don't show alerts for replay
        }
        return;
      }

      if (payload.type === 'event') {
        handleEvent(payload.data, true);
        return;
      }

      if (payload.type === 'pong') return;

    } catch (e) {
      console.error('[AgentWatch] WS parse error:', e);
    }
  };

  ws.onerror = () => {
    connStatus.textContent = '⬤ Error';
    connStatus.style.color = 'var(--red)';
  };

  ws.onclose = () => {
    connStatus.textContent = '⬤ Disconnected — retrying...';
    connStatus.style.color = 'var(--orange)';
    setTimeout(connect, reconnectDelay);
    reconnectDelay = Math.min(reconnectDelay * 1.5, 10000);
  };
}

// ─────────────────────────────────────────────
// Event Handling
// ─────────────────────────────────────────────

function handleEvent(event, showAlerts = true) {
  eventCount++;
  updateHealthScore(event);
  pushSparklineEvent(event);
  pushTimelineEvent(event);
  checkRunComplete(event);

  // Route to Three.js brain
  addOrUpdateNode(event);

  // Route to event feed (skip step_start spam in feed)
  if (event.event_type !== 'step_start') {
    addToFeed(event);
  }

  // Route anomalies to alert overlay
  if (event.event_type === 'anomaly' && showAlerts) {
    showAnomalyAlert(event);
  }
}

// ─────────────────────────────────────────────
// Event Feed Panel
// ─────────────────────────────────────────────

const MAX_FEED_ITEMS = 60;

function addToFeed(event) {
  const item = document.createElement('div');
  item.className = `feed-item ${event.event_type}`;

  const typeLabel = {
    llm_call: '🧠 LLM',
    tool_call: '🔧 TOOL',
    step_end: '✅ STEP',
    anomaly: '⚠️ ANOMALY',
    error: '❌ ERROR',
  }[event.event_type] || event.event_type;

  const meta = buildMeta(event);

  item.innerHTML = `
    <div class="feed-type">${typeLabel}</div>
    <div class="feed-name">${event.step_name || event.tool_name || 'unknown'}</div>
    <div class="feed-meta">${meta}</div>
  `;

  feedList.prepend(item);

  // Remove old items
  while (feedList.children.length > MAX_FEED_ITEMS) {
    feedList.removeChild(feedList.lastChild);
  }
}

function buildMeta(event) {
  const parts = [];
  if (event.duration_ms) parts.push(`${Math.round(event.duration_ms)}ms`);
  if (event.llm_total_tokens) parts.push(`${event.llm_total_tokens} tok`);
  if (event.trust_score != null) {
    const pct = Math.round(event.trust_score * 100);
    const color = pct > 70 ? '#00ff88' : pct > 40 ? '#ffcc00' : '#ff3355';
    parts.push(`<span style="color:${color}">trust ${pct}%</span>`);
  }
  if (event.tool_name && event.event_type === 'tool_call') parts.push(event.tool_name);
  if (event.error) parts.push(`<span style="color:#ff8800">${event.error.substring(0, 40)}</span>`);
  return parts.join(' · ') || '—';
}

// ─────────────────────────────────────────────
// Demo: simulate events if no WS (for static preview)
// ─────────────────────────────────────────────

function startDemoSimulation() {
  connStatus.textContent = '⬤ Demo Mode';
  connStatus.style.color = 'var(--yellow)';

  const demoEvents = [
    { event_type: 'step_start', step_id: 'step-001', step_name: 'research', agent_id: 'demo-001', trust_score: 1.0, trace_id: 'abc123' },
    { event_type: 'llm_call', step_id: 'step-001', step_name: 'research', agent_id: 'demo-001', trust_score: 0.95, llm_total_tokens: 847, llm_model: 'gpt-4o-mini', trace_id: 'abc123' },
    { event_type: 'tool_call', step_id: 'step-002', step_name: 'tool:search_tool', tool_name: 'search_tool', agent_id: 'demo-001', trust_score: 0.88, duration_ms: 234, trace_id: 'abc123' },
    { event_type: 'tool_call', step_id: 'step-003', step_name: 'tool:search_tool', tool_name: 'search_tool', agent_id: 'demo-001', trust_score: 0.75, duration_ms: 198, trace_id: 'abc123' },
    { event_type: 'step_end', step_id: 'step-001', step_name: 'research', agent_id: 'demo-001', trust_score: 0.9, duration_ms: 1200, trace_id: 'abc123' },
    { event_type: 'llm_call', step_id: 'step-004', step_name: 'analysis', agent_id: 'demo-001', trust_score: 0.85, llm_total_tokens: 1203, trace_id: 'abc123' },
    { event_type: 'tool_call', step_id: 'step-005', step_name: 'tool:calculator_tool', tool_name: 'calculator_tool', agent_id: 'demo-001', trust_score: 0.92, duration_ms: 12, trace_id: 'abc123' },
    // Loop starts
    { event_type: 'tool_call', step_id: 'step-006', step_name: 'tool:search_tool', tool_name: 'search_tool', agent_id: 'demo-001', trust_score: 0.60, duration_ms: 210, trace_id: 'abc123' },
    { event_type: 'tool_call', step_id: 'step-006', step_name: 'tool:search_tool', tool_name: 'search_tool', agent_id: 'demo-001', trust_score: 0.42, duration_ms: 215, trace_id: 'abc123' },
    { event_type: 'tool_call', step_id: 'step-006', step_name: 'tool:search_tool', tool_name: 'search_tool', agent_id: 'demo-001', trust_score: 0.28, duration_ms: 208, trace_id: 'abc123' },
    { event_type: 'tool_call', step_id: 'step-006', step_name: 'tool:search_tool', tool_name: 'search_tool', agent_id: 'demo-001', trust_score: 0.18, duration_ms: 225, trace_id: 'abc123' },
    // Anomaly fires
    { event_type: 'anomaly', step_id: 'step-006', step_name: 'tool:search_tool', tool_name: 'search_tool', agent_id: 'demo-001', trust_score: 0.05, reasoning_content: 'Loop detected — search_tool called 23x in 4s', trace_id: 'abc123' },
  ];

  let i = 0;
  const run = () => {
    if (i < demoEvents.length) {
      handleEvent(demoEvents[i], true);
      i++;
      setTimeout(run, 600 + Math.random() * 400);
    } else {
      // Loop the demo after a pause
      setTimeout(() => { i = 0; run(); }, 5000);
    }
  };
  setTimeout(run, 1000);
}

// ─────────────────────────────────────────────
// Start
// ─────────────────────────────────────────────

// Try real WS first; fall back to demo simulation after 3s
const timeout = setTimeout(() => {
  if (!ws || ws.readyState !== WebSocket.OPEN) {
    console.log('[AgentWatch] WS unavailable — starting demo simulation');
    startDemoSimulation();
  }
}, 3000);

connect();