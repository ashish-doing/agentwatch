"""
agentwatch/backend/instrumentation/anomaly_detector.py

Pre-filter anomaly detector that runs BEFORE Cisco Deep Time Series.
Catches loops, token spikes, latency drift, and error bursts in real-time.

Field names match exactly what langgraph_hooks.py emits:
  - tool_name       (from AgentEvent.tool_name)
  - trust_score     (from AgentEvent.trust_score)
  - llm_total_tokens (from AgentEvent.llm_total_tokens)
  - duration_ms     (from AgentEvent.duration_ms)
  - agent_id        (from AgentEvent.agent_id)
  - trace_id        (from AgentEvent.trace_id)
  - event_type      (from AgentEvent.event_type)
  - step_name       (from AgentEvent.step_name)

Used by main.py → broadcast_to_browsers() pipeline.
"""

import time
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("agentwatch.anomaly_detector")

# ── Thresholds (tune these for demo sensitivity) ──────────────────────────
LOOP_THRESHOLD = 5          # same tool called >= N times in one trace → loop
TOKEN_SPIKE_THRESHOLD = 3000 # llm_total_tokens >= N → token spike
LATENCY_DRIFT_MS = 3000     # duration_ms >= N → slow step
ERROR_BURST_THRESHOLD = 3   # >= N errors in one trace → error burst
TRUST_COLLAPSE_THRESHOLD = 0.3  # trust_score <= N → trust collapse


@dataclass
class AnomalyResult:
    """Returned by check_event() when an anomaly is detected."""
    detected: bool
    anomaly_type: str        # loop | token_spike | latency_drift | error_burst | trust_collapse
    severity: str            # low | medium | high | critical
    message: str
    tool_name: str = ""
    call_count: int = 0
    trust_score: float = 1.0
    confidence: float = 0.0
    extra: Dict = field(default_factory=dict)

    @property
    def as_dict(self) -> dict:
        return {
            "anomaly_type": self.anomaly_type,
            "severity": self.severity,
            "message": self.message,
            "tool_name": self.tool_name,
            "call_count": self.call_count,
            "trust_score": self.trust_score,
            "confidence": self.confidence,
            **self.extra,
        }


class AnomalyDetector:
    """
    Stateful anomaly detector — one instance per running agent session.
    Called from main.py after each event is received from the agent WebSocket.

    Key design: mirrors the same trust_score logic in langgraph_hooks.py
    so the detector and hooks stay in sync without duplication.
    """

    def __init__(self):
        # Per-trace, per-tool call counts  {trace_id: {tool_name: count}}
        self._tool_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        # Per-trace error counts  {trace_id: count}
        self._error_counts: Dict[str, int] = defaultdict(int)
        # Per-trace latency history  {trace_id: deque of duration_ms}
        self._latency_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=20))
        # Latest anomaly per trace  {trace_id: AnomalyResult}
        self._latest_anomaly: Dict[str, AnomalyResult] = {}
        # Full anomaly history (for the /api/stats endpoint)
        self.anomaly_log: List[dict] = []

    # ─────────────────────────────────────────────────────────────────────
    # Main entry — called for every incoming event
    # ─────────────────────────────────────────────────────────────────────

    def check_event(self, event: dict) -> Optional[AnomalyResult]:
        """
        Inspect one event dict (as emitted by AgentEvent.to_dict()).
        Returns AnomalyResult if an anomaly is detected, else None.

        Called from main.py right after the agent WebSocket sends an event.
        """
        event_type = event.get("event_type", "")
        trace_id   = event.get("trace_id", "unknown")
        tool_name  = event.get("tool_name", "")
        trust      = float(event.get("trust_score", 1.0))
        tokens     = int(event.get("llm_total_tokens", 0))
        duration   = float(event.get("duration_ms", 0.0))
        step_name  = event.get("step_name", "")

        result: Optional[AnomalyResult] = None

        # ── 1. Loop detection (tool_call events) ─────────────────────────
        if event_type == "tool_call" and tool_name:
            result = self._check_loop(trace_id, tool_name, trust)

        # ── 2. Token spike (llm_call events) ─────────────────────────────
        if result is None and event_type == "llm_call" and tokens > 0:
            result = self._check_token_spike(trace_id, tokens, step_name)

        # ── 3. Latency drift (step_end events) ───────────────────────────
        if result is None and event_type == "step_end" and duration > 0:
            result = self._check_latency(trace_id, duration, step_name)

        # ── 4. Error burst ────────────────────────────────────────────────
        if result is None and event_type == "error":
            result = self._check_error_burst(trace_id, step_name)

        # ── 5. Trust collapse — skip on error events (trust=0.0 is expected for errors)
        if result is None and event_type != "error" and trust <= TRUST_COLLAPSE_THRESHOLD:
            result = self._check_trust_collapse(trace_id, trust, step_name, tool_name)

        if result and result.detected:
            self._latest_anomaly[trace_id] = result
            self.anomaly_log.append({
                "timestamp": time.time(),
                "trace_id": trace_id,
                **result.as_dict,
            })
            logger.warning(
                f"[AnomalyDetector] {result.anomaly_type.upper()} | "
                f"{result.message} | severity={result.severity}"
            )

        return result if (result and result.detected) else None

    # ─────────────────────────────────────────────────────────────────────
    # Detection methods
    # ─────────────────────────────────────────────────────────────────────

    def _check_loop(self, trace_id: str, tool_name: str, trust: float) -> Optional[AnomalyResult]:
        """
        Matches the logic in langgraph_hooks.py on_tool_call():
            count_key = f"{trace_id}:{tool_name}"
            is_anomaly = call_count >= 5
        We track the same counter independently here for pre-filter detection.
        """
        self._tool_counts[trace_id][tool_name] += 1
        count = self._tool_counts[trace_id][tool_name]

        if count < LOOP_THRESHOLD:
            return None

        # Confidence increases with call count — more calls = more certain it's a loop
        confidence = min(0.99, 0.70 + (count - LOOP_THRESHOLD) * 0.05)

        severity = "critical" if count >= 10 else "high"
        return AnomalyResult(
            detected=True,
            anomaly_type="loop",
            severity=severity,
            message=f"Loop detected — {tool_name} called {count}x in this run",
            tool_name=tool_name,
            call_count=count,
            trust_score=trust,
            confidence=confidence,
            extra={"threshold": LOOP_THRESHOLD},
        )

    def _check_token_spike(self, trace_id: str, tokens: int, step_name: str) -> Optional[AnomalyResult]:
        """Token count > TOKEN_SPIKE_THRESHOLD signals runaway generation."""
        if tokens < TOKEN_SPIKE_THRESHOLD:
            return None

        # Severity scales with how far above threshold
        ratio = tokens / TOKEN_SPIKE_THRESHOLD
        severity = "critical" if ratio >= 3 else "high" if ratio >= 2 else "medium"
        confidence = min(0.95, 0.6 + ratio * 0.1)

        return AnomalyResult(
            detected=True,
            anomaly_type="token_spike",
            severity=severity,
            message=f"Token spike at '{step_name}' — {tokens:,} tokens (threshold: {TOKEN_SPIKE_THRESHOLD:,})",
            trust_score=max(0.1, 1.0 - (tokens / 10000)),  # mirrors hooks.py llm_call trust formula
            confidence=confidence,
            extra={"tokens": tokens, "threshold": TOKEN_SPIKE_THRESHOLD},
        )

    def _check_latency(self, trace_id: str, duration_ms: float, step_name: str) -> Optional[AnomalyResult]:
        """
        Detects latency drift: single step too slow, or trend getting worse.
        Matches the 'drift' mode in demo_agent.py:
            base_ms = int(base_ms * (1 + 0.3 * call_count))
        """
        self._latency_history[trace_id].append(duration_ms)

        if duration_ms < LATENCY_DRIFT_MS:
            return None

        history = list(self._latency_history[trace_id])
        # Check for trend: is latency increasing over time?
        if len(history) >= 3:
            trend = history[-1] > history[-2] > history[-3]
            drift_msg = "and trending upward" if trend else ""
        else:
            drift_msg = ""

        severity = "high" if duration_ms > LATENCY_DRIFT_MS * 2 else "medium"
        confidence = min(0.90, 0.65 + (duration_ms / LATENCY_DRIFT_MS) * 0.1)

        return AnomalyResult(
            detected=True,
            anomaly_type="latency_drift",
            severity=severity,
            message=f"Slow step '{step_name}' — {duration_ms:.0f}ms {drift_msg}",
            trust_score=max(0.2, 1.0 - duration_ms / 10000),
            confidence=confidence,
            extra={"duration_ms": duration_ms, "threshold_ms": LATENCY_DRIFT_MS},
        )

    def _check_error_burst(self, trace_id: str, step_name: str) -> Optional[AnomalyResult]:
        """Multiple errors in one trace = error burst."""
        self._error_counts[trace_id] += 1
        count = self._error_counts[trace_id]

        if count < ERROR_BURST_THRESHOLD:
            return None

        severity = "critical" if count >= 5 else "high"
        confidence = min(0.95, 0.70 + count * 0.05)

        return AnomalyResult(
            detected=True,
            anomaly_type="error_burst",
            severity=severity,
            message=f"Error burst — {count} errors in this trace (last at '{step_name}')",
            trust_score=0.0,
            confidence=confidence,
            extra={"error_count": count},
        )

    def _check_trust_collapse(
        self, trace_id: str, trust: float, step_name: str, tool_name: str
    ) -> Optional[AnomalyResult]:
        """
        Trust collapse: trust_score <= 0.3.
        This is the TRUST_COLLAPSE_THRESHOLD check described in the README.
        Only fires if no loop or token spike was already detected for this event.
        """
        severity = "critical" if trust <= 0.1 else "high" if trust <= 0.2 else "medium"
        confidence = min(0.90, 0.60 + (TRUST_COLLAPSE_THRESHOLD - trust) * 2)

        return AnomalyResult(
            detected=True,
            anomaly_type="trust_collapse",
            severity=severity,
            message=f"Trust collapse at '{step_name}' — score dropped to {trust:.2f}",
            tool_name=tool_name,
            trust_score=trust,
            confidence=confidence,
            extra={"threshold": TRUST_COLLAPSE_THRESHOLD},
        )

    # ─────────────────────────────────────────────────────────────────────
    # Public helpers — used by tests and /api/stats
    # ─────────────────────────────────────────────────────────────────────

    def record_tool_call(self, tool_name: str, trace_id: str = "test") -> int:
        """
        Convenience method for unit tests — increment tool call count directly.
        Returns the new count.
        """
        self._tool_counts[trace_id][tool_name] += 1
        return self._tool_counts[trace_id][tool_name]

    def is_loop_detected(self, tool_name: str, trace_id: str = "test") -> bool:
        """Used by unit tests to check loop detection."""
        return self._tool_counts[trace_id][tool_name] >= LOOP_THRESHOLD

    def compute_trust_score(self, identifier: str, trace_id: str = "test") -> float:
        """
        Mirrors the trust formula in langgraph_hooks.py on_tool_call():
            trust = max(0.05, 1.0 / (1 + 0.3 * max(0, call_count - 3)))
        identifier = tool_name
        """
        call_count = self._tool_counts[trace_id].get(identifier, 0)
        return max(0.05, 1.0 / (1 + 0.3 * max(0, call_count - 3)))

    def get_latest_anomaly(self, tool_name: str, trace_id: str = "test") -> Optional[dict]:
        """Returns the latest anomaly dict for a trace, or None."""
        result = self._latest_anomaly.get(trace_id)
        if result:
            return result.as_dict
        return None

    def reset_trace(self, trace_id: str):
        """Clear all state for a completed trace."""
        self._tool_counts.pop(trace_id, None)
        self._error_counts.pop(trace_id, None)
        self._latency_history.pop(trace_id, None)

    def get_stats(self) -> dict:
        """Summary stats for /api/stats endpoint."""
        return {
            "total_anomalies_detected": len(self.anomaly_log),
            "active_traces": len(self._tool_counts),
            "anomaly_breakdown": _count_by_type(self.anomaly_log),
        }


def _count_by_type(log: List[dict]) -> dict:
    counts: Dict[str, int] = {}
    for entry in log:
        t = entry.get("anomaly_type", "unknown")
        counts[t] = counts.get(t, 0) + 1
    return counts