# 🧠 AgentWatch
### AI Agent Observability Platform for Splunk

<p align="center">
  <img src="https://img.shields.io/badge/Splunk-MCP%20Server-FF4500?style=for-the-badge&logo=splunk" />
  <img src="https://img.shields.io/badge/Splunk-AI%20Toolkit-FF4500?style=for-the-badge&logo=splunk" />
  <img src="https://img.shields.io/badge/Foundation--Sec-1.1--8B-00B4D8?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Cisco-Deep%20Time%20Series-1BA0D7?style=for-the-badge&logo=cisco" />
  <img src="https://img.shields.io/badge/LangGraph-0.2.28-green?style=for-the-badge" />
  <img src="https://img.shields.io/badge/OpenTelemetry-1.27.0-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Three.js-r128-black?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Python-3.10-blue?style=for-the-badge&logo=python" />
</p>

<p align="center">
  <strong>Splunk Agentic Ops Hackathon 2026 — Track: Platform & Developer Experience</strong>
</p>

<p align="center">
  <a href="https://ashish-doing.github.io/agentwatch">🌐 Landing Page</a> •
  <a href="https://github.com/ashish-doing/agentwatch">📁 GitHub</a> •
  <a href="#quick-start">🚀 Quick Start</a> •
  <a href="#architecture">🏗️ Architecture</a>
</p>

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

**AgentWatch** is a Splunk Platform app that wraps any LangGraph agent with OpenTelemetry, streams its behavior into Splunk in real time, detects anomalies using Cisco Deep Time Series, reasons over them with Foundation-Sec-1.1-8B, and shows everything on a live Three.js brain visualization.

**One click:** "Explain this anomaly" → plain English answer + fix recommendation + SPL query.

---

## 🏗️ Architecture

```
YOUR LANGGRAPH AGENT
        │
   [OpenTelemetry Hooks]
   Instruments every:
   ├── LLM call (model, tokens, latency, reasoning)
   ├── Tool call (name, input, output, duration)
   ├── Reasoning step (step_id, content, confidence)
   └── Error/exception
        │
        ▼
   [FastAPI WebSocket]  ──────────────────────────────────┐
   Streams OTel events                                     │
   in real time                                            ▼
        │                                    [Three.js Live Brain Graph]
        ▼                                    Force-directed visualization:
   [Splunk HEC]                              ├── Nodes = reasoning steps
   Indexes all telemetry                     ├── Edges = tool calls
   Source type: agentwatch:otel              ├── Color = trust score (green→red)
        │                                    └── Pulse = active right now
        ▼
   [Splunk MCP Server]  ←── All events searchable via SPL
        │
        ▼
   [Cisco Deep Time Series]  ←── via Splunk AI Toolkit
   Anomaly detection on:
   ├── Tool call frequency (loop detection)
   ├── Token count spikes (runaway generation)
   ├── Latency patterns (degradation)
   └── Error rate trends
        │
        ▼
   [Foundation-Sec-1.1-8B]  ←── Splunk hosted model
   Reasons over anomaly context
   Output: plain English + recommended action
        │
        ▼
   [Splunk AI Assistant]  ←── NL → SPL
   "Show me all loops in the last hour"
   → generates SPL → queries Splunk → results
        │
        ▼
   [Dashboard Overlay]
   ⚠️ "Loop detected at tool_search — called 23x in 4s"
   📋 "Fix: add empty-result guard at step 3"
   🔍 "View in Splunk" → deep link to full trace
```

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Agent Instrumentation | OpenTelemetry SDK 1.27.0 | Capture every LLM/tool call |
| Event Indexing | Splunk MCP Server (app 7931) | Real-time telemetry indexing |
| Anomaly Detection | Cisco Deep Time Series via AI Toolkit | Time-series anomaly scoring |
| Reasoning Engine | Foundation-Sec-1.1-8B | Plain English anomaly explanation |
| NL Query | Splunk AI Assistant (app 7245) | Natural language → SPL |
| Demo Agent | LangGraph 0.2.28 | The agent being monitored |
| Backend | FastAPI + WebSocket | Real-time event streaming |
| Visualization | Three.js r128 | Live brain graph |
| Transport | Splunk HEC (port 8088) | Event delivery |

---

## 🚀 Quick Start

### Prerequisites
- Splunk Enterprise (dev license) with these apps installed:
  - [Splunk MCP Server](https://splunkbase.splunk.com/app/7931) (app 7931)
  - [Splunk AI Toolkit](https://splunkbase.splunk.com/app/2890) (app 2890)
  - [Splunk AI Assistant](https://splunkbase.splunk.com/app/7245) (app 7245)
- Python 3.10+
- Git

### 1. Clone & Configure

```bash
git clone https://github.com/ashish-doing/agentwatch.git
cd agentwatch
cp .env.example .env
# Edit .env with your Splunk HEC token and credentials
```

### 2. Splunk Setup

```bash
# In Splunk: Settings → Data Inputs → HTTP Event Collector → New Token
# Name: agentwatch-hec
# Source type: agentwatch:otel
# Default index: agentwatch (create this index first)
# Copy the token to .env → SPLUNK_HEC_TOKEN
```

### 3. Install Dependencies

```bash
pip install -r backend/requirements.txt
```

### 4. Start the Backend

```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --reload
```

### 5. Start the Frontend

```bash
cd frontend
python -m http.server 3000
# Open http://localhost:3000
```

### 6. Run the Demo Agent

```bash
# Normal mode — healthy agent
python backend/agent/agent_runner.py --mode normal

# Loop mode — triggers anomaly detection (demo)
python backend/agent/agent_runner.py --mode loop

# Hallucination mode — token spike anomaly
python backend/agent/agent_runner.py --mode hallucinate

# Drift mode — latency degradation anomaly
python backend/agent/agent_runner.py --mode drift
```

---

## 🎯 Demo Script

```
0:00 — "AI agents are everywhere. Nobody's watching them. AgentWatch changes that."

0:20 — Show LangGraph agent running normally
       Three.js brain graph pulsing green
       Nodes light up as steps execute

1:00 — Trigger loop mode: python agent_runner.py --mode loop
       Graph turns orange → red
       Alert fires: "Loop detected — search_tool called 23x"

1:30 — Click "Explain This"
       Foundation-Sec reasons: "Agent stuck at query refinement
       step — no exit condition when search returns empty"

2:00 — "Fix suggestion: add empty-result guard at step 3"
       Show Splunk with 118+ events indexed, full trace

2:30 — Show AI Assistant: "Show me all loops in the last hour"
       → SPL generated → results returned

3:00 — "AgentWatch: because your agents need a guardian."
```

---

## 📊 What AgentWatch Detects

| Failure Mode | Detection Method | Alert |
|-------------|-----------------|-------|
| Infinite loops | Tool call frequency > threshold | ⚠️ CRITICAL |
| Token spikes | LLM token count anomaly | ⚠️ HIGH |
| Latency drift | Step duration trend analysis | ⚠️ MEDIUM |
| Silent errors | Error rate spike detection | ⚠️ HIGH |
| Trust collapse | Composite score < 0.3 | ⚠️ CRITICAL |

---

## 🔍 Splunk Queries

```spl
# Find all loops in the last hour
index=agentwatch event_type=tool_call earliest=-1h
| stats count as call_count by agent_id, tool_name, trace_id
| where call_count > 5
| sort -call_count

# Token spike detection
index=agentwatch event_type=llm_call
| stats max(llm_total_tokens) as max_tokens by step_name, trace_id
| where max_tokens > 3000
| sort -max_tokens

# Trust score heatmap
index=agentwatch
| stats avg(trust_score) as avg_trust by tool_name
| sort avg_trust

# Full trace reconstruction
index=agentwatch trace_id=YOUR_TRACE_ID
| sort _time
| table _time, event_type, step_name, trust_score, duration_ms
```

---

## 🏆 Judging Criteria

| Criterion | Evidence |
|-----------|---------|
| **Technological Implementation** | 5 Splunk AI tools in coherent pipeline: MCP Server + AI Toolkit + Cisco Deep Time Series + Foundation-Sec + AI Assistant |
| **Design** | Three.js force-directed brain graph, real-time trust scoring, Foundation-Sec reasoning panel |
| **Potential Impact** | Every company deploying LangGraph agents needs this — $2,400/hr loop cost, 34% silent failure rate |
| **Quality of Idea** | First agent observability platform built natively for Splunk |

---

## 📁 Project Structure

```
agentwatch/
├── backend/
│   ├── agent/
│   │   ├── demo_agent.py          # Demo LangGraph agent (4 failure modes)
│   │   └── agent_runner.py        # CLI runner with direct HEC sending
│   ├── instrumentation/
│   │   ├── otel_setup.py          # OpenTelemetry + Splunk HEC exporter
│   │   ├── langgraph_hooks.py     # LangGraph node instrumentation hooks
│   │   └── anomaly_detector.py    # Pre-filter before AI Toolkit
│   ├── api/
│   │   ├── main.py                # FastAPI + WebSocket fan-out
│   │   ├── splunk_client.py       # Splunk REST + MCP + AI Assistant
│   │   └── foundation_sec.py      # Foundation-Sec-1.1-8B client
│   └── requirements.txt
├── frontend/
│   ├── index.html                 # Main app shell
│   └── src/
│       ├── brain.js               # Three.js force-directed brain graph
│       ├── websocket.js           # Real-time WebSocket handler
│       ├── alerts.js              # Anomaly alert overlays
│       └── assistant.js           # Splunk AI Assistant panel
├── splunk/
│   ├── dashboards/agentwatch.xml  # Splunk dashboard
│   └── searches/anomaly_searches.spl
├── docs/
│   └── index.html                 # Landing page (GitHub Pages)
├── docker/
│   ├── Dockerfile.backend
│   └── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🌐 Links

- **Landing Page:** https://ashish-doing.github.io/agentwatch
- **GitHub:** https://github.com/ashish-doing/agentwatch
- **Devpost:** https://splunk.devpost.com
- **Splunk MCP Server:** https://splunkbase.splunk.com/app/7931
- **Splunk AI Toolkit:** https://splunkbase.splunk.com/app/2890

---

## 👤 Author

**Ashish Kumar**
B.Tech ECE, IIIT Guwahati (Batch 2024)
- GitHub: [@ashish-doing](https://github.com/ashish-doing)
- LinkedIn: [linkedin.com/in/ashish-kumar-014aaa3b9](https://linkedin.com/in/ashish-kumar-014aaa3b9)

---

## 📄 License

MIT — built for Splunk Agentic Ops Hackathon 2026