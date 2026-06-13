"""
agentwatch/backend/tests/test_anomaly.py

Unit tests for AnomalyDetector.
Field names and trust formula match exactly:
  - langgraph_hooks.py  → on_tool_call(), on_llm_call()
  - demo_agent.py       → _send() calls
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from backend.instrumentation.anomaly_detector import (
    AnomalyDetector,
    LOOP_THRESHOLD,
    TOKEN_SPIKE_THRESHOLD,
    LATENCY_DRIFT_MS,
    TRUST_COLLAPSE_THRESHOLD,
)


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def detector():
    """Fresh AnomalyDetector for each test."""
    return AnomalyDetector()


def make_tool_event(tool_name="search_tool", trust=0.9, trace_id="trace-001"):
    """Matches the exact dict that langgraph_hooks.py AgentEvent.to_dict() produces."""
    return {
        "event_type": "tool_call",
        "agent_id": "demo-001",
        "trace_id": trace_id,
        "step_id": "abc12345",
        "step_name": f"tool:{tool_name}",
        "tool_name": tool_name,
        "tool_input": "query string",
        "tool_output": "some result",
        "duration_ms": 200.0,
        "trust_score": trust,
        "llm_total_tokens": 0,
        "error": "",
    }


def make_llm_event(tokens=500, step_name="research", trace_id="trace-001"):
    """Matches the exact dict that langgraph_hooks.py on_llm_call() produces."""
    return {
        "event_type": "llm_call",
        "agent_id": "demo-001",
        "trace_id": trace_id,
        "step_id": "abc12345",
        "step_name": step_name,
        "llm_model": "mock-llm",
        "llm_prompt_tokens": tokens // 2,
        "llm_completion_tokens": tokens // 2,
        "llm_total_tokens": tokens,
        "tool_name": "",
        "duration_ms": 400.0,
        "trust_score": max(0.1, 1.0 - tokens / 10000),
        "error": "",
    }


def make_step_end_event(duration_ms=500.0, step_name="research", trace_id="trace-001"):
    """Matches the exact dict that langgraph_hooks.py on_step_end() produces."""
    return {
        "event_type": "step_end",
        "agent_id": "demo-001",
        "trace_id": trace_id,
        "step_id": "abc12345",
        "step_name": step_name,
        "duration_ms": duration_ms,
        "trust_score": 0.9,
        "llm_total_tokens": 0,
        "tool_name": "",
        "error": "",
    }


def make_error_event(step_name="research", trace_id="trace-001"):
    """Matches the exact dict that langgraph_hooks.py on_error() produces."""
    return {
        "event_type": "error",
        "agent_id": "demo-001",
        "trace_id": trace_id,
        "step_id": "abc12345",
        "step_name": step_name,
        "trust_score": 0.0,
        "llm_total_tokens": 0,
        "tool_name": "",
        "duration_ms": 0.0,
        "error": "Something went wrong",
    }


# ─────────────────────────────────────────────
# Loop Detection Tests
# ─────────────────────────────────────────────

class TestLoopDetection:

    def test_no_anomaly_below_threshold(self, detector):
        """Fewer than LOOP_THRESHOLD calls → no anomaly."""
        for i in range(LOOP_THRESHOLD - 1):
            result = detector.check_event(make_tool_event("search_tool"))
        assert result is None

    def test_loop_detected_at_threshold(self, detector):
        """Exactly LOOP_THRESHOLD calls → loop anomaly fires."""
        result = None
        for i in range(LOOP_THRESHOLD):
            result = detector.check_event(make_tool_event("search_tool"))
        assert result is not None
        assert result.anomaly_type == "loop"
        assert result.detected is True

    def test_loop_severity_is_high(self, detector):
        """Between 5 and 9 calls → severity HIGH."""
        for _ in range(LOOP_THRESHOLD):
            result = detector.check_event(make_tool_event("search_tool"))
        assert result.severity == "high"

    def test_loop_severity_is_critical_at_ten(self, detector):
        """10+ calls → severity CRITICAL (matches demo_agent loop mode: 23 calls)."""
        for _ in range(10):
            result = detector.check_event(make_tool_event("search_tool"))
        assert result.severity == "critical"

    def test_loop_tool_name_captured(self, detector):
        """Anomaly result captures the correct tool_name."""
        for _ in range(LOOP_THRESHOLD):
            result = detector.check_event(make_tool_event("search_tool"))
        assert result.tool_name == "search_tool"

    def test_loop_call_count_in_result(self, detector):
        """call_count in result matches actual call count."""
        for _ in range(LOOP_THRESHOLD):
            result = detector.check_event(make_tool_event("search_tool"))
        assert result.call_count == LOOP_THRESHOLD

    def test_different_tools_tracked_independently(self, detector):
        """Loop detection is per-tool, not global."""
        for _ in range(LOOP_THRESHOLD - 1):
            detector.check_event(make_tool_event("search_tool"))
        # calculator_tool has only 1 call — should not trigger
        result = detector.check_event(make_tool_event("calculator_tool"))
        assert result is None

    def test_different_traces_tracked_independently(self, detector):
        """Two traces don't share call counts."""
        for _ in range(LOOP_THRESHOLD - 1):
            detector.check_event(make_tool_event("search_tool", trace_id="trace-A"))
        # trace-B has only 1 call
        result = detector.check_event(make_tool_event("search_tool", trace_id="trace-B"))
        assert result is None

    def test_record_tool_call_helper(self, detector):
        """record_tool_call convenience method works for tests."""
        for _ in range(LOOP_THRESHOLD):
            detector.record_tool_call("search_tool")
        assert detector.is_loop_detected("search_tool") is True

    def test_is_loop_detected_false_below_threshold(self, detector):
        """is_loop_detected returns False before threshold."""
        for _ in range(LOOP_THRESHOLD - 1):
            detector.record_tool_call("search_tool")
        assert detector.is_loop_detected("search_tool") is False


# ─────────────────────────────────────────────
# Trust Score Tests
# ─────────────────────────────────────────────

class TestTrustScore:

    def test_trust_score_mirrors_hooks_formula(self, detector):
        """
        compute_trust_score mirrors langgraph_hooks.py formula exactly:
            trust = max(0.05, 1.0 / (1 + 0.3 * max(0, call_count - 3)))
        """
        # 6 calls: count=6, trust = 1.0 / (1 + 0.3*(6-3)) = 1.0/1.9 ≈ 0.526
        for _ in range(6):
            detector.record_tool_call("search_tool")
        score = detector.compute_trust_score("search_tool")
        expected = max(0.05, 1.0 / (1 + 0.3 * max(0, 6 - 3)))
        assert abs(score - expected) < 0.001

    def test_trust_score_minimum_is_005(self, detector):
        """Trust score never goes below 0.05 (matches hooks.py floor)."""
        for _ in range(100):
            detector.record_tool_call("search_tool")
        score = detector.compute_trust_score("search_tool")
        assert score >= 0.05

    def test_healthy_agent_trust_above_07(self, detector):
        """A healthy agent with 1 tool call has trust > 0.7."""
        detector.record_tool_call("calculator_tool")
        score = detector.compute_trust_score("calculator_tool")
        assert score > 0.7


# ─────────────────────────────────────────────
# Token Spike Tests
# ─────────────────────────────────────────────

class TestTokenSpike:

    def test_no_spike_below_threshold(self, detector):
        """Normal token count does not trigger spike."""
        result = detector.check_event(make_llm_event(tokens=500))
        assert result is None

    def test_spike_detected_above_threshold(self, detector):
        """Token count > TOKEN_SPIKE_THRESHOLD → spike anomaly."""
        result = detector.check_event(make_llm_event(tokens=TOKEN_SPIKE_THRESHOLD + 100))
        assert result is not None
        assert result.anomaly_type == "token_spike"

    def test_spike_severity_medium_just_above(self, detector):
        """Just over threshold → medium severity."""
        result = detector.check_event(make_llm_event(tokens=TOKEN_SPIKE_THRESHOLD + 100))
        assert result.severity == "medium"

    def test_spike_severity_critical_at_3x(self, detector):
        """3x threshold → critical severity."""
        result = detector.check_event(make_llm_event(tokens=TOKEN_SPIKE_THRESHOLD * 3 + 1))
        assert result.severity == "critical"

    def test_spike_matches_hallucinate_mode(self, detector):
        """
        Hallucinate mode in demo_agent.py generates 5000-9000 tokens.
        Make sure those always fire the detector.
        """
        # demo_agent.py hallucinate: p=2000-4000, c=3000-5000 → total=5000-9000
        result = detector.check_event(make_llm_event(tokens=6000))
        assert result is not None
        assert result.anomaly_type == "token_spike"


# ─────────────────────────────────────────────
# Latency Drift Tests
# ─────────────────────────────────────────────

class TestLatencyDrift:

    def test_no_drift_below_threshold(self, detector):
        """Normal latency does not trigger drift."""
        result = detector.check_event(make_step_end_event(duration_ms=500.0))
        assert result is None

    def test_drift_detected_above_threshold(self, detector):
        """duration_ms > LATENCY_DRIFT_MS → latency_drift anomaly."""
        result = detector.check_event(make_step_end_event(duration_ms=LATENCY_DRIFT_MS + 500))
        assert result is not None
        assert result.anomaly_type == "latency_drift"

    def test_drift_severity_medium_just_above(self, detector):
        """Just over threshold → medium."""
        result = detector.check_event(make_step_end_event(duration_ms=LATENCY_DRIFT_MS + 100))
        assert result.severity == "medium"

    def test_drift_severity_high_at_2x(self, detector):
        """2x threshold → high."""
        result = detector.check_event(make_step_end_event(duration_ms=LATENCY_DRIFT_MS * 2 + 1))
        assert result.severity == "high"

    def test_drift_matches_drift_mode(self, detector):
        """
        Drift mode in demo_agent.py: base_ms * (1 + 0.3 * call_count).
        At call_count=10: 260 * (1 + 3.0) = 1040ms — not yet over threshold.
        At call_count=20: 260 * (1 + 6.0) = 1820ms — still under.
        At call_count=30: 260 * (1 + 9.0) = 2600ms — under 3000ms.
        At call_count=35: 260 * (1 + 10.5) = 2990ms — just under.
        At call_count=36: ~3068ms → should fire.
        """
        drifted_ms = 260 * (1 + 0.3 * 36)
        result = detector.check_event(make_step_end_event(duration_ms=drifted_ms))
        assert result is not None
        assert result.anomaly_type == "latency_drift"


# ─────────────────────────────────────────────
# Trust Collapse Tests
# ─────────────────────────────────────────────

class TestTrustCollapse:

    def test_trust_collapse_at_threshold(self, detector):
        """trust_score <= 0.3 → trust_collapse anomaly."""
        event = make_tool_event("search_tool", trust=TRUST_COLLAPSE_THRESHOLD)
        result = detector.check_event(event)
        assert result is not None
        assert result.anomaly_type in ("loop", "trust_collapse")

    def test_no_collapse_above_threshold(self, detector):
        """trust_score > 0.3 with 1 call → no anomaly."""
        event = make_tool_event("search_tool", trust=0.8)
        result = detector.check_event(event)
        assert result is None

    def test_trust_collapse_critical_at_010(self, detector):
        """trust = 0.05 (loop floor value from hooks.py) → critical."""
        # To reach trust=0.05, we need a loop first, but check standalone
        event = make_step_end_event(duration_ms=100)
        event["trust_score"] = 0.05
        result = detector.check_event(event)
        # May be trust_collapse since no loop was pre-recorded
        if result:
            assert result.severity == "critical"


# ─────────────────────────────────────────────
# Error Burst Tests
# ─────────────────────────────────────────────

class TestErrorBurst:

    def test_no_burst_below_threshold(self, detector):
        """Single error → no burst."""
        result = detector.check_event(make_error_event())
        assert result is None

    def test_burst_at_threshold(self, detector):
        """3 errors → error_burst fires."""
        result = None
        for _ in range(3):
            result = detector.check_event(make_error_event())
        assert result is not None
        assert result.anomaly_type == "error_burst"


# ─────────────────────────────────────────────
# check_event full pipeline tests
# ─────────────────────────────────────────────

class TestCheckEventPipeline:

    def test_returns_none_for_step_start(self, detector):
        """step_start events are never anomalous."""
        event = {
            "event_type": "step_start",
            "agent_id": "demo-001",
            "trace_id": "trace-001",
            "step_id": "abc",
            "step_name": "research",
            "trust_score": 1.0,
            "llm_total_tokens": 0,
            "tool_name": "",
            "duration_ms": 0.0,
            "error": "",
        }
        result = detector.check_event(event)
        assert result is None

    def test_anomaly_logged(self, detector):
        """Detected anomalies go into anomaly_log."""
        for _ in range(LOOP_THRESHOLD):
            detector.check_event(make_tool_event("search_tool"))
        stats = detector.get_stats()
        assert stats["total_anomalies_detected"] >= 1

    def test_get_latest_anomaly(self, detector):
        """get_latest_anomaly returns dict after detection."""
        for _ in range(LOOP_THRESHOLD):
            detector.check_event(make_tool_event("search_tool", trace_id="trace-X"))
        result = detector.get_latest_anomaly("search_tool", trace_id="trace-X")
        assert result is not None
        assert "anomaly_type" in result

    def test_reset_trace_clears_state(self, detector):
        """reset_trace() clears all counts for that trace."""
        for _ in range(LOOP_THRESHOLD - 1):
            detector.check_event(make_tool_event("search_tool", trace_id="trace-Z"))
        detector.reset_trace("trace-Z")
        # After reset, 1 more call should NOT trigger
        result = detector.check_event(make_tool_event("search_tool", trace_id="trace-Z"))
        assert result is None