"""
agentwatch/backend/api/foundation_sec.py

Client for Foundation-Sec-1.1-8B hosted on Splunk.
Used to reason over anomaly events and produce plain English explanations
with recommended fix actions.

When Splunk's Foundation-Sec endpoint isn't available (local dev), falls
back to a structured rule-based explanation engine so the demo always works.
"""

import os
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("agentwatch.foundation_sec")


# ─────────────────────────────────────────────
# Prompt Templates
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are Foundation-Sec, a security and reliability AI assistant 
specialized in analyzing AI agent behavior. You are embedded in AgentWatch, 
an observability platform for LangGraph agents.

When given an anomaly event and recent context, you:
1. Explain what went wrong in plain English (2-3 sentences)
2. Identify the root cause
3. Provide a specific, actionable fix recommendation
4. Assign a severity: low | medium | high | critical

Always respond with valid JSON matching this schema:
{
  "explanation": "...",
  "root_cause": "...",
  "recommended_action": "...",
  "severity": "low|medium|high|critical",
  "confidence": 0.0-1.0
}"""

ANOMALY_PROMPT_TEMPLATE = """Analyze this AI agent anomaly:

ANOMALY EVENT:
{anomaly}

RECENT CONTEXT (last {n} events before anomaly):
{context}

Explain what happened and how to fix it."""


# ─────────────────────────────────────────────
# Client
# ─────────────────────────────────────────────

class FoundationSecClient:
    def __init__(self):
        self.endpoint = os.getenv("SPLUNK_AI_ENDPOINT", "")
        self.token = os.getenv("SPLUNK_AI_TOKEN", "")
        self._client = httpx.AsyncClient(verify=False, timeout=30.0)

    async def explain(self, anomaly: Dict[str, Any], context: List[Dict]) -> Dict[str, str]:
        """
        Send anomaly + context to Foundation-Sec for reasoning.
        Returns dict with: explanation, root_cause, recommended_action, severity.
        """
        prompt = ANOMALY_PROMPT_TEMPLATE.format(
            anomaly=json.dumps(anomaly, indent=2),
            n=len(context),
            context=json.dumps(context[-10:], indent=2),
        )

        # Try Splunk-hosted Foundation-Sec
        if self.endpoint and self.token:
            try:
                result = await self._call_foundation_sec(prompt)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Foundation-Sec API error: {e} — using fallback")

        # Fallback: rule-based explanation engine
        return self._rule_based_explain(anomaly, context)

    async def _call_foundation_sec(self, prompt: str) -> Optional[Dict]:
        """Call the Splunk-hosted Foundation-Sec-1.1-8B endpoint."""
        resp = await self._client.post(
            self.endpoint,
            json={
                "model": "foundation-sec-1.1-8b",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": 500,
                "temperature": 0.1,
            },
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Parse JSON response
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON block from response
            import re
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                return json.loads(match.group())
        return None

    def _rule_based_explain(self, anomaly: Dict, context: List[Dict]) -> Dict[str, str]:
        """
        Fallback: structured rule-based anomaly explanation.
        Covers the most common agent failure modes detected by AgentWatch.
        """
        event_type = anomaly.get("event_type", "")
        tool_name = anomaly.get("tool_name", "unknown_tool")
        trust_score = float(anomaly.get("trust_score", 1.0))
        reasoning = anomaly.get("reasoning_content", "")
        step_name = anomaly.get("step_name", "unknown_step")

        # ── Loop Detection ──
        if "loop" in reasoning.lower() or "called" in reasoning.lower():
            call_count = _extract_call_count(reasoning)
            return {
                "explanation": (
                    f"The agent entered an infinite loop at the '{tool_name}' step, "
                    f"calling it {call_count}x without making progress. "
                    f"This typically occurs when the tool returns empty or unhelpful results "
                    f"and the agent has no exit condition."
                ),
                "root_cause": (
                    f"Missing termination condition in the routing logic after '{tool_name}'. "
                    f"The agent keeps retrying because it doesn't detect the 'no results' case."
                ),
                "recommended_action": (
                    f"Add an empty-result guard: if search returns no results after 3 attempts, "
                    f"route to a fallback node instead of looping. "
                    f"In LangGraph: check for empty tool output in your conditional edge function."
                ),
                "severity": "critical",
                "confidence": 0.92,
            }

        # ── Token Spike ──
        total_tokens = int(anomaly.get("llm_total_tokens", 0))
        if total_tokens > 5000:
            return {
                "explanation": (
                    f"The agent generated an unusually large response at step '{step_name}' "
                    f"({total_tokens:,} tokens). This suggests runaway text generation, "
                    f"likely caused by an unconstrained prompt or recursive context building."
                ),
                "root_cause": (
                    f"The prompt at '{step_name}' is accumulating the full message history "
                    f"without truncation, causing token counts to grow unboundedly."
                ),
                "recommended_action": (
                    f"Add max_tokens=1000 to the LLM call at '{step_name}'. "
                    f"Consider trimming the message history to the last 10 messages "
                    f"before each LLM invocation."
                ),
                "severity": "high",
                "confidence": 0.85,
            }

        # ── Low Trust / General Anomaly ──
        if trust_score < 0.3:
            return {
                "explanation": (
                    f"The agent's trust score dropped to {trust_score:.2f} at step '{step_name}', "
                    f"indicating degraded reliability. Multiple anomaly signals were detected "
                    f"including elevated error rates and unusual execution patterns."
                ),
                "root_cause": (
                    f"Compound failure: the agent accumulated errors across multiple steps "
                    f"without recovery, causing cascading trust degradation."
                ),
                "recommended_action": (
                    f"Review the last 10 events in Splunk for this trace. "
                    f"Add error handling and retry logic to nodes with trust_score < 0.5. "
                    f"Consider adding a 'recovery' node that resets state when trust drops below threshold."
                ),
                "severity": "high" if trust_score < 0.15 else "medium",
                "confidence": 0.78,
            }

        # ── Error ──
        if event_type == "error":
            error_msg = anomaly.get("error", "unknown error")
            return {
                "explanation": (
                    f"An unhandled exception occurred at step '{step_name}': {error_msg[:100]}. "
                    f"The agent crashed without a graceful recovery path."
                ),
                "root_cause": f"Unhandled exception at '{step_name}'.",
                "recommended_action": (
                    f"Wrap '{step_name}' in a try/except block. "
                    f"Add error handling that routes to a recovery node instead of crashing."
                ),
                "severity": "high",
                "confidence": 0.90,
            }

        # ── Generic ──
        return {
            "explanation": (
                f"Anomalous behavior detected at step '{step_name}' with trust score {trust_score:.2f}. "
                f"The agent's execution pattern deviated from expected baseline behavior."
            ),
            "root_cause": "Unknown — review full trace in Splunk for details.",
            "recommended_action": (
                f"Inspect the full event trace in Splunk: "
                f"search index=agentwatch step_name={step_name} | sort -_time"
            ),
            "severity": "medium",
            "confidence": 0.60,
        }


def _extract_call_count(text: str) -> str:
    """Extract call count from reasoning text like 'called 23x'."""
    import re
    match = re.search(r'(\d+)x', text)
    return match.group(1) if match else "multiple"
