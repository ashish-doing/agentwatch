# AgentWatch — System Architecture

## Overview

AgentWatch is a real-time AI agent observability platform that instruments LangGraph agents with OpenTelemetry, streams telemetry to Splunk via HEC, and visualizes trust scores and anomalies through a Three.js brain visualization and Splunk dashboards.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI AGENT LAYER                               │
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌──────────────────┐  │
│  │   LangGraph     │   │  OpenTelemetry  │   │  Foundation-Sec  │  │
│  │  Demo Agent     │──▶│  Instrumentation│   │  (Splunk hosted  │  │
│  │                 │   │                 │   │   model)         │  │
│  │ • normal mode   │   │ • traces        │   │                  │  │
│  │ • loop mode     │   │ • spans         │   │ • rule-based     │  │
│  │ • hallucinate   │   │ • trust scores  │   │   reasoning      │  │
│  │ • drift mode    │   │ • token counts  │   │ • "Explain This" │  │
│  └─────────────────┘   └────────┬────────┘   └──────────────────┘  │
└────────────────────────────────┬┴────────────────────────────────────┘
                                 │ OTel events
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND LAYER                               │
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌──────────────────┐  │
│  │    FastAPI      │   │  Event Stream   │   │  SplunkClient    │  │
│  │                 │   │                 │   │                  │  │
│  │ • REST API      │──▶│ • WebSocket     │   │ • HEC indexing   │  │
│  │ • /run endpoint │   │ • real-time     │   │ • SPL search     │  │
│  │ • /search       │   │   event push    │   │ • AI Assistant   │  │
│  │ • /anomalies    │   │                 │   │   NL → SPL       │  │
│  └────────┬────────┘   └─────────────────┘   └────────┬─────────┘  │
└───────────┼──────────────────────────────────────────┼─────────────┘
            │ HEC POST                                  │ SPL queries
            ▼                                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        SPLUNK PLATFORM                              │
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌──────────────────┐  │
│  │   HEC Ingest    │   │   AI Toolkit    │   │   MCP Server     │  │
│  │                 │   │                 │   │                  │  │
│  │ index: agent-   │   │ • IQR anomaly   │   │ • natural lang.  │  │
│  │ watch           │   │   detection     │   │   queries        │  │
│  │ sourcetype:     │   │ • time-series   │   │ • Splunk prize   │  │
│  │ agentwatch:otel │   │   analysis      │   │   category       │  │
│  │ 118+ events     │   │                 │   │                  │  │
│  └────────┬────────┘   └─────────────────┘   └──────────────────┘  │
│           │                                                         │
│  ┌────────▼────────────────────────────────────────────────────┐   │
│  │                    Splunk Dashboard                          │   │
│  │  KPI panel · Anomaly table · Trust heatmap                  │   │
│  │  Latency drift · Full event log · AI Assistant query bar    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
            │ WebSocket events
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND LAYER                               │
│                                                                     │
│  ┌─────────────────┐   ┌─────────────────┐   ┌──────────────────┐  │
│  │  Three.js Brain │   │  Live Events    │   │  Landing Page    │  │
│  │  Visualization  │   │  Feed           │   │                  │  │
│  │                 │   │                 │   │ GitHub Pages     │  │
│  │ localhost:3000  │   │ • anomaly alerts│   │ ashish-doing.    │  │
│  │                 │   │ • node inspector│   │ github.io/       │  │
│  │ • real-time     │   │ • trust scores  │   │ agentwatch       │  │
│  │   node pulses   │   │                 │   │                  │  │
│  │ • anomaly glow  │   │                 │   │                  │  │
│  └─────────────────┘   └─────────────────┘   └──────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
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
OpenTelemetry captures each step → trust score calculated
       │
       ├──▶ FastAPI backend receives OTel event
       │           │
       │           ├──▶ WebSocket → Three.js brain lights up in real-time
       │           │
       │           └──▶ SplunkClient.index_event() → HEC POST
       │                       │
       │                       ▼
       │               Splunk agentwatch index
       │                       │
       │                       ├──▶ Dashboard panels refresh
       │                       ├──▶ AI Toolkit IQR anomaly detection
       │                       └──▶ MCP Server NL queries
       │
       └──▶ Anomaly detected → Foundation-Sec "Explain This" reasoning
```

---

## Key Stats (Real Data)

| Metric | Value |
|--------|-------|
| Total events indexed | 118+ |
| Anomalies detected | 18 |
| Total tokens processed | 13,822 |
| Splunk index | `agentwatch` |
| Source type | `agentwatch:otel` |
| HEC token | `agentwatch-hec-v3` |

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LangGraph (Python) |
| Observability | OpenTelemetry |
| Backend API | FastAPI + WebSockets |
| AI observability | Splunk Enterprise + HEC |
| ML anomaly detection | Splunk AI Toolkit (IQR) |
| Natural language queries | Splunk AI Assistant (NL→SPL) |
| Hosted AI model | Foundation-Sec (Splunk) |
| Agent integration | Splunk MCP Server |
| 3D visualization | Three.js |
| Frontend hosting | GitHub Pages |

---

## Splunk AI Capabilities Used

- ✅ **Splunk MCP Server** — agent integration via Model Context Protocol
- ✅ **Splunk AI Assistant** — natural language to SPL query generation
- ✅ **Foundation-Sec** — Splunk hosted model for anomaly explanation
- ✅ **Splunk AI Toolkit** — IQR time-series anomaly detection