"""
agentwatch/backend/api/main.py
Live-demo enabled version:
- Adds /api/demo/trigger to run the demo agent in-process and stream
  events straight into the existing browser pipeline (no second WS hop).
- Adds /api/demo/status so the frontend can poll/disable buttons while busy.
- Serves the frontend as static files so backend+frontend deploy as one unit.
- Optional-HEC: public demo runs skip Splunk indexing by default
  (set PUBLIC_DEMO_INDEX_TO_SPLUNK=true to index them too).

NEW (hackathon additions):
- /api/history       — TASK 1: last 30 run summaries for trust trend chart
- /api/config        — TASK 2: alert rules configurator (GET + POST)
- /api/export/incident — TASK 4: PDF incident report export
- Slack webhook      — TASK 3: CRITICAL anomaly notifications
"""

import asyncio
import io
import json
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import List, Set, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from .splunk_client import SplunkClient
from .foundation_sec import FoundationSecClient
from ..instrumentation.anomaly_detector import AnomalyDetector
from .autopsy import run_autopsy

logger = logging.getLogger("agentwatch.api")

app = FastAPI(title="AgentWatch API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

event_buffer: deque = deque(maxlen=500)
browser_connections: Set[WebSocket] = set()
agent_connections: Set[WebSocket] = set()

splunk = SplunkClient()
foundation_sec = FoundationSecClient()
anomaly_detector = AnomalyDetector()

# ─────────────────────────────────────────────
# Public demo config
# ─────────────────────────────────────────────
PUBLIC_DEMO_INDEX_TO_SPLUNK = os.getenv("PUBLIC_DEMO_INDEX_TO_SPLUNK", "false").lower() == "true"
demo_lock = asyncio.Lock()
demo_running = False
demo_last_mode: Optional[str] = None
demo_last_finished_at: Optional[float] = None

# ─────────────────────────────────────────────
# TASK 2: In-memory alert config (defaults match anomaly_detector.py constants)
# ─────────────────────────────────────────────
alert_config: dict = {
    "loop_threshold": 5,
    "token_spike_threshold": 3000,
    "latency_drift_ms": 2000,
    "trust_score_critical": 0.3,
}

# ─────────────────────────────────────────────
# TASK 3: Slack webhook
# ─────────────────────────────────────────────
SLACK_WEBHOOK_URL: Optional[str] = os.getenv("SLACK_WEBHOOK_URL")
SPLUNK_BASE_URL: str = os.getenv("SPLUNK_URL", "http://localhost:8000")


async def notify_slack_critical(anomaly_event: dict, foundation_sec_summary: str = ""):
    """
    POST a CRITICAL anomaly notification to Slack.
    Gracefully skips if SLACK_WEBHOOK_URL is not set.
    """
    if not SLACK_WEBHOOK_URL:
        return

    agent_id = anomaly_event.get("agent_id", "unknown")
    anomaly_type = anomaly_event.get("anomaly_type", "unknown")
    trace_id = anomaly_event.get("trace_id", "")

    spl = f"index=agentwatch trace_id={trace_id} event_type=anomaly"
    encoded = f"search {spl}"
    splunk_deep_link = (
        f"{SPLUNK_BASE_URL}/en-US/app/search/search"
        f"?q={encoded}&earliest=-1h&latest=now"
    )

    summary = foundation_sec_summary or anomaly_event.get("reasoning_content", "No summary available")

    message = (
        f"🚨 AgentWatch CRITICAL: {anomaly_type} detected on agent {agent_id}"
        f" — {summary}"
        f" — View trace: {splunk_deep_link}"
    )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                SLACK_WEBHOOK_URL,
                json={"text": message},
                headers={"Content-Type": "application/json"},
            )
        logger.info(f"Slack notification sent for CRITICAL {anomaly_type} on {agent_id}")
    except Exception as e:
        logger.warning(f"Slack notification failed (non-fatal): {e}")


async def broadcast_to_browsers(event: dict):
    message = json.dumps({"type": "event", "data": event})
    dead = set()
    for ws in list(browser_connections):
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    for ws in dead:
        browser_connections.discard(ws)


async def ingest_event(event: dict, index_to_splunk: bool = True):
    """
    Shared ingestion path used by BOTH:
      - the real agent WebSocket stream (/ws/agent-stream)
      - the in-process public demo trigger (/api/demo/trigger)

    Runs anomaly detection, appends to the rolling buffer, broadcasts
    to connected browsers, and optionally indexes to Splunk HEC.
    """
    event_buffer.append(event)

    anomaly = anomaly_detector.check_event(event)
    if anomaly:
        anomaly_event = {
            **event,
            "event_type": "anomaly",
            "anomaly_type": anomaly.anomaly_type,
            "severity": anomaly.severity,
            "reasoning_content": anomaly.message,
            "trust_score": anomaly.trust_score,
            "confidence": anomaly.confidence,
        }
        event_buffer.append(anomaly_event)
        await broadcast_to_browsers(anomaly_event)

        # TASK 3: fire Slack notification for CRITICAL anomalies
        if anomaly.severity == "critical":
            asyncio.create_task(
                notify_slack_critical(anomaly_event, anomaly.message)
            )

    await broadcast_to_browsers(event)

    if index_to_splunk:
        asyncio.create_task(splunk.index_event(event))


@app.websocket("/ws/agent-stream")
async def agent_stream(ws: WebSocket):
    await ws.accept()
    agent_connections.add(ws)
    logger.info(f"Agent connected. Active: {len(agent_connections)}")
    try:
        while True:
            raw = await ws.receive_text()
            event = json.loads(raw)
            await ingest_event(event, index_to_splunk=True)
    except WebSocketDisconnect:
        agent_connections.discard(ws)
    except Exception as e:
        agent_connections.discard(ws)
        logger.error(f"Agent stream error: {e}")


@app.websocket("/ws/browser")
async def browser_stream(ws: WebSocket):
    await ws.accept()
    browser_connections.add(ws)
    logger.info(f"Browser connected. Watching: {len(browser_connections)}")
    recent = list(event_buffer)[-100:]
    if recent:
        await ws.send_text(json.dumps({"type": "replay", "events": recent}))
    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            if data.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        browser_connections.discard(ws)
    except Exception:
        browser_connections.discard(ws)


class ExplainRequest(BaseModel):
    anomaly_event: dict
    recent_events: Optional[List[dict]] = None
    trace_id: Optional[str] = None


class ExplainResponse(BaseModel):
    explanation: str
    recommended_action: str
    severity: str
    splunk_spl: str


@app.post("/api/explain", response_model=ExplainResponse)
async def explain_anomaly(req: ExplainRequest):
    try:
        context_events = req.recent_events or list(event_buffer)[-10:]
        result = await foundation_sec.explain(
            anomaly=req.anomaly_event,
            context=context_events,
        )
        trace_id = req.trace_id or req.anomaly_event.get("trace_id", "*")
        spl = await splunk.generate_spl(
            nl_query=f"Show me all events for trace {trace_id} where trust_score < 0.3"
        )
        return ExplainResponse(
            explanation=result["explanation"],
            recommended_action=result["recommended_action"],
            severity=result["severity"],
            splunk_spl=spl,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class QueryRequest(BaseModel):
    natural_language: str
    time_range: str = "-1h"


class QueryResponse(BaseModel):
    spl: str
    results: list
    result_count: int


@app.post("/api/query", response_model=QueryResponse)
async def nl_query(req: QueryRequest):
    try:
        spl = await splunk.generate_spl(nl_query=req.natural_language, time_range=req.time_range)
        results = await splunk.run_search(spl)
        return QueryResponse(spl=spl, results=results, result_count=len(results))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/events")
async def get_events(limit: int = 100, event_type: Optional[str] = None):
    events = list(event_buffer)
    if event_type:
        events = [e for e in events if e.get("event_type") == event_type]
    return {"events": events[-limit:], "total": len(events)}


@app.get("/api/stats")
async def get_stats():
    events = list(event_buffer)
    if not events:
        return {"total_events": 0, "anomalies": 0, "agents": 0, "avg_trust": 1.0}
    anomalies = [e for e in events if e.get("event_type") == "anomaly"]
    agents = set(e.get("agent_id") for e in events if e.get("agent_id"))
    trust_scores = [e.get("trust_score", 1.0) for e in events if e.get("trust_score") is not None]
    avg_trust = sum(trust_scores) / len(trust_scores) if trust_scores else 1.0
    detector_stats = anomaly_detector.get_stats()
    return {
        "total_events": len(events),
        "anomalies": len(anomalies),
        "agents": len(agents),
        "avg_trust": round(avg_trust, 3),
        "browser_connections": len(browser_connections),
        "detector_anomalies": detector_stats["total_anomalies_detected"],
        "anomaly_breakdown": detector_stats["anomaly_breakdown"],
    }


# ─────────────────────────────────────────────
# TASK 1: Trust Score History
# ─────────────────────────────────────────────

@app.get("/api/history")
async def get_history(limit: int = 30):
    """
    Returns the last `limit` agent runs (grouped by trace_id) with:
      run_id, timestamp, avg_trust, anomaly_count
    Used by the Trust Score Trend chart in the frontend.
    """
    events = list(event_buffer)

    runs: dict = {}
    for e in events:
        tid = e.get("trace_id")
        if not tid:
            continue
        if tid not in runs:
            runs[tid] = {
                "run_id": tid,
                "timestamp": e.get("timestamp") or e.get("ts") or time.time(),
                "trust_scores": [],
                "anomaly_count": 0,
            }
        ts = e.get("trust_score")
        if ts is not None:
            runs[tid]["trust_scores"].append(float(ts))
        if e.get("event_type") == "anomaly":
            runs[tid]["anomaly_count"] += 1

    sorted_runs = sorted(runs.values(), key=lambda r: r["timestamp"])
    recent = sorted_runs[-limit:]

    result = []
    for r in recent:
        scores = r["trust_scores"]
        result.append({
            "run_id": r["run_id"],
            "timestamp": r["timestamp"],
            "avg_trust": round(sum(scores) / len(scores), 3) if scores else 1.0,
            "anomaly_count": r["anomaly_count"],
        })

    return {"runs": result, "total": len(runs)}


# ─────────────────────────────────────────────
# TASK 2: Alert Rules Config
# ─────────────────────────────────────────────

class AlertConfig(BaseModel):
    loop_threshold: Optional[int] = None
    token_spike_threshold: Optional[int] = None
    latency_drift_ms: Optional[int] = None
    trust_score_critical: Optional[float] = None


@app.get("/api/config")
async def get_config():
    """Return current alert thresholds."""
    return alert_config


@app.post("/api/config")
async def set_config(req: AlertConfig):
    """
    Update alert thresholds in memory and push them into the live
    AnomalyDetector instance so changes take effect immediately.
    """
    global alert_config

    if req.loop_threshold is not None:
        alert_config["loop_threshold"] = req.loop_threshold
        anomaly_detector.update_thresholds(loop_threshold=req.loop_threshold)

    if req.token_spike_threshold is not None:
        alert_config["token_spike_threshold"] = req.token_spike_threshold
        anomaly_detector.update_thresholds(token_spike_threshold=req.token_spike_threshold)

    if req.latency_drift_ms is not None:
        alert_config["latency_drift_ms"] = req.latency_drift_ms
        anomaly_detector.update_thresholds(latency_drift_ms=req.latency_drift_ms)

    if req.trust_score_critical is not None:
        alert_config["trust_score_critical"] = req.trust_score_critical
        anomaly_detector.update_thresholds(trust_score_critical=req.trust_score_critical)

    logger.info(f"Alert config updated: {alert_config}")
    return {"status": "ok", "config": alert_config}


# ─────────────────────────────────────────────
# TASK 4: Incident Report PDF Export
# ─────────────────────────────────────────────

class IncidentExportRequest(BaseModel):
    trace_id: Optional[str] = None
    anomaly_data: Optional[dict] = None
    foundation_sec_reasoning: Optional[str] = None


@app.post("/api/export/incident")
async def export_incident(req: IncidentExportRequest):
    """
    Generate a PDF incident report using reportlab and return it as a download.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib import colors
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="reportlab not installed. Run: pip install reportlab"
        )

    # Pull event data
    anomaly = req.anomaly_data or {}
    trace_id = req.trace_id or anomaly.get("trace_id", "unknown")
    agent_id = anomaly.get("agent_id", "unknown")
    anomaly_type = anomaly.get("anomaly_type", "unknown")
    severity = anomaly.get("severity", "unknown")
    trust_score = anomaly.get("trust_score", 1.0)
    timestamp_raw = anomaly.get("timestamp") or anomaly.get("ts") or time.time()
    try:
        ts_str = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(float(timestamp_raw)))
    except Exception:
        ts_str = str(timestamp_raw)

    reasoning = req.foundation_sec_reasoning or anomaly.get("reasoning_content", "No reasoning provided.")

    # Relevant SPL queries
    spl_queries = [
        f'index=agentwatch trace_id={trace_id} | sort -_time | table _time, event_type, step_name, trust_score, tool_name',
        f'index=agentwatch trace_id={trace_id} event_type=anomaly | table _time, anomaly_type, severity, reasoning_content',
        f'index=agentwatch agent_id={agent_id} | timechart avg(trust_score) by agent_id',
    ]

    # Build PDF in memory
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    style_header = ParagraphStyle(
        "aw_header",
        parent=styles["Heading1"],
        fontSize=22,
        textColor=colors.HexColor("#1a1a2e"),
        spaceAfter=4,
        alignment=TA_CENTER,
    )
    style_sub = ParagraphStyle(
        "aw_sub",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#5a7090"),
        alignment=TA_CENTER,
        spaceAfter=16,
    )
    style_section = ParagraphStyle(
        "aw_section",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=colors.HexColor("#1a1a2e"),
        spaceBefore=16,
        spaceAfter=6,
        borderPad=4,
    )
    style_body = ParagraphStyle(
        "aw_body",
        parent=styles["Normal"],
        fontSize=10,
        leading=16,
        textColor=colors.HexColor("#2c2c2c"),
    )
    style_code = ParagraphStyle(
        "aw_code",
        parent=styles["Code"],
        fontSize=8,
        leading=13,
        backColor=colors.HexColor("#f0f4ff"),
        textColor=colors.HexColor("#1a3a6e"),
        leftIndent=8,
        rightIndent=8,
        spaceBefore=4,
        spaceAfter=4,
    )
    style_label = ParagraphStyle(
        "aw_label",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#5a7090"),
        spaceAfter=2,
    )

    severity_color = {
        "critical": colors.HexColor("#ff3355"),
        "high": colors.HexColor("#ff8800"),
        "medium": colors.HexColor("#ffcc00"),
        "low": colors.HexColor("#00cc66"),
    }.get(severity.lower(), colors.HexColor("#888888"))

    story = []

    # ── Header ──
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("AgentWatch", style_header))
    story.append(Paragraph("AI Agent Observability Platform — Incident Report", style_sub))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor("#4f8fff"), spaceAfter=16))

    # ── Incident Summary Table ──
    story.append(Paragraph("Incident Summary", style_section))

    summary_data = [
        ["Field", "Value"],
        ["Trace ID", trace_id],
        ["Agent ID", agent_id],
        ["Timestamp", ts_str],
        ["Anomaly Type", anomaly_type.replace("_", " ").title()],
        ["Severity", severity.upper()],
        ["Trust Score", f"{float(trust_score):.3f}"],
    ]

    table = Table(summary_data, colWidths=[4 * cm, 13 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8f9ff")),
        ("BACKGROUND", (0, -2), (-1, -2), colors.HexColor("#fff0f0")),  # severity row
        ("TEXTCOLOR", (1, -2), (1, -2), severity_color),
        ("FONTNAME", (1, -2), (1, -2), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9ff"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d0d8f0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8f9ff"), colors.white]),
    ]))
    story.append(table)

    # ── Foundation-Sec Reasoning ──
    story.append(Paragraph("Foundation-Sec Analysis", style_section))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d0d8f0"), spaceAfter=8))
    # Split reasoning into paragraphs for readability
    for para in reasoning.split("\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para, style_body))
            story.append(Spacer(1, 4))

    # ── SPL Queries ──
    story.append(Paragraph("Relevant SPL Queries", style_section))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d0d8f0"), spaceAfter=8))
    story.append(Paragraph("Use these queries in Splunk to reproduce and investigate this incident:", style_body))
    story.append(Spacer(1, 6))

    query_labels = [
        "Full trace timeline:",
        "Anomaly events only:",
        "Trust score trend for this agent:",
    ]
    for label, spl in zip(query_labels, spl_queries):
        story.append(Paragraph(label, style_label))
        story.append(Paragraph(spl, style_code))
        story.append(Spacer(1, 4))

    # ── Footer ──
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#d0d8f0"), spaceBefore=8))
    generated_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    story.append(Paragraph(
        f"Generated by AgentWatch · {generated_at} · Powered by Foundation-Sec-1.1-8B + Splunk AI Toolkit",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=8,
                       textColor=colors.HexColor("#aaaaaa"), alignment=TA_CENTER, spaceBefore=6)
    ))

    doc.build(story)
    buf.seek(0)

    filename = f"agentwatch-incident-{trace_id[:8]}-{int(time.time())}.pdf"
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─────────────────────────────────────────────
# Autopsy
# ─────────────────────────────────────────────

class AutopsyRequest(BaseModel):
    trace_id: Optional[str] = None
    last_n_events: int = 200


@app.post("/api/autopsy")
async def get_autopsy(req: AutopsyRequest):
    """
    Post-run agent autopsy — sends full trace to Foundation-Sec
    and returns a structured diagnostic report.
    """
    try:
        events = list(event_buffer)
        if req.trace_id:
            events = [e for e in events if e.get("trace_id") == req.trace_id]
        else:
            events = events[-req.last_n_events:]

        if not events:
            raise HTTPException(status_code=404, detail="No events found for this trace")

        result = await run_autopsy(events, foundation_sec)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────
# Live public demo trigger
# ─────────────────────────────────────────────

class DemoTriggerRequest(BaseModel):
    mode: str = "normal"  # normal | loop | hallucinate | drift


class DemoTriggerResponse(BaseModel):
    status: str
    mode: str
    trace_id: Optional[str] = None
    message: str


@app.get("/api/demo/status")
async def demo_status():
    return {
        "running": demo_running,
        "last_mode": demo_last_mode,
        "last_finished_at": demo_last_finished_at,
    }


@app.post("/api/demo/trigger", response_model=DemoTriggerResponse)
async def demo_trigger(req: DemoTriggerRequest):
    global demo_running, demo_last_mode, demo_last_finished_at

    valid_modes = {"normal", "loop", "hallucinate", "drift"}
    if req.mode not in valid_modes:
        raise HTTPException(status_code=400, detail=f"mode must be one of {valid_modes}")

    if demo_lock.locked():
        raise HTTPException(
            status_code=429,
            detail="A demo run is already in progress. Please try again in a few seconds.",
        )

    async with demo_lock:
        demo_running = True
        try:
            from ..agent.demo_runner_lib import run_demo_in_process

            loop = asyncio.get_event_loop()

            def emit(event: dict):
                asyncio.run_coroutine_threadsafe(
                    ingest_event(event, index_to_splunk=PUBLIC_DEMO_INDEX_TO_SPLUNK),
                    loop,
                )

            trace_id = await loop.run_in_executor(
                None, run_demo_in_process, req.mode, emit
            )

            demo_last_mode = req.mode
            demo_last_finished_at = time.time()

            return DemoTriggerResponse(
                status="completed",
                mode=req.mode,
                trace_id=trace_id,
                message=f"Demo run ({req.mode}) completed. Watch the live feed and brain graph above.",
            )
        finally:
            demo_running = False


@app.get("/api/health")
async def health():
    try:
        splunk_connected = await asyncio.wait_for(splunk.ping(), timeout=2.0)
    except asyncio.TimeoutError:
        splunk_connected = False

    return {
        "status": "ok",
        "splunk_connected": splunk_connected,
        "buffer_size": len(event_buffer),
        "agent_connections": len(agent_connections),
        "browser_connections": len(browser_connections),
        "demo_running": demo_running,
        "public_demo_indexes_to_splunk": PUBLIC_DEMO_INDEX_TO_SPLUNK,
    }


# ─────────────────────────────────────────────
# Static frontend
# ─────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/src", StaticFiles(directory=str(FRONTEND_DIR / "src")), name="frontend-src")

    @app.get("/")
    async def serve_index():
        index_path = FRONTEND_DIR / "index.html"
        return FileResponse(str(index_path))

    @app.get("/ops")
    async def serve_ops():
        ops_path = FRONTEND_DIR / "ops.html"
        return FileResponse(str(ops_path))

    @app.get("/topology")
    async def serve_topology():
        return FileResponse(str(FRONTEND_DIR / "topology.html"))

    @app.get("/guide.js")
    async def serve_guide():
        return FileResponse(str(FRONTEND_DIR / "guide.js"))
else:
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR} — static serving disabled.")