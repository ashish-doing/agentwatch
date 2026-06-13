"""
agentwatch/backend/agentwatch_hooks.py
=======================================
Framework-agnostic AgentWatch hooks.

Supported frameworks:
  • CrewAI        — AgentWatchCrewAI (callback handler)
  • OpenAI Agents SDK — AgentWatchOpenAI (hook class)
  • AutoGen       — AgentWatchAutoGen (message hook)
  • Generic       — @watch_tool / @watch_llm / AgentWatchContext (already in agentwatch_sdk.py)

All hooks emit the EXACT same event schema as agentwatch_sdk.py so
the AnomalyDetector, Splunk dashboard, and brain visualization work
with zero changes.

Usage — CrewAI:
    from agentwatch_hooks import AgentWatchCrewAI
    from crewai import Agent, Task, Crew

    aw = AgentWatchCrewAI(agent_name="my_crew")
    agent = Agent(role="Researcher", ..., callbacks=[aw])
    crew = Crew(agents=[agent], tasks=[...])
    crew.kickoff()

Usage — OpenAI Agents SDK:
    from agentwatch_hooks import AgentWatchOpenAI
    from agents import Agent, Runner

    hooks = AgentWatchOpenAI(agent_name="my_agent")
    agent = Agent(name="Assistant", instructions="...", hooks=hooks)
    Runner.run_sync(agent, "What is AI observability?")

Usage — AutoGen:
    from agentwatch_hooks import AgentWatchAutoGen
    hook = AgentWatchAutoGen(agent_name="autogen_crew")
    # pass hook.on_message as message callback

Usage — Any framework (manual):
    from agentwatch_hooks import watch_tool, watch_llm
    
    @watch_tool(agent_name="my_agent", tool_name="search")
    def search_tool(query: str) -> str:
        ...

    @watch_llm(agent_name="my_agent")
    def call_llm(prompt: str) -> dict:
        ...
"""

from __future__ import annotations

import functools
import logging
import time
import uuid
from typing import Any, Callable, Dict, Optional

from .agentwatch_sdk import (
    AgentWatchEmitter,
    _base_event,
    _compute_trust,
    _get_emitter,
    _get_or_create_default_trace,
    _trace_error_counts,
    DEFAULT_WS_URL,
    DEFAULT_HTTP_URL,
)

logger = logging.getLogger("agentwatch.hooks")


# ─────────────────────────────────────────────────────────────────────────────
# Shared emit helper
# ─────────────────────────────────────────────────────────────────────────────

def _emit(
    emitter: AgentWatchEmitter,
    event_type: str,
    step_name: str,
    agent_id: str,
    trace_id: str,
    trust: float = 1.0,
    **extra,
):
    emitter.emit(_base_event(
        event_type, step_name, agent_id, trace_id,
        uuid.uuid4().hex[:8], trust, **extra
    ))


# ─────────────────────────────────────────────────────────────────────────────
# CrewAI — Callback Handler
# ─────────────────────────────────────────────────────────────────────────────

class AgentWatchCrewAI:
    """
    CrewAI callback handler. Pass as callbacks=[aw] to Agent or Crew.

    Hooks into CrewAI's callback protocol:
      on_agent_start / on_agent_finish
      on_tool_start  / on_tool_end / on_tool_error
      on_llm_start   / on_llm_end  / on_llm_error

    Compatible with crewai>=0.28.0
    """

    def __init__(
        self,
        agent_name: str,
        ws_url: str = DEFAULT_WS_URL,
        http_url: str = DEFAULT_HTTP_URL,
        trace_id: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.agent_id   = f"{agent_name}-crewai-{uuid.uuid4().hex[:6]}"
        self.trace_id   = trace_id or str(uuid.uuid4())
        self._emitter   = _get_emitter(ws_url, http_url)
        self._step_starts: Dict[str, float] = {}
        logger.info(f"[AgentWatch/CrewAI] Attached to '{agent_name}' trace={self.trace_id}")

    def on_agent_start(self, agent: Any = None, **kwargs):
        role = getattr(agent, "role", "agent") if agent else "agent"
        _emit(self._emitter, "step_start", f"agent:{role}",
              self.agent_id, self.trace_id, 1.0,
              reasoning_content=f"CrewAI agent '{role}' starting")
        self._step_starts[f"agent:{role}"] = time.perf_counter()

    def on_agent_finish(self, agent: Any = None, output: Any = None, **kwargs):
        role = getattr(agent, "role", "agent") if agent else "agent"
        key = f"agent:{role}"
        elapsed = (time.perf_counter() - self._step_starts.pop(key, time.perf_counter())) * 1000
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "step_end", key,
              self.agent_id, self.trace_id, trust,
              duration_ms=round(elapsed, 2),
              reasoning_content=str(output)[:500] if output else "")

    def on_tool_start(self, tool: Any = None, input_str: str = "", **kwargs):
        tool_name = getattr(tool, "name", str(tool)) if tool else "unknown_tool"
        self._step_starts[f"tool:{tool_name}"] = time.perf_counter()
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "tool_call", f"tool:{tool_name}",
              self.agent_id, self.trace_id, trust,
              tool_name=tool_name,
              tool_input=str(input_str)[:300])

    def on_tool_end(self, output: str = "", tool: Any = None, **kwargs):
        tool_name = getattr(tool, "name", str(tool)) if tool else "unknown_tool"
        key = f"tool:{tool_name}"
        elapsed = (time.perf_counter() - self._step_starts.pop(key, time.perf_counter())) * 1000
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "step_end", key,
              self.agent_id, self.trace_id, trust,
              duration_ms=round(elapsed, 2),
              tool_name=tool_name,
              tool_output=str(output)[:300])

    def on_tool_error(self, error: Exception = None, tool: Any = None, **kwargs):
        tool_name = getattr(tool, "name", str(tool)) if tool else "unknown_tool"
        _trace_error_counts[self.trace_id] += 1
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "error", f"tool:{tool_name}",
              self.agent_id, self.trace_id, trust,
              error=f"{type(error).__name__}: {error}" if error else "Tool error")

    def on_llm_start(self, serialized: Any = None, prompts: Any = None, **kwargs):
        self._step_starts["llm"] = time.perf_counter()

    def on_llm_end(self, response: Any = None, **kwargs):
        elapsed = (time.perf_counter() - self._step_starts.pop("llm", time.perf_counter())) * 1000
        # Extract token usage from LLMResult if available
        tokens = 0
        try:
            usage = response.llm_output.get("token_usage", {}) if response else {}
            tokens = usage.get("total_tokens", 0)
        except Exception:
            pass
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "llm_call", "llm",
              self.agent_id, self.trace_id, trust,
              duration_ms=round(elapsed, 2),
              llm_total_tokens=tokens)

    def on_llm_error(self, error: Exception = None, **kwargs):
        _trace_error_counts[self.trace_id] += 1
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "error", "llm",
              self.agent_id, self.trace_id, trust,
              error=f"{type(error).__name__}: {error}" if error else "LLM error")

    # CrewAI also calls these on Task events
    def on_task_start(self, task: Any = None, **kwargs):
        desc = getattr(task, "description", "task")[:60] if task else "task"
        _emit(self._emitter, "step_start", f"task:{desc}",
              self.agent_id, self.trace_id, 1.0)

    def on_task_end(self, task: Any = None, output: Any = None, **kwargs):
        desc = getattr(task, "description", "task")[:60] if task else "task"
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "step_end", f"task:{desc}",
              self.agent_id, self.trace_id, trust,
              reasoning_content=str(output)[:500] if output else "")


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI Agents SDK — Hook class
# ─────────────────────────────────────────────────────────────────────────────

class AgentWatchOpenAI:
    """
    Hook class for the OpenAI Agents SDK (openai-agents>=0.0.3).

    Pass as hooks=AgentWatchOpenAI(...) to Agent().

    Compatible with the AgentHooks protocol:
      on_start / on_end / on_tool_start / on_tool_end / on_handoff
    """

    def __init__(
        self,
        agent_name: str,
        ws_url: str = DEFAULT_WS_URL,
        http_url: str = DEFAULT_HTTP_URL,
        trace_id: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.agent_id   = f"{agent_name}-openai-{uuid.uuid4().hex[:6]}"
        self.trace_id   = trace_id or str(uuid.uuid4())
        self._emitter   = _get_emitter(ws_url, http_url)
        self._t0: Dict[str, float] = {}
        logger.info(f"[AgentWatch/OpenAI] Attached to '{agent_name}' trace={self.trace_id}")

    async def on_start(self, context: Any = None, agent: Any = None):
        name = getattr(agent, "name", self.agent_name) if agent else self.agent_name
        self._t0["agent"] = time.perf_counter()
        _emit(self._emitter, "step_start", f"agent:{name}",
              self.agent_id, self.trace_id, 1.0,
              reasoning_content=f"OpenAI agent '{name}' started")

    async def on_end(self, context: Any = None, agent: Any = None, output: Any = None):
        name = getattr(agent, "name", self.agent_name) if agent else self.agent_name
        elapsed = (time.perf_counter() - self._t0.pop("agent", time.perf_counter())) * 1000
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        content = ""
        try:
            content = str(output.final_output)[:500] if output else ""
        except Exception:
            pass
        _emit(self._emitter, "step_end", f"agent:{name}",
              self.agent_id, self.trace_id, trust,
              duration_ms=round(elapsed, 2),
              reasoning_content=content)

    async def on_tool_start(self, context: Any = None, agent: Any = None, tool: Any = None):
        tool_name = getattr(tool, "name", str(tool)) if tool else "tool"
        self._t0[f"tool:{tool_name}"] = time.perf_counter()
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "tool_call", f"tool:{tool_name}",
              self.agent_id, self.trace_id, trust,
              tool_name=tool_name)

    async def on_tool_end(self, context: Any = None, agent: Any = None,
                          tool: Any = None, result: str = ""):
        tool_name = getattr(tool, "name", str(tool)) if tool else "tool"
        key = f"tool:{tool_name}"
        elapsed = (time.perf_counter() - self._t0.pop(key, time.perf_counter())) * 1000
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "step_end", key,
              self.agent_id, self.trace_id, trust,
              duration_ms=round(elapsed, 2),
              tool_name=tool_name,
              tool_output=str(result)[:300])

    async def on_handoff(self, context: Any = None, agent: Any = None,
                         source: Any = None):
        """Fired when one agent hands off to another — great for multi-agent topology."""
        from_name = getattr(source, "name", "unknown") if source else "unknown"
        to_name   = getattr(agent,  "name", "unknown") if agent  else "unknown"
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "tool_call", f"handoff:{from_name}→{to_name}",
              self.agent_id, self.trace_id, trust,
              tool_name="agent_handoff",
              tool_input=from_name,
              tool_output=to_name,
              reasoning_content=f"Agent handoff: {from_name} → {to_name}")

    async def on_llm_start(self, context: Any = None, agent: Any = None):
        self._t0["llm"] = time.perf_counter()

    async def on_llm_end(self, context: Any = None, agent: Any = None,
                         response: Any = None):
        elapsed = (time.perf_counter() - self._t0.pop("llm", time.perf_counter())) * 1000
        tokens = 0
        try:
            tokens = response.usage.total_tokens if response and hasattr(response, "usage") else 0
        except Exception:
            pass
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "llm_call", "llm",
              self.agent_id, self.trace_id, trust,
              duration_ms=round(elapsed, 2),
              llm_total_tokens=tokens)


# ─────────────────────────────────────────────────────────────────────────────
# AutoGen — Message Hook
# ─────────────────────────────────────────────────────────────────────────────

class AgentWatchAutoGen:
    """
    AutoGen hook. Compatible with autogen>=0.2.0.

    Use as a reply function or message hook:
        aw = AgentWatchAutoGen(agent_name="autogen_crew")
        assistant.register_reply(
            trigger=autogen.ConversableAgent,
            reply_func=aw.on_message,
            position=0,
        )
    """

    def __init__(
        self,
        agent_name: str,
        ws_url: str = DEFAULT_WS_URL,
        http_url: str = DEFAULT_HTTP_URL,
        trace_id: Optional[str] = None,
    ):
        self.agent_name = agent_name
        self.agent_id   = f"{agent_name}-autogen-{uuid.uuid4().hex[:6]}"
        self.trace_id   = trace_id or str(uuid.uuid4())
        self._emitter   = _get_emitter(ws_url, http_url)
        logger.info(f"[AgentWatch/AutoGen] Attached to '{agent_name}' trace={self.trace_id}")

    def on_message(self, recipient: Any = None, messages: Any = None,
                   sender: Any = None, config: Any = None):
        """
        Register as a reply function. Emits an llm_call event for each
        message exchange and returns False so AutoGen continues normally.
        """
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        last_msg = ""
        tokens = 0
        if isinstance(messages, list) and messages:
            last = messages[-1]
            if isinstance(last, dict):
                last_msg = str(last.get("content", ""))[:500]
                tokens = last.get("token_count", 0)

        sender_name = getattr(sender, "name", "unknown") if sender else "unknown"
        _emit(self._emitter, "llm_call", f"message:{sender_name}",
              self.agent_id, self.trace_id, trust,
              llm_total_tokens=tokens,
              reasoning_content=last_msg)
        return False, None  # AutoGen: (reply_produced, reply_content)

    def on_tool_call(self, tool_name: str, tool_input: str = "",
                     tool_output: str = "", duration_ms: float = 0.0):
        """Call manually from inside AutoGen tool functions."""
        trust = _compute_trust(_trace_error_counts[self.trace_id])
        _emit(self._emitter, "tool_call", f"tool:{tool_name}",
              self.agent_id, self.trace_id, trust,
              tool_name=tool_name,
              tool_input=tool_input[:300],
              tool_output=tool_output[:300],
              duration_ms=duration_ms)


# ─────────────────────────────────────────────────────────────────────────────
# Generic decorators — @watch_tool / @watch_llm
# Works with ANY framework — just wrap your function
# ─────────────────────────────────────────────────────────────────────────────

def watch_tool(
    agent_name: str,
    tool_name: Optional[str] = None,
    ws_url: str = DEFAULT_WS_URL,
    http_url: str = DEFAULT_HTTP_URL,
    trace_id: Optional[str] = None,
):
    """
    Decorator for any tool function. Framework-agnostic.

    @watch_tool(agent_name="my_agent", tool_name="search")
    def search(query: str) -> str:
        return requests.get(...).text

    Emits tool_call + step_end (with duration) + error on exception.
    """
    def decorator(fn: Callable) -> Callable:
        _tid      = trace_id or _get_or_create_default_trace()
        _aid      = f"{agent_name}-{uuid.uuid4().hex[:6]}"
        _tname    = tool_name or fn.__name__
        _emitter  = _get_emitter(ws_url, http_url)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            trust = _compute_trust(_trace_error_counts[_tid])
            tool_input = str(args[0])[:300] if args else str(kwargs)[:300]
            _emit(_emitter, "tool_call", f"tool:{_tname}",
                  _aid, _tid, trust, tool_name=_tname, tool_input=tool_input)
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000
                trust2 = _compute_trust(_trace_error_counts[_tid])
                _emit(_emitter, "step_end", f"tool:{_tname}",
                      _aid, _tid, trust2,
                      duration_ms=round(elapsed, 2),
                      tool_name=_tname,
                      tool_output=str(result)[:300])
                return result
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                _trace_error_counts[_tid] += 1
                trust_err = _compute_trust(_trace_error_counts[_tid])
                _emit(_emitter, "error", f"tool:{_tname}",
                      _aid, _tid, trust_err,
                      duration_ms=round(elapsed, 2),
                      error=f"{type(exc).__name__}: {exc}")
                raise
        return wrapper
    return decorator


def watch_llm(
    agent_name: str,
    ws_url: str = DEFAULT_WS_URL,
    http_url: str = DEFAULT_HTTP_URL,
    trace_id: Optional[str] = None,
):
    """
    Decorator for any LLM call function. Framework-agnostic.

    @watch_llm(agent_name="my_agent")
    def call_openai(prompt: str) -> dict:
        return openai.chat.completions.create(...)

    Extracts token counts from common OpenAI response shapes automatically.
    Emits llm_call event with duration + token count.
    """
    def decorator(fn: Callable) -> Callable:
        _tid     = trace_id or _get_or_create_default_trace()
        _aid     = f"{agent_name}-{uuid.uuid4().hex[:6]}"
        _emitter = _get_emitter(ws_url, http_url)

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = (time.perf_counter() - t0) * 1000
                # Extract tokens from OpenAI response shape
                tokens = 0
                try:
                    tokens = result.usage.total_tokens
                except Exception:
                    try:
                        tokens = result.get("usage", {}).get("total_tokens", 0)
                    except Exception:
                        pass
                trust = _compute_trust(_trace_error_counts[_tid])
                _emit(_emitter, "llm_call", "llm",
                      _aid, _tid, trust,
                      duration_ms=round(elapsed, 2),
                      llm_total_tokens=tokens)
                return result
            except Exception as exc:
                elapsed = (time.perf_counter() - t0) * 1000
                _trace_error_counts[_tid] += 1
                trust_err = _compute_trust(_trace_error_counts[_tid])
                _emit(_emitter, "error", "llm",
                      _aid, _tid, trust_err,
                      duration_ms=round(elapsed, 2),
                      error=f"{type(exc).__name__}: {exc}")
                raise
        return wrapper
    return decorator


# ─────────────────────────────────────────────────────────────────────────────
# Framework detection helper — tells users what's available
# ─────────────────────────────────────────────────────────────────────────────

def detect_frameworks() -> dict:
    """
    Returns a dict of {framework: available} for all supported frameworks.
    Useful for debugging or for building framework-auto-detection.
    """
    result = {}
    for name, pkg in [
        ("crewai",        "crewai"),
        ("openai_agents", "agents"),
        ("autogen",       "autogen"),
        ("langgraph",     "langgraph"),
        ("langchain",     "langchain"),
    ]:
        try:
            __import__(pkg)
            result[name] = True
        except ImportError:
            result[name] = False
    return result