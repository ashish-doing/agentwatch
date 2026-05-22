"""
agentwatch/backend/agent/demo_agent.py

NO API KEY REQUIRED.
Simulates a realistic LangGraph agent and sends real OTel events to Splunk.

Modes:
  normal      → healthy research agent, trust scores 0.85-1.0
  loop        → search_tool called 23x, trust drops to 0.05, anomaly fires
  hallucinate → token spikes to 8000+, trust degrades
  drift       → each step gets 30% slower, latency anomaly fires
"""

import random
import time
from typing import TypedDict, List
from langgraph.graph import StateGraph, END


class AgentState(TypedDict):
    messages: List[dict]
    research_topic: str
    search_results: List[str]
    calculations: List[str]
    final_report: str
    loop_count: int
    mode: str


SEARCH_RESULTS = [
    "Global AI agent market projected at $28.5B by 2028, growing 43% CAGR.",
    "LangGraph: 50,000+ GitHub stars, used by Fortune 500 for agent orchestration.",
    "34% of production AI agents fail silently due to missing observability tooling.",
    "Splunk processes 1+ petabyte daily across enterprise customers.",
    "Loop failures account for 67% of all AI agent production incidents.",
    "Average cost of undetected agent loop: $2,400/hour in wasted API calls.",
    "OpenTelemetry adoption grew 280% in 2025, driven by AI/ML monitoring.",
    "Agent observability is the #1 gap in enterprise AI deployments 2026.",
]

REASONING_STEPS = [
    "Analyzing search results for key market trends and statistics.",
    "Cross-referencing data sources to validate growth projections.",
    "Computing ROI metrics based on failure cost analysis.",
    "Synthesizing findings into executive summary format.",
    "Identifying top 3 actionable recommendations from data.",
]

FINAL_REPORTS = [
    "Executive Summary: AI agent observability market represents a $28.5B opportunity. "
    "With 34% of agents failing silently and loop failures costing $2,400/hour, "
    "AgentWatch addresses a critical enterprise gap. Recommendations: "
    "(1) Deploy observability before production rollout, "
    "(2) Instrument all LangGraph nodes with OpenTelemetry, "
    "(3) Set trust score alerts at threshold 0.5.",
]


def simulate_search(query: str, mode: str, call_count: int) -> dict:
    base_ms = 180 + random.randint(20, 80)
    if mode == "drift":
        base_ms = int(base_ms * (1 + 0.3 * call_count))
    time.sleep(base_ms / 1000)
    if mode == "loop" and call_count > 2:
        output = "No results found. Retrying with different query terms..."
    else:
        output = random.choice(SEARCH_RESULTS)
    return {"tool_name": "search_tool", "input": query, "output": output, "duration_ms": base_ms}


def simulate_calculator(expression: str) -> dict:
    time.sleep(0.012)
    return {"tool_name": "calculator_tool", "input": expression, "output": "40.755B USD projected 2027", "duration_ms": 12}


def simulate_llm(step: str, mode: str) -> dict:
    if mode == "hallucinate":
        p, c = random.randint(2000, 4000), random.randint(3000, 5000)
    elif mode == "loop":
        p, c = random.randint(300, 500), random.randint(100, 200)
    else:
        p, c = random.randint(300, 800), random.randint(200, 600)
    latency = (p + c) * 0.8 + random.randint(100, 300)
    time.sleep(latency / 1000)
    return {"model": "mock-llm", "prompt_tokens": p, "completion_tokens": c,
            "total_tokens": p + c, "duration_ms": latency, "reasoning": random.choice(REASONING_STEPS)}


def research_node(state: AgentState) -> AgentState:
    mode = state.get("mode", "normal")
    loop_count = state.get("loop_count", 0)
    llm = simulate_llm("research", mode)
    search = simulate_search(f"AI {state.get('research_topic', 'observability')}", mode, loop_count)
    results = state.get("search_results", [])
    results.append(search["output"])
    messages = state.get("messages", [])
    messages.append({"role": "assistant", "content": llm["reasoning"],
                     "tokens": llm["total_tokens"], "tool_call": search})
    return {**state, "messages": messages, "search_results": results, "loop_count": loop_count + 1}


def analysis_node(state: AgentState) -> AgentState:
    mode = state.get("mode", "normal")
    llm = simulate_llm("analysis", mode)
    calc = simulate_calculator("28.5 * 1.43")
    calcs = state.get("calculations", [])
    calcs.append(calc["output"])
    messages = state.get("messages", [])
    messages.append({"role": "assistant", "content": llm["reasoning"], "tokens": llm["total_tokens"]})
    return {**state, "messages": messages, "calculations": calcs}


def synthesis_node(state: AgentState) -> AgentState:
    mode = state.get("mode", "normal")
    llm = simulate_llm("synthesis", mode)
    messages = state.get("messages", [])
    report = random.choice(FINAL_REPORTS)
    messages.append({"role": "assistant", "content": report, "tokens": llm["total_tokens"]})
    return {**state, "messages": messages, "final_report": report}


def should_continue(state: AgentState) -> str:
    mode = state.get("mode", "normal")
    count = state.get("loop_count", 0)
    if mode == "loop" and count < 23:
        return "research"
    if mode == "normal" and count < 2:
        return "research"
    return "analysis"


def build_demo_agent():
    graph = StateGraph(AgentState)
    graph.add_node("research", research_node)
    graph.add_node("analysis", analysis_node)
    graph.add_node("synthesis", synthesis_node)
    graph.set_entry_point("research")
    graph.add_conditional_edges("research", should_continue, {
        "research": "research", "analysis": "analysis"})
    graph.add_edge("analysis", "synthesis")
    graph.add_edge("synthesis", END)
    return graph.compile()


def make_initial_state(mode: str = "normal", topic: str = "AI agent observability") -> AgentState:
    topics = {
        "normal": "AI agent observability market size and trends 2026",
        "loop": "latest AI agent failure modes and loop detection",
        "hallucinate": "quantum AI breakthrough announcements 2026",
        "drift": "enterprise software adoption patterns and ROI",
    }
    return AgentState(messages=[], research_topic=topics.get(mode, topic),
                      search_results=[], calculations=[], final_report="",
                      loop_count=0, mode=mode)
