"""
agentwatch/backend/api/main.py
Live-demo enabled version:
- Adds /api/demo/trigger to run the demo agent in-process and stream
  events straight into the existing browser pipeline (no second WS hop).
- Adds /api/demo/status so the frontend can poll/disable buttons while busy.
- Serves the frontend as static files so backend+frontend deploy as one unit.
- Optional-HEC: public demo runs skip Splunk indexing by default
  (set PUBLIC_DEMO_INDEX_TO_SPLUNK=true to index them too).
"""

import asyncio
import json
import logging
import os
import time
from collections import deque
from pathlib import Path
from typing import List, Set, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
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
    """
    Runs the demo LangGraph agent in-process for the given mode and streams
    every event through the same anomaly-detection + broadcast pipeline used
    by real agent connections. Used by the public live-demo buttons on the
    frontend so visitors can trigger anomalies themselves without running
    anything locally.

    Only one demo run is allowed at a time (free-tier friendly).
    """
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
            # Import here to avoid import-time side effects / circular imports
            from ..agent.demo_runner_lib import run_demo_in_process

            loop = asyncio.get_event_loop()

            def emit(event: dict):
                # Called from the worker thread — schedule the async ingest
                # back on the main event loop.
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
# Resolve frontend dir relative to repo root: backend/api/main.py -> ../../frontend
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/src", StaticFiles(directory=str(FRONTEND_DIR / "src")), name="frontend-src")

    @app.get("/")
    async def serve_index():
        index_path = FRONTEND_DIR / "index.html"
        return FileResponse(str(index_path))
else:
    logger.warning(f"Frontend directory not found at {FRONTEND_DIR} — static serving disabled.")