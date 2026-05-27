# AgentWatch — System Architecture

## Overview

AgentWatch is a real-time AI agent observability platform that instruments LangGraph agents with OpenTelemetry, streams telemetry to Splunk via HEC, and visualizes trust scores and anomalies through a Three.js brain visualization and Splunk dashboards.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          AI AGENT LAYER                                 │
│                                                                         │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────┐  │
│  │   LangGraph      │   │  OpenTelemetry   │   │  Foundation-Sec    │  │
│  │   Demo Agent     │──▶│  Instrumentation │   │  (Splunk hosted    │  │
│  │                  │   │                  │   │   model)           │  │
│  │  • normal mode   │   │  • traces        │   │                    │  │
│  │  • loop mode     │   │  • spans         │   │  • rule-based      │  │
│  │  • hallucinate   │   │  • trust scores  │   │    reasoning       │  │
│  │  • drift mode    │   │  • token counts  │   │  • "Explain This"  │  │
│  └──────────────────┘   └────────┬─────────┘   └────────────────────┘  │
└───────────────────────────────── │ ────────────────────────────────────┘
                                   │ OTel events + HEC POST
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          BACKEND LAYER                                  │
│                                                                         │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────┐  │
│  │    FastAPI       │   │   Event Stream   │   │   SplunkClient     │  │
│  │                  │   │                  │   │                    │  │
│  │  • REST API      │──▶│  • WebSocket     │   │  • HEC indexing    │  │
│  │  • /run          │   │  • real-time     │   │  • SPL search      │  │
│  │  • /search       │   │    event push    │   │  • AI Assistant    │  │
│  │  • /anomalies    │   │  • 500-event     │   │    NL → SPL        │  │
│  │  • /explain      │   │    ring buffer   │   │  • foundation_sec  │  │
│  └────────┬─────────┘   └──────────────────┘   └─────────┬──────────┘  │
└───────────│─────────────────────────────────────────────│──────────────┘
            │ HEC POST                                     │ SPL queries
            ▼                                             ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SPLUNK PLATFORM                                 │
│                                                                         │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────┐  │
│  │   HEC Ingest     │   │   AI Toolkit     │   │   MCP Server       │  │
│  │                  │   │                  │   │                    │  │
│  │  index:          │   │  anomalydetect-  │   │  • NL queries      │  │
│  │  agentwatch      │   │  ion command     │   │  • SPL generation  │  │
│  │                  │   │                  │   │  • prize category  │  │
│  │  sourcetype:     │   │  • tool call     │   │                    │  │
│  │  agentwatch:otel │   │    frequency     │   │  AI Assistant      │  │
│  │                  │   │  • time-series   │   │  • NL → SPL bar    │  │
│  │  1,269+ events   │   │    analysis      │   │  • auto-generated  │  │
│  └────────┬─────────┘   └──────────────────┘   └────────────────────┘  │
│           │                                                             │
│  ┌────────▼─────────────────────────────────────────────────────────┐  │
│  │                     Splunk Dashboard (8 panels)                   │  │
│  │   KPI · Anomaly table · Trust heatmap · Loop detection chart     │  │
│  │   Token usage · Latency drift · Full event log · Trust by tool   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
            │ WebSocket (demo simulation)
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND LAYER                                  │
│                                                                         │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────────┐  │
│  │  Three.js Brain  │   │  Live Events     │   │  Landing Page      │  │
│  │  Visualization   │   │  Feed            │   │                    │  │
│  │                  │   │                  │   │  GitHub Pages      │  │
│  │  localhost:3000  │   │  • anomaly alerts│   │  ashish-doing.     │  │
│  │                  │   │  • node inspector│   │  github.io/        │  │
│  │  • node pulses   │   │  • trust scores  │   │  agentwatch        │  │
│  │  • anomaly glow  │   │  • Foundation-   │   │                    │  │
│  │  • trust colors  │   │    Sec panel     │   │                    │  │
│  └──────────────────┘   └──────────────────┘   └────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

```
Agent run triggered
        │
        ▼
LangGraph executes steps (normal / loop / hallucinate / drift)
        │
        ▼
demo_agent.py sends events directly → Splunk HEC
        │
        ├──▶ Splunk agentwatch index
        │           │
        │           ├──▶ Dashboard panels (8 panels, 30d range)
        │           ├──▶ AI Toolkit anomalydetection
        │           └──▶ MCP Server NL queries
        │
        └──▶ Anomaly detected → Foundation-Sec "Explain This"
                                plain English + recommended fix + SPL

Browser connects to localhost:3000
        │
        ▼
websocket.js tries ws://localhost:8001/ws/browser
        │
        ├── Connected → real events from FastAPI
        └── Failed    → demo simulation auto-starts
                        (loop anomaly, trust degradation, alerts)
```

---

## Key Stats (Real Data)

| Metric | Value |
|--------|-------|
| Total events indexed | 1,269+ |
| Anomalies detected | 180 |
| Avg trust score | 59.7% |
| Total tokens processed | 159,970 |
| Splunk index | `agentwatch` |
| Source type | `agentwatch:otel` |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LangGraph (Python) |
| Observability | OpenTelemetry |
| Backend API | FastAPI + WebSockets |
| Event transport | Splunk HEC (port 8088) |
| Anomaly detection | Splunk AI Toolkit — `anomalydetection` |
| Natural language queries | Splunk AI Assistant (NL→SPL) |
| Hosted AI model | Foundation-Sec-1.1-8B (Splunk) |
| Agent integration | Splunk MCP Server |
| 3D visualization | Three.js r128 |
| Frontend hosting | GitHub Pages |

---

## Splunk AI Capabilities Used

- ✅ **Splunk MCP Server** — all agent telemetry indexed and searchable via SPL
- ✅ **Splunk AI Assistant** — natural language to SPL query generation
- ✅ **Foundation-Sec-1.1-8B** — hosted model for anomaly explanation ("Explain This")
- ✅ **Splunk AI Toolkit** — native `anomalydetection` command on tool call time-series