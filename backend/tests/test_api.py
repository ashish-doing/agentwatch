"""
agentwatch/backend/tests/test_api.py

Integration tests for the FastAPI layer:
  - GET  /api/history        (TASK 1)
  - GET  /api/config         (TASK 2)
  - POST /api/config         (TASK 2 — live threshold propagation)
  - POST /api/export/incident (TASK 4 — PDF generation)
  - POST /api/explain        (Foundation-Sec path)
  - GET  /api/events         (event buffer filtering)
  - GET  /api/stats          (stats aggregation)
  - GET  /api/health         (health probe)
  - Slack webhook            (TASK 3 — mocked, never hits real URL)
  - update_thresholds()      (TASK 2 — live effect on AnomalyDetector)

Design rules:
  - No real Splunk, no real Slack, no real Foundation-Sec endpoint required.
  - All external HTTP calls are intercepted via pytest monkeypatch or
    unittest.mock.AsyncMock so the suite runs fully offline.
  - Tests are grouped by feature so it's easy to map failures back to tasks.
  - Every test function is independent — no shared mutable state between tests
    (each uses TestClient which gets a fresh app import, or explicitly resets
    module-level state where needed).
"""

import io
import json
import time
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_event(
    event_type="tool_call",
    tool_name="search_tool",
    trace_id="trace-test-001",
    agent_id="agent-test-001",
    trust_score=0.9,
    tokens=200,
    duration_ms=150.0,
    step_name="research",
):
    """Build a minimal valid AgentEvent dict matching demo_agent._send() schema."""
    return {
        "event_type": event_type,
        "agent_id": agent_id,
        "trace_id": trace_id,
        "step_id": "step-abc",
        "step_name": step_name,
        "tool_name": tool_name,
        "trust_score": trust_score,
        "llm_total_tokens": tokens,
        "duration_ms": duration_ms,
        "timestamp": time.time(),
        "error": "",
        "reasoning_content": "",
    }


def _make_anomaly_event(
    trace_id="trace-test-001",
    agent_id="agent-test-001",
    anomaly_type="loop",
    severity="critical",
    trust_score=0.05,
):
    """Build a minimal anomaly event (as emitted by ingest_event)."""
    return {
        **_make_event(trace_id=trace_id, agent_id=agent_id),
        "event_type": "anomaly",
        "anomaly_type": anomaly_type,
        "severity": severity,
        "trust_score": trust_score,
        "reasoning_content": f"Loop detected — search_tool called 23x in 4s",
        "confidence": 0.95,
    }


# ── App fixture ───────────────────────────────────────────────────────────────

@pytest.fixture()
def client():
    """
    Return a TestClient with the FastAPI app.
    Patches SplunkClient and FoundationSecClient so no real network is needed.
    Resets the module-level event_buffer and alert_config between tests.
    """
    with patch("backend.api.main.SplunkClient") as MockSplunk, \
         patch("backend.api.main.FoundationSecClient") as MockFoundSec:

        # SplunkClient: index_event always succeeds; generate_spl returns template SPL
        splunk_instance = MockSplunk.return_value
        splunk_instance.index_event = AsyncMock(return_value=True)
        splunk_instance.ping = AsyncMock(return_value=False)   # not connected in test
        splunk_instance.generate_spl = AsyncMock(
            return_value="index=agentwatch | sort -_time | head 50"
        )
        splunk_instance.run_search = AsyncMock(return_value=[])

        # FoundationSecClient: explain() returns a plausible structured result
        fsec_instance = MockFoundSec.return_value
        fsec_instance.explain = AsyncMock(return_value={
            "explanation": "The agent entered an infinite loop at search_tool.",
            "root_cause": "Missing empty-result guard.",
            "recommended_action": "Add exit condition after 3 failed searches.",
            "severity": "critical",
            "confidence": 0.92,
        })

        from backend.api import main as app_module
        from fastapi.testclient import TestClient

        # Reset shared mutable state so tests are isolated
        app_module.event_buffer.clear()
        app_module.alert_config = {
            "loop_threshold": 5,
            "token_spike_threshold": 3000,
            "latency_drift_ms": 2000,
            "trust_score_critical": 0.3,
        }
        # Fresh detector so loop counts don't leak between tests
        from backend.instrumentation.anomaly_detector import AnomalyDetector
        app_module.anomaly_detector = AnomalyDetector()

        yield TestClient(app_module.app)


# ─────────────────────────────────────────────────────────────────────────────
# /api/health
# ─────────────────────────────────────────────────────────────────────────────

class TestHealth:

    def test_health_returns_ok(self, client):
        """Health endpoint always returns status=ok."""
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_reports_buffer_size(self, client):
        """Buffer size in health response reflects actual buffer."""
        r = client.get("/api/health")
        assert "buffer_size" in r.json()
        assert r.json()["buffer_size"] == 0  # buffer was cleared in fixture


# ─────────────────────────────────────────────────────────────────────────────
# /api/events
# ─────────────────────────────────────────────────────────────────────────────

class TestEvents:

    def test_empty_buffer_returns_empty_list(self, client):
        r = client.get("/api/events")
        assert r.status_code == 200
        data = r.json()
        assert data["events"] == []
        assert data["total"] == 0

    def test_events_returns_seeded_events(self, client):
        """Events in the buffer are returned by /api/events."""
        from backend.api import main as m
        m.event_buffer.append(_make_event(event_type="tool_call"))
        m.event_buffer.append(_make_event(event_type="llm_call"))

        r = client.get("/api/events")
        assert r.status_code == 200
        assert r.json()["total"] == 2

    def test_event_type_filter(self, client):
        """?event_type= filters by event_type field."""
        from backend.api import main as m
        m.event_buffer.append(_make_event(event_type="tool_call"))
        m.event_buffer.append(_make_event(event_type="llm_call"))
        m.event_buffer.append(_make_event(event_type="anomaly"))

        r = client.get("/api/events?event_type=anomaly")
        events = r.json()["events"]
        assert all(e["event_type"] == "anomaly" for e in events)
        assert len(events) == 1

    def test_limit_param(self, client):
        """?limit= caps the number of events returned."""
        from backend.api import main as m
        for i in range(20):
            m.event_buffer.append(_make_event(trace_id=f"trace-{i}"))

        r = client.get("/api/events?limit=5")
        assert len(r.json()["events"]) == 5


# ─────────────────────────────────────────────────────────────────────────────
# /api/stats
# ─────────────────────────────────────────────────────────────────────────────

class TestStats:

    def test_stats_empty_buffer(self, client):
        r = client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total_events"] == 0
        assert data["anomalies"] == 0
        assert data["avg_trust"] == 1.0

    def test_stats_aggregates_correctly(self, client):
        """Stats counts match what was seeded into the buffer."""
        from backend.api import main as m
        m.event_buffer.append(_make_event(event_type="tool_call", trust_score=0.8, agent_id="agent-A"))
        m.event_buffer.append(_make_event(event_type="anomaly", trust_score=0.1, agent_id="agent-A"))
        m.event_buffer.append(_make_event(event_type="llm_call", trust_score=0.9, agent_id="agent-B"))

        r = client.get("/api/stats")
        data = r.json()
        assert data["total_events"] == 3
        assert data["anomalies"] == 1
        assert data["agents"] == 2
        # avg trust = (0.8 + 0.1 + 0.9) / 3 = 0.6
        assert abs(data["avg_trust"] - 0.6) < 0.01


# ─────────────────────────────────────────────────────────────────────────────
# TASK 1 — /api/history
# ─────────────────────────────────────────────────────────────────────────────

class TestHistory:

    def test_empty_buffer_returns_empty_runs(self, client):
        r = client.get("/api/history")
        assert r.status_code == 200
        data = r.json()
        assert data["runs"] == []
        assert data["total"] == 0

    def test_single_trace_appears_as_one_run(self, client):
        """All events sharing a trace_id produce exactly one run entry."""
        from backend.api import main as m
        for _ in range(4):
            m.event_buffer.append(_make_event(trace_id="trace-AAA", trust_score=0.9))

        r = client.get("/api/history")
        data = r.json()
        assert data["total"] == 1
        assert len(data["runs"]) == 1
        assert data["runs"][0]["run_id"] == "trace-AAA"

    def test_multiple_traces_produce_multiple_runs(self, client):
        """Two distinct trace_ids → two run entries."""
        from backend.api import main as m
        m.event_buffer.append(_make_event(trace_id="trace-X"))
        m.event_buffer.append(_make_event(trace_id="trace-Y"))

        r = client.get("/api/history")
        run_ids = {run["run_id"] for run in r.json()["runs"]}
        assert "trace-X" in run_ids
        assert "trace-Y" in run_ids

    def test_avg_trust_computed_per_run(self, client):
        """avg_trust in each run entry is the mean trust_score of its events."""
        from backend.api import main as m
        m.event_buffer.append(_make_event(trace_id="trace-T", trust_score=0.6))
        m.event_buffer.append(_make_event(trace_id="trace-T", trust_score=0.4))

        r = client.get("/api/history")
        run = r.json()["runs"][0]
        assert abs(run["avg_trust"] - 0.5) < 0.01

    def test_anomaly_count_per_run(self, client):
        """anomaly_count reflects anomaly events within that trace."""
        from backend.api import main as m
        m.event_buffer.append(_make_event(trace_id="trace-ANO", event_type="tool_call"))
        m.event_buffer.append(_make_anomaly_event(trace_id="trace-ANO"))
        m.event_buffer.append(_make_anomaly_event(trace_id="trace-ANO"))

        r = client.get("/api/history")
        run = r.json()["runs"][0]
        assert run["anomaly_count"] == 2

    def test_limit_param_caps_runs(self, client):
        """?limit= caps the number of runs returned."""
        from backend.api import main as m
        for i in range(10):
            m.event_buffer.append(_make_event(trace_id=f"trace-{i:03d}"))

        r = client.get("/api/history?limit=3")
        assert len(r.json()["runs"]) == 3

    def test_runs_have_required_fields(self, client):
        """Each run entry has run_id, timestamp, avg_trust, anomaly_count."""
        from backend.api import main as m
        m.event_buffer.append(_make_event(trace_id="trace-FIELDS"))

        r = client.get("/api/history")
        run = r.json()["runs"][0]
        for field in ("run_id", "timestamp", "avg_trust", "anomaly_count"):
            assert field in run, f"Missing field: {field}"

    def test_events_without_trace_id_are_ignored(self, client):
        """Events with no trace_id don't create ghost run entries."""
        from backend.api import main as m
        bare_event = _make_event()
        bare_event.pop("trace_id")        # remove trace_id entirely
        m.event_buffer.append(bare_event)
        m.event_buffer.append(_make_event(trace_id="trace-REAL"))

        r = client.get("/api/history")
        assert r.json()["total"] == 1     # only the real trace


# ─────────────────────────────────────────────────────────────────────────────
# TASK 2 — /api/config (GET + POST) and live threshold propagation
# ─────────────────────────────────────────────────────────────────────────────

class TestConfig:

    def test_get_config_returns_defaults(self, client):
        """GET /api/config returns the four default threshold fields."""
        r = client.get("/api/config")
        assert r.status_code == 200
        data = r.json()
        assert data["loop_threshold"] == 5
        assert data["token_spike_threshold"] == 3000
        assert data["latency_drift_ms"] == 2000
        assert data["trust_score_critical"] == 0.3

    def test_post_config_updates_loop_threshold(self, client):
        """POST /api/config with loop_threshold updates the stored value."""
        r = client.post("/api/config", json={"loop_threshold": 10})
        assert r.status_code == 200
        data = r.json()
        assert data["config"]["loop_threshold"] == 10

    def test_post_config_updates_token_spike_threshold(self, client):
        r = client.post("/api/config", json={"token_spike_threshold": 5000})
        assert r.json()["config"]["token_spike_threshold"] == 5000

    def test_post_config_updates_latency_drift_ms(self, client):
        r = client.post("/api/config", json={"latency_drift_ms": 4000})
        assert r.json()["config"]["latency_drift_ms"] == 4000

    def test_post_config_updates_trust_score_critical(self, client):
        r = client.post("/api/config", json={"trust_score_critical": 0.15})
        assert abs(r.json()["config"]["trust_score_critical"] - 0.15) < 0.001

    def test_post_config_returns_status_ok(self, client):
        r = client.post("/api/config", json={"loop_threshold": 7})
        assert r.json()["status"] == "ok"

    def test_post_config_partial_update_preserves_other_fields(self, client):
        """Updating one field does not reset the others."""
        r = client.post("/api/config", json={"loop_threshold": 8})
        cfg = r.json()["config"]
        assert cfg["token_spike_threshold"] == 3000   # unchanged default
        assert cfg["latency_drift_ms"] == 2000        # unchanged default

    def test_get_config_reflects_posted_changes(self, client):
        """GET /api/config after POST returns the updated values."""
        client.post("/api/config", json={"loop_threshold": 12})
        r = client.get("/api/config")
        assert r.json()["loop_threshold"] == 12

    # ── Live propagation to AnomalyDetector ──────────────────────────────────

    def test_loop_threshold_propagates_to_detector(self, client):
        """
        After POST /api/config with loop_threshold=3, the detector fires
        at 3 calls — not at the old default of 5.
        """
        from backend.api import main as m

        client.post("/api/config", json={"loop_threshold": 3})

        # 3 calls should now trigger — would have been safe with old threshold=5
        result = None
        for _ in range(3):
            result = m.anomaly_detector.check_event({
                "event_type": "tool_call",
                "agent_id": "test",
                "trace_id": "trace-thresh",
                "step_id": "s1",
                "step_name": "tool:search",
                "tool_name": "search_tool",
                "trust_score": 0.9,
                "llm_total_tokens": 0,
                "duration_ms": 100.0,
                "error": "",
            })
        assert result is not None
        assert result.anomaly_type == "loop"

    def test_token_spike_threshold_propagates_to_detector(self, client):
        """
        After setting token_spike_threshold=1000, a 1500-token call
        triggers a spike (default 3000 would not).
        """
        from backend.api import main as m
        client.post("/api/config", json={"token_spike_threshold": 1000})

        result = m.anomaly_detector.check_event({
            "event_type": "llm_call",
            "agent_id": "test",
            "trace_id": "trace-tok",
            "step_id": "s1",
            "step_name": "research",
            "tool_name": "",
            "trust_score": 0.8,
            "llm_total_tokens": 1500,
            "duration_ms": 300.0,
            "error": "",
        })
        assert result is not None
        assert result.anomaly_type == "token_spike"

    def test_latency_threshold_propagates_to_detector(self, client):
        """
        After setting latency_drift_ms=500, a 700ms step fires drift
        (default 2000ms would not).
        """
        from backend.api import main as m
        client.post("/api/config", json={"latency_drift_ms": 500})

        result = m.anomaly_detector.check_event({
            "event_type": "step_end",
            "agent_id": "test",
            "trace_id": "trace-lat",
            "step_id": "s1",
            "step_name": "slow_step",
            "tool_name": "",
            "trust_score": 0.9,
            "llm_total_tokens": 0,
            "duration_ms": 700.0,
            "error": "",
        })
        assert result is not None
        assert result.anomaly_type == "latency_drift"

    def test_trust_threshold_propagates_to_detector(self, client):
        """
        After setting trust_score_critical=0.5, an event with trust=0.4
        triggers trust_collapse (default 0.3 would not).
        """
        from backend.api import main as m
        client.post("/api/config", json={"trust_score_critical": 0.5})

        result = m.anomaly_detector.check_event({
            "event_type": "step_end",
            "agent_id": "test",
            "trace_id": "trace-trust",
            "step_id": "s1",
            "step_name": "synthesis",
            "tool_name": "",
            "trust_score": 0.4,     # above old default (0.3), below new (0.5)
            "llm_total_tokens": 0,
            "duration_ms": 100.0,
            "error": "",
        })
        assert result is not None
        assert result.anomaly_type == "trust_collapse"

    def test_update_thresholds_all_at_once(self, client):
        """POST with all four fields simultaneously updates all."""
        r = client.post("/api/config", json={
            "loop_threshold": 2,
            "token_spike_threshold": 500,
            "latency_drift_ms": 300,
            "trust_score_critical": 0.6,
        })
        cfg = r.json()["config"]
        assert cfg["loop_threshold"] == 2
        assert cfg["token_spike_threshold"] == 500
        assert cfg["latency_drift_ms"] == 300
        assert abs(cfg["trust_score_critical"] - 0.6) < 0.001


# ─────────────────────────────────────────────────────────────────────────────
# TASK 3 — Slack webhook (mocked — never hits real URL)
# ─────────────────────────────────────────────────────────────────────────────

class TestSlackWebhook:

    @pytest.mark.asyncio
    async def test_slack_not_called_when_url_unset(self):
        """notify_slack_critical is a no-op when SLACK_WEBHOOK_URL is empty."""
        from backend.api.main import notify_slack_critical
        with patch("backend.api.main.SLACK_WEBHOOK_URL", None):
            # Should return silently, no HTTP call
            await notify_slack_critical({"agent_id": "x", "anomaly_type": "loop", "trace_id": "t"})
            # If we got here without an error, the guard worked

    @pytest.mark.asyncio
    async def test_slack_posts_when_url_set(self):
        """notify_slack_critical makes an HTTP POST when SLACK_WEBHOOK_URL is configured."""
        from backend.api.main import notify_slack_critical

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("backend.api.main.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test/fake"), \
             patch("httpx.AsyncClient") as MockClient:

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(return_value=mock_response)
            MockClient.return_value = mock_instance

            await notify_slack_critical(
                {
                    "agent_id": "agent-loop",
                    "anomaly_type": "loop",
                    "trace_id": "trace-slack-test",
                    "reasoning_content": "Loop detected — search_tool called 23x",
                },
                foundation_sec_summary="Agent stuck in infinite loop",
            )

            mock_instance.post.assert_called_once()
            call_kwargs = mock_instance.post.call_args
            # Verify the URL was the configured webhook
            assert "hooks.slack.com" in call_kwargs[0][0]

    @pytest.mark.asyncio
    async def test_slack_message_contains_anomaly_type(self):
        """Slack message body includes the anomaly type."""
        from backend.api.main import notify_slack_critical

        posted_payloads = []

        async def capture_post(url, json, headers):
            posted_payloads.append(json)
            return MagicMock(status_code=200)

        with patch("backend.api.main.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test/fake"), \
             patch("httpx.AsyncClient") as MockClient:

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(side_effect=capture_post)
            MockClient.return_value = mock_instance

            await notify_slack_critical(
                {"agent_id": "a", "anomaly_type": "token_spike", "trace_id": "t"},
            )

        assert posted_payloads, "No Slack POST was made"
        assert "token_spike" in posted_payloads[0]["text"]

    @pytest.mark.asyncio
    async def test_slack_failure_is_non_fatal(self):
        """A Slack POST failure does not raise an exception (graceful skip)."""
        from backend.api.main import notify_slack_critical

        with patch("backend.api.main.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test/fake"), \
             patch("httpx.AsyncClient") as MockClient:

            mock_instance = AsyncMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=False)
            mock_instance.post = AsyncMock(side_effect=Exception("Network error"))
            MockClient.return_value = mock_instance

            # Should not raise
            await notify_slack_critical(
                {"agent_id": "a", "anomaly_type": "loop", "trace_id": "t"},
            )


# ─────────────────────────────────────────────────────────────────────────────
# TASK 4 — /api/export/incident (PDF generation)
# ─────────────────────────────────────────────────────────────────────────────

class TestPDFExport:

    def test_pdf_returned_with_correct_content_type(self, client):
        """POST /api/export/incident returns a PDF (Content-Type: application/pdf)."""
        r = client.post("/api/export/incident", json={
            "trace_id": "trace-pdf-001",
            "anomaly_data": {
                "agent_id": "agent-test",
                "anomaly_type": "loop",
                "severity": "critical",
                "trust_score": 0.05,
                "trace_id": "trace-pdf-001",
                "timestamp": time.time(),
            },
            "foundation_sec_reasoning": (
                "The agent entered an infinite loop at search_tool.\n"
                "Add an empty-result guard to break after 3 failed attempts."
            ),
        })
        assert r.status_code == 200
        assert "application/pdf" in r.headers["content-type"]

    def test_pdf_content_is_non_empty(self, client):
        """PDF response body is not empty."""
        r = client.post("/api/export/incident", json={
            "trace_id": "trace-pdf-002",
            "anomaly_data": {"agent_id": "a", "anomaly_type": "loop", "severity": "high",
                             "trust_score": 0.2, "trace_id": "trace-pdf-002"},
        })
        assert len(r.content) > 0

    def test_pdf_starts_with_pdf_magic_bytes(self, client):
        """Response content starts with the PDF magic number %%PDF."""
        r = client.post("/api/export/incident", json={
            "trace_id": "trace-pdf-magic",
            "anomaly_data": {"agent_id": "a", "anomaly_type": "token_spike", "severity": "high",
                             "trust_score": 0.3, "trace_id": "trace-pdf-magic"},
        })
        assert r.content[:4] == b"%PDF", "Response is not a valid PDF file"

    def test_pdf_filename_in_content_disposition(self, client):
        """Content-Disposition header includes a .pdf filename."""
        r = client.post("/api/export/incident", json={
            "trace_id": "trace-pdf-filename",
            "anomaly_data": {"agent_id": "a", "anomaly_type": "loop", "severity": "critical",
                             "trust_score": 0.05, "trace_id": "trace-pdf-filename"},
        })
        cd = r.headers.get("content-disposition", "")
        assert ".pdf" in cd

    def test_pdf_without_anomaly_data_still_works(self, client):
        """Calling the endpoint with only a trace_id and no anomaly_data doesn't crash."""
        r = client.post("/api/export/incident", json={"trace_id": "trace-minimal"})
        assert r.status_code == 200
        assert r.content[:4] == b"%PDF"

    def test_pdf_with_all_severity_levels(self, client):
        """PDF generates cleanly for each severity level (critical/high/medium/low)."""
        for severity in ("critical", "high", "medium", "low"):
            r = client.post("/api/export/incident", json={
                "trace_id": f"trace-{severity}",
                "anomaly_data": {
                    "agent_id": "a",
                    "anomaly_type": "loop",
                    "severity": severity,
                    "trust_score": 0.1,
                    "trace_id": f"trace-{severity}",
                    "timestamp": time.time(),
                },
            })
            assert r.status_code == 200, f"PDF failed for severity={severity}"
            assert r.content[:4] == b"%PDF", f"Not a PDF for severity={severity}"


# ─────────────────────────────────────────────────────────────────────────────
# /api/explain  (Foundation-Sec path)
# ─────────────────────────────────────────────────────────────────────────────

class TestExplain:

    def test_explain_returns_expected_fields(self, client):
        """POST /api/explain returns explanation, recommended_action, severity, splunk_spl."""
        r = client.post("/api/explain", json={
            "anomaly_event": _make_anomaly_event(),
            "recent_events": [_make_event()],
            "trace_id": "trace-explain-001",
        })
        assert r.status_code == 200
        data = r.json()
        for field in ("explanation", "recommended_action", "severity", "splunk_spl"):
            assert field in data, f"Missing field: {field}"

    def test_explain_with_minimal_payload(self, client):
        """anomaly_event is the only required field."""
        r = client.post("/api/explain", json={
            "anomaly_event": {"event_type": "anomaly", "anomaly_type": "loop"},
        })
        assert r.status_code == 200

    def test_explain_severity_is_string(self, client):
        r = client.post("/api/explain", json={"anomaly_event": _make_anomaly_event()})
        assert isinstance(r.json()["severity"], str)

    def test_explain_splunk_spl_is_string(self, client):
        r = client.post("/api/explain", json={"anomaly_event": _make_anomaly_event()})
        assert isinstance(r.json()["splunk_spl"], str)
        assert len(r.json()["splunk_spl"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# update_thresholds() unit tests (direct — no HTTP layer)
# ─────────────────────────────────────────────────────────────────────────────

class TestUpdateThresholds:
    """
    Test AnomalyDetector.update_thresholds() directly, without the API layer.
    Confirms the method updates internal state and that detection behaviour changes.
    """

    def test_update_loop_threshold_changes_detection(self):
        from backend.instrumentation.anomaly_detector import AnomalyDetector
        d = AnomalyDetector()
        d.update_thresholds(loop_threshold=2)

        events = []
        for _ in range(2):
            event = {
                "event_type": "tool_call", "agent_id": "a", "trace_id": "t",
                "step_id": "s", "step_name": "tool:x", "tool_name": "x",
                "trust_score": 0.9, "llm_total_tokens": 0, "duration_ms": 100.0, "error": "",
            }
            events.append(d.check_event(event))

        assert events[-1] is not None
        assert events[-1].anomaly_type == "loop"

    def test_update_token_threshold_changes_detection(self):
        from backend.instrumentation.anomaly_detector import AnomalyDetector
        d = AnomalyDetector()
        d.update_thresholds(token_spike_threshold=200)

        result = d.check_event({
            "event_type": "llm_call", "agent_id": "a", "trace_id": "t",
            "step_id": "s", "step_name": "r", "tool_name": "",
            "trust_score": 0.9, "llm_total_tokens": 300, "duration_ms": 200.0, "error": "",
        })
        assert result is not None
        assert result.anomaly_type == "token_spike"

    def test_update_latency_threshold_changes_detection(self):
        from backend.instrumentation.anomaly_detector import AnomalyDetector
        d = AnomalyDetector()
        d.update_thresholds(latency_drift_ms=100.0)

        result = d.check_event({
            "event_type": "step_end", "agent_id": "a", "trace_id": "t",
            "step_id": "s", "step_name": "slow", "tool_name": "",
            "trust_score": 0.9, "llm_total_tokens": 0, "duration_ms": 200.0, "error": "",
        })
        assert result is not None
        assert result.anomaly_type == "latency_drift"

    def test_update_trust_threshold_changes_detection(self):
        from backend.instrumentation.anomaly_detector import AnomalyDetector
        d = AnomalyDetector()
        d.update_thresholds(trust_score_critical=0.8)

        result = d.check_event({
            "event_type": "step_end", "agent_id": "a", "trace_id": "t",
            "step_id": "s", "step_name": "x", "tool_name": "",
            "trust_score": 0.7,       # below new threshold 0.8
            "llm_total_tokens": 0, "duration_ms": 50.0, "error": "",
        })
        assert result is not None
        assert result.anomaly_type == "trust_collapse"

    def test_partial_update_leaves_other_thresholds_unchanged(self):
        from backend.instrumentation.anomaly_detector import AnomalyDetector
        d = AnomalyDetector()
        original_token = d.token_spike_threshold
        original_latency = d.latency_drift_ms

        d.update_thresholds(loop_threshold=3)

        assert d.token_spike_threshold == original_token
        assert d.latency_drift_ms == original_latency
        assert d.loop_threshold == 3

    def test_update_with_none_values_is_no_op(self):
        from backend.instrumentation.anomaly_detector import AnomalyDetector
        d = AnomalyDetector()
        original_loop = d.loop_threshold
        d.update_thresholds(loop_threshold=None)
        assert d.loop_threshold == original_loop