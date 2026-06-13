/**
 * agentwatch/frontend/src/autopsy_panel.js
 *
 * Agent Autopsy panel — triggered when agent run completes (synthesis step_end).
 * Calls POST /api/autopsy and renders results in the existing #reasoning-panel.
 *
 * HOW TO WIRE (1 line in websocket.js — see comment at bottom):
 *   import { checkRunComplete } from './autopsy_panel.js';
 *   // inside handleEvent(), add: checkRunComplete(event);
 *
 * Zero conflicts — only writes to #reasoning-panel (same as alerts.js)
 * but only fires AFTER agent run completes, never during active anomalies.
 */

const API_URL = window.__API_URL || 'http://localhost:8001';

const GRADE_COLOR = {
  A: '#00ff88',
  B: '#88ff44',
  C: '#ffcc00',
  D: '#ff8800',
  F: '#ff3355',
};

const SEVERITY_COLOR = {
  healthy:  '#00ff88',
  degraded: '#ffcc00',
  critical: '#ff3355',
};

// Track if autopsy already shown for this trace
let _lastAutopsyTrace = null;
let _autopsyPending = false;

/**
 * Call this for every event inside handleEvent().
 * Triggers autopsy when synthesis step_end fires — meaning the agent run is complete.
 */
export function checkRunComplete(event) {
  // Synthesis step_end = agent run complete
  if (
    event.event_type === 'step_end' &&
    event.step_name === 'synthesis' &&
    event.trace_id !== _lastAutopsyTrace &&
    !_autopsyPending
  ) {
    _lastAutopsyTrace = event.trace_id;
    _autopsyPending = true;

    // Small delay so the last events finish indexing
    setTimeout(() => {
      _runAutopsy(event.trace_id);
    }, 1200);
  }
}

async function _runAutopsy(trace_id) {
  const panel = document.getElementById('reasoning-panel');
  if (!panel) { _autopsyPending = false; return; }

  // Show loading state
  panel.style.display = 'block';
  panel.innerHTML = `
    <div class="reasoning-card" style="border-color:var(--accent2)">
      <div class="reasoning-header">
        <div class="reasoning-title">🔬 Agent Autopsy</div>
        <button class="reasoning-close" onclick="document.getElementById('reasoning-panel').style.display='none'">✕</button>
      </div>
      <div style="padding:16px;text-align:center">
        <div style="color:var(--accent2);font-size:20px;animation:spin 1s linear infinite">◌</div>
        <div style="color:var(--text-dim);font-size:11px;margin-top:8px">Foundation-Sec analyzing full trace...</div>
        <div style="color:var(--text-dim);font-size:9px;margin-top:4px;opacity:0.6">trace: ${(trace_id||'').substring(0,12)}…</div>
      </div>
    </div>
    <style>
      @keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
    </style>
  `;

  try {
    const resp = await fetch(`${API_URL}/api/autopsy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trace_id, last_n_events: 200 }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    _renderAutopsy(data, trace_id);

  } catch (e) {
    // Show offline message — don't break anything
    panel.innerHTML = `
      <div class="reasoning-card" style="border-color:var(--text-dim)">
        <div class="reasoning-header">
          <div class="reasoning-title">🔬 Agent Autopsy</div>
          <button class="reasoning-close" onclick="document.getElementById('reasoning-panel').style.display='none'">✕</button>
        </div>
        <div style="padding:16px;font-size:11px;color:var(--text-dim)">
          Backend not connected — run the FastAPI server to see autopsy reports.
        </div>
      </div>
    `;
  } finally {
    _autopsyPending = false;
  }
}

function _renderAutopsy(data, trace_id) {
  const panel = document.getElementById('reasoning-panel');
  if (!panel) return;

  const grade = data.performance_grade || 'B';
  const gradeColor = GRADE_COLOR[grade] || '#ffcc00';
  const severity = data.severity || 'healthy';
  const severityColor = SEVERITY_COLOR[severity] || '#ffcc00';
  const source = data._source || 'foundation-sec';
  const ctx = data._context || {};

  const successes = (data.successes || []).map(s =>
    `<div style="display:flex;gap:6px;margin-bottom:4px">
       <span style="color:var(--green);flex-shrink:0">✓</span>
       <span style="font-size:11px;color:var(--text);line-height:1.5">${s}</span>
     </div>`
  ).join('');

  panel.style.display = 'block';
  panel.innerHTML = `
    <div class="reasoning-card" style="border-color:${gradeColor}40;max-height:80vh;overflow-y:auto">
      <div class="reasoning-header">
        <div class="reasoning-title">🔬 Agent Autopsy</div>
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:9px;color:var(--text-dim);font-family:var(--mono)">${source}</span>
          <button class="reasoning-close" onclick="document.getElementById('reasoning-panel').style.display='none'">✕</button>
        </div>
      </div>

      <!-- Grade + Severity -->
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;padding:12px;
                  background:rgba(0,0,0,0.3);border-radius:8px">
        <div style="text-align:center">
          <div style="font-size:36px;font-weight:700;color:${gradeColor};line-height:1;font-family:var(--mono)">${grade}</div>
          <div style="font-size:8px;color:var(--text-dim);letter-spacing:2px;text-transform:uppercase;margin-top:2px">Grade</div>
        </div>
        <div style="flex:1">
          <div style="font-size:11px;color:var(--text);margin-bottom:4px">${data.grade_reason || ''}</div>
          <span style="font-size:9px;padding:2px 8px;border-radius:3px;border:1px solid ${severityColor};color:${severityColor};text-transform:uppercase;letter-spacing:1px">${severity}</span>
        </div>
        <div style="text-align:right">
          <div style="font-size:14px;font-weight:700;color:var(--accent2)">${data.key_metric || ''}</div>
          <div style="font-size:8px;color:var(--text-dim);margin-top:2px">Key metric</div>
        </div>
      </div>

      <!-- Objective -->
      <div class="reasoning-section">
        <h4>Objective</h4>
        <p>${data.objective || '—'}</p>
      </div>

      <!-- Successes -->
      ${successes ? `
      <div class="reasoning-section">
        <h4>What Worked</h4>
        ${successes}
      </div>` : ''}

      <!-- Root Cause -->
      ${data.root_cause ? `
      <div class="reasoning-section">
        <h4>Root Cause</h4>
        <p style="color:var(--orange)">${data.root_cause}</p>
      </div>` : ''}

      <!-- Fix -->
      ${data.fix_recommendation ? `
      <div class="reasoning-section">
        <h4>📋 Fix Recommendation</h4>
        <p style="color:var(--accent2)">${data.fix_recommendation}</p>
      </div>` : ''}

      <!-- Stats row -->
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin:12px 0;
                  background:rgba(0,0,0,0.3);border-radius:6px;padding:10px">
        <div style="text-align:center">
          <div style="font-size:14px;font-weight:700;color:var(--accent2)">${(ctx.total_tokens||0).toLocaleString()}</div>
          <div style="font-size:8px;color:var(--text-dim);margin-top:2px">Tokens</div>
        </div>
        <div style="text-align:center">
          <div style="font-size:14px;font-weight:700;color:var(--yellow)">$${data.estimated_cost_usd || '0.00'}</div>
          <div style="font-size:8px;color:var(--text-dim);margin-top:2px">Est. Cost</div>
        </div>
        <div style="text-align:center">
          <div style="font-size:14px;font-weight:700;color:${ctx.anomaly_count > 0 ? 'var(--red)' : 'var(--green)'}">${ctx.anomaly_count || 0}</div>
          <div style="font-size:8px;color:var(--text-dim);margin-top:2px">Anomalies</div>
        </div>
      </div>

      <!-- Actions -->
      <div style="display:flex;gap:8px;margin-top:4px;flex-wrap:wrap">
        <button class="btn btn-secondary" onclick="_copyAutopsyReport()" style="font-size:9px">
          📋 Copy Report
        </button>
        <button class="btn btn-secondary" onclick="document.getElementById('reasoning-panel').style.display='none'" style="font-size:9px">
          Close
        </button>
      </div>
    </div>
  `;

  // Store for copy
  window._lastAutopsyData = data;
}

window._copyAutopsyReport = function() {
  if (!window._lastAutopsyData) return;
  const d = window._lastAutopsyData;
  const text = [
    `AgentWatch Autopsy Report`,
    `========================`,
    `Grade: ${d.performance_grade} | Severity: ${d.severity}`,
    `${d.grade_reason}`,
    ``,
    `Objective: ${d.objective}`,
    d.root_cause ? `Root Cause: ${d.root_cause}` : null,
    d.fix_recommendation ? `Fix: ${d.fix_recommendation}` : null,
    `Key Metric: ${d.key_metric}`,
    `Est. Cost: $${d.estimated_cost_usd}`,
    `Source: ${d._source}`,
  ].filter(Boolean).join('\n');

  navigator.clipboard.writeText(text).then(() => {
    alert('Autopsy report copied to clipboard!');
  });
};