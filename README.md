<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Syne&weight=800&size=24&duration=3000&pause=1000&color=00E5FF&center=true&vCenter=true&width=1200&lines=AgentWatch+%E2%80%94+AI+Agent+Observability+for+Splunk;Real-time+anomaly+detection+for+AI+agents;Loop+detected+%E2%80%94+search_tool+called+23%C3%97+in+4s;Foundation-Sec+root+cause+in+plain+English;Splunk+MCP+%C2%B7+AI+Toolkit+%C2%B7+Foundation-Sec+%C2%B7+AI+Assistant" alt="AgentWatch" />

</div>

<p align="center">
  <img src="https://img.shields.io/badge/Splunk-MCP%20Server-FF4500?style=for-the-badge&logo=splunk" />
  <img src="https://img.shields.io/badge/Splunk-AI%20Toolkit-FF4500?style=for-the-badge&logo=splunk" />
  <img src="https://img.shields.io/badge/Foundation--Sec-1.1--8B-00B4D8?style=for-the-badge" />
  <img src="https://img.shields.io/badge/LangGraph-0.2.28-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/CrewAI-supported-blue?style=for-the-badge" />
  <img src="https://img.shields.io/badge/OpenAI%20Agents-supported-412991?style=for-the-badge" />
  <img src="https://img.shields.io/badge/OpenTelemetry-1.27.0-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Three.js-r128-black?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/Tests-81%20passing-brightgreen?style=for-the-badge&logo=pytest" />
</p>

<p align="center">
  <strong>Splunk Agentic Ops Hackathon 2026 — Track: Platform &amp; Developer Experience</strong>
</p>

<p align="center">
  🌐 <a href="https://ashish-doing.github.io/agentwatch">Landing Page</a> &nbsp;•&nbsp;
  🚀 <a href="https://agentwatch-production-4a86.up.railway.app">Live Demo</a> &nbsp;•&nbsp;
  📊 <a href="https://agentwatch-production-4a86.up.railway.app/ops">Agent Ops Dashboard</a> &nbsp;•&nbsp;
  🗺️ <a href="https://agentwatch-production-4a86.up.railway.app/topology">Topology Map</a> &nbsp;•&nbsp;
  ⚡ <a href="#-quick-start">Quick Start</a>
</p>

---

## 🎬 Demo Video

> **Recording in progress** — video will be added before the June 15 deadline.

<!-- Replace this comment with your video embed once recorded:
[![AgentWatch Demo](https://img.youtube.com/vi/YOUR_VIDEO_ID/maxresdefault.jpg)](https://youtu.be/YOUR_VIDEO_ID)
▶ [Watch the demo on YouTube](https://youtu.be/YOUR_VIDEO_ID)
-->

---

## 🏆 Hackathon Track

| | |
|---|---|
| **Event** | Splunk Agentic Ops Hackathon 2026 |
| **Track** | Platform & Developer Experience |
| **Prize pool** | $20,000 + .conf26 passes |
| **Deadline** | June 15, 2026 @ 9:00am PDT |
| **Bonus eligibility** | Best Use of Splunk MCP Server · Best Use of Splunk Hosted Models · Best Developer Tool |

**Why Platform & Developer Experience:** AgentWatch is a developer tool that simplifies how AI agent teams build on Splunk — zero-config SDK, live anomaly detection, and plain-English root cause analysis. It makes Splunk's AI capabilities accessible to developers who don't know SPL.

---

## The Gap in AI Agent Monitoring

**2,299 events indexed. 342 anomalies detected. 4 Splunk AI capabilities unified in one pipeline.**

AI agents are entering production faster than teams can instrument them. When a LangGraph agent calls the same tool 23 times in 4 seconds, when token counts spike to 8,000+, when trust scores drop to 5% — most teams find out hours later from user complaints or API bills. Existing observability tools (Datadog, LangSmith, Arize) are not Splunk-native, meaning enterprises already running Splunk infrastructure have to maintain a separate monitoring stack.

AgentWatch addresses this by building agent observability directly on top of Splunk's existing AI capabilities — HEC, MCP Server, AI Toolkit, Foundation-Sec, and AI Assistant — so teams get real-time anomaly detection and plain-English root cause analysis without leaving the platform they already use.

---

## 🔥 The Problem

- **34%** of production AI agents fail silently due to missing observability tooling
- Loop failures cost enterprises **$2,400/hour** in wasted API calls
- Mean time to detect an agent failure without tooling: **4.2 hours**
- Teams running Splunk infrastructure have no native agent observability option

---

## 💡 What AgentWatch Does

AgentWatch wraps any LangGraph, CrewAI, or OpenAI Agents SDK agent with OpenTelemetry, streams its behavior into Splunk in real time, runs in-process anomaly detection before events even reach Splunk, explains anomalies in plain English via Foundation-Sec-1.1-8B, and delivers a post-run Agent Autopsy graded A–F.

- **"Explain This"** → Foundation-Sec root cause + recommended fix + SPL query
- **"Export PDF"** → incident report with full Foundation-Sec reasoning + SPL queries
- **"Run Autopsy"** → post-run performance grade A–F + cost estimate + fix recommendation
- **⚙ Config panel** → adjust all anomaly thresholds live without editing SPL

---

## 📸 Screenshots

### 🧠 Live Brain — Anomaly Detected in Real Time
*Force-directed Three.js graph showing 164 events, 65 anomalies, 0.47 avg trust. Red pulsing nodes = anomaly paths. Alert overlay shows Foundation-Sec explanation with EXPLAIN / SPLUNK / EXPORT PDF actions. SPL Assistant running "What are the slowest steps?" below.*

![AgentWatch Live Brain — anomaly detected, trust collapse alert, SPL assistant active](docs/screenshots/screenshot-hero.png)

---

### 📊 Agent Operations CRM Dashboard — `/ops`
*CRM-style run history across 6 agent runs: trust trend line chart, anomaly type doughnut (260 total anomalies), SLO status panel, and per-run cost tracker. Sortable table shows HEALTHY / WARNING / CRITICAL status per run with trust bars, token counts, and duration.*

![AgentWatch Agent Ops Dashboard — run history, trust trend, anomaly breakdown, SLO status](docs/screenshots/screenshot-ops.png)

---

### 📊 Splunk Dashboard — Real Telemetry
*Native Splunk dashboard showing real indexed data: 2,299 total events, 342 anomalies detected, 58.1% avg trust score, 1 active agent, 279,993 total tokens. Panels include agent events over time, tool call frequency (loop detection), token usage by step, trust score by tool, and recent anomalies table — all from `index=agentwatch`.*

![AgentWatch Splunk Dashboard — 2,299 events, 342 anomalies, 58.1% avg trust, 279,993 tokens](docs/screenshots/screenshot-dashboard.png)

---

### 🗺️ Multi-Agent Topology Map — `/topology`
*Second Three.js visualization: 1 agent hub (octahedral, purple), 48 nodes, 47 edges, 7 anomalies. Red pulsing rings on anomaly nodes, teal data-flow edges, red anomaly-path edges. Node Inspector panel shows trust score bar and connection count on click.*

![AgentWatch Multi-Agent Topology Map — force-directed graph with anomaly nodes and node inspector](docs/screenshots/screenshot-topology.png)


---

## 🏗️ Architecture

![AgentWatch Architecture](architecture.svg)

> Full annotated diagram with data-flow sequences: [`architecture.md`](architecture.md)

**Two-stage anomaly detection pipeline:**

AgentWatch runs anomaly detection in two stages. First, an in-process `AnomalyDetector` pre-filters events before they reach Splunk — catching loops, token spikes, latency drift, error bursts, and trust collapse in real time with live-configurable thresholds. Second, SPL queries feed tool-call time-series into Splunk AI Toolkit's `anomalydetection` command for statistical confirmation (99.25% confidence). Both stages are complementary: the pre-filter catches failures instantly; the Splunk layer provides historical statistical context.

```
ANY AGENT (LangGraph · CrewAI · OpenAI Agents · AutoGen)
         │
         ▼
[AgentWatch SDK / Framework Hooks]
 ├── @watch(agent_name="my_agent")     → individual nodes
 ├── watch_graph(compiled, ...)        → entire graph in one line
 ├── AgentWatchCrewAI(...)             → CrewAI callback
 ├── AgentWatchOpenAI(...)             → OpenAI Agents hook
 └── AgentWatchAutoGen(...)            → AutoGen message hook
         │
         ▼
[OpenTelemetry] → LLM calls · tool calls · reasoning · trust scores
         │
         ├──────────────────────────────────────────┐
         ▼                                          ▼
[FastAPI + WebSocket]                   [Three.js Live Brain /]
 500-event ring buffer                  anomaly glow · trust colors
 14 API endpoints
         │
         ▼
[Stage 1 — AnomalyDetector (in-process pre-filter)]
 loop ≥5 · token spike ≥3k · latency ≥3s · error burst ≥3 · trust ≤0.3
 all thresholds configurable live via /api/config + UI
 CRITICAL anomalies → Slack webhook notification
         │
         ▼
[Splunk HEC] → index=agentwatch · sourcetype=agentwatch:otel
         │
         ├── [Stage 2] Splunk AI Toolkit — anomalydetection (99.25% confidence)
         ├── Splunk MCP Server — all telemetry searchable via SPL
         ├── Splunk AI Assistant — "show loops last hour" → SPL
         └── Foundation-Sec-1.1-8B — Explain · Autopsy · PDF
         │
         ▼
[Three pages of UI]
 /           — Live Brain (Three.js force-directed graph)
 /ops        — Agent Operations CRM Dashboard
 /topology   — Multi-Agent Topology Map (second Three.js graph)
```

---

## ⚔️ How AgentWatch Compares

| Capability | AgentWatch | LangSmith | Arize Phoenix | Raw Splunk |
|---|---|---|---|---|
| **Splunk-native** | ✅ | ❌ SaaS only | ❌ SaaS only | ✅ but no agent SDK |
| **Zero-config SDK** | ✅ `@watch` decorator | ⚠️ manual | ⚠️ manual | ❌ |
| **In-process pre-filter** | ✅ before HEC | ❌ | ❌ | ❌ |
| **Foundation-Sec reasoning** | ✅ | ❌ | ❌ | ❌ |
| **Agent Autopsy A–F** | ✅ | ❌ | ❌ | ❌ |
| **NL → SPL** | ✅ AI Assistant | ❌ | ❌ | ❌ |
| **Multi-framework** | ✅ 5 frameworks | ⚠️ LangChain | ⚠️ manual | ❌ |
| **Live threshold config** | ✅ UI sliders | ❌ | ❌ | SPL only |
| **Incident PDF export** | ✅ | ❌ | ❌ | ❌ |
| **Slack alerts** | ✅ CRITICAL only | ⚠️ paid | ⚠️ paid | ⚠️ alerts app |
| **Topology map** | ✅ Three.js graph | ❌ | ❌ | ❌ |
| **CRM Ops Dashboard** | ✅ /ops | ❌ | ❌ | ❌ |
| **Cost tracker** | ✅ per-run USD | ⚠️ paid | ⚠️ paid | ❌ |
| **SLO manager** | ✅ | ❌ | ❌ | ❌ |
| **Splunk Cloud app** | ✅ native packaging | ❌ | ❌ | ✅ |
| **Open source** | ✅ MIT | ❌ proprietary | ✅ | ✅ |

---

## ✅ Splunk AI Capabilities Used

| Capability | How AgentWatch Uses It |
|---|---|
| **Splunk MCP Server** | All agent telemetry indexed to `index=agentwatch`; SPL queries run directly from the UI assistant panel |
| **Splunk AI Toolkit** | `anomalydetection` on tool-call time-series — 99.25% confidence, 342 anomalies caught |
| **Foundation-Sec-1.1-8B** | "Explain This" per-anomaly root cause + "Run Autopsy" full-trace graded report + PDF incident export |
| **Splunk AI Assistant** | NL → SPL; type "show me all loops in the last hour" → live SPL results |

---

## 📊 What AgentWatch Detects

| Failure Mode | Trigger | Severity | Configurable |
|---|---|---|---|
| Infinite loops | Same tool ≥5 calls in one trace | CRITICAL | ✅ UI slider |
| Token spikes | LLM tokens ≥3,000 | HIGH | ✅ UI slider |
| Latency drift | Step duration ≥3,000ms | MEDIUM | ✅ UI slider |
| Error burst | ≥3 errors in one trace | HIGH | ✅ UI slider |
| Trust collapse | trust_score ≤0.3 | CRITICAL | ✅ UI slider |

All thresholds are adjustable live via the **⚙ Config** panel — no SPL editing required. Changes propagate immediately to the `AnomalyDetector` instance via `POST /api/config`.

---

## 🧪 Tests

AgentWatch has **81 tests** across two files covering the full detection + API pipeline.

### Run all tests

```bash
pip install pytest pytest-asyncio httpx reportlab
pytest backend/tests/ -v
# 81 passed in ~1s
```

### Test files

| File | Tests | What it covers |
|---|---|---|
| `backend/tests/test_anomaly.py` | 32 | `AnomalyDetector` class — all 5 detection types, trust formula, severity levels, trace isolation, reset |
| `backend/tests/test_api.py` | 49 | FastAPI endpoints — `/api/history`, `/api/config` GET+POST, `/api/export/incident` PDF, `/api/explain`, Slack webhook, live threshold propagation |

### Coverage by feature

**`test_anomaly.py` — AnomalyDetector unit tests**

| Class | Tests | Verifies |
|---|---|---|
| `TestLoopDetection` | 10 | Threshold boundary, severity HIGH→CRITICAL at 10 calls, per-tool isolation, per-trace isolation, `record_tool_call` / `is_loop_detected` helpers |
| `TestTrustScore` | 3 | Formula matches `langgraph_hooks.py` exactly, floor of 0.05, healthy agent > 0.7 |
| `TestTokenSpike` | 5 | Below threshold = no anomaly, spike at threshold+1, severity MEDIUM→CRITICAL at 3×, matches hallucinate mode (5k–9k tokens) |
| `TestLatencyDrift` | 5 | Threshold boundary, severity MEDIUM→HIGH at 2×, matches drift mode formula at call_count=36 |
| `TestTrustCollapse` | 3 | Fires at ≤0.3, silent above 0.3, CRITICAL at 0.05 floor |
| `TestErrorBurst` | 2 | Silent at 1 error, fires at 3 |
| `TestCheckEventPipeline` | 4 | `step_start` never fires, anomaly logged to stats, `get_latest_anomaly`, `reset_trace` clears counts |

**`test_api.py` — FastAPI integration tests (all external calls mocked)**

| Class | Tests | Verifies |
|---|---|---|
| `TestHealth` | 2 | Returns `status=ok`, buffer size correct |
| `TestEvents` | 4 | Empty buffer, seeded events returned, `?event_type=` filter, `?limit=` cap |
| `TestStats` | 2 | Empty buffer defaults, correct aggregation (events / anomalies / agents / avg_trust) |
| `TestHistory` | 8 | Empty buffer, single trace → one run, multiple traces, avg_trust math, anomaly_count, `?limit=`, required fields, events missing `trace_id` ignored |
| `TestConfig` | 11 | GET defaults, POST each field, partial update preserves others, GET reflects POST — plus **4 live propagation tests**: loop/token/latency/trust threshold changes immediately affect `AnomalyDetector` firing behaviour |
| `TestSlackWebhook` | 4 | No-op when URL unset, POST fires when set, message contains anomaly type, HTTP failure is non-fatal |
| `TestPDFExport` | 6 | `application/pdf` Content-Type, non-empty body, `%PDF` magic bytes, filename in Content-Disposition, minimal payload, all 4 severity levels |
| `TestExplain` | 4 | Required fields present, minimal payload, severity/SPL are strings |
| `TestUpdateThresholds` | 6 | Direct `AnomalyDetector.update_thresholds()` unit tests — all 4 fields + partial update + `None` is no-op |

### What the live-propagation tests prove

The `TestConfig` propagation tests are the most important for the hackathon: they prove that changing a threshold via the UI (`POST /api/config`) immediately changes what the detector catches — not just what's stored in `alert_config`. For example:

```python
# Set loop threshold to 3 via the API
client.post("/api/config", json={"loop_threshold": 3})

# Now 3 tool calls fires a loop anomaly — with default 5 it would have been silent
result = anomaly_detector.check_event(tool_event)
assert result.anomaly_type == "loop"  # ✅ passes
```

---

## 🔭 Framework Support

AgentWatch works with any Python AI agent framework via `agentwatch_hooks.py`:

**LangGraph** (zero-config):
```python
from agentwatch_sdk import watch, watch_graph
compiled = watch_graph(graph.compile(), agent_name="my_agent")
```

**CrewAI**:
```python
from agentwatch_hooks import AgentWatchCrewAI
aw = AgentWatchCrewAI(agent_name="my_crew")
agent = Agent(role="Researcher", ..., callbacks=[aw])
```

**OpenAI Agents SDK**:
```python
from agentwatch_hooks import AgentWatchOpenAI
hooks = AgentWatchOpenAI(agent_name="my_agent")
agent = Agent(name="Assistant", instructions="...", hooks=hooks)
```

**AutoGen**:
```python
from agentwatch_hooks import AgentWatchAutoGen
hook = AgentWatchAutoGen(agent_name="autogen_crew")
assistant.register_reply(trigger=autogen.ConversableAgent, reply_func=hook.on_message)
```

**Any framework** (generic decorators):
```python
from agentwatch_hooks import watch_tool, watch_llm

@watch_tool(agent_name="my_agent", tool_name="search")
def search_tool(query: str) -> str: ...

@watch_llm(agent_name="my_agent")
def call_llm(prompt: str) -> dict: ...
```

---

## 🗂️ Agent Operations Dashboard (`/ops`)

A CRM-style dashboard for managing agent runs at scale:

- **KPI row** — total runs, avg trust, anomaly count, token usage, estimated cost, live events
- **Run history table** — sortable by trust, anomalies, cost, duration; filter by mode
- **Trust trend chart** — 30-run line chart with Chart.js
- **Anomaly breakdown** — doughnut chart by type
- **SLO status** — uptime · loop-free rate · cost · latency · trust SLOs
- **Cost tracker** — per-run USD at $0.15/1M tokens
- **Live activity feed** — real-time WebSocket stream

---

## 🗺️ Multi-Agent Topology Map (`/topology`)

A second Three.js visualization for multi-agent systems:

- Agent hub nodes (octahedral), step nodes colored by type and trust
- Animated particles flowing along edges showing data movement
- Force-directed layout with repulsion + attraction physics
- Drag to orbit, scroll to zoom, click any node for inspector details
- Rebuilds live as new events arrive via WebSocket

---

## 📄 Incident Report PDF Export

One-click PDF from the alert overlay or Agent Ops table:

- Incident summary table (trace ID, agent, timestamp, anomaly type, severity, trust)
- Full Foundation-Sec reasoning and recommended fix
- SPL queries to reproduce the incident in Splunk

---

## 🔔 Slack Notifications

Add `SLACK_WEBHOOK_URL` to `.env` to receive CRITICAL anomaly alerts:

```
🚨 AgentWatch CRITICAL: loop detected on agent demo-001
— search_tool called 23x — View trace: [Splunk deep link]
```

Gracefully skips if env var is not set — optional feature.

---

## 📦 Splunk Cloud App

`splunk_app/agentwatch/` is a complete Splunk app package ready for Splunkbase or Cloud install:

- `app.conf` — app metadata
- `indexes.conf` — agentwatch index definition
- `inputs.conf` — HEC input + log monitor
- `props.conf` — agentwatch:otel sourcetype config
- `transforms.conf` — field extractions (trust_score, agent_id, anomaly_type, etc.)
- `savedsearches.conf` — 7 pre-built SPL searches + CRON alert for CRITICAL anomalies

Install: upload `splunk_app/` to Splunk Cloud or copy to `$SPLUNK_HOME/etc/apps/`.

---

## ⚡ Quick Start

### Prerequisites

- Python 3.10+
- Splunk Enterprise with HEC enabled *(or use the Railway live demo — no Splunk needed)*

### 1. Clone & Configure

```bash
git clone https://github.com/ashish-doing/agentwatch.git
cd agentwatch
cp .env.example .env
# Edit .env — add SPLUNK_HEC_TOKEN and SPLUNK_AI_TOKEN
# Optional: SLACK_WEBHOOK_URL for CRITICAL anomaly Slack alerts
```

### 2. Install & Run

```bash
pip install -r backend/requirements.txt
uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --reload
```

Open `http://localhost:8001` — all three pages available at `/`, `/ops`, `/topology`.

### 3. Run the Demo Agent

```bash
python backend/agent/agent_runner.py --mode normal      # healthy run
python backend/agent/agent_runner.py --mode loop        # loop anomaly
python backend/agent/agent_runner.py --mode hallucinate # token spike
python backend/agent/agent_runner.py --mode drift       # latency drift
```

Or click the demo buttons directly in the UI — no terminal needed.

### 4. Run Tests

```bash
pip install pytest pytest-asyncio httpx reportlab
pytest backend/tests/ -v
```

Expected output:
```
backend/tests/test_anomaly.py ................................ [ 39%]
backend/tests/test_api.py ..................................................  [100%]
81 passed in 0.81s
```

### 5. Try the API

```bash
# Trigger a loop demo
curl -X POST https://agentwatch-production-4a86.up.railway.app/api/demo/trigger \
  -H "Content-Type: application/json" -d '{"mode": "loop"}'

# Run post-run autopsy
curl -X POST https://agentwatch-production-4a86.up.railway.app/api/autopsy \
  -H "Content-Type: application/json" -d '{"last_n_events": 200}'

# Get run history for trend chart
curl https://agentwatch-production-4a86.up.railway.app/api/history

# View and update alert thresholds
curl https://agentwatch-production-4a86.up.railway.app/api/config
curl -X POST https://agentwatch-production-4a86.up.railway.app/api/config \
  -H "Content-Type: application/json" -d '{"loop_threshold": 3}'
```

---

## 📡 API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| `WS` | `/ws/agent-stream` | Agent → backend event stream |
| `WS` | `/ws/browser` | Backend → browser live events |
| `POST` | `/api/explain` | Anomaly explanation via Foundation-Sec |
| `POST` | `/api/query` | NL → SPL via AI Assistant |
| `POST` | `/api/autopsy` | Post-run trace analysis, grade A–F |
| `GET` | `/api/history` | Last 30 run summaries for trust trend chart |
| `GET` | `/api/config` | Current alert thresholds |
| `POST` | `/api/config` | Update alert thresholds live |
| `POST` | `/api/export/incident` | Generate PDF incident report |
| `POST` | `/api/demo/trigger` | Trigger demo run (normal/loop/hallucinate/drift) |
| `GET` | `/api/demo/status` | Check if demo is running |
| `GET` | `/api/events` | Recent events from ring buffer |
| `GET` | `/api/stats` | Live stats (events, anomalies, trust) |
| `GET` | `/api/health` | Backend health + Splunk connectivity |
| `GET` | `/` | Live Brain visualization |
| `GET` | `/ops` | Agent Operations CRM Dashboard |
| `GET` | `/topology` | Multi-agent topology map |

---

## 🔍 Useful SPL Queries

```spl
-- All anomalies
index=agentwatch event_type=anomaly | sort -_time
| table _time, agent_id, anomaly_type, severity, trust_score, reasoning_content

-- Loop detection
index=agentwatch event_type=tool_call
| stats count as calls by trace_id, tool_name | where calls >= 5 | sort -calls

-- Trust trend over time
index=agentwatch trust_score=* | timechart span=5m avg(trust_score) by agent_id

-- Token spikes
index=agentwatch event_type=llm_call llm_total_tokens>=3000
| table _time, agent_id, trace_id, llm_total_tokens, step_name

-- Native Splunk anomaly detection (Stage 2)
index=agentwatch event_type=tool_call | timechart span=1h count as tool_calls
| anomalydetection tool_calls
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Agent frameworks | LangGraph 0.2.28 · CrewAI · OpenAI Agents · AutoGen | Agents being monitored |
| Observability | OpenTelemetry SDK 1.27.0 | Capture every LLM/tool call |
| SDK | `agentwatch_sdk.py` + `agentwatch_hooks.py` | Zero-config instrumentation |
| Event transport | Splunk HEC (port 8088) | Real-time telemetry delivery |
| Anomaly detection | `AnomalyDetector` + Splunk AI Toolkit | In-process pre-filter + statistical confirmation |
| Reasoning | Foundation-Sec-1.1-8B | Explain · Autopsy · PDF |
| NL queries | Splunk AI Assistant | Natural language → SPL |
| Notifications | Slack webhook (httpx) | CRITICAL anomaly alerts |
| Backend | FastAPI 0.115.4 + WebSocket | All endpoints + event streaming |
| 3D visualization | Three.js r128 | Brain graph + topology map |
| Ops dashboard | Chart.js 4.4.1 | Trust trend + anomaly charts |
| PDF export | reportlab ≥4.0.0 | Incident report generation |
| Testing | pytest + pytest-asyncio | 81 tests, fully offline |
| Splunk app | Native `.conf` packaging | Splunkbase-ready |
| Deployment | Railway | Live demo |
| Frontend hosting | GitHub Pages | Landing page |

---

## 📁 Project Structure

```
agentwatch/
├── backend/
│   ├── agent/
│   │   ├── demo_agent.py          # LangGraph demo agent (4 failure modes)
│   │   ├── agent_runner.py        # CLI runner
│   │   └── demo_runner_lib.py     # In-process demo trigger
│   ├── instrumentation/
│   │   ├── otel_setup.py          # OpenTelemetry + HEC exporter
│   │   ├── langgraph_hooks.py     # LangGraph node hooks
│   │   └── anomaly_detector.py    # In-process pre-filter (5 anomaly types)
│   ├── api/
│   │   ├── main.py                # FastAPI + WebSocket + all 14 endpoints
│   │   ├── splunk_client.py       # Splunk REST + MCP + AI Assistant
│   │   ├── foundation_sec.py      # Foundation-Sec-1.1-8B client
│   │   └── autopsy.py             # Agent Autopsy (grade A–F)
│   ├── tests/
│   │   ├── test_anomaly.py        # 32 unit tests — AnomalyDetector (all 5 types)
│   │   └── test_api.py            # 49 integration tests — all API endpoints
│   ├── agentwatch_sdk.py          # Zero-config @watch / watch_graph
│   ├── agentwatch_hooks.py        # CrewAI · OpenAI Agents · AutoGen hooks
│   └── requirements.txt
├── frontend/
│   ├── index.html                 # Live Brain (main app)
│   ├── ops.html                   # Agent Operations CRM Dashboard
│   ├── topology.html              # Multi-agent topology map
│   └── src/
│       ├── brain.js               # Three.js force-directed brain
│       ├── websocket.js           # WebSocket + demo fallback
│       ├── alerts.js              # Anomaly overlays + PDF export button
│       ├── assistant.js           # AI Assistant panel
│       ├── health_score.js
│       ├── sparklines.js
│       ├── trace_timeline.js
│       └── autopsy_panel.js
├── splunk/
│   ├── dashboards/agentwatch.xml  # 8-panel Splunk dashboard
│   └── searches/anomaly_searches.spl
├── splunk_app/
│   └── agentwatch/                # Splunk Cloud native app
│       ├── default/               # app · indexes · inputs · props · transforms · savedsearches
│       └── metadata/
├── docs/
│   ├── screenshots/
│   │   ├── screenshot-hero.png         # Live Brain — anomaly detected
│   │   ├── screenshot-ops.png          # Agent Ops CRM Dashboard
│   │   ├── screenshot-topology.png     # Multi-Agent Topology Map
│   │   └── screenshot-dashboard.png    # Splunk dashboard — real telemetry
│   └── index.html                 # GitHub Pages landing
├── architecture.svg               # Architecture diagram (dark theme)
├── architecture.md                # Annotated architecture with data flows
├── .env.example
├── LICENSE
├── CONTRIBUTING.md
└── README.md
```

---

## 📊 Key Numbers (Real Data)

| Metric | Value |
|---|---|
| Events indexed | 2,299+ |
| Anomalies detected | 342 |
| Avg trust score | 58.1% |
| Tokens processed | 279,993 |
| Loop confidence (Splunk AI Toolkit) | 99.25% |
| Frameworks supported | 5 |
| Frontend pages | 3 |
| API endpoints | 14 |
| Splunk AI capabilities used | 4 |
| Test coverage | 81 tests passing |

---

## 🌐 Links

- **Live Demo:** https://agentwatch-production-4a86.up.railway.app
- **Agent Ops:** https://agentwatch-production-4a86.up.railway.app/ops
- **Topology:** https://agentwatch-production-4a86.up.railway.app/topology
- **Landing Page:** https://ashish-doing.github.io/agentwatch
- **GitHub:** https://github.com/ashish-doing/agentwatch

---

## 👤 Author

**Ashish Kumar** — B.Tech ECE, IIIT Guwahati (Batch 2024)

[![GitHub](https://img.shields.io/badge/GitHub-ashish--doing-181717?style=flat-square&logo=github)](https://github.com/ashish-doing)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-ashish--kumar-0A66C2?style=flat-square&logo=linkedin)](https://linkedin.com/in/ashish-kumar-014aaa3b9)

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built for the **Splunk Agentic Ops Hackathon 2026**

*Powered by Splunk MCP Server · Splunk AI Toolkit · Foundation-Sec-1.1-8B · Splunk AI Assistant*

</div>