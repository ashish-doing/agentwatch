# Contributing to AgentWatch

Thanks for your interest in AgentWatch! This guide covers everything you need to contribute — from running tests to adding new agent framework support.

---

## Ways to Contribute

- **Bug reports** — open an issue with steps to reproduce
- **Feature requests** — open an issue describing the use case
- **Code contributions** — fork, branch, PR
- **New agent framework support** — add hooks for any framework via `agentwatch_hooks.py`
- **New anomaly detection types** — extend `AnomalyDetector` in `backend/instrumentation/anomaly_detector.py`
- **SPL queries** — add useful searches to `splunk/searches/anomaly_searches.spl`
- **Tests** — expand `backend/tests/` coverage

---

## Local Setup

```bash
git clone https://github.com/ashish-doing/agentwatch.git
cd agentwatch
cp .env.example .env
# Fill in SPLUNK_HEC_TOKEN and SPLUNK_AI_TOKEN
# Optional: SLACK_WEBHOOK_URL for CRITICAL anomaly Slack alerts
pip install -r backend/requirements.txt
```

Start the backend:
```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --reload
```

All three UI pages will be available at:
- `http://localhost:8001/` — Live Brain
- `http://localhost:8001/ops` — Agent Ops CRM Dashboard
- `http://localhost:8001/topology` — Multi-Agent Topology Map

Run the demo agent (pick a failure mode):
```bash
python backend/agent/agent_runner.py --mode normal      # healthy run
python backend/agent/agent_runner.py --mode loop        # infinite loop anomaly
python backend/agent/agent_runner.py --mode hallucinate # token spike anomaly
python backend/agent/agent_runner.py --mode drift       # latency drift anomaly
```

Or trigger demos directly from the UI buttons — no terminal needed.

---

## Running Tests

AgentWatch has **81 tests** across two files. Run them before submitting any PR:

```bash
pip install pytest pytest-asyncio httpx reportlab
pytest backend/tests/ -v
```

Expected output:
```
backend/tests/test_anomaly.py ................................ [ 39%]
backend/tests/test_api.py ..................................................  [100%]
81 passed in ~1s
```

All tests run fully offline — no real Splunk, Slack, or Foundation-Sec endpoint required.

### Test files

| File | Tests | Covers |
|---|---|---|
| `backend/tests/test_anomaly.py` | 32 | `AnomalyDetector` — all 5 detection types, trust formula, severity levels, trace isolation, reset |
| `backend/tests/test_api.py` | 49 | All API endpoints — `/api/history`, `/api/config`, `/api/export/incident`, `/api/explain`, Slack webhook, live threshold propagation |

When adding new features, add corresponding tests. PRs without tests for new detection logic or API endpoints will be asked to add them before merging.

---

## Project Structure

```
agentwatch/
├── backend/
│   ├── agent/
│   │   ├── demo_agent.py          # LangGraph demo agent (4 failure modes)
│   │   ├── agent_runner.py        # CLI runner
│   │   └── demo_runner_lib.py     # In-process demo trigger for UI buttons
│   ├── instrumentation/
│   │   ├── otel_setup.py          # OpenTelemetry + HEC exporter
│   │   ├── langgraph_hooks.py     # LangGraph node hooks
│   │   └── anomaly_detector.py    # In-process pre-filter (5 anomaly types)
│   ├── api/
│   │   ├── main.py                # FastAPI + WebSocket + all 14 endpoints
│   │   ├── splunk_client.py       # Splunk REST + MCP + AI Assistant
│   │   ├── foundation_sec.py      # Foundation-Sec-1.1-8B client + fallback
│   │   └── autopsy.py             # Agent Autopsy (grade A–F)
│   ├── tests/
│   │   ├── test_anomaly.py        # 32 unit tests — AnomalyDetector
│   │   └── test_api.py            # 49 integration tests — API endpoints
│   ├── agentwatch_sdk.py          # Zero-config @watch / watch_graph
│   ├── agentwatch_hooks.py        # CrewAI · OpenAI Agents · AutoGen hooks
│   └── requirements.txt
├── frontend/
│   ├── index.html                 # Live Brain
│   ├── ops.html                   # Agent Ops CRM Dashboard
│   ├── topology.html              # Multi-Agent Topology Map
│   └── src/                       # JS modules (brain, websocket, alerts, etc.)
├── splunk/
│   ├── dashboards/agentwatch.xml  # 8-panel Splunk dashboard XML
│   └── searches/anomaly_searches.spl
├── splunk_app/agentwatch/         # Splunk Cloud native app package
├── docker/                        # Docker Compose + Dockerfile
├── docs/screenshots/              # README screenshots
├── architecture.svg               # Architecture diagram
└── architecture.md                # Annotated architecture + data flows
```

---

## Adding a New Agent Framework

To add support for a new framework, add a hook class to `backend/agentwatch_hooks.py` following the existing pattern:

1. Hook into the framework's execution lifecycle (callbacks, decorators, or middleware)
2. Build an event dict with these required fields every time:

```python
event = {
    "event_type": "tool_call",      # tool_call | llm_call | step_start | step_end | error
    "agent_id": agent_name,
    "trace_id": trace_id,           # unique per agent run
    "step_id": step_id,
    "step_name": step_name,
    "tool_name": tool_name,         # empty string for non-tool events
    "trust_score": trust_score,     # float 0.0–1.0
    "llm_total_tokens": tokens,     # 0 for non-LLM events
    "duration_ms": duration_ms,
    "error": "",                    # error message or empty string
}
```

3. Send it via WebSocket to `ws://localhost:8001/ws/agent-stream`:

```python
import websocket, json
ws = websocket.WebSocket()
ws.connect("ws://localhost:8001/ws/agent-stream")
ws.send(json.dumps(event))
```

Or use the SDK convenience wrapper:

```python
from agentwatch_sdk import watch

@watch(agent_name="my_agent")
def my_node(state): ...
```

---

## Adding a New Anomaly Detection Type

Extend `AnomalyDetector` in `backend/instrumentation/anomaly_detector.py`:

1. Add a threshold constant at the top of the file
2. Add detection logic inside `check_event()` returning an `AnomalyResult`
3. Call `update_thresholds()` to make it live-configurable via `/api/config`
4. Add the new threshold field to `AlertConfig` in `backend/api/main.py`
5. Write tests in `backend/tests/test_anomaly.py` covering at least: below threshold (no anomaly), at threshold (fires), severity levels, and trace isolation

---

## Adding SPL Queries

Add new searches to `splunk/searches/anomaly_searches.spl` and the corresponding saved search to `splunk_app/agentwatch/default/savedsearches.conf`. Follow the naming pattern `agentwatch_<description>`.

---

## Code Style

- **Python** — PEP 8, type hints on all function signatures, docstrings on public methods
- **JavaScript** — vanilla ES modules, no build step, no bundler required
- **Commit messages** — `type: description` (e.g. `feat: add error_burst Slack notification`, `fix: trust score floor off-by-one`, `test: add latency drift edge cases`, `docs: update framework support table`)

---

## PR Process

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Make changes and run `pytest backend/tests/ -v` — all 81 must pass
4. Add tests for any new detection logic or API endpoints
5. Open a PR with a clear description of what changed and why

---

## Questions

Open an issue or reach out via GitHub Discussions.