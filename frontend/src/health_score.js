/**
 * agentwatch/frontend/src/health_score.js
 *
 * Agent Health Score panel — live 0–100 composite score.
 * Reads the exact same event fields that langgraph_hooks.py / demo_agent.py emit:
 *   event_type, tool_name, trust_score, llm_total_tokens, duration_ms, error
 *
 * Usage in websocket.js:
 *   import { updateHealthScore } from './health_score.js';
 *   // inside your message handler, after parsing event:
 *   updateHealthScore(event);
 *
 * Add this to index.html inside #header (after the stat-chips div):
 *   <div id="health-score-widget"></div>
 */

// ── Weights match the 5 failure modes in the README ──────────────────────
const PENALTY = {
  loop:          40,   // loop detected          → -40
  token_spike:   20,   // llm_total_tokens > 3000 → -20
  latency_drift: 20,   // duration_ms > 3000ms    → -20
  error:         15,   // any error event         → -15
  trust_low:     5,    // trust_score < 0.5       → -5 per event
};

// State — reset when a new trace starts
let _score       = 100;
let _loopFired   = false;
let _tokenFired  = false;
let _latencyFired = false;

/**
 * Call this for every event received over the WebSocket.
 * event = the raw dict from AgentEvent.to_dict() or demo_agent._send()
 */
export function updateHealthScore(event) {
  const type    = event.event_type  || '';
  const trust   = parseFloat(event.trust_score     || 1.0);
  const tokens  = parseInt(event.llm_total_tokens  || 0, 10);
  const dur     = parseFloat(event.duration_ms     || 0);
  const tool    = event.tool_name   || '';

  // ── Reset on new agent run ────────────────────────────────────────────
  if (type === 'step_start' && event.step_name === 'research') {
    const prevScore = _score;
    if (prevScore < 80) {
      // Only reset fully if previous run was bad — keeps demo dramatic
      _score = 100;
      _loopFired = false;
      _tokenFired = false;
      _latencyFired = false;
    }
  }

  // ── Anomaly event (emitted directly by langgraph_hooks._emit_anomaly) ─
  if (type === 'anomaly') {
    if (!_loopFired) {
      _score = Math.max(0, _score - PENALTY.loop);
      _loopFired = true;
    }
  }

  // ── Token spike (llm_call with high tokens) ───────────────────────────
  if (type === 'llm_call' && tokens > 3000 && !_tokenFired) {
    _score = Math.max(0, _score - PENALTY.token_spike);
    _tokenFired = true;
  }

  // ── Latency drift (step_end with high duration) ───────────────────────
  if (type === 'step_end' && dur > 3000 && !_latencyFired) {
    _score = Math.max(0, _score - PENALTY.latency_drift);
    _latencyFired = true;
  }

  // ── Error event ───────────────────────────────────────────────────────
  if (type === 'error') {
    _score = Math.max(0, _score - PENALTY.error);
  }

  // ── Continuous trust degradation ──────────────────────────────────────
  if (trust < 0.5 && type === 'tool_call') {
    _score = Math.max(0, _score - PENALTY.trust_low);
  }

  _renderHealthScore(_score);
}

/** Reset to 100 manually (e.g. when a new demo mode starts). */
export function resetHealthScore() {
  _score = 100;
  _loopFired = false;
  _tokenFired = false;
  _latencyFired = false;
  _renderHealthScore(100);
}

// ── Render ────────────────────────────────────────────────────────────────

function _getColor(score) {
  if (score >= 75) return '#00ff88';   // --green in index.html
  if (score >= 40) return '#ffcc00';   // --yellow
  if (score >= 20) return '#ff8800';   // --orange
  return '#ff3355';                    // --red
}

function _getLabel(score) {
  if (score >= 75) return 'Healthy';
  if (score >= 40) return 'Degraded';
  if (score >= 20) return 'Critical';
  return 'CRITICAL';
}

function _renderHealthScore(score) {
  const widget = document.getElementById('health-score-widget');
  if (!widget) return;

  const color = _getColor(score);
  const label = _getLabel(score);
  const rounded = Math.round(score);

  widget.innerHTML = `
    <div style="
      display:flex;
      flex-direction:column;
      align-items:center;
      background:rgba(8,14,30,0.85);
      border:1px solid rgba(100,160,255,0.15);
      border-radius:8px;
      padding:6px 16px;
      min-width:90px;
    ">
      <div style="
        font-size:22px;
        font-weight:700;
        color:${color};
        line-height:1;
        transition:color 0.5s ease;
        font-family:'Space Mono',monospace;
      ">${rounded}</div>
      <div style="
        font-size:8px;
        color:rgba(90,112,144,1);
        letter-spacing:2px;
        text-transform:uppercase;
        margin-top:3px;
      ">Health</div>
      <div style="
        font-size:8px;
        color:${color};
        margin-top:2px;
        font-weight:700;
        letter-spacing:1px;
      ">${label}</div>
      <div style="
        margin-top:5px;
        height:2px;
        width:60px;
        background:rgba(255,255,255,0.08);
        border-radius:1px;
        overflow:hidden;
      ">
        <div style="
          height:100%;
          width:${rounded}%;
          background:${color};
          border-radius:1px;
          transition:width 0.8s ease, background 0.5s ease;
        "></div>
      </div>
    </div>
  `;
}