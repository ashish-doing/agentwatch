"""
agentwatch/backend/api/autopsy.py

Post-run Agent Autopsy — called after each complete agent run.
Uses the existing FoundationSecClient from foundation_sec.py to
produce a structured diagnostic report over the full trace.

Wired into main.py as a new endpoint:  POST /api/autopsy
Called from frontend after agent run completes (step with step_name='synthesis' + step_end).

Fields it reads match exactly what demo_agent._send() and langgraph_hooks emit:
  event_type, step_name, trust_score, llm_total_tokens, duration_ms, tool_name, error, trace_id
"""

import json
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger("agentwatch.autopsy")

# ── Autopsy prompt — structured for Foundation-Sec ───────────────────────

AUTOPSY_SYSTEM = """You are Foundation-Sec, an AI agent performance analyst embedded in AgentWatch.
Analyze a complete agent trace and return a structured autopsy JSON report.

Respond ONLY with valid JSON, no preamble, no markdown fences.
Schema:
{
  "objective": "What was the agent trying to accomplish? (1-2 sentences)",
  "successes": ["thing it did well 1", "thing it did well 2"],
  "root_cause": "Root cause of any failure or null if healthy",
  "fix_recommendation": "Specific code-level fix or null if healthy",
  "severity": "healthy | degraded | critical",
  "performance_grade": "A | B | C | D | F",
  "grade_reason": "One sentence justification for the grade",
  "estimated_cost_usd": 0.00,
  "key_metric": "The single most important metric from this run"
}"""

AUTOPSY_PROMPT = """Analyze this complete agent run:

Agent: {agent_name}
Mode: {mode}
Total Steps: {total_steps}
Total Tokens: {total_tokens}
Total Duration: {duration_ms}ms
Anomalies Detected: {anomaly_count}
Errors: {error_count}
Lowest Trust Score: {min_trust}
Average Trust Score: {avg_trust}
Tool Call Summary: {tool_summary}
Final Report Generated: {has_report}

Produce the autopsy JSON."""


# ── Autopsy builder ───────────────────────────────────────────────────────

def build_autopsy_context(events: List[dict]) -> dict:
    """
    Summarise a list of trace events into the stats needed for the prompt.
    event fields match demo_agent._send() / langgraph_hooks AgentEvent.to_dict()
    """
    if not events:
        return {}

    total_tokens = sum(int(e.get("llm_total_tokens") or 0) for e in events)
    total_duration = sum(float(e.get("duration_ms") or 0) for e in events)
    anomalies = [e for e in events if e.get("event_type") == "anomaly"]
    errors = [e for e in events if e.get("event_type") == "error"]

    trust_scores = [float(e["trust_score"]) for e in events if e.get("trust_score") is not None]
    min_trust = round(min(trust_scores), 3) if trust_scores else 1.0
    avg_trust = round(sum(trust_scores) / len(trust_scores), 3) if trust_scores else 1.0

    tool_counts: Dict[str, int] = {}
    for e in events:
        if e.get("event_type") == "tool_call" and e.get("tool_name"):
            t = e["tool_name"]
            tool_counts[t] = tool_counts.get(t, 0) + 1

    has_report = any(e.get("step_name") == "synthesis" and e.get("event_type") == "step_end" for e in events)
    agent_name = events[0].get("agent_id", "demo-001") if events else "unknown"
    mode = "unknown"
    # Try to infer mode from anomaly patterns
    if len(anomalies) > 3:
        mode = "loop"
    elif total_tokens > 30000:
        mode = "hallucinate"
    elif total_duration > 20000:
        mode = "drift"
    else:
        mode = "normal"

    return {
        "agent_name": agent_name,
        "mode": mode,
        "total_steps": len(events),
        "total_tokens": total_tokens,
        "duration_ms": round(total_duration),
        "anomaly_count": len(anomalies),
        "error_count": len(errors),
        "min_trust": min_trust,
        "avg_trust": avg_trust,
        "tool_summary": json.dumps(tool_counts),
        "has_report": has_report,
    }


def rule_based_autopsy(ctx: dict) -> dict:
    """
    Fallback autopsy when Foundation-Sec endpoint is unavailable.
    Covers all 4 demo_agent modes.
    """
    grade = "A"
    severity = "healthy"
    root_cause = None
    fix = None
    successes = []
    key_metric = f"avg trust {ctx.get('avg_trust', 1.0)}"

    # Cost estimate: ~$0.002 per 1K tokens (GPT-4 mini equivalent)
    cost = round((ctx.get("total_tokens", 0) / 1000) * 0.002, 4)

    anomaly_count = ctx.get("anomaly_count", 0)
    min_trust = ctx.get("min_trust", 1.0)
    total_tokens = ctx.get("total_tokens", 0)
    duration_ms = ctx.get("duration_ms", 0)
    tool_summary = ctx.get("tool_summary", "{}")

    try:
        tools = json.loads(tool_summary)
    except Exception:
        tools = {}

    max_tool_calls = max(tools.values(), default=0)

    # ── Loop mode ──────────────────────────────────────────────────────
    if max_tool_calls >= 5 or anomaly_count >= 3:
        grade = "F"
        severity = "critical"
        root_cause = (
            f"Agent entered infinite loop — tool called {max_tool_calls}x "
            f"without exit condition. {anomaly_count} anomalies detected."
        )
        fix = (
            "Add empty-result guard in LangGraph conditional edge: "
            "if tool returns no results after 3 attempts, route to fallback node. "
            "In demo_agent.py: check `if loop_count >= 3: return 'analysis'` in should_continue()."
        )
        key_metric = f"max tool calls: {max_tool_calls}x"

    # ── Hallucinate mode ──────────────────────────────────────────────
    elif total_tokens > 20000:
        grade = "D"
        severity = "critical"
        root_cause = (
            f"Runaway token generation — {total_tokens:,} total tokens consumed. "
            "Agent generated excessively long completions without truncation."
        )
        fix = (
            "Add max_tokens=1000 to LLM call in simulate_llm(). "
            "Trim message history to last 10 messages before each LLM invocation."
        )
        key_metric = f"total tokens: {total_tokens:,}"

    # ── Drift mode ────────────────────────────────────────────────────
    elif duration_ms > 15000:
        grade = "C"
        severity = "degraded"
        root_cause = (
            f"Latency drift — total duration {duration_ms:,}ms. "
            "Step latency increased monotonically, indicating resource starvation or retry accumulation."
        )
        fix = (
            "Add timeout guards to each node: if step duration > 3s, route to fast-path. "
            "In simulate_search(), cap base_ms at 500ms regardless of call_count."
        )
        key_metric = f"total duration: {duration_ms:,}ms"

    # ── Normal / healthy ──────────────────────────────────────────────
    else:
        if min_trust > 0.8:
            grade = "A"
            successes = [
                "All reasoning steps completed within expected latency bounds",
                "Trust score remained above 80% throughout the run",
                "No anomalies or errors detected",
            ]
            key_metric = f"min trust: {min_trust}"
        else:
            grade = "B"
            severity = "healthy"
            successes = [
                "Agent completed all steps without critical failures",
                f"Final report generated successfully",
            ]
            key_metric = f"avg trust: {ctx.get('avg_trust', 1.0)}"

    return {
        "objective": (
            f"Research and synthesize information about AI agent observability "
            f"using a {ctx.get('mode', 'normal')}-mode LangGraph agent with "
            f"{len(json.loads(tool_summary))} tools."
        ),
        "successes": successes or [
            "Agent attempted all defined graph nodes",
            "OpenTelemetry spans captured for all steps",
        ],
        "root_cause": root_cause,
        "fix_recommendation": fix,
        "severity": severity,
        "performance_grade": grade,
        "grade_reason": _grade_reason(grade, ctx),
        "estimated_cost_usd": cost,
        "key_metric": key_metric,
    }


def _grade_reason(grade: str, ctx: dict) -> str:
    reasons = {
        "A": f"All steps healthy, avg trust {ctx.get('avg_trust', 1.0)}, zero anomalies.",
        "B": f"Minor degradation, avg trust {ctx.get('avg_trust', 1.0)}, recoverable.",
        "C": f"Latency drift or moderate anomalies — needs tuning.",
        "D": f"Significant token overuse ({ctx.get('total_tokens', 0):,} tokens) — production risk.",
        "F": f"Loop failure with {ctx.get('anomaly_count', 0)} anomalies — do not deploy without fix.",
    }
    return reasons.get(grade, "See root cause above.")


async def run_autopsy(events: List[dict], foundation_sec_client) -> dict:
    """
    Main entry point. Tries Foundation-Sec first, falls back to rule-based.
    foundation_sec_client = the existing FoundationSecClient instance from main.py
    """
    ctx = build_autopsy_context(events)
    if not ctx:
        return {"error": "No events to analyze"}

    prompt = AUTOPSY_PROMPT.format(**ctx)

    # Try Foundation-Sec
    try:
        # Reuse the existing explain() method with a synthetic anomaly event
        # that carries the full autopsy prompt as reasoning_content
        synthetic = {
            "event_type": "autopsy_request",
            "step_name": "full_trace_autopsy",
            "trust_score": ctx["avg_trust"],
            "reasoning_content": prompt,
            "tool_name": "",
            "llm_total_tokens": ctx["total_tokens"],
        }
        # Override the system prompt for autopsy by calling _call_foundation_sec directly
        if foundation_sec_client.endpoint and foundation_sec_client.token:
            import httpx
            resp = await foundation_sec_client._client.post(
                foundation_sec_client.endpoint,
                json={
                    "model": "foundation-sec-1.1-8b",
                    "messages": [
                        {"role": "system", "content": AUTOPSY_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 600,
                    "temperature": 0.1,
                },
                headers={
                    "Authorization": f"Bearer {foundation_sec_client.token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group())
                result["_source"] = "foundation-sec-1.1-8b"
                result["_context"] = ctx
                return result
    except Exception as e:
        logger.warning(f"Foundation-Sec autopsy failed: {e} — using rule-based fallback")

    result = rule_based_autopsy(ctx)
    result["_source"] = "rule-based-fallback"
    result["_context"] = ctx
    return result