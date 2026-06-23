# AgentWatch — System Architecture

## Overview

AgentWatch is a real-time AI agent observability platform. It wraps any LangGraph, CrewAI, OpenAI Agents SDK, or AutoGen agent with the AgentWatch SDK (zero-config `@watch` / `watch_graph` / framework hooks), streams telemetry to Splunk via HEC, runs an in-process anomaly pre-filter before the events ever reach Splunk, and surfaces anomalies through three frontend pages (Live Brain, Agent Ops CRM, Multi-Agent Topology), an 8-panel Splunk dashboard, and a post-run Agent Autopsy graded A–F via Foundation-Sec-1.1-8B. CRITICAL anomalies fire Slack webhook notifications. All thresholds are configurable live via the UI.

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph AGENT["🤖 AI AGENT LAYER"]
        SDK["AgentWatch SDK\n━━━━━━━━━━━━━━━\n• @watch decorator\n• watch_graph(compiled, ...)\n• AgentWatchContext\n• emit_event()"]
        HOOKS["Framework Hooks\n━━━━━━━━━━━━━━━\n• AgentWatchCrewAI\n• AgentWatchOpenAI\n• AgentWatchAutoGen\n• @watch_tool / @watch_llm"]
        LG["Demo Agent\n━━━━━━━━━━━━━━━\n• normal mode\n• loop mode\n• hallucinate\n• drift mode"]
        OT["OpenTelemetry SDK\n━━━━━━━━━━━━━━━\n• traces & spans\n• trust scores\n• token counts\n• latency"]
        LG -->|instruments| OT
        SDK -->|wraps nodes| OT
        HOOKS -->|callbacks| OT
    end

    subgraph BACKEND["⚙️ BACKEND LAYER"]
        API["FastAPI\n━━━━━━━━━━━━━━━\n• /api/explain\n• /api/query\n• /api/autopsy\n• /api/history\n• /api/config\n• /api/export/incident\n• /api/demo/trigger\n• /api/demo/status\n• /api/events /api/stats\n• serves /, /ops, /topology"]
        AD["AnomalyDetector\n━━━━━━━━━━━━━━━\nIn-process pre-filter:\n• loop detection (≥5 calls)\n• token spike (≥3,000)\n• latency drift (≥3,000ms)\n• error burst (≥3 errors)\n• trust collapse (≤0.3)\n• all thresholds configurable"]
        WS["WebSocket Stream\n━━━━━━━━━━━━━━━\n• /ws/browser\n• /ws/agent-stream\n• real-time push\n• 500-event ring buffer\n• 100-event replay on connect"]
        SC["SplunkClient\n━━━━━━━━━━━━━━━\n• HEC indexing\n• SPL search (REST)\n• AI Assistant NL→SPL\n• template fallback"]
        SLACK["Notifications\n━━━━━━━━━━━━━━━\n• Slack webhook\n• CRITICAL anomaly only\n• SLACK_WEBHOOK_URL env\n• graceful skip if unset"]
        PDF["PDF Export\n━━━━━━━━━━━━━━━\n• reportlab\n• incident summary table\n• Foundation-Sec reasoning\n• SPL queries to reproduce"]
        DRL["demo_runner_lib\n━━━━━━━━━━━━━━━\n• in-process agent run\n• emit() callback\n• no external process\n• thread executor"]
        API -->|every event| AD
        API -->|fan-out| WS
        API --> SC
        API -->|POST /demo/trigger| DRL
        DRL -->|emit callback| API
        AD -->|anomaly events| WS
        AD -->|CRITICAL| SLACK
        API -->|POST /api/export/incident| PDF
    end

    subgraph SPLUNK["☁️ SPLUNK PLATFORM"]
        HEC["Splunk HEC\n━━━━━━━━━━━━━━━\nindex: agentwatch\nsourcetype:\nagentwatch:otel\n2,299+ events\nprops + transforms\nsavedsearches.conf"]
        AITK["Splunk AI Toolkit\n━━━━━━━━━━━━━━━\nnative anomalydetection\n• tool call frequency\n• time-series analysis\n• 99.25% confidence"]
        MCP["Splunk MCP Server\n━━━━━━━━━━━━━━━\n• all telemetry indexed\n• NL query interface\n• SPL generation"]
        ASST["Splunk AI Assistant\n━━━━━━━━━━━━━━━\nNatural Language → SPL\nshow loops last hour\n→ valid SPL query"]
        FSEC["Foundation-Sec-1.1-8B\n━━━━━━━━━━━━━━━\nSplunk hosted model:\n• Explain This button\n• root cause + fix rec\n• Agent Autopsy (A–F)\n• cost estimate\n• PDF incident export\n• rule-based fallback"]
        DASH["📊  Splunk Dashboard — 8 Panels\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nKPI · Anomaly table · Trust heatmap · Loop detection\nToken usage · Latency drift · Event log · Trust by tool"]
        APP["Splunk Cloud App\n━━━━━━━━━━━━━━━\nsplunk_app/agentwatch/\n• app.conf\n• indexes.conf\n• inputs.conf\n• props.conf\n• transforms.conf\n• savedsearches.conf"]
        HEC --> AITK
        HEC --> MCP
        MCP --> ASST
        AITK --> DASH
        ASST --> DASH
        FSEC --> DASH
        HEC --> APP
    end

    subgraph FRONTEND["🖥️ FRONTEND LAYER"]
        BRAIN["Three.js Brain  /\n━━━━━━━━━━━━━━━\n• force-directed graph\n• node pulses on event\n• anomaly glow + ring\n• trust-score colors\n• click → node inspector\n• alert rules config ⚙\n• trust trend chart\n• AI Assistant panel"]
        OPS["Agent Ops  /ops\n━━━━━━━━━━━━━━━\n• CRM-style dashboard\n• run history table\n• trust trend chart\n• anomaly doughnut\n• SLO manager\n• cost tracker\n• live activity feed"]
        TOPO["Topology  /topology\n━━━━━━━━━━━━━━━\n• multi-agent graph\n• Three.js r128\n• force-directed\n• edge particles\n• orbit camera\n• node inspector"]
        LAND["Landing Page\n━━━━━━━━━━━━━━━\nGitHub Pages\nashish-doing.github.io\n/agentwatch"]
    end

    OT -->|HEC POST| HEC
    OT -->|events| API
    SC -->|SPL queries| MCP
    SC -->|explain + autopsy| FSEC
    WS -->|WebSocket| BRAIN
    WS --> OPS
    WS --> TOPO
```

---

## Data Flow — Real-Time Event Pipeline

```mermaid
sequenceDiagram
    participant Agent as Any Agent (LangGraph/CrewAI/OpenAI)
    participant SDK as AgentWatch SDK / Hooks
    participant API as FastAPI Backend
    participant AD as AnomalyDetector
    participant SLACK as Slack Webhook
    participant HEC as Splunk HEC
    participant WS as WebSocket
    participant Brain as Three.js Brain
    participant FS as Foundation-Sec

    SDK->>API: step_start event (ws://localhost:8001/ws/agent-stream)
    Agent->>HEC: tool_call event (trust_score, trace_id)
    Agent->>HEC: llm_call event (tokens, latency)
    API->>AD: check_event(tool_call)
    AD-->>API: AnomalyResult (loop detected, confidence=0.92, severity=critical)
    API->>SLACK: POST webhook (CRITICAL anomaly only)
    API->>WS: broadcast anomaly_event to browsers
    Agent->>HEC: anomaly event (loop detected, trust=0.05)
    HEC->>HEC: Index to agentwatch
    HEC->>HEC: anomalydetection command fires
    WS-->>Brain: anomaly event pushed
    Brain->>Brain: Node pulses red 🔴, ring spins
    Brain->>FS: Click "Explain This" → POST /api/explain
    FS-->>Brain: root cause + recommended fix + severity
    Brain->>FS: Click "Run Autopsy" → POST /api/autopsy
    FS-->>Brain: grade A–F + cost estimate + fix recommendation
    Brain->>API: Click "Export PDF" → POST /api/export/incident
    API-->>Brain: PDF download (Foundation-Sec reasoning + SPL queries)
```

---

## Data Flow — Public Live Demo (No Local Setup)

```mermaid
sequenceDiagram
    participant User as Browser Visitor
    participant FE as Frontend (Railway)
    participant API as FastAPI
    participant DRL as demo_runner_lib
    participant AD as AnomalyDetector
    participant WS as WebSocket

    User->>FE: Click "▶ Run Loop Demo"
    FE->>API: POST /api/demo/trigger {"mode":"loop"}
    API->>DRL: run_in_executor(run_demo_in_process, "loop", emit)
    DRL->>DRL: Build LangGraph agent in-process
    DRL->>API: emit(tool_call) × 23 iterations
    API->>AD: check_event() on each event
    AD-->>API: loop anomaly detected at call #5
    API->>WS: broadcast to all browser connections
    WS-->>FE: real-time event stream
    FE-->>User: Brain nodes pulse red, anomaly alert fires
    API-->>FE: POST /api/demo/trigger → {status:"completed", trace_id}
```

---

## Data Flow — Alert Rules Config

```mermaid
sequenceDiagram
    participant UI as Browser UI (⚙ Config panel)
    participant API as FastAPI /api/config
    participant AD as AnomalyDetector

    UI->>API: GET /api/config
    API-->>UI: {loop_threshold:5, token_spike_threshold:3000, ...}
    UI->>UI: User moves slider (loop_threshold → 3)
    UI->>API: POST /api/config {loop_threshold: 3}
    API->>AD: update_thresholds(loop_threshold=3)
    AD-->>API: thresholds updated in-memory
    API-->>UI: {status:"ok", config:{...}}
    Note over AD: New threshold active immediately<br/>Next event processed with loop_threshold=3
```

---

## Component Reference

### Agent Layer

| Component | File | Purpose |
|---|---|---|
| **AgentWatch SDK** | `backend/agentwatch_sdk.py` | Zero-config `@watch` / `watch_graph` / `AgentWatchContext` / `emit_event()` |
| **Framework Hooks** | `backend/agentwatch_hooks.py` | CrewAI · OpenAI Agents SDK · AutoGen · `@watch_tool` / `@watch_llm` generic decorators |
| **LangGraph Demo Agent** | `backend/agent/demo_agent.py` | 4 failure modes: normal, loop, hallucinate, drift |
| **Agent Runner (CLI)** | `backend/agent/agent_runner.py` | CLI wrapper — runs agent, sends events to HEC |
| **Demo Runner Lib** | `backend/agent/demo_runner_lib.py` | In-process variant — used by `/api/demo/trigger` |
| **OpenTelemetry Setup** | `backend/instrumentation/otel_setup.py` | `SplunkHECExporter` + `ConsoleStructuredExporter` |
| **LangGraph Hooks** | `backend/instrumentation/langgraph_hooks.py` | Node-level hooks that populate `AgentEvent` fields |

### Backend Layer

| Component | File | Purpose |
|---|---|---|
| **FastAPI App** | `backend/api/main.py` | REST + WebSocket server; all 14 endpoints; static serving for /, /ops, /topology |
| **AnomalyDetector** | `backend/instrumentation/anomaly_detector.py` | In-process pre-filter — loop, token spike, latency drift, error burst, trust collapse |
| **SplunkClient** | `backend/api/splunk_client.py` | HEC indexing, SPL search via REST, NL→SPL via AI Assistant |
| **Foundation-Sec Client** | `backend/api/foundation_sec.py` | Calls Splunk-hosted Foundation-Sec-1.1-8B; rule-based fallback |
| **Autopsy** | `backend/api/autopsy.py` | Post-run trace analysis — graded A–F, cost estimate, fix recommendation |
| **Notifications** | `backend/api/main.py` (inline) | Slack webhook for CRITICAL anomalies via `notify_slack_critical()` |
| **PDF Export** | `backend/api/main.py` (inline) | `POST /api/export/incident` → reportlab PDF |

### Splunk Platform

| Capability | Detail |
|---|---|
| **Splunk HEC** | `index=agentwatch`, `sourcetype=agentwatch:otel`, 2,299+ events indexed |
| **Splunk MCP Server** | All telemetry queryable via SPL from the UI |
| **Splunk AI Toolkit** | Native `anomalydetection` command — 139-tool-call spike at 99.25% confidence |
| **Splunk AI Assistant** | NL → SPL; e.g. "show me all loops in the last hour" → valid SPL |
| **Foundation-Sec-1.1-8B** | Powers "Explain This", "Run Autopsy", and PDF incident export |
| **Dashboard** | 8 panels: KPI, anomaly table, trust heatmap, loop chart, token usage, latency drift, event log, trust by tool |
| **Splunk Cloud App** | `splunk_app/agentwatch/` — app.conf, indexes.conf, inputs.conf, props.conf, transforms.conf, savedsearches.conf |

### Frontend Layer

| Module | File | Purpose |
|---|---|---|
| **Three.js Brain** | `frontend/index.html` + `src/brain.js` | Force-directed graph: nodes = steps, color = trust, pulse = event, ring = anomaly |
| **Agent Ops Dashboard** | `frontend/ops.html` | CRM dashboard: run history, trust trend, anomaly breakdown, SLOs, cost tracker |
| **Topology Map** | `frontend/topology.html` | Multi-agent force-directed graph: agent hubs, edge particles, orbit camera |
| **WebSocket Client** | `frontend/src/websocket.js` | WS connection with auto-reconnect; replay on connect |
| **Alert Overlays** | `frontend/src/alerts.js` | Anomaly alert banners + "Export PDF" button + Foundation-Sec explanation |
| **AI Assistant** | `frontend/src/assistant.js` | NL query → `/api/query` → SPL + results table |
| **Health Score** | `frontend/src/health_score.js` | Live composite health score |
| **Sparklines** | `frontend/src/sparklines.js` | Mini trust/token/latency sparklines |
| **Trace Timeline** | `frontend/src/trace_timeline.js` | Step-by-step trace timeline |
| **Autopsy Panel** | `frontend/src/autopsy_panel.js` | Post-run autopsy: grade, cost, root cause, fix |
| **Landing Page** | `docs/index.html` | GitHub Pages marketing site |

---

## Key Stats (Real Data)

| Metric | Value |
|--------|-------|
| Total events indexed | 2,299+ |
| Anomalies detected | 342 |
| Avg trust score | 58.1% |
| Total tokens processed | 279,993 |
| Loop spike confidence | 99.25% |
| Frameworks supported | 5 (LangGraph · CrewAI · OpenAI Agents · AutoGen · generic) |
| Frontend pages | 3 (Brain · Ops · Topology) |
| API endpoints | 14 |
| Splunk AI capabilities | 4 (MCP · AI Toolkit · Foundation-Sec · AI Assistant) |
| Splunk index | `agentwatch` |
| Source type | `agentwatch:otel` |
| Live demo | https://agentwatch-i555.onrender.com |

---

## Anomaly Detection Thresholds

| Anomaly Type | Trigger Condition | Severity | Confidence Formula | Configurable |
|---|---|---|---|---|
| **Loop** | Same tool called ≥ 5× in one trace | HIGH / CRITICAL (≥10×) | `min(0.99, 0.70 + (count−5) × 0.05)` | ✅ |
| **Token Spike** | `llm_total_tokens` ≥ 3,000 | MEDIUM / HIGH / CRITICAL | `min(0.95, 0.6 + ratio × 0.1)` | ✅ |
| **Latency Drift** | `duration_ms` ≥ 3,000ms | MEDIUM / HIGH (≥6,000ms) | `min(0.90, 0.65 + ms/threshold × 0.1)` | ✅ |
| **Error Burst** | ≥ 3 errors in one trace | HIGH / CRITICAL (≥5) | `min(0.95, 0.70 + count × 0.05)` | ✅ |
| **Trust Collapse** | `trust_score` ≤ 0.3 | MEDIUM / HIGH / CRITICAL | `min(0.90, 0.60 + (0.3−trust) × 2)` | ✅ |

All thresholds configurable live via `POST /api/config` or the **⚙ Config** panel in the UI.

---

## Trust Score Formula

```
trust = max(0.05, 1.0 / (1 + 0.3 × max(0, error_count − 3)))
```

| Error Count | Trust Score |
|---|---|
| 0–3 | 1.00 |
| 4 | 0.77 |
| 5 | 0.63 |
| 8 | 0.40 |
| 12 | 0.28 |
| 20+ | ~0.05 (floor) |

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `WS` | `/ws/agent-stream` | Agent → backend event stream |
| `WS` | `/ws/browser` | Backend → browser live events |
| `POST` | `/api/explain` | Anomaly explanation via Foundation-Sec |
| `POST` | `/api/query` | Natural language → SPL via AI Assistant |
| `POST` | `/api/autopsy` | Post-run trace analysis, grade A–F |
| `GET` | `/api/history` | Last 30 run summaries for trust trend chart |
| `GET` | `/api/config` | Current alert thresholds |
| `POST` | `/api/config` | Update alert thresholds live (takes effect immediately) |
| `POST` | `/api/export/incident` | Generate PDF incident report (reportlab) |
| `POST` | `/api/demo/trigger` | Trigger in-process demo run (normal/loop/hallucinate/drift) |
| `GET` | `/api/demo/status` | Check if a demo run is active |
| `GET` | `/api/events` | Recent events from ring buffer |
| `GET` | `/api/stats` | Live stats: event count, anomalies, avg trust |
| `GET` | `/api/health` | Backend health + Splunk connectivity check |
| `GET` | `/` | Serves Live Brain (`frontend/index.html`) |
| `GET` | `/ops` | Serves Agent Ops Dashboard (`frontend/ops.html`) |
| `GET` | `/topology` | Serves Topology Map (`frontend/topology.html`) |

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `SPLUNK_HOST` | `localhost` | Splunk server hostname |
| `SPLUNK_PORT` | `8089` | Splunk REST API port |
| `SPLUNK_HEC_PORT` | `8088` | HEC ingestion port |
| `SPLUNK_HEC_TOKEN` | — | HEC authentication token |
| `SPLUNK_USERNAME` | `admin` | REST API login |
| `SPLUNK_PASSWORD` | `changeme` | REST API password |
| `SPLUNK_INDEX` | `agentwatch` | Target index |
| `SPLUNK_AI_ENDPOINT` | — | Foundation-Sec API endpoint |
| `SPLUNK_AI_TOKEN` | — | Foundation-Sec auth token |
| `SLACK_WEBHOOK_URL` | — | Slack incoming webhook for CRITICAL alerts (optional) |
| `SPLUNK_URL` | `http://localhost:8000` | Splunk base URL for deep links in Slack messages |
| `OTEL_EXPORTER` | `console` | `splunk_hec` or `console` or `otlp` |
| `PUBLIC_DEMO_INDEX_TO_SPLUNK` | `false` | Index public demo runs to Splunk |

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Agent framework | LangGraph | 0.2.28 |
| Framework hooks | CrewAI · OpenAI Agents SDK · AutoGen | via `agentwatch_hooks.py` |
| Observability | OpenTelemetry SDK | 1.27.0 |
| SDK | `agentwatch_sdk.py` + `agentwatch_hooks.py` | in-repo |
| Backend API | FastAPI + uvicorn | 0.115.4 / 0.32.0 |
| WebSocket | websockets | 13.1 |
| HTTP client | httpx | 0.27.2 |
| PDF generation | reportlab | ≥4.0.0 |
| Event transport | Splunk HEC | port 8088 |
| Anomaly detection (in-process) | `anomaly_detector.py` | in-repo |
| Anomaly detection (Splunk) | Splunk AI Toolkit `anomalydetection` | — |
| Natural language queries | Splunk AI Assistant | — |
| Hosted AI model | Foundation-Sec-1.1-8B | Splunk |
| Agent integration | Splunk MCP Server | — |
| 3D visualization (brain) | Three.js | r128 |
| 3D visualization (topology) | Three.js | r128 |
| Ops dashboard charts | Chart.js | 4.4.1 |
| Splunk app packaging | Native `.conf` files | splunk_app/ |
| Deployment | Railway | — |
| Frontend hosting | GitHub Pages | — |

---

## Splunk AI Capabilities Used

- ✅ **Splunk MCP Server** — all agent telemetry indexed and searchable via SPL
- ✅ **Splunk AI Assistant** — natural language to SPL query generation with template fallback
- ✅ **Foundation-Sec-1.1-8B** — Splunk-hosted model for "Explain This", "Run Autopsy", and PDF incident export
- ✅ **Splunk AI Toolkit** — native `anomalydetection` command on tool-call time-series (99.25% confidence on loop spike)