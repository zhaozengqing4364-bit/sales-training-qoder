"""
v1-8: Capability Processor — Extracted from EnhancedSalesHandler.

Handles:
- Running capability modules (fuzzy detection, sales stage, scoring, knowledge retrieval)
- Sending real-time feedback messages to the client
"""

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import WebSocket

from agent.capabilities.runner import CapabilityRunner
from agent.context import AgentContext
from common.monitoring.logger import get_logger
from common.websocket.base_handler import ConnectionManager

logger = get_logger(__name__)


class CapabilityProcessor:
    """
    Runs capability modules and delivers real-time feedback to the client.

    Capabilities include:
    - fuzzy_detection: Detects vague/fuzzy language
    - sales_stage: Tracks conversation sales stage
    - realtime_scoring: Provides real-time scoring
    - knowledge_retrieval: Retrieves relevant knowledge base content
    """

    def __init__(self, capability_runner: CapabilityRunner):
        self.capability_runner = capability_runner
        self._last_emitted_stage: str | None = None

    async def run_and_send_feedback(
        self,
        text: str,
        context: AgentContext,
        websocket: WebSocket,
        manager: ConnectionManager,
        db_lock: asyncio.Lock,
    ) -> tuple[dict[str, Any], str]:
        """
        Run all capabilities and send feedback messages to client.

        Args:
            text: User text to analyze
            context: Agent context for capabilities
            websocket: WebSocket connection for sending feedback
            manager: Connection manager for message delivery
            db_lock: Lock to serialize DB access

        Returns:
            Tuple of (analysis_data dict, knowledge_context string)
        """
        analysis_data: dict[str, Any] = {}
        knowledge_context: str = ""

        logger.info("[CAPABILITY] Running capability modules...")

        async with db_lock:
            capability_results = await self.capability_runner.run_all(context, text)

        trace_id = context.trace_id if context else None

        for i, result in enumerate(capability_results):
            if not result.success:
                continue

            cap = self.capability_runner.capabilities[i]

            if cap.capability_id == "fuzzy_detection" and result.data:
                detections = result.data.get("detections", [])
                if detections:
                    await self._send_fuzzy_detection(
                        detections, websocket, manager, trace_id
                    )
                    analysis_data["fuzzy_words"] = detections

            elif cap.capability_id == "sales_stage" and result.data:
                stage_data = result.data
                current_stage = stage_data.get("current_stage")
                stage_changed = bool(stage_data.get("stage_changed", False))

                if isinstance(current_stage, str) and current_stage:
                    should_emit = (
                        self._last_emitted_stage is None
                        or stage_changed
                        or current_stage != self._last_emitted_stage
                    )
                    if should_emit:
                        await self._send_stage_update(
                            stage_data, websocket, manager, trace_id
                        )
                        self._last_emitted_stage = current_stage
                    analysis_data["sales_stage"] = current_stage

            elif cap.capability_id == "realtime_scoring" and result.data:
                await self._send_score_update(
                    result.data, websocket, manager, trace_id
                )
                analysis_data["score_snapshot"] = result.data

            elif cap.capability_id == "knowledge_retrieval" and result.data:
                knowledge_context = result.data.get("context", "")
                if knowledge_context:
                    logger.info(
                        f"Knowledge retrieval returned {len(result.data.get('results', []))} results"
                    )

        return analysis_data, knowledge_context

    # ── Feedback message senders ──

    async def _send_fuzzy_detection(
        self,
        detections: list[dict],
        websocket: WebSocket,
        manager: ConnectionManager,
        trace_id: str | None,
    ) -> None:
        """Send fuzzy word detection message to client."""
        await manager.send_json(
            websocket,
            {
                "type": "fuzzy_detection",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": trace_id,
                "data": {"detections": detections},
            },
        )

    async def _send_stage_update(
        self,
        stage_data: dict,
        websocket: WebSocket,
        manager: ConnectionManager,
        trace_id: str | None,
    ) -> None:
        """Send sales stage update message to client."""
        await manager.send_json(
            websocket,
            {
                "type": "stage_update",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": trace_id,
                "data": stage_data,
            },
        )

    async def _send_score_update(
        self,
        score_data: dict,
        websocket: WebSocket,
        manager: ConnectionManager,
        trace_id: str | None,
    ) -> None:
        """Send score update message to client."""
        await manager.send_json(
            websocket,
            {
                "type": "score_update",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": trace_id,
                "data": score_data,
            },
        )
