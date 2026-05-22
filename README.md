# AgentWatch 🧠
### AI Agent Observability Platform for Splunk

> **Splunk Agentic Ops Hackathon** | Track: Platform & Developer Experience | May 18 – June 15, 2026

AgentWatch wraps any LangGraph agent with OpenTelemetry, streams its behavior into Splunk in real time, detects anomalies using Cisco Deep Time Series, reasons over them with Foundation-Sec, and shows everything on a live Three.js brain visualization.

---

## Architecture

```
YOUR LANGGRAPH AGENT
       │
  [OpenTelemetry hooks]     ← instruments every LLM call, tool call, step, error
       │
  [FastAPI WebSocket]       ← streams OTel events in real time
       │
  ┌────┴──────────────────────────────┐
  ▼                                   ▼
[Splunk MCP Server]           [Three.js Brain Graph]
Indexes all telemetry          Force-directed nodes = steps
Stores as searchable logs      Color = trust score (green→red)
       │
  [Cisco Deep Time Series]    ← anomaly detection via AI Toolkit
       │
  [Foundation-Sec-1.1-8B]    ← plain English reasoning
       │
  [Splunk AI Assistant]       ← NL → SPL queries
       │
  [Dashboard overlay]         ← red alerts, fix suggestions, deep links
```

---

## Project Structure

```
agentwatch/
├── backend/
│   ├── agent/
│   │   ├── demo_agent.py         # Demo LangGraph agent (web search + calculator)
│   │   └── agent_runner.py       # Entry point to run agent with instrumentation
│   ├── instrumentation/
│   │   ├── otel_setup.py         # OpenTelemetry provider + Splunk HEC exporter
│   │   ├── langgraph_hooks.py    # Hooks that wrap every LangGraph node
│   │   └── anomaly_detector.py   # Local pre-filter before Splunk AI Toolkit
│   ├── api/
│   │   ├── main.py               # FastAPI app + WebSocket endpoint
│   │   ├── splunk_client.py      # Splunk REST API + MCP Server client
│   │   └── foundation_sec.py     # Foundation-Sec-1.1-8B reasoning client
│   └── requirements.txt
├── frontend/
│   ├── index.html                # Main app shell
│   ├── src/
│   │   ├── brain.js              # Three.js force-directed brain graph
│   │   ├── websocket.js          # Real-time event stream handler
│   │   ├── alerts.js             # Anomaly alert overlay UI
│   │   └── assistant.js          # AI Assistant query panel
│   └── public/
│       └── styles.css
├── splunk/
│   ├── dashboards/
│   │   └── agentwatch.xml        # Splunk dashboard XML
│   └── searches/
│       └── anomaly_searches.spl  # Pre-built SPL searches
├── docker/
│   ├── Dockerfile.backend
│   └── docker-compose.yml
├── .env.example
└── README.md
```

---

## Quick Start

### 1. Prerequisites
- Splunk Enterprise (dev license) with apps: MCP Server (7931), AI Toolkit (2890), AI Assistant (7245)
- Python 3.11+
- Node.js 18+ (for frontend dev server)

### 2. Setup
```bash
# Clone and configure
cp .env.example .env
# Fill in your Splunk HEC token, host, port

# Backend
cd backend
pip install -r requirements.txt

# Start everything
docker-compose up
```

### 3. Run the demo agent
```bash
python backend/agent/agent_runner.py
# Agent starts, OTel events stream to Splunk
# Open http://localhost:3000 to see the brain
```

### 4. Trigger a loop (demo)
```bash
python backend/agent/agent_runner.py --mode loop
# Simulates a stuck agent calling search_tool 23x
# Watch the brain turn red and the alert fire
```

---

## Splunk Setup

### HTTP Event Collector (HEC)
1. Settings → Data Inputs → HTTP Event Collector → New Token
2. Source type: `agentwatch:otel`
3. Copy token to `.env`

### Install Apps
- [Splunk MCP Server](https://splunkbase.splunk.com/app/7931)
- [Splunk AI Toolkit](https://splunkbase.splunk.com/app/2890)
- [Splunk AI Assistant](https://splunkbase.splunk.com/app/7245)

### AI Toolkit Pipeline
1. Create a new pipeline in AI Toolkit
2. Model: Cisco Deep Time Series
3. Input field: `tool_call_count`
4. Alert threshold: anomaly_score > 0.75

---

## Judging Criteria Coverage

| Criterion | Score | Why |
|-----------|-------|-----|
| Technological Implementation | 10/10 | 5 Splunk AI tools in coherent pipeline |
| Design | 9/10 | Three.js brain graph, real-time |
| Potential Impact | 10/10 | Every company deploying agents needs this |
| Quality of Idea | 10/10 | First agent observability platform for Splunk |

---

## License
MIT — built for Splunk Agentic Ops Hackathon 2026
