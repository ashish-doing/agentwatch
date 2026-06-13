"""
agentwatch/backend/agent/demo_runner_lib.py

In-process variant of agent_runner.py for the live public demo.

Unlike agent_runner.py (a CLI script that sends events ONLY to Splunk HEC),
this module runs the demo LangGraph agent synchronously and calls an
`emit(event_dict)` callback for every event — letting the FastAPI backend
pipe events straight into its existing anomaly-detection + WebSocket
broadcast pipeline (event_buffer / broadcast_to_browsers in main.py).

HEC indexing is still supported and controlled by the caller: if
SPLUNK_HEC_TOKEN is set AND the caller passes index_to_splunk=True (via
demo_agent's existing _send mechanism), events are also sent to Splunk.
For the public demo this is OFF by default (see main.py
PUBLIC_DEMO_INDEX_TO_SPLUNK) to avoid polluting the curated Splunk index
with stranger-triggered runs and to avoid HEC rate limits during judging.

This module deliberately has NO asyncio — it's designed to be called via
loop.run_in_executor(None, run_demo_in_process, mode, emit) from main.py,
since demo_agent's simulate_* functions use blocking time.sleep().
"""

import os
import sys
import uuid
import asyncio
from pathlib import Path
from typing import Callable, Optional

# Make sure backend/agent/ is importable regardless of cwd
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import demo_agent as da
from demo_agent import build_demo_agent, make_initial_state

HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "")
HEC_HOST = os.getenv("SPLUNK_HOST", "localhost")
HEC_PORT = os.getenv("SPLUNK_HEC_PORT", "8088")
INDEX = os.getenv("SPLUNK_INDEX", "agentwatch")
HEC_URL = f"https://{HEC_HOST}:{HEC_PORT}/services/collector/event"


def run_demo_in_process(mode: str, emit: Callable[[dict], None]) -> str:
    """
    Runs the demo agent for the given mode, calling emit(event_dict) for
    every event produced. Returns the trace_id of this run.

    mode: one of "normal", "loop", "hallucinate", "drift"
    emit: callback invoked synchronously with each event dict, in the
          same shape demo_agent._send() builds (event_type, step_name,
          timestamp, trace_id, agent_id, step_id, trust_score, ...).

    NOTE: this function is BLOCKING (demo_agent uses time.sleep() to
    simulate latency). Call it from a thread executor, not the event loop.
    """
    trace_id = uuid.uuid4().hex

    # Wire demo_agent's module-level config:
    # - _hec_token / _hec_url / _index: only used if HEC indexing is desired
    # - _trace_id: stamped onto every event
    # - _emit_callback: NEW hook, called by _send() for every event
    da._trace_id = trace_id
    da._index = INDEX
    da._hec_url = HEC_URL

    # Only set the HEC token if the operator explicitly wants public demo
    # runs indexed to Splunk. Controlled by the same env flag main.py reads.
    public_index = os.getenv("PUBLIC_DEMO_INDEX_TO_SPLUNK", "false").lower() == "true"
    da._hec_token = HEC_TOKEN if public_index else ""

    da._emit_callback = emit

    graph = build_demo_agent()
    state = make_initial_state(mode=mode)

    # demo_agent's nodes are plain sync functions; the graph itself supports
    # both sync .invoke() and async .ainvoke(). Use sync invoke here since
    # we're already off the event loop (running in an executor thread).
    graph.invoke(state, config={"recursion_limit": 50})

    return trace_id