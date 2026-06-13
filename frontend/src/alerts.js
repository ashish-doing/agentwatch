/**
 * agentwatch/frontend/src/alerts.js
 * Anomaly alerts with Foundation-Sec reasoning panel.
 * TASK 4: Export Incident Report button wired into both the anomaly card
 *         and the reasoning panel.
 */

const API_URL = window.__API_URL || 'http://localhost:8001';
const SPLUNK_URL = window.__SPLUNK_URL || 'http://localhost:8000';
const overlay = document.getElementById('anomaly-overlay');
const reasoningPanel = document.getElementById('reasoning-panel');

let activeAnomaly = null;
let lastReasoningText = '';  // TASK 4: stash reasoning for PDF export

// ── Show Anomaly Alert ──────────────────────────────────────

export function showAnomalyAlert(event) {
  activeAnomaly = event;
  overlay.style.display = 'flex';

  const message = event.reasoning_content || `Anomaly detected at ${event.step_name}`;
  const tool = event.tool_name || event.step_name || 'unknown';
  const trust = Math.round((event.trust_score || 0) * 100);
  const timeStr = new Date().toLocaleTimeString();
  const traceShort = (event.trace_id || '').substring(0, 12);

  const card = document.createElement('div');
  card.className = 'anomaly-card';
  card.innerHTML = `
    <div class="anomaly-header">
      <span class="anomaly-icon">⚠️</span>
      <div style="flex:1">
        <div class="anomaly-title">Anomaly Detected</div>
        <div style="font-size:9px;color:var(--text-dim);margin-top:2px;font-family:var(--mono)">${timeStr} · trace:${traceShort}...</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
        <span style="font-size:9px;letter-spacing:1px;text-transform:uppercase;padding:2px 8px;border-radius:3px;background:rgba(255,51,85,0.2);color:var(--red);border:1px solid var(--red)">${(event.severity || 'CRITICAL').toUpperCase()}</span>
        <button onclick="this.closest('.anomaly-card').remove(); checkOverlayEmpty()"
          style="background:none;border:none;color:var(--text-dim);cursor:pointer;font-size:14px;padding:0">✕</button>
      </div>
    </div>

    <div style="background:rgba(0,0,0,0.3);border-radius:6px;padding:10px 12px;margin:10px 0;border-left:3px solid var(--red)">
      <div style="font-size:12px;color:var(--text);font-weight:700">${message}</div>
    </div>

    <div style="display:flex;gap:12px;margin:8px 0;font-size:10px;font-family:var(--mono)">
      <div style="flex:1">
        <div style="color:var(--text-dim);margin-bottom:3px">TOOL</div>
        <div style="color:var(--accent2)">${tool}</div>
      </div>
      <div style="flex:1">
        <div style="color:var(--text-dim);margin-bottom:3px">TRUST</div>
        <div style="color:var(--red)">${trust}%</div>
      </div>
      <div style="flex:1">
        <div style="color:var(--text-dim);margin-bottom:3px">AGENT</div>
        <div style="color:var(--text)">${event.agent_id || 'demo-001'}</div>
      </div>
    </div>

    <div style="height:3px;background:rgba(255,255,255,0.08);border-radius:2px;margin:10px 0;overflow:hidden">
      <div style="height:100%;width:${trust}%;background:var(--red);border-radius:2px;transition:width 0.5s"></div>
    </div>

    <div class="anomaly-actions">
      <button class="btn btn-primary" onclick="explainAnomaly()">🔍 Explain</button>
      <button class="btn btn-secondary" onclick="openSplunk('${event.trace_id}', '${tool}')">📊 Splunk</button>
      <button id="export-incident-btn" class="btn btn-secondary" onclick="window.exportIncidentReport(window._activeAnomaly, window._lastReasoning)">📄 Export PDF</button>
      <button class="btn btn-secondary" onclick="this.closest('.anomaly-card').remove(); checkOverlayEmpty()">Dismiss</button>
    </div>
  `;

  // Keep only 1 card at a time
  while (overlay.children.length >= 1) {
    overlay.removeChild(overlay.firstChild);
  }
  overlay.appendChild(card);

  // Stash on window so the export button can reach it
  window._activeAnomaly = event;
  window._lastReasoning = '';

  // Auto-dismiss after 45s
  setTimeout(() => {
    if (card.parentNode) {
      card.style.opacity = '0';
      card.style.transition = 'opacity 0.5s';
      setTimeout(() => { if (card.parentNode) { card.remove(); checkOverlayEmpty(); } }, 500);
    }
  }, 45000);
}

function checkOverlayEmpty() {
  if (overlay.children.length === 0) overlay.style.display = 'none';
}

// ── Explain This (Foundation-Sec) ────────────────────────────────────────

window.explainAnomaly = async function() {
  if (!activeAnomaly) return;

  reasoningPanel.style.display = 'block';
  reasoningPanel.innerHTML = `
    <div class="reasoning-card">
      <div class="reasoning-header">
        <div class="reasoning-title">🧠 Foundation-Sec Analysis</div>
        <button class="reasoning-close" onclick="document.getElementById('reasoning-panel').style.display='none'">✕</button>
      </div>
      <div style="padding:20px;text-align:center">
        <div style="color:var(--accent2);font-size:24px;margin-bottom:12px">⟳</div>
        <div style="color:var(--text-dim);font-size:11px">Analyzing anomaly pattern...</div>
        <div style="color:var(--text-dim);font-size:10px;margin-top:4px">Foundation-Sec-1.1-8B reasoning</div>
      </div>
    </div>
  `;

  try {
    const resp = await fetch(`${API_URL}/api/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ anomaly_event: activeAnomaly, trace_id: activeAnomaly.trace_id }),
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const result = await resp.json();
    lastReasoningText = result.explanation + '\n\n' + result.recommended_action;
    window._lastReasoning = lastReasoningText;
    renderReasoning(result);
  } catch (e) {
    const fallback = getRuleBasedExplanation(activeAnomaly);
    lastReasoningText = fallback.explanation + '\n\n' + fallback.recommended_action;
    window._lastReasoning = lastReasoningText;
    renderReasoning(fallback);
  }
};

function renderReasoning(result) {
  const severityClass = `severity-${result.severity || 'high'}`;
  reasoningPanel.innerHTML = `
    <div class="reasoning-card">
      <div class="reasoning-header">
        <div class="reasoning-title">🧠 Foundation-Sec Analysis</div>
        <button class="reasoning-close" onclick="document.getElementById('reasoning-panel').style.display='none'">✕</button>
      </div>

      <div style="display:flex;align-items:center;gap:10px;margin-bottom:16px">
        <span class="severity-badge ${severityClass}">${(result.severity || 'high').toUpperCase()}</span>
        <span style="font-size:10px;color:var(--text-dim);font-family:var(--mono)">Foundation-Sec-1.1-8B</span>
      </div>

      <div class="reasoning-section">
        <h4>What Happened</h4>
        <p>${result.explanation || '—'}</p>
      </div>

      <div class="reasoning-section">
        <h4>Root Cause</h4>
        <p style="color:var(--orange)">${result.root_cause || result.explanation || '—'}</p>
      </div>

      <div class="reasoning-section">
        <h4>📋 Recommended Fix</h4>
        <p style="color:var(--accent2)">${result.recommended_action || '—'}</p>
      </div>

      ${result.splunk_spl ? `
      <div class="reasoning-section">
        <h4>🔍 SPL Query</h4>
        <div class="spl-code">${result.splunk_spl}</div>
      </div>` : ''}

      <div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn btn-primary" onclick="openSplunk('${activeAnomaly?.trace_id}', '')">View in Splunk</button>
        <button class="btn btn-secondary" onclick="copyText('${encodeURIComponent(result.recommended_action || '')}')">Copy Fix</button>
        <button class="btn btn-accent" onclick="window.exportIncidentReport(window._activeAnomaly, window._lastReasoning)">📄 Export PDF</button>
        <button class="btn btn-secondary" onclick="document.getElementById('reasoning-panel').style.display='none'">Close</button>
      </div>
    </div>
  `;
}

// ── Splunk deep link ──────────────────────────────────────────────────────

window.openSplunk = function(traceId, toolName) {
  let spl;
  if (traceId) {
    spl = `index=agentwatch trace_id=${traceId} | sort -_time | table _time, event_type, step_name, trust_score, tool_name, reasoning_content`;
  } else if (toolName) {
    spl = `index=agentwatch tool_name=${toolName} event_type=anomaly | sort -_time`;
  } else {
    spl = `index=agentwatch event_type=anomaly | sort -_time | table _time, agent_id, tool_name, reasoning_content, trust_score`;
  }
  const encoded = encodeURIComponent(`search ${spl}`);
  window.open(`${SPLUNK_URL}/en-US/app/search/search?q=${encoded}&earliest=-1h&latest=now`, '_blank');
};

window.copyText = function(encoded) {
  navigator.clipboard.writeText(decodeURIComponent(encoded)).then(() => {
    alert('Copied to clipboard!');
  });
};

window.checkOverlayEmpty = checkOverlayEmpty;

// ── Rule-based fallback explanation ──────────────────────────────────────

function getRuleBasedExplanation(event) {
  const msg = event.reasoning_content || '';
  if (msg.toLowerCase().includes('loop')) {
    return {
      explanation: `The agent entered an infinite loop at '${event.tool_name}', calling it repeatedly without making progress. This happens when the tool returns empty or unhelpful results and the agent has no exit condition defined.`,
      root_cause: `Missing termination condition in the routing logic after '${event.tool_name}'. The agent keeps retrying because it doesn't handle the 'no results' case.`,
      recommended_action: `Add an empty-result guard: if ${event.tool_name} returns no results after 3 attempts, route to a fallback node. In LangGraph, add a conditional edge that checks for empty tool output.`,
      severity: 'critical',
      splunk_spl: `index=agentwatch event_type=tool_call tool_name=${event.tool_name} trace_id=${event.trace_id} | stats count by trace_id | where count > 5`,
    };
  }
  return {
    explanation: `Anomalous behavior detected at step '${event.step_name}' with trust score ${Math.round((event.trust_score || 0) * 100)}%.`,
    root_cause: 'Compound failure across multiple steps causing trust degradation.',
    recommended_action: `Review the full trace in Splunk and add error handling to nodes with trust_score < 0.5.`,
    severity: 'high',
    splunk_spl: `index=agentwatch trace_id=${event.trace_id} | sort -_time | table _time, event_type, step_name, trust_score`,
  };
}