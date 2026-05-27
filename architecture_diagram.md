# AgentWatch — System Architecture

## Overview

AgentWatch is a real-time AI agent observability platform that instruments LangGraph agents with OpenTelemetry, streams telemetry to Splunk via HEC, and visualizes trust scores and anomalies through a Three.js brain visualization and Splunk dashboards.

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph AGENT["🤖 AI AGENT LAYER"]
        LG["LangGraph Demo Agent\n━━━━━━━━━━━━━━━\n• normal mode\n• loop mode\n• hallucinate\n• drift mode"]
        OT["OpenTelemetry\n━━━━━━━━━━━━━━━\n• traces & spans\n• trust scores\n• token counts"]
        FS["Foundation-Sec-1.1-8B\n━━━━━━━━━━━━━━━\n• Splunk hosted model\n• rule-based reasoning\n• Explain This button"]
        LG -->|instruments| OT
    end

    subgraph BACKEND["⚙️ BACKEND LAYER"]
        API["FastAPI\n━━━━━━━━━━━━━━━\n• REST API\n• /run /search\n• /anomalies /explain"]
        WS["Event Stream\n━━━━━━━━━━━━━━━\n• WebSocket\n• real-time push\n• 500-event buffer"]
        SC["SplunkClient\n━━━━━━━━━━━━━━━\n• HEC indexing\n• SPL search\n• AI Assistant NL→SPL"]
        API -->|fan-out| WS
    end

    subgraph SPLUNK["☁️ SPLUNK PLATFORM"]
        HEC["HEC Ingest\n━━━━━━━━━━━━━━━\nindex: agentwatch\nsourcetype:\nagentwatch:otel\n1,269+ events"]
        AITK["AI Toolkit\n━━━━━━━━━━━━━━━\nanomaly detection\n• tool call frequency\n• time-series analysis"]
        MCP["MCP Server\n━━━━━━━━━━━━━━━\n• NL queries\n• SPL generation"]
        DASH["Splunk Dashboard — 8 Panels\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\nKPI · Anomaly table · Trust heatmap · Loop detection\nToken usage · Latency drift · Event log · Trust by tool"]
        HEC --> AITK
        HEC --> MCP
        AITK --> DASH
        MCP --> DASH
    end

    subgraph FRONTEND["🖥️ FRONTEND LAYER"]
        BRAIN["Three.js Brain\n━━━━━━━━━━━━━━━\nlocalhost:3000\n• node pulses\n• anomaly glow\n• trust colors"]
        FEED["Live Events Feed\n━━━━━━━━━━━━━━━\n• anomaly alerts\n• node inspector\n• Foundation-Sec panel"]
        LAND["Landing Page\n━━━━━━━━━━━━━━━\nGitHub Pages\nashish-doing.\ngithub.io/agentwatch"]
    end

    OT -->|HEC POST| HEC
    OT -->|events| API
    API --> SC
    SC -->|SPL queries| MCP
    WS -->|WebSocket| BRAIN
    WS --> FEED
    FS --> FEED
```

---

## Data Flow

```mermaid
sequenceDiagram
    participant Agent as LangGraph Agent
    participant HEC as Splunk HEC
    participant Splunk as Splunk Dashboard
    participant Brain as Three.js Brain
    participant FS as Foundation-Sec

    Agent->>HEC: tool_call event (trust_score, trace_id)
    Agent->>HEC: llm_call event (tokens, latency)
    Agent->>HEC: anomaly event (loop detected, trust=0.05)
    HEC->>Splunk: Index to agentwatch
    Splunk->>Splunk: anomalydetection command fires
    Splunk-->>Brain: WebSocket demo simulation
    Brain->>Brain: Node pulses red 🔴
    Brain->>FS: Click "Explain This"
    FS-->>Brain: Root cause + recommended fix
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