"""
agentwatch/backend/api/main.py
Fixed version - browser_connections global scope bug resolved
"""

import asyncio
import json
import logging
import time
from collections import deque
from typing import List, Set, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .splunk_client import SplunkClient
from .foundation_sec import FoundationSecClient
from ..instrumentation.anomaly_detector import AnomalyDetector

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


@app.websocket("/ws/agent-stream")
async def agent_stream(ws: WebSocket):
    await ws.accept()
    agent_connections.add(ws)
    logger.info(f"Agent connected. Active: {len(agent_connections)}")
    try:
        while True:
            raw = await ws.receive_text()
            event = json.loads(raw)
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
            asyncio.create_task(splunk.index_event(event))
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


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "splunk_connected": await splunk.ping(),
        "buffer_size": len(event_buffer),
        "agent_connections": len(agent_connections),
        "browser_connections": len(browser_connections),
    }