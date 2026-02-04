"""
Evaluation WebSocket Broadcaster (C5)

Non-intrusive real-time evaluation feedback broadcaster.
Sends stage evaluation results and comprehensive reports to connected WebSocket clients.

Features:
- Broadcast evaluation feedback without interrupting user experience
- Send stage completion notifications
- Send comprehensive report when session ends
- Rate limiting to prevent message spam
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from fastapi import WebSocket

from src.common.websocket.base_handler import get_connection_manager
from src.evaluation.services.staged_evaluation import StageEvaluationResult
from src.evaluation.services.comprehensive_report import ComprehensiveReport
from src.common.monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FeedbackMessage:
    """Evaluation feedback message structure."""
    type: str  # "stage_feedback", "comprehensive_report", "milestone"
    session_id: str
    timestamp: str
    data: dict[str, Any]


class EvaluationBroadcaster:
    """
    Broadcasts evaluation feedback to WebSocket connections.

    Non-intrusive design:
    - Feedback sent as side-channel (doesn't block main conversation)
    - Client decides how to display (no forced popups)
    - Rate limited to prevent UI flooding
    """

    def __init__(
        self,
        rate_limit_seconds: float = 5.0,
    ):
        """
        Initialize broadcaster.

        Args:
            rate_limit_seconds: Minimum seconds between feedback messages
        """
        self.rate_limit_seconds = rate_limit_seconds
        self._last_broadcast: dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self.manager = get_connection_manager()

    async def broadcast_stage_feedback(
        self,
        session_id: str,
        scenario: str,
        result: StageEvaluationResult,
    ) -> bool:
        """
        Broadcast stage evaluation feedback.

        Args:
            session_id: Practice session ID
            scenario: Scenario type (sales/presentation)
            result: Stage evaluation result

        Returns:
            True if broadcast successful
        """
        # Rate limiting check
        if not await self._check_rate_limit(session_id):
            logger.debug(f"Rate limit skipped broadcast for {session_id}")
            return False

        message = FeedbackMessage(
            type="stage_feedback",
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            data={
                "stage_number": result.stage_number,
                "start_turn": result.start_turn,
                "end_turn": result.end_turn,
                "scores": result.scores,
                "strengths": result.strengths[:3],  # Limit to top 3
                "suggestions": result.suggestions[:2],  # Limit to top 2
                "summary": result.summary[:200] if len(result.summary) > 200 else result.summary,
            }
        )

        await self._broadcast(session_id, scenario, message)
        return True

    async def broadcast_milestone(
        self,
        session_id: str,
        scenario: str,
        milestone_type: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """
        Broadcast milestone notification.

        Args:
            session_id: Practice session ID
            scenario: Scenario type
            milestone_type: Type of milestone (e.g., "stage_complete", "halfway")
            message: Human-readable message
            data: Additional data
        """
        feedback_msg = FeedbackMessage(
            type="milestone",
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            data={
                "milestone_type": milestone_type,
                "message": message,
                "extra": data or {},
            }
        )

        await self._broadcast(session_id, scenario, feedback_msg)

    async def broadcast_comprehensive_report(
        self,
        session_id: str,
        scenario: str,
        report: ComprehensiveReport,
    ) -> None:
        """
        Broadcast comprehensive report at session end.

        Args:
            session_id: Practice session ID
            scenario: Scenario type
            report: Comprehensive evaluation report
        """
        message = FeedbackMessage(
            type="comprehensive_report",
            session_id=session_id,
            timestamp=datetime.utcnow().isoformat(),
            data={
                "overall_score": report.overall_score,
                "dimension_scores": [
                    {
                        "name": ds.name,
                        "score": ds.score,
                        "weight": ds.weight,
                    }
                    for ds in report.dimension_scores
                ],
                "key_strengths": report.key_strengths[:5],
                "key_improvements": report.key_improvements[:5],
                "recommendations": report.recommendations[:5],
                "detailed_feedback": report.detailed_feedback[:500] if len(report.detailed_feedback) > 500 else report.detailed_feedback,
            }
        )

        await self._broadcast(session_id, scenario, message)
        logger.info(f"Comprehensive report broadcasted for session {session_id}")

    async def _check_rate_limit(self, session_id: str) -> bool:
        """Check if broadcast is allowed by rate limit."""
        async with self._lock:
            now = datetime.utcnow()
            last = self._last_broadcast.get(session_id)

            if last is None:
                self._last_broadcast[session_id] = now
                return True

            elapsed = (now - last).total_seconds()
            if elapsed >= self.rate_limit_seconds:
                self._last_broadcast[session_id] = now
                return True

            return False

    async def _broadcast(
        self,
        session_id: str,
        scenario: str,
        message: FeedbackMessage,
    ) -> None:
        """Send message to WebSocket connection."""
        try:
            websocket = self.manager.active_connections.get(scenario, {}).get(session_id)
            if websocket:
                await self.manager.send_json(websocket, {
                    "type": "evaluation_feedback",
                    "timestamp": message.timestamp,
                    "data": {
                        "feedback_type": message.type,
                        **message.data,
                    }
                })
                logger.debug(f"Evaluation feedback sent to {session_id}")
            else:
                logger.debug(f"No WebSocket connection for session {session_id}")
        except Exception as e:
            logger.error(f"Failed to broadcast evaluation feedback: {e}")

    def cleanup_session(self, session_id: str) -> None:
        """Clean up rate limiting data for session."""
        self._last_broadcast.pop(session_id, None)


# Singleton instance
_broadcaster: EvaluationBroadcaster | None = None


def get_evaluation_broadcaster() -> EvaluationBroadcaster:
    """Get singleton evaluation broadcaster."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EvaluationBroadcaster()
    return _broadcaster
