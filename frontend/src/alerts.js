/**
 * agentwatch/frontend/src/alerts.js
 *
 * Anomaly alert overlay management.
 * When an anomaly event arrives:
 *   1. Show a red alert card in the center overlay
 *   2. "Explain This" button → calls /api/explain → shows Foundation-Sec reasoning
 */

const API_URL = window.__API_URL || 'http://localhost:8000';
const overlay = document.getElementById('anomaly-overlay');
const reasoningPanel = document.getElementById('reasoning-panel');

let activeAnomaly = null;

// ─────────────────────────────────────────────
// Show Anomaly Alert
// ─────────────────────────────────────────────

export function showAnomalyAlert(event) {
  activeAnomaly = event;
  overlay.style.display = 'flex';

  const message = event.reasoning_content || `Anomaly detected at ${event.step_name}`;
  const tool = event.tool_name || event.step_name || 'unknown';

  const card = document.createElement('div');
  card.className = 'anomaly-card';
  card.innerHTML = `
    <div class="anomaly-header">
      <span class="anomaly-icon">⚠️</span>
      <div>
        <div class="anomaly-title">Anomaly Detected</div>
        <div style="font-size:10px;color:var(--text-dim);margin-top:2px">${new Date().toLocaleTimeString()}</div>
      </div>
      <button onclick="this.closest('.anomaly-card').remove(); checkOverlayEmpty()" 
        style="margin-left:auto;background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:16px">✕</button>
    </div>
    <div class="anomaly-body">
      <strong style="color:var(--red)">${message}</strong>
    </div>
    <div class="anomaly-actions">
      <button class="btn btn-primary" onclick="explainAnomaly()">🔍 Explain This</button>
      <button class="btn btn-secondary" onclick="openSplunk('${event.trace_id}')">📊 View in Splunk</button>
      <button class="btn btn-secondary" onclick="this.closest('.anomaly-card').remove(); checkOverlayEmpty()">Dismiss</button>
    </div>
  `;

  // Remove previous cards beyond 3
  while (overlay.children.length >= 3) {
    overlay.removeChild(overlay.firstChild);
  }
  overlay.appendChild(card);

  // Auto-dismiss after 30 seconds
  setTimeout(() => {
    if (card.parentNode) {
      card.style.opacity = '0';
      card.style.transition = 'opacity 0.5s';
      setTimeout(() => { card.remove(); checkOverlayEmpty(); }, 500);
    }
  }, 30000);
}

function checkOverlayEmpty() {
  if (overlay.children.length === 0) {
    overlay.style.display = 'none';
  }
}

// ─────────────────────────────────────────────
// Explain This — calls Foundation-Sec
// ─────────────────────────────────────────────

window.explainAnomaly = async function() {
  if (!activeAnomaly) return;

  reasoningPanel.style.display = 'block';
  reasoningPanel.innerHTML = `
    <div class="reasoning-card">
      <div class="reasoning-header">
        <div class="reasoning-title">🧠 Foundation-Sec Analysis</div>
        <button class="reasoning-close" onclick="document.getElementById('reasoning-panel').style.display='none'">✕</button>
      </div>
      <div style="color:var(--text-dim);font-size:11px;text-align:center;padding:20px">
        Analyzing anomaly...<br>
        <span style="font-size:9px;animation:pulse-dot 1s infinite">▋</span>
      </div>
    </div>
  `;

  try {
    const resp = await fetch(`${API_URL}/api/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        anomaly_event: activeAnomaly,
        trace_id: activeAnomaly.trace_id,
      }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const result = await resp.json();
    renderReasoning(result);

  } catch (e) {
    // Fallback: show rule-based explanation inline
    renderReasoning(getRuleBasedExplanation(activeAnomaly));
  }
};

function renderReasoning(result) {
  const severityClass = `severity-${result.severity || 'medium'}`;

  reasoningPanel.innerHTML = `
    <div class="reasoning-card">
      <div class="reasoning-header">
        <div class="reasoning-title">🧠 Foundation-Sec Analysis</div>
        <button class="reasoning-close" onclick="document.getElementById('reasoning-panel').style.display='none'">✕</button>
      </div>

      <div class="reasoning-section">
        <h4>Severity</h4>
        <span class="severity-badge ${severityClass}">${(result.severity || 'medium').toUpperCase()}</span>
      </div>

      <div class="reasoning-section">
        <h4>What Happened</h4>
        <p>${result.explanation || '—'}</p>
      </div>

      <div class="reasoning-section">
        <h4>📋 Recommended Fix</h4>
        <p style="color:var(--accent2)">${result.recommended_action || '—'}</p>
      </div>

      ${result.splunk_spl ? `
      <div class="reasoning-section">
        <h4>🔍 Splunk SPL</h4>
        <div class="spl-code">${result.splunk_spl}</div>
      </div>` : ''}

      <div style="margin-top:16px;display:flex;gap:8px">
        <button class="btn btn-secondary" onclick="copyFix('${encodeURIComponent(result.recommended_action || '')}')">Copy Fix</button>
        <button class="btn btn-secondary" onclick="document.getElementById('reasoning-panel').style.display='none'">Close</button>
      </div>
    </div>
  `;
}

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

window.openSplunk = function(traceId) {
  const host = window.__SPLUNK_HOST || 'localhost';
  const port = window.__SPLUNK_PORT || '8000';
  const spl = encodeURIComponent(`index=agentwatch trace_id=${traceId} | sort -_time`);
  window.open(`http://${host}:${port}/en-US/app/search/search?q=${spl}`, '_blank');
};

window.copyFix = function(encoded) {
  const text = decodeURIComponent(encoded);
  navigator.clipboard.writeText(text).then(() => {
    alert('Fix suggestion copied to clipboard!');
  });
};

window.checkOverlayEmpty = checkOverlayEmpty;

function getRuleBasedExplanation(event) {
  const msg = event.reasoning_content || '';
  if (msg.toLowerCase().includes('loop')) {
    return {
      explanation: `The agent entered an infinite loop at '${event.tool_name}', calling it repeatedly without progress. This happens when the tool returns empty results and no exit condition is defined.`,
      recommended_action: `Add an empty-result guard: if ${event.tool_name} returns no results after 3 attempts, route to a fallback node. In LangGraph, add a conditional edge that checks for empty tool output.`,
      severity: 'critical',
      splunk_spl: `index=agentwatch event_type=tool_call tool_name=${event.tool_name} | stats count by trace_id | where count > 5`,
    };
  }
  return {
    explanation: `Anomalous behavior detected at ${event.step_name} with trust score ${Math.round((event.trust_score || 0) * 100)}%.`,
    recommended_action: 'Review the full event trace in Splunk for details.',
    severity: 'high',
    splunk_spl: `index=agentwatch trace_id=${event.trace_id} | sort -_time | table _time, event_type, step_name, trust_score`,
  };
}
