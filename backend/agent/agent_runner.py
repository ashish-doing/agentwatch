"""
agentwatch/backend/agent/agent_runner.py
Sends events directly to Splunk HEC.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import demo_agent as da
from demo_agent import build_demo_agent, make_initial_state

from rich.console import Console
from rich.panel import Panel
console = Console()
logging.basicConfig(level=logging.WARNING)

HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "")
HEC_HOST = os.getenv("SPLUNK_HOST", "localhost")
HEC_PORT = os.getenv("SPLUNK_HEC_PORT", "8088")
INDEX = os.getenv("SPLUNK_INDEX", "agentwatch")
HEC_URL = f"https://{HEC_HOST}:{HEC_PORT}/services/collector/event"

EVENTS_SENT = 0

def print_banner(mode):
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

    print_banner(args.mode)

    trace_id = uuid.uuid4().hex

    # Inject HEC config into demo_agent module
    da._hec_token = "" if args.no_splunk else HEC_TOKEN
    da._hec_url = HEC_URL
    da._trace_id = trace_id
    da._index = INDEX

    console.print(f"\n[dim]Initializing OpenTelemetry...[/dim]")
    console.print(f"[dim]Building LangGraph agent...[/dim]")
    console.print(f"[dim]HEC Token: {HEC_TOKEN[:15]}...[/dim]")
    console.print(f"[dim]HEC URL: {HEC_URL}[/dim]")

    topic_map = {
        "normal": "AI agent observability market size and trends 2026",
        "loop": "latest AI agent failure modes and loop detection",
        "hallucinate": "quantum AI breakthrough announcements 2026",
        "drift": "enterprise software adoption patterns and ROI",
    }
    console.print(f"\n[bold]Starting agent run...[/bold] topic=[cyan]{topic_map[args.mode]}[/cyan]\n")

    graph = build_demo_agent()
    state = make_initial_state(mode=args.mode)
    result = asyncio.run(graph.ainvoke(state, config={"recursion_limit": 50}))

    report = result.get("final_report", "No report generated")
    console.print("\n")
    console.print(Panel(
        f"\n[bold white]{report}[/bold white]\n",
        title="[bold green]📄 AgentWatch — Final Report[/bold green]",
        border_style="green",
        padding=(1, 4),
        expand=False,
    ))
    console.print(f"\n[bold green]✅ Agent run complete[/bold green]")
    console.print(f"[cyan]📊 Events indexed:[/cyan] [white]check Splunk dashboard[/white]")
    console.print(f"[cyan]🔗 Splunk trace:[/cyan]  [dim]search index={INDEX} trace_id={trace_id}[/dim]")
    console.print(f"[cyan]🧠 Brain:[/cyan]          [dim]http://localhost:3000[/dim]")
    console.print(f"[cyan]📊 Dashboard:[/cyan]      [dim]http://localhost:8000/en-US/app/search/agentwatch[/dim]\n")


if __name__ == "__main__":
    main()