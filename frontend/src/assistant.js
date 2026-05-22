/**
 * agentwatch/frontend/src/assistant.js
 *
 * Splunk AI Assistant integration.
 * Takes a natural language query → sends to /api/query
 * → displays generated SPL + results.
 */

const API_URL = window.__API_URL || 'http://localhost:8000';

const nlInput = document.getElementById('nl-query');
const splOutput = document.getElementById('spl-output');
const resultsList = document.getElementById('results-list');

// ─────────────────────────────────────────────
// Submit Query
// ─────────────────────────────────────────────

window.submitQuery = async function() {
  const query = nlInput.value.trim();
  if (!query) return;

  splOutput.textContent = 'Generating SPL...';
  splOutput.style.color = 'var(--text-dim)';
  resultsList.innerHTML = '<div style="color:var(--text-dim);font-size:10px">Loading...</div>';

  try {
    const resp = await fetch(`${API_URL}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ natural_language: query }),
    });

    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    splOutput.textContent = data.spl;
    splOutput.style.color = 'var(--accent2)';

    renderResults(data.results, data.result_count);

  } catch (e) {
    // Offline fallback: show what SPL would look like
    const mockSpl = mockGenerateSPL(query);
    splOutput.textContent = mockSpl;
    splOutput.style.color = 'var(--accent2)';
    resultsList.innerHTML = '<div style="color:var(--text-dim);font-size:10px">Connect Splunk to see results</div>';
  }
};

// Enter key support
nlInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') window.submitQuery();
});

// ─────────────────────────────────────────────
// Render Results
// ─────────────────────────────────────────────

function renderResults(results, count) {
  if (!results || results.length === 0) {
    resultsList.innerHTML = '<div style="color:var(--text-dim);font-size:10px">No results</div>';
    return;
  }

  const cols = ['_time', 'event_type', 'step_name', 'trust_score', 'tool_name', 'count', 'error'];
  const html = results.slice(0, 8).map(row => {
    const fields = cols
      .filter(c => row[c] !== undefined && row[c] !== '')
      .map(c => {
        let val = row[c];
        let valStyle = '';
        if (c === 'trust_score') {
          const pct = Math.round(parseFloat(val) * 100);
          const color = pct > 70 ? 'var(--green)' : pct > 40 ? 'var(--yellow)' : 'var(--red)';
          val = `${pct}%`;
          valStyle = `color:${color}`;
        }
        if (c === '_time') val = val.replace('T', ' ').substring(0, 19);
        return `<div class="result-row">
          <span class="result-key">${c}</span>
          <span class="result-val" style="${valStyle}">${String(val).substring(0, 40)}</span>
        </div>`;
      }).join('');
    return fields;
  }).join('<div style="margin:6px 0;border-top:1px solid rgba(255,255,255,0.05)"></div>');

  resultsList.innerHTML = html + (count > 8 ? `<div style="color:var(--text-dim);font-size:9px;margin-top:8px">+${count - 8} more rows</div>` : '');
}

// ─────────────────────────────────────────────
// Offline SPL Generator (mirrors backend template logic)
// ─────────────────────────────────────────────

function mockGenerateSPL(nl) {
  const q = nl.toLowerCase();
  if (q.includes('loop')) return 'index=agentwatch event_type=anomaly | stats count by tool_name, trace_id | where count > 5 | sort -count';
  if (q.includes('token') || q.includes('spike')) return 'index=agentwatch event_type=llm_call | stats max(llm_total_tokens) as max_tokens by trace_id, step_name | where max_tokens > 3000 | sort -max_tokens';
  if (q.includes('trust')) return 'index=agentwatch | stats avg(trust_score) as avg_trust by tool_name | sort avg_trust | head 10';
  if (q.includes('error')) return 'index=agentwatch event_type=error | stats count by step_name, error | sort -count';
  if (q.includes('anomal')) return 'index=agentwatch event_type=anomaly | sort -_time | table _time, agent_id, tool_name, reasoning_content, trust_score';
  if (q.includes('slow') || q.includes('latency')) return 'index=agentwatch | stats avg(duration_ms) as avg_ms, max(duration_ms) as max_ms by step_name | sort -avg_ms | head 10';
  return 'index=agentwatch | sort -_time | table _time, event_type, step_name, trust_score, tool_name | head 50';
}

// ─────────────────────────────────────────────
// Preset Query Buttons (populate the input)
// ─────────────────────────────────────────────

const PRESET_QUERIES = [
  'Show me all loops in the last hour',
  'Which tools have the lowest trust scores?',
  'Find token spikes above 3000',
  'Show all anomalies today',
  'What are the slowest steps?',
];

// Inject preset chips below the input
const queryPanel = document.getElementById('query-panel');
const presetRow = document.createElement('div');
presetRow.style.cssText = 'display:flex;gap:6px;padding:8px 16px;flex-wrap:wrap;border-top:1px solid var(--border)';

for (const q of PRESET_QUERIES) {
  const chip = document.createElement('button');
  chip.textContent = q;
  chip.style.cssText = `
    background: rgba(79,143,255,0.08);
    border: 1px solid rgba(79,143,255,0.2);
    color: var(--text-dim);
    border-radius: 4px;
    padding: 3px 10px;
    font-family: var(--mono);
    font-size: 9px;
    cursor: pointer;
    transition: all 0.15s;
  `;
  chip.onmouseover = () => { chip.style.color = 'var(--accent2)'; chip.style.borderColor = 'var(--accent2)'; };
  chip.onmouseout = () => { chip.style.color = 'var(--text-dim)'; chip.style.borderColor = 'rgba(79,143,255,0.2)'; };
  chip.onclick = () => {
    nlInput.value = q;
    window.submitQuery();
  };
  presetRow.appendChild(chip);
}

queryPanel.appendChild(presetRow);
