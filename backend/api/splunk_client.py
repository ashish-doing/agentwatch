"""
agentwatch/backend/api/splunk_client.py

Handles all Splunk interactions:
  - Index events via HEC
  - Run SPL searches via Splunk REST API
  - Generate SPL via Splunk AI Assistant (NL → SPL)
"""

import os
import json
import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("agentwatch.splunk")


class SplunkClient:
    def __init__(self):
        self.host = os.getenv("SPLUNK_HOST", "localhost")
        self.port = int(os.getenv("SPLUNK_PORT", "8089"))
        self.hec_port = int(os.getenv("SPLUNK_HEC_PORT", "8088"))
        self.hec_token = os.getenv("SPLUNK_HEC_TOKEN", "")
        self.username = os.getenv("SPLUNK_USERNAME", "admin")
        self.password = os.getenv("SPLUNK_PASSWORD", "changeme")
        self.index = os.getenv("SPLUNK_INDEX", "agentwatch")

        self.base_url = f"https://{self.host}:{self.port}"
        self.hec_url = f"https://{self.host}:{self.hec_port}/services/collector/event"

        self._client = httpx.AsyncClient(verify=False, timeout=10.0)
        self._session_key: Optional[str] = None

    # ── Authentication ──────────────────────────

    async def _get_session_key(self) -> str:
        if self._session_key:
            return self._session_key
        try:
            resp = await self._client.post(
                f"{self.base_url}/services/auth/login",
                data={"username": self.username, "password": self.password},
            )
            resp.raise_for_status()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            key = root.find("sessionKey")
            self._session_key = key.text if key is not None else ""
            return self._session_key
        except Exception as e:
            logger.error(f"Splunk auth failed: {e}")
            return ""

    async def ping(self) -> bool:
        try:
            session_key = await self._get_session_key()
            return bool(session_key)
        except Exception:
            return False

    # ── HEC Indexing ────────────────────────────

    async def index_event(self, event: Dict[str, Any]) -> bool:
        """Index a single AgentWatch event via HEC."""
        if not self.hec_token:
            return False  # No HEC configured — skip silently

        payload = {
            "time": event.get("timestamp", time.time()),
            "index": self.index,
            "source": "agentwatch",
            "sourcetype": "agentwatch:otel",
            "event": event,
        }
        try:
            resp = await self._client.post(
                self.hec_url,
                content=json.dumps(payload),
                headers={
                    "Authorization": f"Splunk {self.hec_token}",
                    "Content-Type": "application/json",
                },
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.debug(f"HEC index error: {e}")
            return False

    # ── SPL Search ──────────────────────────────

    async def run_search(self, spl: str, earliest: str = "-1h", latest: str = "now") -> List[Dict]:
        """Execute a SPL search and return results as a list of dicts."""
        session_key = await self._get_session_key()
        if not session_key:
            logger.warning("Splunk not connected — returning mock results")
            return self._mock_search_results(spl)

        try:
            # Create search job
            resp = await self._client.post(
                f"{self.base_url}/services/search/jobs",
                data={
                    "search": f"search {spl}",
                    "earliest_time": earliest,
                    "latest_time": latest,
                    "output_mode": "json",
                },
                headers={"Authorization": f"Splunk {session_key}"},
            )
            resp.raise_for_status()
            sid = resp.json()["sid"]

            # Poll until complete
            for _ in range(30):
                await asyncio.sleep(0.5)
                status_resp = await self._client.get(
                    f"{self.base_url}/services/search/jobs/{sid}",
                    params={"output_mode": "json"},
                    headers={"Authorization": f"Splunk {session_key}"},
                )
                job = status_resp.json()["entry"][0]["content"]
                if job["dispatchState"] == "DONE":
                    break

            # Fetch results
            results_resp = await self._client.get(
                f"{self.base_url}/services/search/jobs/{sid}/results",
                params={"output_mode": "json", "count": 100},
                headers={"Authorization": f"Splunk {session_key}"},
            )
            return results_resp.json().get("results", [])

        except Exception as e:
            logger.error(f"SPL search error: {e}")
            return []

    # ── AI Assistant: NL → SPL ──────────────────

    async def generate_spl(self, nl_query: str, time_range: str = "-1h") -> str:
        """
        Use Splunk AI Assistant to convert natural language to SPL.
        Falls back to template-based generation when AI Assistant isn't available.
        """
        session_key = await self._get_session_key()
        if session_key:
            try:
                resp = await self._client.post(
                    f"{self.base_url}/services/assistant/generate_spl",
                    json={"query": nl_query, "index": self.index, "time_range": time_range},
                    headers={"Authorization": f"Splunk {session_key}"},
                )
                if resp.status_code == 200:
                    return resp.json().get("spl", "")
            except Exception as e:
                logger.debug(f"AI Assistant unavailable: {e}")

        # Fallback: template-based NL → SPL
        return self._nl_to_spl_template(nl_query, time_range)

    def _nl_to_spl_template(self, nl: str, time_range: str) -> str:
        """Heuristic NL → SPL conversion for common AgentWatch queries."""
        nl_lower = nl.lower()
        index_prefix = f'index={self.index} earliest={time_range}'

        if "loop" in nl_lower:
            return (
                f'{index_prefix} event_type=anomaly '
                f'| stats count by tool_name, trace_id '
                f'| where count > 5 '
                f'| sort -count'
            )
        if "token" in nl_lower and ("spike" in nl_lower or "high" in nl_lower):
            return (
                f'{index_prefix} event_type=llm_call '
                f'| stats max(llm_total_tokens) as max_tokens by trace_id, step_name '
                f'| where max_tokens > 3000 '
                f'| sort -max_tokens'
            )
        if "trust" in nl_lower and ("low" in nl_lower or "worst" in nl_lower):
            return (
                f'{index_prefix} '
                f'| stats avg(trust_score) as avg_trust by tool_name '
                f'| sort avg_trust '
                f'| head 10'
            )
        if "error" in nl_lower:
            return (
                f'{index_prefix} event_type=error '
                f'| stats count by step_name, error '
                f'| sort -count'
            )
        if "anomaly" in nl_lower or "anomalies" in nl_lower:
            return (
                f'{index_prefix} event_type=anomaly '
                f'| sort -_time '
                f'| table _time, agent_id, tool_name, reasoning_content, trust_score'
            )
        if "latency" in nl_lower or "slow" in nl_lower:
            return (
                f'{index_prefix} '
                f'| stats avg(duration_ms) as avg_ms, max(duration_ms) as max_ms by step_name '
                f'| sort -avg_ms '
                f'| head 10'
            )

        # Generic fallback
        return (
            f'{index_prefix} '
            f'| sort -_time '
            f'| table _time, event_type, step_name, trust_score, tool_name, error '
            f'| head 50'
        )

    def _mock_search_results(self, spl: str) -> List[Dict]:
        """Return mock results when Splunk isn't connected (for local dev)."""
        return [
            {"_time": "2026-05-18T10:00:00", "event_type": "tool_call", "step_name": "search_tool", "trust_score": "0.45", "tool_name": "search_tool"},
            {"_time": "2026-05-18T10:00:01", "event_type": "anomaly", "step_name": "tool:search_tool", "trust_score": "0.05", "reasoning_content": "Loop detected — search_tool called 23x"},
            {"_time": "2026-05-18T10:00:02", "event_type": "llm_call", "step_name": "research", "llm_total_tokens": "1247", "trust_score": "0.87"},
        ]
