"""
agentwatch/backend/instrumentation/otel_setup.py

OpenTelemetry provider configured to export spans to Splunk HEC.
Every LangGraph step, LLM call, tool call, and error becomes a searchable
event in Splunk with full context.
"""

import json
import time
import uuid
import os
import logging
from typing import Any, Dict, Optional, Sequence
from dataclasses import dataclass, field, asdict

import httpx
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider, ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult, BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import SpanKind, Status, StatusCode

logger = logging.getLogger("agentwatch.otel")


# ─────────────────────────────────────────────
# Custom Splunk HEC Span Exporter
# ─────────────────────────────────────────────

class SplunkHECExporter(SpanExporter):
    """
    Exports OpenTelemetry spans to Splunk HTTP Event Collector.
    Each span becomes a structured JSON event indexed under agentwatch:otel.
    """

    def __init__(
        self,
        hec_url: str,
        hec_token: str,
        index: str = "agentwatch",
        source: str = "agentwatch",
        sourcetype: str = "agentwatch:otel",
        verify_ssl: bool = False,
    ):
        self.hec_url = hec_url.rstrip("/") + "/services/collector/event"
        self.hec_token = hec_token
        self.index = index
        self.source = source
        self.sourcetype = sourcetype
        self.verify_ssl = verify_ssl
        self._client = httpx.Client(verify=verify_ssl, timeout=5.0)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        events = []
        for span in spans:
            event = self._span_to_hec_event(span)
            events.append(event)

        payload = "\n".join(json.dumps(e) for e in events)
        try:
            resp = self._client.post(
                self.hec_url,
                content=payload,
                headers={
                    "Authorization": f"Splunk {self.hec_token}",
                    "Content-Type": "application/json",
                },
            )
            if resp.status_code not in (200, 201):
                logger.error(f"HEC export failed: {resp.status_code} {resp.text}")
                return SpanExportResult.FAILURE
            return SpanExportResult.SUCCESS
        except Exception as e:
            logger.error(f"HEC export exception: {e}")
            return SpanExportResult.FAILURE

    def _span_to_hec_event(self, span: ReadableSpan) -> Dict[str, Any]:
        attrs = dict(span.attributes or {})
        start_ns = span.start_time or 0
        end_ns = span.end_time or 0
        duration_ms = (end_ns - start_ns) / 1_000_000

        event_data = {
            "trace_id": format(span.context.trace_id, "032x"),
            "span_id": format(span.context.span_id, "016x"),
            "span_name": span.name,
            "span_kind": span.kind.name,
            "status": span.status.status_code.name,
            "duration_ms": round(duration_ms, 2),
            "start_time": start_ns / 1_000_000_000,
            # AgentWatch-specific fields (set by langgraph_hooks.py)
            "event_type": attrs.get("agentwatch.event_type", "unknown"),
            "agent_id": attrs.get("agentwatch.agent_id", ""),
            "step_id": attrs.get("agentwatch.step_id", ""),
            "step_name": attrs.get("agentwatch.step_name", span.name),
            "tool_name": attrs.get("agentwatch.tool_name", ""),
            "tool_input": attrs.get("agentwatch.tool_input", ""),
            "tool_output": attrs.get("agentwatch.tool_output", ""),
            "llm_model": attrs.get("agentwatch.llm_model", ""),
            "llm_prompt_tokens": attrs.get("agentwatch.llm_prompt_tokens", 0),
            "llm_completion_tokens": attrs.get("agentwatch.llm_completion_tokens", 0),
            "llm_total_tokens": attrs.get("agentwatch.llm_total_tokens", 0),
            "confidence_score": attrs.get("agentwatch.confidence_score", 1.0),
            "trust_score": attrs.get("agentwatch.trust_score", 1.0),
            "error": attrs.get("agentwatch.error", ""),
            "reasoning_content": attrs.get("agentwatch.reasoning_content", ""),
            # Raw attributes
            **{k: v for k, v in attrs.items() if not k.startswith("agentwatch.")},
        }

        return {
            "time": start_ns / 1_000_000_000,
            "index": self.index,
            "source": self.source,
            "sourcetype": self.sourcetype,
            "event": event_data,
        }

    def shutdown(self) -> None:
        self._client.close()


# ─────────────────────────────────────────────
# Console Exporter (for local dev without Splunk)
# ─────────────────────────────────────────────

class ConsoleStructuredExporter(SpanExporter):
    """Pretty-prints spans to console. Use when OTEL_EXPORTER=console."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            attrs = dict(span.attributes or {})
            event_type = attrs.get("agentwatch.event_type", "span")
            step_name = attrs.get("agentwatch.step_name", span.name)
            duration_ms = ((span.end_time or 0) - (span.start_time or 0)) / 1_000_000
            status = "✅" if span.status.status_code != StatusCode.ERROR else "❌"
            print(
                f"{status} [{event_type.upper():12s}] {step_name:30s} "
                f"{duration_ms:8.1f}ms  "
                f"tokens={attrs.get('agentwatch.llm_total_tokens', '-'):>6}"
            )
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


# ─────────────────────────────────────────────
# Provider Setup
# ─────────────────────────────────────────────

_tracer: Optional[trace.Tracer] = None


def setup_otel(
    service_name: str = "agentwatch-agent",
    agent_id: Optional[str] = None,
) -> trace.Tracer:
    """
    Initialize OpenTelemetry with the appropriate exporter.
    Call once at startup before running any agent.

    Returns a tracer — pass this to AgentWatchHooks.
    """
    global _tracer

    exporter_type = os.getenv("OTEL_EXPORTER", "console")
    agent_id = agent_id or str(uuid.uuid4())[:8]

    resource = Resource.create({
        "service.name": service_name,
        "agentwatch.agent_id": agent_id,
        "agentwatch.version": "1.0.0",
    })

    provider = TracerProvider(resource=resource)

    if exporter_type == "splunk_hec":
        host = os.getenv("SPLUNK_HOST", "localhost")
        port = os.getenv("SPLUNK_HEC_PORT", "8088")
        token = os.getenv("SPLUNK_HEC_TOKEN", "")
        index = os.getenv("SPLUNK_INDEX", "agentwatch")

        if not token:
            raise ValueError("SPLUNK_HEC_TOKEN must be set when OTEL_EXPORTER=splunk_hec")

        hec_url = f"https://{host}:{port}"
        exporter = SplunkHECExporter(hec_url=hec_url, hec_token=token, index=index)
        logger.info(f"OTel → Splunk HEC at {hec_url} (index={index})")
    else:
        exporter = ConsoleStructuredExporter()
        logger.info("OTel → Console (set OTEL_EXPORTER=splunk_hec for Splunk)")

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _tracer = trace.get_tracer("agentwatch")
    return _tracer


def get_tracer() -> trace.Tracer:
    if _tracer is None:
        return setup_otel()
    return _tracer
