# 🧠 AgentWatch
### AI Agent Observability Platform for Splunk

<p align="center">
  <img src="https://img.shields.io/badge/Splunk-MCP%20Server-FF4500?style=for-the-badge&logo=splunk" />
  <img src="https://img.shields.io/badge/Splunk-AI%20Toolkit-FF4500?style=for-the-badge&logo=splunk" />
  <img src="https://img.shields.io/badge/Foundation--Sec-1.1--8B-00B4D8?style=for-the-badge" />
  <img src="https://img.shields.io/badge/LangGraph-0.2.28-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/OpenTelemetry-1.27.0-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Three.js-r128-black?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python" />
</p>

<p align="center">
  <strong>Splunk Agentic Ops Hackathon 2026 — Track: Platform & Developer Experience</strong>
</p>

<p align="center">
  🌐 <a href="https://ashish-doing.github.io/agentwatch">Landing Page</a> &nbsp;•&nbsp;
  🚀 <a href="https://agentwatch-production-4a86.up.railway.app">Live Demo</a> &nbsp;•&nbsp;
  ⚡ <a href="#quick-start">Quick Start</a> &nbsp;•&nbsp;
  🏗️ <a href="#architecture">Architecture</a> &nbsp;•&nbsp;
  📋 <a href="architecture_diagram.md">Full Diagram</a>
</p>

---

![AgentWatch Demo](docs/screenshots/demo.gif)

---

## The Problem Nobody's Solving (Until Now)

**1,269 events indexed. 180 anomalies detected. 5 Splunk AI capabilities unified in a single pipeline.**

AI agents are entering production every day — and failing silently. When your LangGraph agent calls the same tool 23 times in 4 seconds, when token counts spike to 8,000+, when trust scores collapse to 5% — nobody notices until users are screaming or your API bill arrives. AgentWatch is the first Splunk-native platform that watches every heartbeat of your AI agent in real time, catches failures before they cascade, and explains them in plain English.

---

## 🔥 The Problem

The world is filling with AI agents that **fail silently**.

- **34%** of production AI agents fail silently due to missing observability tooling
- Loop failures cost enterprises **$2,400/hour** in wasted API calls
- Mean time to detect an agent failure: **4.2 hours**
- **Zero** enterprise-grade observability tools exist for LangGraph agents on Splunk

When your agent gets stuck calling the same tool 23 times, nobody knows. When token counts spike to 8,000+, nobody notices. When latency drifts 300% over 2 hours, nobody catches it.

**Until now.**

---

## 💡 The Solution

**AgentWatch** is a Splunk Platform app that wraps any LangGraph agent with OpenTelemetry, streams its behavior into Splunk in real time, detects anomalies automatically, explains them in plain English with Foundation-Sec-1.1-8B, and runs a full post-run **Agent Autopsy** graded A–F.

**One click:** "Explain this anomaly" → plain English root cause + recommended fix + SPL query.  
**End of run:** "Run Autopsy" → performance grade, cost estimate, and fix recommendation.

---

## ⚔️ Why AgentWatch?

| Capability | AgentWatch | LangSmith | Arize Phoenix | No Observability |
|---|---|---|---|---|
| **Splunk-native** | ✅ First & only | ❌ SaaS only | ❌ SaaS only | — |
| **Real-time anomaly detection** | ✅ Native SPL `anomalydetection` + in-process pre-filter | ⚠️ Manual rules | ⚠️ Drift metrics only | ❌ |
| **Plain-English root cause** | ✅ Foundation-Sec-1.1-8B | ❌ | ❌ | ❌ |
| **Post-run Agent Autopsy** | ✅ Graded A–F with cost estimate | ❌ | ❌ | ❌ |
| **NL → SPL query generation** | ✅ Splunk AI Assistant | ❌ | ❌ | ❌ |
| **Loop detection** | ✅ Statistical (99.25% confidence) | ⚠️ Rule-based | ❌ | ❌ |
| **Zero-config SDK** | ✅ `@watch` / `watch_graph` decorator | ⚠️ Manual | ⚠️ Manual | ❌ |
| **Live demo (no setup)** | ✅ One-click Railway deploy | ❌ | ❌ | — |
| **Works inside enterprise Splunk** | ✅ On-prem + Cloud | ❌ | ❌ | — |
| **Open source** | ✅ MIT | ❌ Proprietary | ✅ | — |

AgentWatch is the **only observability tool built natively on Splunk** — every agent event is instantly searchable with SPL, anomaly detection runs on real Splunk infrastructure, and security teams can audit agent behavior in the same platform they already use.

---

## 🏗️ Architecture

![AgentWatch Architecture Diagram](architecture.png)

The full annotated diagram with data-flow details lives in [`architecture_diagram.md`](architecture_diagram.md).

**How it flows:**

```
YOUR LANGGRAPH AGENT
         │
         ▼
[AgentWatch SDK — @watch / watch_graph]
 Zero-config wrapper:
 ├── @watch(agent_name="my_agent")      → decorate individual nodes
 ├── watch_graph(compiled, ...)         → instrument entire graph in one line
 └── AgentWatchContext(...)             → scoped trace per run
         │
         ▼
[OpenTelemetry Instrumentation]
 Captures every:
 ├── LLM call         → model, tokens, latency, reasoning
 ├── Tool call        → name, input, output, duration
 ├── Reasoning step   → step_id, content, trust score
 └── Error/exception  → full context
         │
         ├─────────────────────────────────────────┐
         ▼                                         ▼
[FastAPI + WebSocket]                   [Three.js Live Brain Graph]
 Real-time event fan-out                Force-directed visualization:
 500-event ring buffer                  ├── Nodes  = reasoning steps
                                        ├── Edges  = execution flow
         │                              ├── Color  = trust score (green → red)
         ▼                              ├── Size   = token count
[AnomalyDetector — in-process]          └── Pulse  = anomaly detected
 Pre-filter before Splunk:
 ├── Tool call frequency  → loop detection
 ├── Token count spikes   → runaway generation
 ├── Latency patterns     → drift detection
 ├── Error rate trends    → burst detection
 └── Trust collapse       → composite score < 0.3
         │
         ▼
[Splunk HEC]
 index: agentwatch
 sourcetype: agentwatch:otel
         │
         ▼
[Splunk MCP Server] ◄─── All events instantly searchable via SPL
         │
         ▼
[Splunk AI Toolkit — anomalydetection]
 Statistical time-series analysis:
 ├── Tool call frequency → loop detection
 ├── Token count spikes  → runaway generation
 ├── Latency patterns    → drift detection
 └── Error rate trends   → silent failure
         │
         ▼
[Foundation-Sec-1.1-8B] ◄─── Splunk hosted model
 "Explain This" button:
   Input:  anomaly context + last 10 agent events
   Output: what happened · root cause · recommended fix · severity

 "Run Autopsy" (POST /api/autopsy):
   Input:  full trace
   Output: performance grade A–F · cost estimate · fix recommendation
         │
         ▼
[Splunk AI Assistant] ◄─── NL → SPL
 "Show me all loops in the last hour"
  → generates SPL → queries Splunk → returns results
         │
         ▼
[Dashboard Alert Overlay]
 ⚠️  "Loop detected — search_tool called 23x in 4s"
 📋  "Fix: add empty-result guard at step 3"
 🔍  "View in Splunk" → deep link to full trace
```

---

## 📸 Screenshots

### 🧠 Live Brain Visualization — Loop Anomaly Detected
![AgentWatch brain visualization showing live anomaly detection with Foundation-Sec explanation](docs/screenshots/screenshot-hero.png)
*510 events · 42 anomalies · Loop detected — search_tool called 23x · Foundation-Sec root cause + fix recommendation*

### 📊 Splunk Dashboard — Real Telemetry Data
![AgentWatch Splunk dashboard showing 1269 events, 180 anomalies, 59.7% trust score](docs/screenshots/screenshot-dashboard-top.png)
*1,269 events · 180 anomalies · 59.7% avg trust score · 159,970 tokens — all real data*

![AgentWatch Splunk dashboard bottom panels showing anomaly table and full event log](docs/screenshots/screenshot-dashboard-bottom.png)
*Loop detection chart, anomaly table, trust heatmap, latency drift, full event log*

### 🔍 Splunk Anomaly Detection — Statistical Analysis
![AgentWatch Splunk anomaly detection report showing 139 tool call spike](docs/screenshots/screenshot-anomaly-detection.png)
*Native Splunk anomalydetection caught a 139-tool-call spike with 99.25% confidence*

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent Framework | LangGraph 0.2.28 | The agent being monitored |
| Observability | OpenTelemetry SDK 1.27.0 | Capture every LLM/tool call |
| SDK | `agentwatch_sdk.py` | Zero-config `@watch` / `watch_graph` decorator |
| Event Transport | Splunk HEC (port 8088) | Real-time telemetry delivery |
| Event Indexing | Splunk MCP Server | All telemetry searchable via SPL |
| Anomaly Detection (in-process) | `AnomalyDetector` | Pre-filter: loop, spike, drift, error burst, trust collapse |
| Anomaly Detection (Splunk) | Splunk AI Toolkit — `anomalydetection` | Statistical time-series scoring |
| Reasoning Engine | Foundation-Sec-1.1-8B | Plain English anomaly explanation + Agent Autopsy |
| NL Queries | Splunk AI Assistant | Natural language → SPL |
| Backend API | FastAPI + WebSocket | Real-time event streaming + demo trigger |
| 3D Visualization | Three.js r128 | Live brain graph |
| Frontend Modules | Health score, sparklines, trace timeline, autopsy panel | Dashboard UI |
| Deployment | Railway | One-click live demo (no Splunk needed) |
| Frontend Hosting | GitHub Pages | Landing page |

---

## ✅ Splunk AI Capabilities Used

| Capability | How AgentWatch Uses It |
|-----------|-------|
| **Splunk MCP Server** | All agent telemetry indexed; SPL queries run directly from the UI panel |
| **Splunk AI Toolkit** | `anomalydetection` command on tool-call time-series — caught 180 anomalies with statistical scoring |
| **Foundation-Sec-1.1-8B** | Powers "Explain This" (per-anomaly) and "Run Autopsy" (full-trace graded report) |
| **Splunk AI Assistant** | Natural language to SPL; type "show me all loops in the last hour" and get live results |

---

## 📊 What AgentWatch Detects

| Failure Mode | Detection Method | Alert Level |
|-------------|-----------------|-------------|
| Infinite loops | Tool call frequency — in-process + Splunk `anomalydetection` | ⚠️ CRITICAL |
| Token spikes | LLM token count outlier (threshold: 3,000) | ⚠️ HIGH |
| Latency drift | Step duration trend — monotonic increase detection | ⚠️ MEDIUM |
| Error burst | ≥ 3 errors in one trace | ⚠️ HIGH |
| Trust collapse | Composite score ≤ 0.3 | ⚠️ CRITICAL |

---

## 🔭 AgentWatch SDK

Zero-config instrumentation for any LangGraph agent or Python function.

### Installation

No new packages needed — `websockets` and `httpx` are already in `requirements.txt`.

```bash
# Copy agentwatch_sdk.py into your backend/ folder, then:
from agentwatch_sdk import watch, watch_graph, emit_event
```

### Usage

**Option A — Decorate individual nodes (recommended)**

```python
from agentwatch_sdk import watch

@watch(agent_name="my_agent")            # zero required config beyond this
def research_node(state):
    ...
    return state

@watch(agent_name="my_agent")
def analysis_node(state):
    ...
    return state
```

**Option B — Instrument an entire compiled graph in one line**

```python
from agentwatch_sdk import watch_graph

compiled = graph.compile()
compiled = watch_graph(compiled, agent_name="my_agent")   # wraps every node
result   = compiled.invoke(initial_state)
```

**Option C — Emit tool_call / llm_call events from inside a node**

```python
from agentwatch_sdk import emit_event

emit_event(
    "tool_call", "research", agent_name="my_agent",
    tool_name="search_tool",
    tool_input="AI observability 2026",
    tool_output="Market at $28.5B...",
    duration_ms=180.0,
    trust_score=0.92,
)
```

**Option D — Context manager for scoped per-run traces**

```python
from agentwatch_sdk import watch_graph, AgentWatchContext

with AgentWatchContext(agent_name="my_agent") as ctx:
    result = compiled.invoke(state)
# ctx.trace_id → the UUID used for this run (log it!)
```

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `agent_name` | *(required)* | Appears as `agent_id` in the dashboard |
| `ws_url` | `ws://localhost:8001/ws/agent-stream` | AgentWatch backend WebSocket |
| `http_url` | `http://localhost:8001/api/events/ingest` | HTTP fallback |
| `trace_id` | auto-generated UUID | Pin multiple nodes to the same trace |
| `step_name` | function `__name__` | Override the step name in events |

> **Graceful degradation:** if the backend is unreachable, events are silently dropped and your agent runs unaffected.

---

## ⚡ Quick Start

### Prerequisites
- Splunk Enterprise (dev license) with HEC enabled
- [Splunk AI Toolkit](https://splunkbase.splunk.com/app/2890) installed
- [Splunk MCP Server](https://splunkbase.splunk.com/app/7931) installed
- Python 3.10+

### 1. Clone & Configure

```bash
git clone https://github.com/ashish-doing/agentwatch.git
cd agentwatch
cp .env.example .env
# Edit .env with your Splunk HEC token and credentials
```

### 2. Splunk Setup

```
In Splunk:
  Settings → Data Inputs → HTTP Event Collector → New Token
  Name:        agentwatch-hec
  Source type: agentwatch:otel
  Index:       agentwatch  (create this index first)
  Copy token → .env → SPLUNK_HEC_TOKEN
```

### 3. Install & Run Backend

```bash
pip install -r backend/requirements.txt
uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --reload
```

The backend also serves the frontend as static files — open `http://localhost:8001` and everything is available without a separate server.

### 4. Run the Demo Agent

```bash
# Healthy agent — trust scores 85-100%
python backend/agent/agent_runner.py --mode normal

# Loop mode — search_tool called 23x, anomaly fires
python backend/agent/agent_runner.py --mode loop

# Hallucination — token spike to 8000+
python backend/agent/agent_runner.py --mode hallucinate

# Drift — each step 30% slower
python backend/agent/agent_runner.py --mode drift
```

Or trigger a demo run from the UI (no terminal needed):

```bash
curl -X POST https://agentwatch-production-4a86.up.railway.app/api/demo/trigger \
  -H "Content-Type: application/json" \
  -d '{"mode": "loop"}'
```

### 5. Run Autopsy After a Run

```bash
curl -X POST https://agentwatch-production-4a86.up.railway.app/api/autopsy \
  -H "Content-Type: application/json" \
  -d '{"last_n_events": 200}'
```

Returns: performance grade A–F, root cause, fix recommendation, estimated cost in USD.

---

## 🔍 Useful SPL Queries

```spl
-- Find all loop anomalies
index=agentwatch event_type=tool_call earliest=-30d
| stats count as call_count by agent_id, tool_name, trace_id
| where call_count > 5
| sort -call_count

-- Token spike detection
index=agentwatch event_type=llm_call earliest=-30d
| stats max(llm_total_tokens) as max_tokens by step_name, trace_id
| where max_tokens > 3000
| sort -max_tokens

-- Trust score heatmap by tool
index=agentwatch earliest=-30d
| stats avg(trust_score) as avg_trust by tool_name
| sort avg_trust

-- Native anomaly detection on tool call frequency
index=agentwatch event_type=tool_call earliest=-30d
| timechart span=1h count as tool_calls
| fillnull value=0
| anomalydetection tool_calls
```

---

## 📁 Project Structure

```
agentwatch/
├── backend/
│   ├── agent/
│   │   ├── demo_agent.py          # LangGraph demo agent (4 failure modes)
│   │   ├── agent_runner.py        # CLI runner with direct HEC sending
│   │   └── demo_runner_lib.py     # In-process demo trigger (used by /api/demo/trigger)
│   ├── instrumentation/
│   │   ├── otel_setup.py          # OpenTelemetry + Splunk HEC exporter
│   │   ├── langgraph_hooks.py     # LangGraph node instrumentation hooks
│   │   └── anomaly_detector.py    # In-process pre-filter anomaly detector
│   ├── api/
│   │   ├── main.py                # FastAPI + WebSocket + demo trigger + static serving
│   │   ├── splunk_client.py       # Splunk REST + MCP + AI Assistant
│   │   ├── foundation_sec.py      # Foundation-Sec-1.1-8B client
│   │   └── autopsy.py             # Post-run Agent Autopsy (grade A–F)
│   ├── agentwatch_sdk.py          # Zero-config @watch / watch_graph SDK
│   └── requirements.txt
├── frontend/
│   ├── index.html                 # Main app shell
│   └── src/
│       ├── brain.js               # Three.js force-directed brain graph
│       ├── websocket.js           # Real-time WebSocket + demo simulation
│       ├── alerts.js              # Anomaly alert overlays
│       ├── assistant.js           # Splunk AI Assistant panel
│       ├── health_score.js        # Live health score tracker
│       ├── sparklines.js          # Mini trust/token sparkline charts
│       ├── trace_timeline.js      # Trace step timeline
│       └── autopsy_panel.js       # Post-run autopsy results panel
├── splunk/
│   ├── dashboards/
│   │   └── agentwatch.xml         # Splunk dashboard (8 panels, 30d range)
│   └── searches/
│       └── anomaly_searches.spl   # Saved SPL queries
├── docs/
│   ├── screenshots/               # README screenshots
│   └── index.html                 # Landing page (GitHub Pages)
├── docker/
│   ├── Dockerfile.backend
│   └── docker-compose.yml
├── architecture.png               # System architecture diagram
├── architecture_diagram.md        # Architecture with annotated data flows
├── .env.example
├── LICENSE                        # MIT
└── README.md
```

---

## 🗺️ Roadmap

Future directions for AgentWatch — not commitments, but where AI agent observability on Splunk needs to go:

| Area | Feature |
|---|---|
| **Alerting** | Alert rules configurator UI — set loop/trust/token thresholds without editing SPL |
| **Reporting** | Incident report PDF export — share post-mortems in one click |
| **Trust** | 30-run trust score trend chart — see stability over time |
| **Integrations** | Slack & PagerDuty webhooks — route anomaly alerts to existing on-call workflows |
| **Frameworks** | CrewAI + OpenAI Agents SDK support — not just LangGraph |
| **Topology** | Multi-agent topology map — visualize agent-to-agent calls and handoffs |
| **Operations** | CRM-style Agent Ops Dashboard — manage a fleet of agents like a product |
| **Cost** | Token cost tracker — attribution per agent, per tool, per run |
| **SLOs** | SLO manager — define and track uptime/trust SLOs for production agents |
| **Packaging** | Splunk Cloud native packaging — one-click install from Splunkbase |

---

## 🌐 Links

- **Live Demo:** https://agentwatch-production-4a86.up.railway.app
- **Landing Page:** https://ashish-doing.github.io/agentwatch
- **GitHub:** https://github.com/ashish-doing/agentwatch
- **Splunk AI Toolkit:** https://splunkbase.splunk.com/app/2890
- **Splunk MCP Server:** https://splunkbase.splunk.com/app/7931

---

## 👤 Author

**Ashish Kumar**  
B.Tech ECE, IIIT Guwahati (Batch 2024)

- GitHub: [@ashish-doing](https://github.com/ashish-doing)
- LinkedIn: [linkedin.com/in/ashish-kumar-014aaa3b9](https://linkedin.com/in/ashish-kumar-014aaa3b9)

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.