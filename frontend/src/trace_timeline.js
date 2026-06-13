/**
 * agentwatch/frontend/src/trace_timeline.js
 *
 * Horizontal Gantt-style trace timeline.
 * Reads directly from brain.js `nodes` Map — no new state needed.
 * Clicking a bar populates the existing #inspector-content panel.
 *
 * HOW TO WIRE (see PATCH section at bottom of this file):
 *   1. Import and call initTimeline() once in websocket.js
 *   2. Call pushTimelineEvent(event) inside handleEvent()
 *   3. Add <div id="timeline-panel"> to index.html (see patch)
 *
 * Zero conflicts — reads existing DOM IDs: #inspector-content only on click.
 */

// ── State ─────────────────────────────────────────────────────────────────
const _steps = [];          // { step_id, step_name, event_type, start_ms, end_ms, trust, tokens, tool_name }
const _stepStart = new Map(); // step_id → start timestamp ms
let _traceStart = null;
let _currentTraceId = null;

// ── Public API ────────────────────────────────────────────────────────────

export function initTimeline() {
  const panel = document.getElementById('timeline-panel');
  if (!panel) return;
  panel.innerHTML = `
    <div style="font-size:8px;color:rgba(90,112,144,1);letter-spacing:2px;
                text-transform:uppercase;padding:8px 12px 4px;
                border-bottom:1px solid rgba(100,160,255,0.1);
                display:flex;justify-content:space-between;align-items:center">
      <span>Trace Timeline</span>
      <span id="tl-trace-id" style="color:rgba(79,143,255,0.6);font-size:7px"></span>
    </div>
    <div id="tl-canvas-wrap" style="padding:6px 12px;overflow-x:auto;overflow-y:hidden">
      <div id="tl-bars" style="position:relative;min-height:32px"></div>
    </div>
  `;
}

export function pushTimelineEvent(event) {
  const type     = event.event_type || '';
  const step_id  = event.step_id   || '';
  const trace_id = event.trace_id  || '';
  const now      = Date.now();

  // New trace → reset
  if (trace_id && trace_id !== _currentTraceId) {
    _steps.length = 0;
    _stepStart.clear();
    _traceStart = now;
    _currentTraceId = trace_id;
    const el = document.getElementById('tl-trace-id');
    if (el) el.textContent = trace_id.substring(0, 12) + '…';
  }

  // step_start → record start time
  if (type === 'step_start' && step_id) {
    _stepStart.set(step_id, now);
  }

  // step_end → complete the bar
  if (type === 'step_end' && step_id) {
    const start = _stepStart.get(step_id) || now;
    _steps.push({
      step_id,
      step_name:  event.step_name  || step_id,
      event_type: type,
      start_ms:   start - (_traceStart || start),
      end_ms:     now   - (_traceStart || now),
      trust:      parseFloat(event.trust_score ?? 1.0),
      tokens:     parseInt(event.llm_total_tokens || 0, 10),
      tool_name:  event.tool_name || '',
      duration:   now - start,
    });
    _renderTimeline();
  }

  // tool_call → thin bar
  if (type === 'tool_call' && event.tool_name) {
    const start = _stepStart.get(step_id) || now;
    _steps.push({
      step_id:    step_id + ':' + event.tool_name,
      step_name:  event.tool_name,
      event_type: 'tool_call',
      start_ms:   start - (_traceStart || start),
      end_ms:     start - (_traceStart || start) + (parseFloat(event.duration_ms) || 50),
      trust:      parseFloat(event.trust_score ?? 1.0),
      tokens:     0,
      tool_name:  event.tool_name,
      duration:   parseFloat(event.duration_ms) || 50,
    });
    _renderTimeline();
  }

  // anomaly → mark it
  if (type === 'anomaly') {
    _steps.push({
      step_id:    'anomaly:' + now,
      step_name:  '⚠ ' + (event.tool_name || 'anomaly'),
      event_type: 'anomaly',
      start_ms:   now - (_traceStart || now),
      end_ms:     now - (_traceStart || now) + 80,
      trust:      parseFloat(event.trust_score ?? 0.05),
      tokens:     0,
      tool_name:  event.tool_name || '',
      duration:   80,
    });
    _renderTimeline();
  }
}

// ── Render ────────────────────────────────────────────────────────────────

function _getColor(step) {
  if (step.event_type === 'anomaly') return '#ff3355';
  if (step.event_type === 'tool_call') return '#00e5ff';
  const t = step.trust;
  if (t > 0.7) return '#00ff88';
  if (t > 0.5) return '#88ff44';
  if (t > 0.3) return '#ffcc00';
  if (t > 0.15) return '#ff8800';
  return '#ff3355';
}

function _renderTimeline() {
  const bars = document.getElementById('tl-bars');
  if (!bars || _steps.length === 0) return;

  const W = bars.parentElement.clientWidth || 400;
  const maxMs = Math.max(..._steps.map(s => s.end_ms), 100);
  const ROW_H = 14;
  const GAP   = 3;

  // Assign rows — pack overlapping bars
  const rows = [];
  const placed = _steps.map(step => {
    let row = 0;
    while (rows[row] && rows[row] > step.start_ms) row++;
    rows[row] = step.end_ms;
    return { ...step, row };
  });

  const totalH = (Math.max(...placed.map(s => s.row)) + 1) * (ROW_H + GAP);
  bars.style.height = totalH + 'px';
  bars.style.position = 'relative';

  bars.innerHTML = placed.map(step => {
    const x = (step.start_ms / maxMs) * W;
    const w = Math.max(4, ((step.end_ms - step.start_ms) / maxMs) * W);
    const y = step.row * (ROW_H + GAP);
    const color = _getColor(step);
    const label = step.step_name.length > 12
      ? step.step_name.substring(0, 11) + '…'
      : step.step_name;
    const tooltip = `${step.step_name} | ${Math.round(step.duration)}ms | trust ${Math.round(step.trust * 100)}%`;

    return `<div
      title="${tooltip}"
      data-step-id="${step.step_id}"
      onclick="window._tlClick('${step.step_id}')"
      style="
        position:absolute;
        left:${x}px;
        top:${y}px;
        width:${w}px;
        height:${ROW_H}px;
        background:${color};
        opacity:0.82;
        border-radius:2px;
        cursor:pointer;
        display:flex;
        align-items:center;
        overflow:hidden;
        transition:opacity .15s;
        box-sizing:border-box;
      "
      onmouseenter="this.style.opacity=1"
      onmouseleave="this.style.opacity=0.82"
    >${w > 30 ? `<span style="font-size:7px;color:#000;font-weight:700;padding:0 3px;white-space:nowrap;overflow:hidden">${label}</span>` : ''}</div>`;
  }).join('');
}

// ── Click handler — populates existing #inspector-content ─────────────────

window._tlClick = function(step_id) {
  const step = _steps.find(s => s.step_id === step_id);
  if (!step) return;

  const panel = document.getElementById('inspector-content');
  if (!panel) return;

  const trustPct = Math.round(step.trust * 100);
  const trustColor = step.trust > 0.7 ? '#00ff88' : step.trust > 0.4 ? '#ffcc00' : '#ff3355';

  panel.innerHTML = `
    <div class="inspector-field">
      <label>Step Name</label>
      <value>${step.step_name}</value>
    </div>
    <div class="inspector-field">
      <label>Event Type</label>
      <value>${step.event_type}</value>
    </div>
    <div class="inspector-field">
      <label>Trust Score</label>
      <value style="color:${trustColor}">${trustPct}%</value>
      <div class="trust-bar">
        <div class="trust-fill" style="width:${trustPct}%;background:${trustColor}"></div>
      </div>
    </div>
    <div class="inspector-field">
      <label>Duration</label>
      <value>${Math.round(step.duration)}ms</value>
    </div>
    ${step.tokens ? `<div class="inspector-field"><label>Tokens</label><value>${step.tokens.toLocaleString()}</value></div>` : ''}
    ${step.tool_name ? `<div class="inspector-field"><label>Tool</label><value>${step.tool_name}</value></div>` : ''}
    <div class="inspector-field">
      <label>Start offset</label>
      <value style="color:var(--text-dim)">${Math.round(step.start_ms)}ms into trace</value>
    </div>
  `;
};