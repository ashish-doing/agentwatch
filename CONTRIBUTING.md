# Contributing to AgentWatch

Thanks for your interest in AgentWatch! This guide will help you get started.

## Ways to Contribute

- **Bug reports** — open an issue with steps to reproduce
- **Feature requests** — open an issue describing the use case
- **Code contributions** — fork, branch, PR
- **New agent support** — add instrumentation for CrewAI, AutoGen, or other frameworks

## Local Setup

```bash
git clone https://github.com/ashish-doing/agentwatch.git
cd agentwatch
cp .env.example .env
# Fill in your Splunk HEC token and credentials
pip install -r backend/requirements.txt
```

Start the backend:
```bash
uvicorn backend.api.main:app --host 0.0.0.0 --port 8001 --reload
```

Start the frontend:
```bash
cd frontend && python -m http.server 3000
```

Run the demo agent:
```bash
python backend/agent/agent_runner.py --mode loop
```

## Adding a New Agent Framework

To instrument a new framework (e.g. CrewAI), create a new file in `backend/instrumentation/` following the pattern in `langgraph_hooks.py`:

1. Hook into the framework's execution lifecycle
2. Call `_send()` with the appropriate event type and fields
3. Include `trust_score`, `trace_id`, `agent_id`, `step_name` in every event

## Code Style

- Python: follow PEP 8, use type hints
- JavaScript: vanilla ES modules, no build step required
- Commit messages: `type: description` (e.g. `fix: correct trust score calculation`)

## PR Process

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Make changes and test locally
4. Open a PR with a clear description of what and why

## Questions

Open an issue or reach out via GitHub discussions.