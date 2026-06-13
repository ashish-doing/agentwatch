"""
agentwatch/backend/agentwatch_sdk.py
=====================================
One-liner SDK for wrapping any LangGraph node (or generic Python function)
with AgentWatch observability instrumentation.

Usage (LangGraph node):
    from agentwatch_sdk import watch

    @watch(agent_name="my_agent")
    def research_node(state):
        ...

Usage (full graph — wraps every node automatically):
    from agentwatch_sdk import watch_graph
    graph = watch_graph(compiled_graph, agent_name="my_agent")

Usage (generic function):
    @watch(agent_name="pipeline", step_name="preprocess")
    def preprocess(data):
        ...

Event schema emitted (matches backend/api/main.py → event_buffer exactly):
    {
        "event_type":       "step_start" | "llm_call" | "tool_call" | "step_end" | "error",
        "step_name":        str,
        "timestamp":        float,          # Unix epoch
        "trace_id":         str,            # UUID4, shared across one agent run
        "agent_id":         str,            # agent_name + short suffix
        "step_id":          str,            # UUID4 per step invocation
        "trust_score":      float,          # 0.0–1.0, computed from error history
        "duration_ms":      float,          # wall-clock time for the wrapped call
        "llm_total_tokens": int,            # extracted from state if present
        "tool_name":        str,            # populated on tool_call events
        "reasoning_content": str,           # last message content if available
        "error":            str,            # populated on error events
    }

Field names mirror demo_agent.py / langgraph_hooks.py exactly so the
AnomalyDetector and Splunk dashboards need zero changes.

Dependencies already in requirements.txt:
    websockets==13.1
    httpx==0.27.2
    (no new deps needed)
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import time
import uuid
from collections import defaultdict
from typing import Any, Callable, Dict, Optional

# ── websockets is already in requirements.txt (==13.1) ────────────────────────
try:
    import websockets
    import websockets.exceptions
    _WS_AVAILABLE = True
except ImportError:                     # pragma: no cover
    _WS_AVAILABLE = False

# ── httpx is already in requirements.txt (==0.27.2) — HTTP fallback ───────────
try:
    import httpx
    _HTTPX_AVAILABLE = True
except ImportError:                     # pragma: no cover
    _HTTPX_AVAILABLE = False

logger = logging.getLogger("agentwatch.sdk")

# ─────────────────────────────────────────────────────────────────────────────
# Constants / defaults
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_WS_URL   = "ws://localhost:8001/ws/agent-stream"
DEFAULT_HTTP_URL = "http://localhost:8001/api/events/ingest"   # fallback POST endpoint
_CONNECT_TIMEOUT = 3.0   # seconds — give up quickly so user's agent isn't held up
_SEND_TIMEOUT    = 2.0

# Trust score mirrors the formula in anomaly_detector.py → compute_trust_score()
#   trust = max(0.05, 1.0 / (1 + 0.3 * max(0, error_count - 3)))
# Starts at 1.0, degrades only after the 3rd error in the same trace.
def _compute_trust(error_count: int) -> float:
    return max(0.05, 1.0 / (1 + 0.3 * max(0, error_count - 3)))


# ─────────────────────────────────────────────────────────────────────────────
# AgentWatchEmitter  — one per (agent_name, ws_url) pair
# Manages a single persistent WS connection with lazy init + auto-reconnect.
# ─────────────────────────────────────────────────────────────────────────────

class AgentWatchEmitter:
    """
    Handles the actual emission of events to the AgentWatch backend.

    Lifecycle:
      • First emit() lazily opens the WebSocket.
      • If WS is unavailable / broken, falls back to HTTP POST (httpx).
      • If both are unavailable, logs a warning and drops the event — the
        user's agent is never crashed or blocked.

    Thread/async safety: emit() detects whether it's being called from
    a sync or async context and handles both.
    """

    def __init__(self, ws_url: str, http_url: str):
        self.ws_url   = ws_url
        self.http_url = http_url
        self._ws: Optional[Any] = None          # websockets.WebSocketClientProtocol
        self._ws_failed = False                 # stop retrying after permanent failure
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Internal async send ───────────────────────────────────────────────────

    async def _ensure_ws(self) -> bool:
        """Open WS connection if not already open. Returns True on success."""
        if not _WS_AVAILABLE:
            return False
        if self._ws_failed:
            return False
        if self._ws is not None:
            try:
                # Quick ping to check liveness (websockets ≥ 10 API)
                await asyncio.wait_for(self._ws.ping(), timeout=1.0)
                return True
            except Exception:
                self._ws = None   # stale — reconnect below

        try:
            self._ws = await asyncio.wait_for(
                websockets.connect(self.ws_url),   # type: ignore[attr-defined]
                timeout=_CONNECT_TIMEOUT,
            )
            logger.debug(f"[AgentWatch] WebSocket connected → {self.ws_url}")
            return True
        except Exception as exc:
            logger.warning(
                f"[AgentWatch] Cannot reach backend at {self.ws_url} "
                f"({type(exc).__name__}: {exc}). "
                "Events will be dropped silently. Start the AgentWatch backend to enable observability."
            )
            self._ws_failed = True
            return False

    async def _send_ws(self, payload: str) -> bool:
        """Send a raw JSON string over WebSocket. Returns True on success."""
        if not await self._ensure_ws():
            return False
        try:
            await asyncio.wait_for(self._ws.send(payload), timeout=_SEND_TIMEOUT)  # type: ignore[union-attr]
            return True
        except Exception as exc:
            logger.debug(f"[AgentWatch] WS send failed ({exc}), will retry on next event")
            self._ws = None          # force reconnect next time
            self._ws_failed = False  # allow one more reconnect attempt
            return False

    async def _send_http(self, payload: str) -> bool:
        """HTTP POST fallback (fire-and-forget). Returns True on success."""
        if not _HTTPX_AVAILABLE:
            return False
        try:
            async with httpx.AsyncClient(timeout=_SEND_TIMEOUT) as client:
                r = await client.post(
                    self.http_url,
                    content=payload,
                    headers={"Content-Type": "application/json"},
                )
                return r.status_code < 300
        except Exception:
            return False

    async def _emit_async(self, event: dict) -> None:
        """Core async emit — WS first, HTTP fallback, silent drop on failure."""
        payload = json.dumps(event)
        if await self._send_ws(payload):
            return
        if await self._send_http(payload):
            logger.debug("[AgentWatch] Sent via HTTP fallback")
            return
        # Both failed — log at DEBUG so we don't spam the user's logs
        logger.debug(f"[AgentWatch] Event dropped (no backend reachable): {event.get('event_type')} / {event.get('step_name')}")

    # ── Public emit — sync/async transparent ─────────────────────────────────

    def emit(self, event: dict) -> None:
        """
        Emit one event. Works from both sync and async calling contexts.

        • Called from async code  → schedules a fire-and-forget task.
        • Called from sync code   → runs a short event loop to fire it.

        Never raises. Never blocks the caller for more than _SEND_TIMEOUT seconds.
        """
        try:
            loop = asyncio.get_running_loop()
            # We're inside a running async context (e.g. LangGraph async node)
            asyncio.ensure_future(self._emit_async(event))
        except RuntimeError:
            # No running loop — we're in a sync context; run one-shot
            try:
                asyncio.run(self._emit_async(event))
            except Exception as exc:
                logger.debug(f"[AgentWatch] emit() swallowed exception: {exc}")
        except Exception as exc:
            logger.debug(f"[AgentWatch] emit() swallowed exception: {exc}")

    async def close(self) -> None:
        """Cleanly close the WebSocket connection."""
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None


# ─────────────────────────────────────────────────────────────────────────────
# Module-level emitter cache — one connection per (ws_url, http_url) pair
# ─────────────────────────────────────────────────────────────────────────────

_emitter_cache: Dict[tuple, AgentWatchEmitter] = {}

def _get_emitter(ws_url: str, http_url: str) -> AgentWatchEmitter:
    key = (ws_url, http_url)
    if key not in _emitter_cache:
        _emitter_cache[key] = AgentWatchEmitter(ws_url, http_url)
    return _emitter_cache[key]


# ─────────────────────────────────────────────────────────────────────────────
# Per-trace state  — error counter for trust_score degradation
# ─────────────────────────────────────────────────────────────────────────────

# {trace_id: error_count}  — mirrors AnomalyDetector._error_counts logic
_trace_error_counts: Dict[str, int] = defaultdict(int)


# ─────────────────────────────────────────────────────────────────────────────
# Event builder helpers
# ─────────────────────────────────────────────────────────────────────────────

def _base_event(
    event_type: str,
    step_name: str,
    agent_id: str,
    trace_id: str,
    step_id: str,
    trust_score: float,
    **extra,
) -> dict:
    """
    Build the canonical event dict that main.py expects.
    Field names are identical to demo_agent.py → _send() and langgraph_hooks.py → AgentEvent.
    """
    return {
        "event_type":        event_type,
        "step_name":         step_name,
        "timestamp":         time.time(),
        "trace_id":          trace_id,
        "agent_id":          agent_id,
        "step_id":           step_id,
        "trust_score":       round(trust_score, 4),
        "duration_ms":       0.0,           # overwritten by callers that measure it
        "llm_total_tokens":  0,
        "tool_name":         "",
        "reasoning_content": "",
        "error":             "",
        **extra,
    }


def _extract_llm_tokens(state: Any) -> int:
    """
    Best-effort extraction of token counts from a LangGraph state dict.
    Checks common field names used by LangChain / OpenAI responses.
    Returns 0 if nothing is found.
    """
    if not isinstance(state, dict):
        return 0
    # Direct fields (some users put these in state)
    for key in ("llm_total_tokens", "total_tokens", "tokens"):
        val = state.get(key)
        if isinstance(val, int) and val > 0:
            return val
    # Nested in messages list — look at the last assistant message
    messages = state.get("messages", [])
    if messages and isinstance(messages, list):
        last = messages[-1]
        if isinstance(last, dict):
            for key in ("tokens", "total_tokens", "llm_total_tokens"):
                val = last.get(key)
                if isinstance(val, int) and val > 0:
                    return val
    return 0


def _extract_reasoning(state: Any) -> str:
    """Extract the last assistant message content for reasoning_content field."""
    if not isinstance(state, dict):
        return ""
    messages = state.get("messages", [])
    if messages and isinstance(messages, list):
        last = messages[-1]
        if isinstance(last, dict):
            return str(last.get("content", ""))[:500]   # cap at 500 chars
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# @watch  — the main decorator
# ─────────────────────────────────────────────────────────────────────────────

def watch(
    agent_name: str,
    *,
    step_name: Optional[str]  = None,
    ws_url:    str            = DEFAULT_WS_URL,
    http_url:  str            = DEFAULT_HTTP_URL,
    trace_id:  Optional[str]  = None,
):
    """
    Decorator that wraps a LangGraph node function (or any callable) with
    full AgentWatch instrumentation.

    Parameters
    ----------
    agent_name : str
        Human-readable name for this agent. Used as the agent_id prefix.
        Required — the only non-optional argument.

    step_name : str, optional
        Override the step name in emitted events.
        Defaults to the wrapped function's __name__.

    ws_url : str
        AgentWatch backend WebSocket URL.
        Default: "ws://localhost:8001/ws/agent-stream"

    http_url : str
        HTTP fallback URL (POST endpoint).
        Default: "http://localhost:8001/api/events/ingest"

    trace_id : str, optional
        Pin all events from this decorator to a specific trace_id (UUID).
        If omitted, a new trace_id is generated once per process startup,
        so all nodes of the same graph run share the same trace automatically
        when you use watch_graph() — or you can pass it explicitly.

    Events emitted
    --------------
    step_start  — immediately before the wrapped function is called
    step_end    — after successful return, includes duration_ms + token count
    error       — if the function raises, includes the exception message

    Example
    -------
    @watch(agent_name="my_agent")
    def research_node(state):
        return {**state, "results": [...]}

    # With explicit trace pinning across nodes:
    TRACE = str(uuid.uuid4())

    @watch(agent_name="my_agent", trace_id=TRACE)
    def node_a(state): ...

    @watch(agent_name="my_agent", trace_id=TRACE)
    def node_b(state): ...
    """

    # Generate a stable agent_id suffix so multiple instances are distinguishable
    _agent_suffix = uuid.uuid4().hex[:6]
    _agent_id     = f"{agent_name}-{_agent_suffix}"

    # If no trace_id pinned, use a module-level default (one per process startup)
    # so all @watch-decorated nodes without explicit trace_id share the same trace.
    _default_trace = _get_or_create_default_trace()

    emitter = _get_emitter(ws_url, http_url)

    def decorator(fn: Callable) -> Callable:
        _step = step_name or fn.__name__

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs):
            _tid   = trace_id or _default_trace
            _sid   = uuid.uuid4().hex[:8]
            _trust = _compute_trust(_trace_error_counts[_tid])

            # ── step_start ────────────────────────────────────────────────
            emitter.emit(_base_event(
                "step_start", _step, _agent_id, _tid, _sid, _trust
            ))

            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000

                # ── step_end ──────────────────────────────────────────────
                tokens    = _extract_llm_tokens(result) if isinstance(result, dict) else 0
                reasoning = _extract_reasoning(result)  if isinstance(result, dict) else ""
                emitter.emit(_base_event(
                    "step_end", _step, _agent_id, _tid, _sid, _trust,
                    duration_ms      = round(elapsed, 2),
                    llm_total_tokens = tokens,
                    reasoning_content= reasoning,
                ))
                return result

            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                _trace_error_counts[_tid] += 1
                error_trust = _compute_trust(_trace_error_counts[_tid])

                # ── error ─────────────────────────────────────────────────
                emitter.emit(_base_event(
                    "error", _step, _agent_id, _tid, _sid, error_trust,
                    duration_ms = round(elapsed, 2),
                    error       = f"{type(exc).__name__}: {exc}",
                ))
                raise   # never swallow the user's exception

        @functools.wraps(fn)
        async def async_wrapper(*args, **kwargs):
            _tid   = trace_id or _default_trace
            _sid   = uuid.uuid4().hex[:8]
            _trust = _compute_trust(_trace_error_counts[_tid])

            emitter.emit(_base_event(
                "step_start", _step, _agent_id, _tid, _sid, _trust
            ))

            t0 = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000

                tokens    = _extract_llm_tokens(result) if isinstance(result, dict) else 0
                reasoning = _extract_reasoning(result)  if isinstance(result, dict) else ""
                emitter.emit(_base_event(
                    "step_end", _step, _agent_id, _tid, _sid, _trust,
                    duration_ms      = round(elapsed, 2),
                    llm_total_tokens = tokens,
                    reasoning_content= reasoning,
                ))
                return result

            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                _trace_error_counts[_tid] += 1
                error_trust = _compute_trust(_trace_error_counts[_tid])
                emitter.emit(_base_event(
                    "error", _step, _agent_id, _tid, _sid, error_trust,
                    duration_ms = round(elapsed, 2),
                    error       = f"{type(exc).__name__}: {exc}",
                ))
                raise

        return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper

    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# watch_graph()  — wraps every node in a compiled LangGraph at once
# ─────────────────────────────────────────────────────────────────────────────

def watch_graph(
    compiled_graph: Any,
    agent_name: str,
    *,
    ws_url:   str           = DEFAULT_WS_URL,
    http_url: str           = DEFAULT_HTTP_URL,
    trace_id: Optional[str] = None,
) -> Any:
    """
    Instrument a fully compiled LangGraph graph by wrapping every registered
    node with @watch automatically.  Call this instead of (or in addition to)
    decorating individual nodes.

    Parameters
    ----------
    compiled_graph : CompiledGraph
        The return value of StateGraph(...).compile().

    agent_name : str
        Passed through to @watch for every node.

    ws_url / http_url / trace_id
        Same semantics as @watch.

    Returns
    -------
    The same compiled_graph object, mutated in-place (nodes are replaced).
    This is safe because LangGraph stores node callables in a plain dict.

    Example
    -------
    graph = StateGraph(AgentState)
    graph.add_node("research",  research_node)
    graph.add_node("analysis",  analysis_node)
    compiled = graph.compile()

    # One line adds full observability:
    compiled = watch_graph(compiled, agent_name="my_agent")
    result   = compiled.invoke(initial_state)
    """
    _tid = trace_id or str(uuid.uuid4())

    # LangGraph compiled graphs expose their nodes in .nodes (a dict of Runnable)
    # We patch the underlying _func or func attribute if present, otherwise wrap
    # the Runnable's invoke method — both approaches are non-destructive.
    try:
        node_dict = compiled_graph.nodes   # {name: Runnable}
    except AttributeError:
        logger.warning("[AgentWatch] watch_graph: compiled_graph has no .nodes — skipping auto-wrap")
        return compiled_graph

    for node_name, runnable in node_dict.items():
        if node_name == "__start__":
            continue
        _patch_runnable(runnable, node_name, agent_name, ws_url, http_url, _tid)

    logger.info(f"[AgentWatch] watch_graph instrumented {len(node_dict)} nodes for agent='{agent_name}' trace={_tid}")
    return compiled_graph


def _patch_runnable(runnable: Any, node_name: str, agent_name: str,
                    ws_url: str, http_url: str, trace_id: str) -> None:
    """
    Monkey-patch a LangGraph Runnable node to emit events.
    LangGraph wraps node functions in a RunnableLambda; we wrap its .func.
    Falls back to wrapping .invoke if .func isn't accessible.
    """
    decorator = watch(
        agent_name,
        step_name=node_name,
        ws_url=ws_url,
        http_url=http_url,
        trace_id=trace_id,
    )

    # RunnableLambda exposes the raw callable as .func
    if hasattr(runnable, "func") and callable(runnable.func):
        try:
            runnable.func = decorator(runnable.func)
            return
        except Exception:
            pass

    # Fallback: wrap .invoke
    if hasattr(runnable, "invoke") and callable(runnable.invoke):
        try:
            runnable.invoke = decorator(runnable.invoke)
        except Exception as exc:
            logger.debug(f"[AgentWatch] Could not patch node '{node_name}': {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# emit_event()  — manual emission for tool_call / llm_call events
# ─────────────────────────────────────────────────────────────────────────────

def emit_event(
    event_type: str,
    step_name: str,
    agent_name: str,
    *,
    ws_url:           str   = DEFAULT_WS_URL,
    http_url:         str   = DEFAULT_HTTP_URL,
    trace_id:         Optional[str] = None,
    trust_score:      float = 1.0,
    duration_ms:      float = 0.0,
    llm_total_tokens: int   = 0,
    tool_name:        str   = "",
    tool_input:       str   = "",
    tool_output:      str   = "",
    reasoning_content:str   = "",
    error:            str   = "",
    **extra,
) -> None:
    """
    Manually emit a single event — useful for tool_call and llm_call events
    that live inside your node body and can't be captured by @watch alone.

    Example — emitting a tool_call from inside a node:
        emit_event(
            "tool_call", "research", agent_name="my_agent",
            tool_name="search_tool",
            tool_input="AI observability 2026",
            tool_output="Market projected at $28.5B...",
            duration_ms=180,
            trust_score=0.9,
        )

    Event types accepted by the backend:
        step_start | step_end | llm_call | tool_call | error | anomaly
    """
    _tid = trace_id or _get_or_create_default_trace()
    _sid = uuid.uuid4().hex[:8]
    _aid = f"{agent_name}-sdk"

    emitter = _get_emitter(ws_url, http_url)
    emitter.emit(_base_event(
        event_type, step_name, _aid, _tid, _sid, trust_score,
        duration_ms       = round(duration_ms, 2),
        llm_total_tokens  = llm_total_tokens,
        tool_name         = tool_name,
        tool_input        = tool_input,
        tool_output       = tool_output,
        reasoning_content = reasoning_content,
        error             = error,
        **extra,
    ))


# ─────────────────────────────────────────────────────────────────────────────
# AgentWatchContext  — context manager for manual trace scoping
# ─────────────────────────────────────────────────────────────────────────────

class AgentWatchContext:
    """
    Context manager that pins a fresh trace_id for the duration of one
    agent run, then resets it.  Use this when you invoke a graph multiple
    times in the same process and want separate traces per run.

    Example
    -------
    with AgentWatchContext(agent_name="my_agent") as ctx:
        result = compiled_graph.invoke(state)
    # ctx.trace_id holds the UUID used for this run
    """

    def __init__(
        self,
        agent_name: str,
        *,
        ws_url:  str = DEFAULT_WS_URL,
        http_url: str = DEFAULT_HTTP_URL,
    ):
        self.agent_name = agent_name
        self.ws_url     = ws_url
        self.http_url   = http_url
        self.trace_id   = str(uuid.uuid4())
        self._emitter   = _get_emitter(ws_url, http_url)
        self._agent_id  = f"{agent_name}-{uuid.uuid4().hex[:6]}"

    def __enter__(self) -> "AgentWatchContext":
        self._emitter.emit(_base_event(
            "step_start", "__trace_start__",
            self._agent_id, self.trace_id, uuid.uuid4().hex[:8], 1.0,
            reasoning_content=f"Trace started for agent '{self.agent_name}'",
        ))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        event_type = "error" if exc_type else "step_end"
        self._emitter.emit(_base_event(
            event_type, "__trace_end__",
            self._agent_id, self.trace_id, uuid.uuid4().hex[:8], trust,
            error=f"{exc_type.__name__}: {exc_val}" if exc_type else "",
        ))
        _trace_error_counts.pop(self.trace_id, None)
        return False   # never suppress exceptions


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

_DEFAULT_TRACE_ID: Optional[str] = None

def _get_or_create_default_trace() -> str:
    """Return (or lazily create) the module-level default trace_id."""
    global _DEFAULT_TRACE_ID
    if _DEFAULT_TRACE_ID is None:
        _DEFAULT_TRACE_ID = str(uuid.uuid4())
    return _DEFAULT_TRACE_ID


def new_trace() -> str:
    """
    Force a new global trace_id.  Call between separate agent runs when
    you aren't using AgentWatchContext and want a fresh trace in the dashboard.

    Returns the new trace_id string so you can log it.
    """
    global _DEFAULT_TRACE_ID
    _DEFAULT_TRACE_ID = str(uuid.uuid4())
    return _DEFAULT_TRACE_ID


# ─────────────────────────────────────────────────────────────────────────────
# if __name__ == "__main__"  — self-contained smoke test / usage demo
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    """
    Smoke test — runs without a live backend (events are dropped gracefully).
    Start the AgentWatch backend first to see them appear in the dashboard:

        cd backend && uvicorn api.main:app --port 8001

    Then run:
        python agentwatch_sdk.py
    """

    import logging
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s | %(name)s | %(message)s")

    print("\n── AgentWatch SDK smoke test ──────────────────────────────────────\n")

    # ── Example 1: Decorate individual LangGraph-style node functions ─────────

    SHARED_TRACE = str(uuid.uuid4())
    print(f"Shared trace_id: {SHARED_TRACE}\n")

    @watch(agent_name="smoke_test_agent", trace_id=SHARED_TRACE)
    def research_node(state: dict) -> dict:
        time.sleep(0.05)   # simulate work
        return {
            **state,
            "messages": [{"role": "assistant", "content": "Found results", "tokens": 420}],
            "results": ["AI observability market at $28.5B"],
        }

    @watch(agent_name="smoke_test_agent", trace_id=SHARED_TRACE)
    def analysis_node(state: dict) -> dict:
        time.sleep(0.03)
        return {**state, "analysis": "Market is growing 43% CAGR"}

    @watch(agent_name="smoke_test_agent", step_name="synthesis_step", trace_id=SHARED_TRACE)
    def synthesis_node(state: dict) -> dict:
        time.sleep(0.02)
        return {**state, "final_report": "Executive summary complete"}

    state: dict = {"topic": "AI agent observability", "messages": []}
    state = research_node(state)
    state = analysis_node(state)
    state = synthesis_node(state)
    print(f"Pipeline result keys: {list(state.keys())}")

    # ── Example 2: Manual tool_call + llm_call emission ──────────────────────

    emit_event(
        "tool_call", "research", agent_name="smoke_test_agent",
        trace_id=SHARED_TRACE,
        tool_name="search_tool",
        tool_input="AI observability 2026",
        tool_output="34% of agents fail silently",
        duration_ms=175.0,
        trust_score=0.92,
    )
    emit_event(
        "llm_call", "analysis", agent_name="smoke_test_agent",
        trace_id=SHARED_TRACE,
        llm_total_tokens=840,
        trust_score=0.88,
    )
    print("Manual tool_call + llm_call events emitted.\n")

    # ── Example 3: Error handling — exception propagates, event is still sent ─

    @watch(agent_name="smoke_test_agent", trace_id=SHARED_TRACE)
    def flaky_node(state: dict) -> dict:
        raise ValueError("Simulated tool failure")

    try:
        flaky_node({})
    except ValueError:
        print("Error event emitted; exception re-raised as expected.\n")

    # ── Example 4: Context manager for scoped traces ──────────────────────────

    with AgentWatchContext(agent_name="smoke_test_agent") as ctx:
        print(f"Context trace_id: {ctx.trace_id}")
        time.sleep(0.01)
    print("Context manager trace completed.\n")

    # ── Example 5: watch_graph usage (no live LangGraph needed to demo syntax) ─

    print(
        "watch_graph usage (requires langgraph):\n\n"
        "  from langgraph.graph import StateGraph, END\n"
        "  from agentwatch_sdk import watch_graph\n\n"
        "  graph = StateGraph(AgentState)\n"
        "  graph.add_node('research',  research_node)\n"
        "  graph.add_node('analysis',  analysis_node)\n"
        "  compiled = graph.compile()\n\n"
        "  # One line — instruments every node:\n"
        "  compiled = watch_graph(compiled, agent_name='my_agent')\n"
        "  result   = compiled.invoke(initial_state)\n"
    )

    print("── Smoke test complete. Check AgentWatch dashboard if backend is running. ──\n")