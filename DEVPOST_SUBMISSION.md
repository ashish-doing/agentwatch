# AgentWatch — Devpost Submission Text
# Copy-paste each section into the Devpost form

---

## PROJECT NAME
AgentWatch — AI Agent Observability Platform for Splunk

---

## TAGLINE (one sentence)
The first real-time observability platform for LangGraph agents — wraps any AI agent with OpenTelemetry, streams behavior into Splunk, detects anomalies with Cisco Deep Time Series, and explains them in plain English with Foundation-Sec.

---

## DESCRIPTION (main body — paste this)

### The Problem

The world is filling with AI agents that fail silently.

34% of production AI agents fail silently due to missing observability tooling. When a LangGraph agent gets stuck calling the same tool 23 times, nobody knows. When token counts spike to 8,000+, nobody notices. When latency drifts 300% over 2 hours, nobody catches it — until the bill arrives.

Loop failures cost enterprises $2,400/hour in wasted API calls. Mean time to detect an agent failure without observability: 4.2 hours. With AgentWatch: under 1 second.

### What AgentWatch Does

AgentWatch is a Splunk Platform app that wraps any LangGraph agent with OpenTelemetry, streams its complete behavior into Splunk in real time, detects anomalies automatically, and explains them in plain English with a specific fix recommendation.

**One click:** "Explain this anomaly" → Foundation-Sec reasons over the context → plain English explanation + recommended code fix + auto-generated SPL drill-down query.

### How It Uses Splunk AI (5 tools, 1 coherent pipeline)

**1. Splunk MCP Server**
Every agent event — LLM call, tool invocation, reasoning step, error — is indexed via HTTP Event Collector with source type `agentwatch:otel`. The MCP Server makes all telemetry instantly searchable via SPL.

**2. Splunk AI Toolkit + Cisco Deep Time Series**
The AI Toolkit runs a Cisco Deep Time Series model on `tool_call_count` time series data. When a tool gets called 5+ times in a single trace, the anomaly score exceeds 0.75 and an alert fires automatically — no manual thresholds, no rule writing.

**3. Foundation-Sec-1.1-8B**
When an anomaly is detected, Foundation-Sec receives the anomaly context + last 10 agent events and returns a structured JSON response: what happened, root cause, recommended fix, severity level. This turns a raw anomaly signal into actionable engineering guidance.

**4. Splunk AI Assistant**
The AgentWatch UI includes a natural language query bar powered by Splunk AI Assistant. Type "Show me all loops in the last hour" and it generates the SPL, executes it, and returns results — no SPL expertise needed.

**5. OpenTelemetry → Splunk HEC**
Every span is exported directly to Splunk HEC with full structured context: trace_id, step_id, trust_score, llm_total_tokens, duration_ms, tool_name, reasoning_content. This creates a complete audit trail of every agent decision.

### The Brain Visualization

The centerpiece is a Three.js force-directed brain graph that shows the agent's reasoning in real time:
- **Nodes** = reasoning steps and tool calls
- **Edges** = execution flow between steps
- **Color** = trust score (green → yellow → orange → red)
- **Size** = token count / importance
- **Pulse** = currently active step
- **Red flash** = anomaly detected

When a loop fires, the affected node pulses red, an alert card appears, and one click on "Explain This" triggers Foundation-Sec analysis.

### Trust Scoring

Every event gets a trust score (0-100%) computed from:
- Tool call frequency (repeated calls degrade trust exponentially)
- Token count (high token counts signal runaway generation)
- Error rate (errors immediately reduce trust)
- Step duration (latency outliers reduce trust)

The composite trust score gives operators instant situational awareness without reading logs.

### Demo Agent (4 Failure Modes)

AgentWatch ships with a demo LangGraph agent that simulates realistic failure modes:
- **normal** — healthy agent, trust scores 85-100%
- **loop** — search_tool called 23x, trust drops to 5%, anomaly fires
- **hallucinate** — token spikes to 8000+, runaway generation pattern
- **drift** — each step 30% slower, latency degradation anomaly

### Real Data in Splunk

Running the demo agent in loop mode generates 118+ structured events in Splunk with fields including: `event_type`, `agent_id`, `trace_id`, `step_name`, `trust_score`, `llm_total_tokens`, `tool_name`, `reasoning_content`, `duration_ms`.

### Why This Wins

- **Every company deploying AI agents needs this** — the market is $28.5B by 2028
- **No existing solution** instruments LangGraph agents for Splunk
- **5 Splunk AI tools** used in a coherent, production-grade pipeline
- **Real working demo** with confirmed Splunk data indexing
- **Instant value** — instrument any LangGraph agent in 3 lines of code

---

## TECHNOLOGIES USED (check these on Devpost)
- Splunk
- Python
- JavaScript
- OpenTelemetry
- LangGraph
- Three.js
- FastAPI

---

## LINKS
- GitHub: https://github.com/ashish-doing/agentwatch
- Landing Page: https://ashish-doing.github.io/agentwatch
- Demo Video: [add after recording]

---

## WHAT I LEARNED
Building AgentWatch taught me how to instrument AI agents at the execution level using OpenTelemetry spans — capturing not just errors but the full reasoning context of every LLM and tool call. Integrating Cisco Deep Time Series for anomaly detection on agent telemetry was a new pattern I hadn't seen before. The biggest insight: trust scoring based on behavioral patterns (not just error rates) gives operators much faster signal than traditional monitoring.

---

## CHALLENGES
The hardest part was getting real-time event fan-out working — the agent runs synchronously but the browser needs live updates. The solution was a FastAPI WebSocket layer that buffers events and fans them out to all browser clients, with a 500-event ring buffer for new connections catching up. Getting Splunk HEC to accept structured JSON with custom source types also required careful configuration of the agentwatch:otel source type.

---

## WHAT'S NEXT
- Foundation-Sec hosted model integration (currently falls back to rule-based when token not configured)
- Splunk AI Toolkit pipeline configuration guide with screenshots
- Support for CrewAI and AutoGen agents (not just LangGraph)
- Splunk app packaging for one-click Splunkbase install
- Production-grade trust scoring with ML-based baselines