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

TASK 2 addition: update_thresholds() lets main.py push live config changes
from /api/config without restarting the process.
"""

import time
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("agentwatch.anomaly_detector")

# ── Default thresholds (overridable via update_thresholds()) ──────────────
_DEFAULT_LOOP_THRESHOLD = 5
_DEFAULT_TOKEN_SPIKE_THRESHOLD = 3000
_DEFAULT_LATENCY_DRIFT_MS = 2000
_DEFAULT_ERROR_BURST_THRESHOLD = 3
_DEFAULT_TRUST_COLLAPSE_THRESHOLD = 0.3

# Module-level aliases — backward compat with tests and external imports
LOOP_THRESHOLD = _DEFAULT_LOOP_THRESHOLD
TOKEN_SPIKE_THRESHOLD = _DEFAULT_TOKEN_SPIKE_THRESHOLD
LATENCY_DRIFT_MS = _DEFAULT_LATENCY_DRIFT_MS
ERROR_BURST_THRESHOLD = _DEFAULT_ERROR_BURST_THRESHOLD
TRUST_COLLAPSE_THRESHOLD = _DEFAULT_TRUST_COLLAPSE_THRESHOLD


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

    TASK 2: Thresholds are mutable at runtime via update_thresholds().
    """

    def __init__(self):
        # Live thresholds — start at defaults, overridable via /api/config
        self.loop_threshold: int = _DEFAULT_LOOP_THRESHOLD
        self.token_spike_threshold: int = _DEFAULT_TOKEN_SPIKE_THRESHOLD
        self.latency_drift_ms: float = _DEFAULT_LATENCY_DRIFT_MS
        self.error_burst_threshold: int = _DEFAULT_ERROR_BURST_THRESHOLD
        self.trust_collapse_threshold: float = _DEFAULT_TRUST_COLLAPSE_THRESHOLD

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
    # TASK 2: Live threshold update
    # ─────────────────────────────────────────────────────────────────────

    def update_thresholds(
        self,
        loop_threshold: Optional[int] = None,
        token_spike_threshold: Optional[int] = None,
        latency_drift_ms: Optional[float] = None,
        error_burst_threshold: Optional[int] = None,
        trust_score_critical: Optional[float] = None,
    ):
        """
        Update detection thresholds at runtime.
        Called by main.py when POST /api/config is received.
        Only updates fields that are explicitly passed (not None).
        """
        if loop_threshold is not None:
            self.loop_threshold = loop_threshold
        if token_spike_threshold is not None:
            self.token_spike_threshold = token_spike_threshold
        if latency_drift_ms is not None:
            self.latency_drift_ms = latency_drift_ms
        if error_burst_threshold is not None:
            self.error_burst_threshold = error_burst_threshold
        if trust_score_critical is not None:
            self.trust_collapse_threshold = trust_score_critical

        logger.info(
            f"[AnomalyDetector] Thresholds updated — "
            f"loop={self.loop_threshold}, token={self.token_spike_threshold}, "
            f"latency={self.latency_drift_ms}ms, trust<={self.trust_collapse_threshold}"
        )

    # ─────────────────────────────────────────────────────────────────────
    # Main entry — called for every incoming event
    # ─────────────────────────────────────────────────────────────────────

    def check_event(self, event: dict) -> Optional[AnomalyResult]:
        """
        Inspect one event dict (as emitted by AgentEvent.to_dict()).
        Returns AnomalyResult if an anomaly is detected, else None.
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
        if result is None and event_type != "error" and trust <= self.trust_collapse_threshold:
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
        self._tool_counts[trace_id][tool_name] += 1
        count = self._tool_counts[trace_id][tool_name]

        if count < self.loop_threshold:
            return None

        confidence = min(0.99, 0.70 + (count - self.loop_threshold) * 0.05)
        severity = "critical" if count >= self.loop_threshold * 2 else "high"
        return AnomalyResult(
            detected=True,
            anomaly_type="loop",
            severity=severity,
            message=f"Loop detected — {tool_name} called {count}x in this run",
            tool_name=tool_name,
            call_count=count,
            trust_score=trust,
            confidence=confidence,
            extra={"threshold": self.loop_threshold},
        )

    def _check_token_spike(self, trace_id: str, tokens: int, step_name: str) -> Optional[AnomalyResult]:
        if tokens < self.token_spike_threshold:
            return None

        ratio = tokens / self.token_spike_threshold
        severity = "critical" if ratio >= 3 else "high" if ratio >= 2 else "medium"
        confidence = min(0.95, 0.6 + ratio * 0.1)

        return AnomalyResult(
            detected=True,
            anomaly_type="token_spike",
            severity=severity,
            message=f"Token spike at '{step_name}' — {tokens:,} tokens (threshold: {self.token_spike_threshold:,})",
            trust_score=max(0.1, 1.0 - (tokens / 10000)),
            confidence=confidence,
            extra={"tokens": tokens, "threshold": self.token_spike_threshold},
        )

    def _check_latency(self, trace_id: str, duration_ms: float, step_name: str) -> Optional[AnomalyResult]:
        self._latency_history[trace_id].append(duration_ms)

        if duration_ms < self.latency_drift_ms:
            return None

        history = list(self._latency_history[trace_id])
        if len(history) >= 3:
            trend = history[-1] > history[-2] > history[-3]
            drift_msg = "and trending upward" if trend else ""
        else:
            drift_msg = ""

        severity = "high" if duration_ms > self.latency_drift_ms * 2 else "medium"
        confidence = min(0.90, 0.65 + (duration_ms / self.latency_drift_ms) * 0.1)

        return AnomalyResult(
            detected=True,
            anomaly_type="latency_drift",
            severity=severity,
            message=f"Slow step '{step_name}' — {duration_ms:.0f}ms {drift_msg}",
            trust_score=max(0.2, 1.0 - duration_ms / 10000),
            confidence=confidence,
            extra={"duration_ms": duration_ms, "threshold_ms": self.latency_drift_ms},
        )

    def _check_error_burst(self, trace_id: str, step_name: str) -> Optional[AnomalyResult]:
        self._error_counts[trace_id] += 1
        count = self._error_counts[trace_id]

        if count < self.error_burst_threshold:
            return None

        severity = "critical" if count >= self.error_burst_threshold * 2 else "high"
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
        severity = "critical" if trust <= 0.1 else "high" if trust <= 0.2 else "medium"
        confidence = min(0.90, 0.60 + (self.trust_collapse_threshold - trust) * 2)

        return AnomalyResult(
            detected=True,
            anomaly_type="trust_collapse",
            severity=severity,
            message=f"Trust collapse at '{step_name}' — score dropped to {trust:.2f}",
            tool_name=tool_name,
            trust_score=trust,
            confidence=confidence,
            extra={"threshold": self.trust_collapse_threshold},
        )

    # ─────────────────────────────────────────────────────────────────────
    # Public helpers — used by tests and /api/stats
    # ─────────────────────────────────────────────────────────────────────

    def record_tool_call(self, tool_name: str, trace_id: str = "test") -> int:
        self._tool_counts[trace_id][tool_name] += 1
        return self._tool_counts[trace_id][tool_name]

    def is_loop_detected(self, tool_name: str, trace_id: str = "test") -> bool:
        return self._tool_counts[trace_id][tool_name] >= self.loop_threshold

    def compute_trust_score(self, identifier: str, trace_id: str = "test") -> float:
        call_count = self._tool_counts[trace_id].get(identifier, 0)
        return max(0.05, 1.0 / (1 + 0.3 * max(0, call_count - 3)))

    def get_latest_anomaly(self, tool_name: str, trace_id: str = "test") -> Optional[dict]:
        result = self._latest_anomaly.get(trace_id)
        if result:
            return result.as_dict
        return None

    def reset_trace(self, trace_id: str):
        self._tool_counts.pop(trace_id, None)
        self._error_counts.pop(trace_id, None)
        self._latency_history.pop(trace_id, None)

    def get_stats(self) -> dict:
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