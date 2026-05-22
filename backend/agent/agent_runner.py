"""
agentwatch/backend/agent/agent_runner.py
Sends events directly to Splunk HEC — no WebSocket needed.
"""

import os
import sys
import asyncio
import argparse
import json
import time
import uuid
import ssl
import urllib.request
import logging

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.demo_agent import build_demo_agent, make_initial_state

from rich.console import Console
from rich.panel import Panel
console = Console()
logging.basicConfig(level=logging.WARNING)


# ── Direct HEC sender ──────────────────────────────────────

HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "")
HEC_HOST = os.getenv("SPLUNK_HOST", "localhost")
HEC_PORT = os.getenv("SPLUNK_HEC_PORT", "8088")
INDEX = os.getenv("SPLUNK_INDEX", "agentwatch")
HEC_URL = f"https://{HEC_HOST}:{HEC_PORT}/services/collector/event"

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

EVENTS_SENT = 0

def send_to_splunk(event: dict):
    global EVENTS_SENT
    if not HEC_TOKEN:
        return
    payload = json.dumps({
        "time": event.get("timestamp", time.time()),
        "index": INDEX,
        "source": "agentwatch",
        "sourcetype": "agentwatch:otel",
        "event": event,
    }).encode()
    try:
        req = urllib.request.Request(
            HEC_URL,
            data=payload,
            headers={
                "Authorization": f"Splunk {HEC_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        urllib.request.urlopen(req, context=_ctx, timeout=3)
        EVENTS_SENT += 1
    except Exception as e:
        console.print(f"[red]HEC error: {e}[/red]")


# ── Event emitter ──────────────────────────────────────────

AGENT_ID = "demo-001"
TRACE_ID = ""

def emit(event_type: str, step_name: str, **kwargs):
    event = {
        "event_type": event_type,
        "agent_id": AGENT_ID,
        "trace_id": TRACE_ID,
        "step_id": str(uuid.uuid4())[:8],
        "step_name": step_name,
        "timestamp": time.time(),
        **kwargs,
    }
    send_to_splunk(event)
    # Show in console
    trust = kwargs.get("trust_score", 1.0)
    pct = int(trust * 100)
    color = "green" if pct > 70 else "yellow" if pct > 40 else "red"
    console.print(f"  [{color}]{event_type:12s}[/{color}] {step_name:30s} trust=[{color}]{pct}%[/{color}]")


# ── Instrumented graph runner ──────────────────────────────

def run_instrumented(mode: str):
    global TRACE_ID
    TRACE_ID = uuid.uuid4().hex

    graph = build_demo_agent()
    state = make_initial_state(mode=mode)

    console.print(f"\n[dim]Trace ID: {TRACE_ID[:16]}...[/dim]")
    console.print(f"[dim]Sending events to Splunk HEC at {HEC_URL}[/dim]\n")

    # Patch nodes to emit events
    import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import demo_agent as da
    original_research = da.research_node
    original_analysis = da.analysis_node
    original_synthesis = da.synthesis_node

    def patched_research(state):
        emit("step_start", "research", trust_score=1.0)
        result = original_research(state)
        loop_count = result.get("loop_count", 0)
        # Emit LLM call
        msg = result["messages"][-1] if result["messages"] else {}
        tokens = msg.get("tokens", 500) if isinstance(msg, dict) else 500
        emit("llm_call", "research",
             llm_total_tokens=tokens,
             llm_model="mock-llm",
             trust_score=max(0.1, 1.0 - loop_count * 0.04))
        # Emit tool call
        tool = msg.get("tool_call", {}) if isinstance(msg, dict) else {}
        if tool:
            trust = max(0.05, 1.0 - loop_count * 0.05)
            emit("tool_call", f"tool:{tool.get('tool_name','search_tool')}",
                 tool_name=tool.get("tool_name", "search_tool"),
                 tool_input=tool.get("input", ""),
                 tool_output=tool.get("output", ""),
                 duration_ms=tool.get("duration_ms", 200),
                 trust_score=trust)
            # Anomaly after 5 calls
            if loop_count >= 5:
                emit("anomaly", f"tool:{tool.get('tool_name','search_tool')}",
                     tool_name=tool.get("tool_name", "search_tool"),
                     trust_score=0.05,
                     reasoning_content=f"Loop detected — search_tool called {loop_count}x in this run")
        emit("step_end", "research",
             duration_ms=1200,
             trust_score=max(0.1, 1.0 - loop_count * 0.04))
        return result

    def patched_analysis(state):
        emit("step_start", "analysis", trust_score=0.9)
        result = original_analysis(state)
        msg = result["messages"][-1] if result["messages"] else {}
        tokens = msg.get("tokens", 800) if isinstance(msg, dict) else 800
        emit("llm_call", "analysis", llm_total_tokens=tokens, llm_model="mock-llm", trust_score=0.85)
        emit("tool_call", "tool:calculator_tool",
             tool_name="calculator_tool", duration_ms=12, trust_score=0.92)
        emit("step_end", "analysis", duration_ms=900, trust_score=0.88)
        return result

    def patched_synthesis(state):
        emit("step_start", "synthesis", trust_score=0.9)
        result = original_synthesis(state)
        msg = result["messages"][-1] if result["messages"] else {}
        tokens = msg.get("tokens", 600) if isinstance(msg, dict) else 600
        emit("llm_call", "synthesis", llm_total_tokens=tokens, llm_model="mock-llm", trust_score=0.9)
        emit("step_end", "synthesis", duration_ms=700, trust_score=0.9)
        return result

    da.research_node = patched_research
    da.analysis_node = patched_analysis
    da.synthesis_node = patched_synthesis

    graph = build_demo_agent()
    state = make_initial_state(mode=mode)

    import asyncio
    result = asyncio.run(graph.ainvoke(state, config={"recursion_limit": 50}))

    da.research_node = original_research
    da.analysis_node = original_analysis
    da.synthesis_node = original_synthesis

    return result


def print_banner(mode: str):
    colors = {"normal": "green", "loop": "red", "hallucinate": "yellow", "drift": "orange3"}
    color = colors.get(mode, "white")
    console.print(Panel(
        f"[bold white]AgentWatch[/bold white] [dim]AI Agent Observability Platform[/dim]\n\n"
        f"Mode: [{color}]{mode.upper()}[/{color}]\n\n"
        f"[dim]Open http://localhost:3000 to see the live brain visualization[/dim]",
        title="🧠 AgentWatch Demo", border_style=color,
    ))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["normal","loop","hallucinate","drift"], default="normal")
    parser.add_argument("--no-splunk", action="store_true")
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8001/ws/agent-stream")
    args = parser.parse_args()

    if args.no_splunk:
        os.environ["SPLUNK_HEC_TOKEN"] = ""

    print_banner(args.mode)
    console.print(f"\n[dim]Initializing OpenTelemetry...[/dim]")
    console.print(f"[dim]Building LangGraph agent...[/dim]")

    topic_map = {
        "normal": "AI agent observability market size and trends 2026",
        "loop": "latest AI agent failure modes and loop detection",
        "hallucinate": "quantum AI breakthrough announcements 2026",
        "drift": "enterprise software adoption patterns and ROI",
    }
    console.print(f"\n[bold]Starting agent run...[/bold] topic=[cyan]{topic_map[args.mode]}[/cyan]\n")

    result = run_instrumented(args.mode)

    console.print(f"\n")
    console.print(Panel(
        result.get("final_report", "[dim]No report[/dim]"),
        title="📄 Final Report", border_style="green",
    ))
    console.print(f"\n[green]✅ Agent run complete[/green]")
    console.print(f"[cyan]Events sent to Splunk: {EVENTS_SENT}[/cyan]")
    console.print(f"[dim]View full trace in Splunk: search index={INDEX} trace_id={TRACE_ID}[/dim]")


if __name__ == "__main__":
    main()
