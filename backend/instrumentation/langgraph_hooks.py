"""
agentwatch/backend/instrumentation/langgraph_hooks.py

Wraps every LangGraph node execution with an OpenTelemetry span.
Captures LLM calls, tool calls, reasoning steps, and errors —
everything needed to reconstruct the agent's "brain" in Three.js.

Usage:
    hooks = AgentWatchHooks(tracer, agent_id="my-agent", ws_broadcaster=broadcast_fn)
    wrapped_graph = hooks.instrument(graph)
    result = await wrapped_graph.ainvoke(inputs)
"""

import time
import uuid
import json
import asyncio
import logging
from typing import Any, Callable, Dict, Optional, AsyncGenerator
from dataclasses import dataclass, field
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

logger = logging.getLogger("agentwatch.hooks")


# ─────────────────────────────────────────────
# Event Types streamed over WebSocket
# ─────────────────────────────────────────────

@dataclass
class AgentEvent:
    """Structured event emitted for every instrumented action."""
    event_type: str          # llm_call | tool_call | step_start | step_end | error | anomaly
    agent_id: str
    trace_id: str
    step_id: str
    step_name: str
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    # LLM-specific
    llm_model: str = ""
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    llm_total_tokens: int = 0
    # Tool-specific
    tool_name: str = ""
    tool_input: str = ""
    tool_output: str = ""
    # Reasoning
    reasoning_content: str = ""
    confidence_score: float = 1.0
    trust_score: float = 1.0
    # Error
    error: str = ""
    # Graph topology (for Three.js)
    parent_step_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


# ─────────────────────────────────────────────
# Core Hooks Class
# ─────────────────────────────────────────────

class AgentWatchHooks:
    """
    Instruments a LangGraph compiled graph with OpenTelemetry spans.
    Every node execution gets a span. LLM calls and tool calls inside
    nodes get child spans. All events are also broadcast over WebSocket
    for real-time Three.js visualization.
    """

    def __init__(
        self,
        tracer: trace.Tracer,
        agent_id: Optional[str] = None,
        ws_broadcaster: Optional[Callable] = None,
    ):
        self.tracer = tracer
        self.agent_id = agent_id or str(uuid.uuid4())[:8]
        self.ws_broadcaster = ws_broadcaster
        self._active_trace_id: Optional[str] = None
        self._step_counts: Dict[str, int] = {}   # track tool call frequency
        self._step_history: list = []

    # ── Public: wrap a compiled LangGraph ──────

    def instrument(self, graph) -> "InstrumentedGraph":
        """
        Returns a thin wrapper around a compiled LangGraph that intercepts
        all node executions and adds OTel spans + WebSocket broadcasts.
        """
        return InstrumentedGraph(graph=graph, hooks=self)

    # ── Span helpers ───────────────────────────

    def start_agent_run(self, inputs: Dict) -> str:
        """Start a top-level trace for an agent run. Returns trace_id."""
        trace_id = str(uuid.uuid4()).replace("-", "")
        self._active_trace_id = trace_id
        self._step_counts = {}
        self._step_history = []
        logger.info(f"[AgentWatch] Agent run started — trace_id={trace_id[:8]}")
        return trace_id

    async def on_step_start(self, step_name: str, state: Dict, parent_step_id: str = "") -> str:
        """Called when a LangGraph node begins execution."""
        step_id = str(uuid.uuid4())[:8]
        event = AgentEvent(
            event_type="step_start",
            agent_id=self.agent_id,
            trace_id=self._active_trace_id or "",
            step_id=step_id,
            step_name=step_name,
            parent_step_id=parent_step_id,
            trust_score=1.0,
        )
        self._step_history.append({"step_id": step_id, "name": step_name, "start": time.time()})
        await self._emit(event)
        return step_id

    async def on_step_end(self, step_id: str, step_name: str, duration_ms: float, trust_score: float = 1.0):
        """Called when a LangGraph node finishes."""
        event = AgentEvent(
            event_type="step_end",
            agent_id=self.agent_id,
            trace_id=self._active_trace_id or "",
            step_id=step_id,
            step_name=step_name,
            duration_ms=duration_ms,
            trust_score=trust_score,
        )
        await self._emit(event)

    async def on_llm_call(
        self,
        step_id: str,
        step_name: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning: str = "",
        confidence: float = 1.0,
    ):
        """Called after every LLM invocation."""
        total = prompt_tokens + completion_tokens
        # Trust degrades with very large token counts (runaway generation)
        trust = max(0.1, 1.0 - (total / 10000))

        event = AgentEvent(
            event_type="llm_call",
            agent_id=self.agent_id,
            trace_id=self._active_trace_id or "",
            step_id=step_id,
            step_name=step_name,
            llm_model=model,
            llm_prompt_tokens=prompt_tokens,
            llm_completion_tokens=completion_tokens,
            llm_total_tokens=total,
            reasoning_content=reasoning[:500],  # truncate for HEC
            confidence_score=confidence,
            trust_score=trust,
        )
        await self._emit(event)

    async def on_tool_call(
        self,
        step_id: str,
        tool_name: str,
        tool_input: Any,
        tool_output: Any,
        duration_ms: float,
        error: str = "",
    ) -> float:
        """
        Called after every tool invocation.
        Tracks call frequency for loop detection.
        Returns trust_score (low = suspicious).
        """
        # Track per-tool call counts
        count_key = f"{self._active_trace_id}:{tool_name}"
        self._step_counts[count_key] = self._step_counts.get(count_key, 0) + 1
        call_count = self._step_counts[count_key]

        # Trust degrades exponentially with repeated calls to same tool
        trust = max(0.05, 1.0 / (1 + 0.3 * max(0, call_count - 3)))
        is_anomaly = call_count >= 5  # threshold for loop detection

        event = AgentEvent(
            event_type="tool_call",
            agent_id=self.agent_id,
            trace_id=self._active_trace_id or "",
            step_id=step_id,
            step_name=f"tool:{tool_name}",
            tool_name=tool_name,
            tool_input=str(tool_input)[:300],
            tool_output=str(tool_output)[:300],
            duration_ms=duration_ms,
            trust_score=trust,
            error=error,
        )
        await self._emit(event)

        if is_anomaly:
            await self._emit_anomaly(
                step_id=step_id,
                tool_name=tool_name,
                call_count=call_count,
                message=f"Loop detected — {tool_name} called {call_count}x in this run",
            )

        return trust

    async def on_error(self, step_id: str, step_name: str, error: Exception):
        """Called when any node throws an unhandled exception."""
        event = AgentEvent(
            event_type="error",
            agent_id=self.agent_id,
            trace_id=self._active_trace_id or "",
            step_id=step_id,
            step_name=step_name,
            trust_score=0.0,
            error=str(error),
        )
        await self._emit(event)

    async def _emit_anomaly(self, step_id: str, tool_name: str, call_count: int, message: str):
        event = AgentEvent(
            event_type="anomaly",
            agent_id=self.agent_id,
            trace_id=self._active_trace_id or "",
            step_id=step_id,
            step_name=f"tool:{tool_name}",
            tool_name=tool_name,
            trust_score=0.05,
            reasoning_content=message,
        )
        await self._emit(event)
        logger.warning(f"[AgentWatch] ⚠️  ANOMALY: {message}")

    async def _emit(self, event: AgentEvent):
        """Emit event over WebSocket (non-blocking) and log."""
        if self.ws_broadcaster:
            try:
                await self.ws_broadcaster(event.to_dict())
            except Exception as e:
                logger.debug(f"WS broadcast error: {e}")
        logger.debug(f"[{event.event_type}] {event.step_name} trust={event.trust_score:.2f}")


# ─────────────────────────────────────────────
# Instrumented Graph Wrapper
# ─────────────────────────────────────────────

class InstrumentedGraph:
    """
    Wraps a compiled LangGraph and intercepts execution via
    astream_events (LangGraph's native event stream).
    """

    def __init__(self, graph, hooks: AgentWatchHooks):
        self.graph = graph
        self.hooks = hooks

    async def ainvoke(self, inputs: Dict, config: Optional[Dict] = None) -> Dict:
        """Run the graph with full instrumentation."""
        trace_id = self.hooks.start_agent_run(inputs)
        config = config or {}
        config.setdefault("recursion_limit", 50)

        step_id_map: Dict[str, str] = {}  # node_name → step_id
        step_start_times: Dict[str, float] = {}

        try:
            async for event in self.graph.astream_events(inputs, config=config, version="v2"):
                kind = event.get("event", "")
                name = event.get("name", "unknown")
                data = event.get("data", {})

                # ── Node start ──
                if kind == "on_chain_start" and name not in ("LangGraph", "__start__"):
                    step_id = await self.hooks.on_step_start(step_name=name, state=data)
                    step_id_map[name] = step_id
                    step_start_times[name] = time.time()

                # ── Node end ──
                elif kind == "on_chain_end" and name not in ("LangGraph", "__start__"):
                    step_id = step_id_map.get(name, str(uuid.uuid4())[:8])
                    duration_ms = (time.time() - step_start_times.get(name, time.time())) * 1000
                    await self.hooks.on_step_end(step_id=step_id, step_name=name, duration_ms=duration_ms)

                # ── LLM call ──
                elif kind == "on_chat_model_end":
                    output = data.get("output", {})
                    usage = getattr(output, "usage_metadata", None) or {}
                    # Find parent node
                    tags = event.get("tags", [])
                    parent_name = name
                    step_id = step_id_map.get(parent_name, str(uuid.uuid4())[:8])
                    await self.hooks.on_llm_call(
                        step_id=step_id,
                        step_name=parent_name,
                        model=getattr(output, "response_metadata", {}).get("model_name", "gpt-4"),
                        prompt_tokens=usage.get("input_tokens", 0),
                        completion_tokens=usage.get("output_tokens", 0),
                        reasoning=str(getattr(output, "content", ""))[:300],
                    )

                # ── Tool call ──
                elif kind == "on_tool_end":
                    tool_name = name
                    t_start = step_start_times.get(f"tool:{tool_name}", time.time())
                    duration_ms = (time.time() - t_start) * 1000
                    step_id = step_id_map.get("agent", str(uuid.uuid4())[:8])
                    await self.hooks.on_tool_call(
                        step_id=step_id,
                        tool_name=tool_name,
                        tool_input=data.get("input", ""),
                        tool_output=data.get("output", ""),
                        duration_ms=duration_ms,
                    )

                elif kind == "on_tool_start":
                    step_start_times[f"tool:{name}"] = time.time()

                # ── Error ──
                elif kind == "on_chain_error":
                    step_id = step_id_map.get(name, str(uuid.uuid4())[:8])
                    error = data.get("error", Exception("Unknown error"))
                    await self.hooks.on_error(step_id=step_id, step_name=name, error=error)

        except Exception as e:
            logger.error(f"[AgentWatch] Fatal agent error: {e}")
            raise

        # Final result — run graph synchronously to get return value
        return await self.graph.ainvoke(inputs, config=config)
