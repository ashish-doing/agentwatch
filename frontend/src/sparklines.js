/**
 * agentwatch/frontend/src/sparklines.js
 *
 * Three live mini-charts below the brain:
 *   1. Token count per LLM call
 *   2. Step duration (ms) per step_end
 *   3. Trust score per event
 *
 * Pure canvas, NO external libraries — works with your existing python -m http.server setup.
 * Reads exact fields from langgraph_hooks.py / demo_agent.py:
 *   llm_total_tokens, duration_ms, trust_score, event_type
 *
 * Usage in websocket.js:
 *   import { initSparklines, pushSparklineEvent } from './sparklines.js';
 *   initSparklines();  // call once after DOM ready
 *   // inside your message handler:
 *   pushSparklineEvent(event);
 *
 * Add to index.html inside #ui-layer, above #ai-assistant:
 *   <div id="sparklines-row"></div>
 */

const MAX_POINTS = 40;  // how many data points to show

const _data = {
  tokens:  [],   // llm_total_tokens from llm_call events
  latency: [],   // duration_ms from step_end events
  trust:   [],   // trust_score from any event
};

const _config = [
  {
    key:     'tokens',
    label:   'Tokens / LLM call',
    canvasId: 'spark-tokens',
    color:   '#4f8fff',  // --accent
    maxVal:  10000,
    format:  v => v >= 1000 ? (v/1000).toFixed(1)+'k' : String(Math.round(v)),
    danger:  3000,       // threshold line
  },
  {
    key:     'latency',
    label:   'Step latency (ms)',
    canvasId: 'spark-latency',
    color:   '#00e5ff',  // --accent2
    maxVal:  5000,
    format:  v => Math.round(v) + 'ms',
    danger:  3000,
  },
  {
    key:     'trust',
    label:   'Trust score',
    canvasId: 'spark-trust',
    color:   '#00ff88',  // --green
    maxVal:  1.0,
    format:  v => (v * 100).toFixed(0) + '%',
    danger:  0.3,
    invertDanger: true,  // danger = BELOW this value
  },
];

/** Call once to inject the sparklines HTML and set up canvases. */
export function initSparklines() {
  const container = document.getElementById('sparklines-row');
  if (!container) return;

  container.style.cssText = `
    display: flex;
    gap: 8px;
    padding: 6px 12px;
    background: rgba(8,14,30,0.7);
    border-top: 1px solid rgba(100,160,255,0.1);
  `;

  container.innerHTML = _config.map(c => `
    <div style="flex:1;min-width:0">
      <div style="font-size:8px;color:rgba(90,112,144,1);letter-spacing:2px;
                  text-transform:uppercase;margin-bottom:3px;
                  display:flex;justify-content:space-between;align-items:center">
        <span>${c.label}</span>
        <span id="${c.canvasId}-val" style="color:${c.color}">—</span>
      </div>
      <canvas id="${c.canvasId}" height="36" style="width:100%;display:block"></canvas>
    </div>
  `).join('');

  // Set actual pixel widths after layout
  requestAnimationFrame(() => {
    _config.forEach(c => {
      const canvas = document.getElementById(c.canvasId);
      if (canvas) {
        canvas.width = canvas.offsetWidth || 200;
      }
    });
    _redrawAll();
  });
}

/** Call for every event received over WebSocket. */
export function pushSparklineEvent(event) {
  const type   = event.event_type  || '';
  const tokens = parseInt(event.llm_total_tokens || 0, 10);
  const dur    = parseFloat(event.duration_ms    || 0);
  const trust  = parseFloat(event.trust_score    || 1.0);

  // Tokens — only from llm_call events (matches langgraph_hooks.on_llm_call)
  if (type === 'llm_call' && tokens > 0) {
    _push('tokens', tokens);
  }

  // Latency — only from step_end events (matches langgraph_hooks.on_step_end)
  if (type === 'step_end' && dur > 0) {
    _push('latency', dur);
  }

  // Trust — every event has a trust_score
  if (trust !== undefined && type !== 'step_start') {
    _push('trust', trust);
  }

  _redrawAll();
}

function _push(key, value) {
  _data[key].push(value);
  if (_data[key].length > MAX_POINTS) _data[key].shift();
}

function _redrawAll() {
  _config.forEach(c => _drawSparkline(c));
}

function _drawSparkline(cfg) {
  const canvas = document.getElementById(cfg.canvasId);
  const valEl  = document.getElementById(`${cfg.canvasId}-val`);
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  const W = canvas.width;
  const H = canvas.height;
  const data = _data[cfg.key];

  ctx.clearRect(0, 0, W, H);

  if (data.length < 2) {
    ctx.fillStyle = 'rgba(255,255,255,0.05)';
    ctx.fillRect(0, 0, W, H);
    return;
  }

  const maxVal = Math.max(cfg.maxVal, ...data) || 1;
  const minVal = cfg.key === 'trust' ? 0 : 0;

  // ── Background ──────────────────────────────────────────────────────
  ctx.fillStyle = 'rgba(0,0,0,0.3)';
  ctx.fillRect(0, 0, W, H);

  // ── Danger threshold line ───────────────────────────────────────────
  if (cfg.danger !== undefined) {
    let dangerY;
    if (cfg.invertDanger) {
      dangerY = H - ((cfg.danger - minVal) / (maxVal - minVal)) * H;
    } else {
      dangerY = H - ((cfg.danger - minVal) / (maxVal - minVal)) * H;
    }
    ctx.beginPath();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = 'rgba(255,51,85,0.35)';
    ctx.lineWidth = 0.5;
    ctx.moveTo(0, dangerY);
    ctx.lineTo(W, dangerY);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  // ── Line ─────────────────────────────────────────────────────────────
  const stepX = W / (MAX_POINTS - 1);
  const offsetX = (MAX_POINTS - data.length) * stepX;

  // Determine current color — red if in danger zone
  const lastVal = data[data.length - 1];
  let lineColor = cfg.color;
  if (cfg.danger !== undefined) {
    const inDanger = cfg.invertDanger ? lastVal < cfg.danger : lastVal > cfg.danger;
    if (inDanger) lineColor = '#ff3355';
  }

  // Fill under the line
  ctx.beginPath();
  data.forEach((val, i) => {
    const x = offsetX + i * stepX;
    const y = H - ((val - minVal) / (maxVal - minVal)) * (H - 2) - 1;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.lineTo(offsetX + (data.length - 1) * stepX, H);
  ctx.lineTo(offsetX, H);
  ctx.closePath();
  ctx.fillStyle = lineColor + '18';  // 10% opacity fill
  ctx.fill();

  // Draw line
  ctx.beginPath();
  data.forEach((val, i) => {
    const x = offsetX + i * stepX;
    const y = H - ((val - minVal) / (maxVal - minVal)) * (H - 2) - 1;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = lineColor;
  ctx.lineWidth = 1.5;
  ctx.lineJoin = 'round';
  ctx.stroke();

  // Latest value dot
  const lastX = offsetX + (data.length - 1) * stepX;
  const lastY = H - ((lastVal - minVal) / (maxVal - minVal)) * (H - 2) - 1;
  ctx.beginPath();
  ctx.arc(lastX, lastY, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = lineColor;
  ctx.fill();

  // Update label
  if (valEl) {
    valEl.textContent = cfg.format(lastVal);
    valEl.style.color = lineColor;
  }
}