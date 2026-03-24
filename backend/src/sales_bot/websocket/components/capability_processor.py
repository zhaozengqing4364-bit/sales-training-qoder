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
from common.effectiveness import (
    build_sales_effectiveness_metrics,
    evaluate_pass_flags,
)
from common.monitoring.logger import get_logger
from common.websocket.base_handler import ConnectionManager
from sales_bot.websocket.realtime_feedback_arbiter import (
    RealtimeFeedbackArbiter,
    RealtimeFeedbackPacingState,
)

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
        self._feedback_arbiter = RealtimeFeedbackArbiter()
        self._feedback_state = RealtimeFeedbackPacingState()

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
        detections_for_card: list[dict[str, Any]] = []
        suggestions_for_card: list[str] = []
        pass_flags_for_card: dict[str, bool] | None = None
        stage_context_for_arbiter: dict[str, Any] | None = None
        score_context_for_arbiter: dict[str, Any] | None = None

        logger.info("[CAPABILITY] Running capability modules...")

        async with db_lock:
            capability_results = await self.capability_runner.run_all(context, text)

        trace_id = context.trace_id if context else None

        for i, result in enumerate(capability_results):
            if not result.success:
                continue

            cap = self.capability_runner.capabilities[i]

            if cap.capability_id == "fuzzy_detection" and result.data:
                fuzzy_payload = result.data if isinstance(result.data, dict) else {}
                detections = fuzzy_payload.get("detections", [])
                if detections:
                    await self._send_fuzzy_detection(
                        detections, websocket, manager, trace_id
                    )
                    analysis_data["fuzzy_words"] = detections
                    detections_for_card = [
                        item for item in detections if isinstance(item, dict)
                    ]

            elif cap.capability_id == "sales_stage" and result.data:
                if not isinstance(result.data, dict):
                    continue
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
                    stage_context_for_arbiter = dict(stage_data)

            elif cap.capability_id == "realtime_scoring" and result.data:
                score_payload = result.data if isinstance(result.data, dict) else {}
                await self._send_score_update(
                    score_payload, websocket, manager, trace_id
                )
                analysis_data["score_snapshot"] = score_payload
                score_context_for_arbiter = dict(score_payload)
                feedback_message = score_payload.get("feedback")
                if isinstance(feedback_message, str) and feedback_message.strip():
                    suggestions_for_card = [feedback_message.strip()]

                dimension_scores: dict[str, float] = {}
                canonical_dimension_scores = score_payload.get("dimension_scores")
                if isinstance(canonical_dimension_scores, dict):
                    for name, score in canonical_dimension_scores.items():
                        if isinstance(name, str) and isinstance(score, (int, float)):
                            dimension_scores[name] = max(0.0, min(100.0, float(score)))

                if not dimension_scores:
                    dimensions = score_payload.get("dimensions")
                    if isinstance(dimensions, list):
                        for item in dimensions:
                            if not isinstance(item, dict):
                                continue
                            name = item.get("name")
                            score = item.get("score")
                            if isinstance(name, str) and isinstance(score, (int, float)):
                                dimension_scores[name] = max(0.0, min(100.0, float(score)))

                overall_raw = score_payload.get("overall_score")
                if not isinstance(overall_raw, (int, float)):
                    overall_raw = score_payload.get("overall")
                if not isinstance(overall_raw, (int, float)):
                    overall_raw = (
                        sum(dimension_scores.values()) / len(dimension_scores)
                        if dimension_scores
                        else 0.0
                    )
                overall_score = max(0.0, min(100.0, float(overall_raw)))
                turn_count = max(1, int(context.turn_count or 1))
                pass_flags_for_card = evaluate_pass_flags(
                    build_sales_effectiveness_metrics(
                        overall_score=overall_score,
                        dimension_scores=dimension_scores or None,
                        turn_count=turn_count,
                    )
                )

            elif cap.capability_id == "knowledge_retrieval" and result.data:
                knowledge_payload = (
                    result.data if isinstance(result.data, dict) else {}
                )
                knowledge_context = str(knowledge_payload.get("context") or "")
                if knowledge_context:
                    logger.info(
                        f"Knowledge retrieval returned {len(knowledge_payload.get('results', []))} results"
                    )

        decision = self._feedback_arbiter.decide(
            turn_number=getattr(context, "turn_count", None),
            fuzzy_detections=detections_for_card,
            score_suggestions=suggestions_for_card,
            stage_context=stage_context_for_arbiter,
            score_context=score_context_for_arbiter,
            pass_flags=pass_flags_for_card,
            prior_state=self._feedback_state,
        )
        self._feedback_state = decision.state

        if decision.action_card:
            await self._send_action_card(
                decision.action_card, websocket, manager, trace_id
            )
            analysis_data["ai_feedback"] = decision.action_card.get("replacement", "")

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

    async def _send_action_card(
        self,
        action_card: dict[str, str],
        websocket: WebSocket,
        manager: ConnectionManager,
        trace_id: str | None,
    ) -> None:
        """Send one actionable card for the next turn."""
        await manager.send_json(
            websocket,
            {
                "type": "action_card",
                "timestamp": datetime.now(UTC).isoformat(),
                "trace_id": trace_id,
                "data": action_card,
            },
        )
