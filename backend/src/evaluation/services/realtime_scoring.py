"""
Realtime Scoring Service for Sales Training

Requirements: Story 2.6 - Real-time scoring updates and improvement suggestions

Features:
- Incremental scoring with historical weighting
- Real-time score update events via WebSocket
- Suggestion generation based on score dimensions
- Score persistence to conversation messages and reports
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from common.ai.llm_service import LLMService
from common.error_handling.result import Result
from common.monitoring.logger import get_logger
from evaluation.schemas import RealtimeScoringResponse, parse_llm_response
from evaluation.services.ai_scoring import AIScoringService

logger = get_logger(__name__)


@dataclass
class ScoreUpdateEvent:
    """Score update event for WebSocket transmission.

    Attributes:
        session_id: Practice session ID
        timestamp: Event timestamp
        turn_count: Current turn count
        overall_score: Overall performance score (0-100)
        dimension_scores: Dimension-specific scores
        suggestions: Improvement suggestions
        stage_name: Current sales stage name
        trace_id: Trace ID for observability
    """

    session_id: str
    timestamp: str
    turn_count: int
    overall_score: float
    dimension_scores: dict[str, float]
    suggestions: list[str]
    stage_name: str
    trace_id: str = ""

    def to_websocket_event(self) -> dict[str, Any]:
        """Convert to WebSocket event format."""
        return {
            "type": "score_update",
            "timestamp": self.timestamp,
            "trace_id": self.trace_id,
            "data": {
                "session_id": self.session_id,
                "turn_count": self.turn_count,
                "overall_score": self.overall_score,
                "dimension_scores": self.dimension_scores,
                "suggestions": self.suggestions,
                "stage_name": self.stage_name,
            },
        }


@dataclass
class IncrementalScoreState:
    """Maintains incremental scoring state across conversation turns.

    Attributes:
        session_id: Practice session ID
        turn_scores: List of scores per turn
        current_overall: Current overall score (weighted average)
        dimension_history: Historical scores per dimension
        last_update: Last update timestamp
    """

    session_id: str
    turn_scores: list[dict] = field(default_factory=list)
    current_overall: float = 0.0
    dimension_history: dict[str, list[float]] = field(default_factory=dict)
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Weight configuration for incremental scoring
    HISTORY_WEIGHT: float = 0.7  # Weight for historical scores
    CURRENT_WEIGHT: float = 0.3  # Weight for current turn score

    def update_with_new_scores(
        self,
        turn_number: int,
        dimension_scores: dict[str, float],
        overall_score: float,
    ) -> dict[str, Any]:
        """Update state with new turn scores using incremental algorithm.

        Args:
            turn_number: Current turn number
            dimension_scores: Dimension scores for this turn
            overall_score: Overall score for this turn

        Returns:
            Updated score summary
        """
        # Store turn score
        turn_data = {
            "turn": turn_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dimensions": dimension_scores,
            "overall": overall_score,
        }
        self.turn_scores.append(turn_data)

        # Update dimension history
        for dim, score in dimension_scores.items():
            if dim not in self.dimension_history:
                self.dimension_history[dim] = []
            self.dimension_history[dim].append(score)

        # Calculate incremental overall score with history weighting
        if len(self.turn_scores) == 1:
            # First turn - use current score directly
            self.current_overall = overall_score
        else:
            # Incremental update with weighted average
            self.current_overall = (
                self.current_overall * self.HISTORY_WEIGHT
                + overall_score * self.CURRENT_WEIGHT
            )

        self.last_update = datetime.now(timezone.utc)

        # Calculate incremental dimension scores
        incremental_dimensions = {}
        for dim, history in self.dimension_history.items():
            if len(history) == 1:
                incremental_dimensions[dim] = history[0]
            else:
                # Weighted average of historical scores
                weighted_sum = sum(
                    history[i] * (self.HISTORY_WEIGHT if i < len(history) - 1 else self.CURRENT_WEIGHT)
                    for i in range(len(history))
                )
                # Normalize weights
                total_weight = self.HISTORY_WEIGHT * (len(history) - 1) + self.CURRENT_WEIGHT
                incremental_dimensions[dim] = round(weighted_sum / total_weight, 1)

        return {
            "overall": round(self.current_overall, 1),
            "dimensions": incremental_dimensions,
            "turn_count": len(self.turn_scores),
            "latest_turn": turn_data,
        }

    def get_score_trend(self) -> dict[str, Any]:
        """Get score trend analysis.

        Returns:
            Trend data including direction and change rate
        """
        if len(self.turn_scores) < 2:
            return {"direction": "stable", "change_rate": 0.0}

        recent_scores = [t["overall"] for t in self.turn_scores[-3:]]
        if len(recent_scores) < 2:
            return {"direction": "stable", "change_rate": 0.0}

        # Calculate trend
        changes = [
            recent_scores[i] - recent_scores[i - 1]
            for i in range(1, len(recent_scores))
        ]
        avg_change = sum(changes) / len(changes)

        if avg_change > 3:
            direction = "improving"
        elif avg_change < -3:
            direction = "declining"
        else:
            direction = "stable"

        return {
            "direction": direction,
            "change_rate": round(avg_change, 1),
            "recent_average": round(sum(recent_scores) / len(recent_scores), 1),
        }


class RealtimeScoringService:
    """Service for real-time scoring during sales training sessions.

    Provides incremental scoring updates and improvement suggestions
    with P95 latency < 300ms.
    """

    # Score update thresholds
    MIN_TURNS_BEFORE_SCORE = 5  # Minimum turns before first score
    SCORE_UPDATE_INTERVAL = 3   # Update score every N turns

    def __init__(
        self,
        ai_scoring_service: AIScoringService | None = None,
        llm_service: LLMService | None = None,
    ):
        """Initialize service.

        Args:
            ai_scoring_service: AI scoring service for evaluations
            llm_service: LLM service for suggestion generation
        """
        self.ai_scoring = ai_scoring_service or AIScoringService()
        self.llm = llm_service or LLMService()

        # In-memory state storage (should be Redis in production)
        self._score_states: dict[str, IncrementalScoreState] = {}

    async def evaluate_turn(
        self,
        session_id: str,
        turn_number: int,
        conversation_history: list[dict],
        stage_name: str,
        trace_id: str = "",
    ) -> Result[ScoreUpdateEvent | None]:
        """Evaluate a single turn and generate score update if needed.

        Args:
            session_id: Practice session ID
            turn_number: Current turn number
            conversation_history: Full conversation history
            stage_name: Current sales stage name
            trace_id: Trace ID for observability

        Returns:
            Result with ScoreUpdateEvent if update triggered, None otherwise
        """
        try:
            # Check if we should trigger score update
            if not self._should_trigger_score_update(turn_number):
                return Result.ok(None)

            # Get or create score state
            state = self._get_or_create_state(session_id)

            # Perform AI scoring
            scoring_result = await self.ai_scoring.evaluate_conversation(
                conversation_history=conversation_history,
                stage_name=stage_name,
            )

            if not scoring_result.is_success:
                logger.warning(
                    "realtime_scoring_failed",
                    session_id=session_id,
                    turn_number=turn_number,
                    error=scoring_result.fallback,
                )
                # Return failure but don't block conversation
                return Result.fail(scoring_result.fallback or "[SCORING_FAILED]")

            # Extract scores from result
            scoring_data = scoring_result.value
            dimension_scores = {
                d["name"]: d["score"]
                for d in scoring_data.get("dimensions", [])
            }
            overall_score = scoring_data.get("overall", 0)

            # Update incremental state
            updated_scores = state.update_with_new_scores(
                turn_number=turn_number,
                dimension_scores=dimension_scores,
                overall_score=overall_score,
            )

            # Generate suggestions based on scores
            suggestions = await self._generate_suggestions(
                dimension_scores=updated_scores["dimensions"],
                stage_name=stage_name,
                score_trend=state.get_score_trend(),
            )

            # Create score update event
            event = ScoreUpdateEvent(
                session_id=session_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                turn_count=turn_number,
                overall_score=updated_scores["overall"],
                dimension_scores=updated_scores["dimensions"],
                suggestions=suggestions,
                stage_name=stage_name,
                trace_id=trace_id,
            )

            logger.info(
                "realtime_score_updated",
                session_id=session_id,
                turn_number=turn_number,
                overall_score=event.overall_score,
            )

            return Result.ok(event)

        except Exception as e:
            logger.error(
                "realtime_scoring_error",
                session_id=session_id,
                turn_number=turn_number,
                error=str(e),
            )
            return Result.fail(f"[REALTIME_SCORING_ERROR:{str(e)}]")

    def _should_trigger_score_update(self, turn_number: int) -> bool:
        """Check if score update should be triggered for this turn.

        Args:
            turn_number: Current turn number

        Returns:
            True if score update should be triggered
        """
        # Wait for minimum turns before first score
        if turn_number < self.MIN_TURNS_BEFORE_SCORE:
            return False

        # Update every N turns after minimum
        return (turn_number - self.MIN_TURNS_BEFORE_SCORE) % self.SCORE_UPDATE_INTERVAL == 0

    def _get_or_create_state(self, session_id: str) -> IncrementalScoreState:
        """Get or create score state for session.

        Args:
            session_id: Session ID

        Returns:
            IncrementalScoreState for the session
        """
        if session_id not in self._score_states:
            self._score_states[session_id] = IncrementalScoreState(session_id=session_id)
        return self._score_states[session_id]

    async def _generate_suggestions(
        self,
        dimension_scores: dict[str, float],
        stage_name: str,
        score_trend: dict[str, Any],
    ) -> list[str]:
        """Generate improvement suggestions based on scores.

        Args:
            dimension_scores: Current dimension scores
            stage_name: Current sales stage
            score_trend: Score trend analysis

        Returns:
            List of actionable suggestions
        """
        suggestions = []

        # Identify low-scoring dimensions
        low_dimensions = [
            (name, score) for name, score in dimension_scores.items()
            if score < 70
        ]

        # Sort by score (lowest first)
        low_dimensions.sort(key=lambda x: x[1])

        # Generate suggestions for low dimensions
        for dim_name, score in low_dimensions[:2]:  # Top 2 improvement areas
            suggestion = self._get_dimension_suggestion(dim_name, stage_name, score)
            if suggestion:
                suggestions.append(suggestion)

        # Add trend-based suggestion
        trend = score_trend.get("direction", "stable")
        if trend == "declining":
            suggestions.append("注意：最近几轮评分有下降趋势，建议回顾之前的优秀表现")
        elif trend == "improving":
            suggestions.append("很好：你的表现正在稳步提升，继续保持！")

        # Add stage-specific suggestion
        stage_suggestion = self._get_stage_suggestion(stage_name, dimension_scores)
        if stage_suggestion:
            suggestions.append(stage_suggestion)

        return suggestions[:3]  # Max 3 suggestions

    def _get_dimension_suggestion(self, dimension: str, stage: str, score: float) -> str:
        """Get suggestion for a specific dimension.

        Args:
            dimension: Dimension name
            stage: Current stage
            score: Current score

        Returns:
            Suggestion text
        """
        suggestions_map = {
            "专业度": {
                "opening": "开场时先建立信任，再展示专业知识",
                "discovery": "在需求挖掘时，用专业知识引导客户思考",
                "presentation": "产品介绍时，突出专业差异化优势",
                "objection": "用专业数据和案例化解客户疑虑",
                "closing": "专业地总结价值，促成决策",
            },
            "沟通技巧": {
                "opening": "多用开放式问题，让客户多说话",
                "discovery": "积极倾听，适时复述确认理解",
                "presentation": "观察客户反应，调整沟通节奏",
                "objection": "先认同感受，再解释说明",
                "closing": "确认客户无异议后再推进成交",
            },
            "销售流程": {
                "opening": "按 SPIN 流程逐步推进，不要急于推销",
                "discovery": "深入挖掘需求，不要停留在表面",
                "presentation": "方案呈现要针对已挖掘的需求",
                "objection": "把异议视为成交信号，妥善处理",
                "closing": "把握时机，适时提出下一步行动",
            },
            "异议处理": {
                "opening": "提前预判常见异议，准备应对话术",
                "discovery": "通过深入提问，化解潜在异议",
                "presentation": "主动提及并化解可能的顾虑",
                "objection": "用 CPIC 法则：澄清-探究-隔离-解决",
                "closing": "最后确认，消除所有遗留疑虑",
            },
            "成交能力": {
                "opening": "为后续成交铺垫，建立信任基础",
                "discovery": "挖掘真实需求和决策标准",
                "presentation": "强化价值感知，提升成交意愿",
                "objection": "把异议处理转化为成交推进",
                "closing": "明确下一步，推动客户行动",
            },
        }

        # Normalize dimension name
        dim_key = None
        for key in suggestions_map:
            if key in dimension or dimension in key:
                dim_key = key
                break

        if not dim_key:
            return f"{dimension}方面还有提升空间，建议针对性练习"

        # Normalize stage name
        stage_key = "opening"  # default
        stage_mapping = {
            "开场": "opening",
            "需求挖掘": "discovery",
            "方案呈现": "presentation",
            "异议处理": "objection",
            "成交": "closing",
            "opening": "opening",
            "discovery": "discovery",
            "presentation": "presentation",
            "objection": "objection",
            "closing": "closing",
        }
        for key, value in stage_mapping.items():
            if key in stage or stage in key:
                stage_key = value
                break

        suggestion = suggestions_map.get(dim_key, {}).get(stage_key)
        if suggestion:
            return f"【{dimension}】{suggestion}"

        return f"{dimension}得分{score:.0f}分，建议针对性加强练习"

    def _get_stage_suggestion(self, stage: str, dimension_scores: dict[str, float]) -> str:
        """Get stage-specific suggestion.

        Args:
            stage: Current stage
            dimension_scores: Current dimension scores

        Returns:
            Stage-specific suggestion
        """
        stage_suggestions = {
            "opening": "开场阶段重点：建立信任、引发兴趣",
            "discovery": "需求挖掘重点：SPIN提问、深度倾听",
            "presentation": "方案呈现重点：价值导向、差异化",
            "objection": "异议处理重点：同理心、证据支撑",
            "closing": "成交阶段重点：时机把握、行动推动",
        }

        # Find matching stage
        for key, suggestion in stage_suggestions.items():
            if key in stage.lower() or stage.lower() in key:
                return f"当前阶段提示：{suggestion}"

        return ""

    def clear_session_state(self, session_id: str) -> None:
        """Clear score state for a session (call when session ends).

        Args:
            session_id: Session ID to clear
        """
        if session_id in self._score_states:
            del self._score_states[session_id]
            logger.info("realtime_scoring_state_cleared", session_id=session_id)

    def get_session_summary(self, session_id: str) -> dict[str, Any] | None:
        """Get scoring summary for a session.

        Args:
            session_id: Session ID

        Returns:
            Session summary or None if not found
        """
        state = self._score_states.get(session_id)
        if not state:
            return None

        trend = state.get_score_trend()

        return {
            "session_id": session_id,
            "final_score": round(state.current_overall, 1),
            "dimension_scores": {
                dim: round(sum(scores) / len(scores), 1) if scores else 0
                for dim, scores in state.dimension_history.items()
            },
            "total_turns": len(state.turn_scores),
            "trend": trend,
            "last_update": state.last_update.isoformat(),
        }

    async def save_scoring_context(
        self,
        session_id: str,
        db_session: Any | None = None,
    ) -> Result[dict[str, Any]]:
        """Save scoring context to database for report generation.

        This method persists the realtime scoring data to the database
        so that Track F's report generation can access it.

        Args:
            session_id: Session ID
            db_session: Optional database session (if not provided, uses in-memory only)

        Returns:
            Result with saved scoring context data

        Data Contract:
            {
                "session_id": str,
                "final_score": float,
                "dimension_scores": dict[str, float],
                "total_turns": int,
                "trend": {"direction": str, "change_rate": float},
                "scoring_history": list[dict],
                "stored_at": str (ISO timestamp)
            }
        """
        try:
            # Get current scoring summary
            summary = self.get_session_summary(session_id)
            if not summary:
                return Result.fail(f"[SCORING_CONTEXT_NOT_FOUND] No scoring data for session {session_id}")

            # Get full state for scoring history
            state = self._score_states.get(session_id)
            if state:
                summary["scoring_history"] = state.turn_scores
            else:
                summary["scoring_history"] = []

            summary["stored_at"] = datetime.now(timezone.utc).isoformat()

            # If database session provided, persist to database
            if db_session is not None:
                try:
                    from sqlalchemy import select
                    from common.db.models import PracticeSession

                    # Update session with scoring data
                    result = await db_session.execute(
                        select(PracticeSession).where(PracticeSession.session_id == session_id)
                    )
                    session = result.scalar_one_or_none()

                    if session:
                        # Store scoring context in voice_policy_snapshot or create dedicated field
                        # For now, we store it in a way that Track F can retrieve
                        scoring_context = {
                            "realtime_scores": {
                                "final_score": summary["final_score"],
                                "dimension_scores": summary["dimension_scores"],
                                "total_turns": summary["total_turns"],
                                "trend": summary["trend"],
                                "scoring_history": summary["scoring_history"],
                                "stored_at": summary["stored_at"],
                            }
                        }

                        # Merge with existing snapshot if present
                        existing_snapshot = session.voice_policy_snapshot or {}
                        if isinstance(existing_snapshot, dict):
                            existing_snapshot.update(scoring_context)
                        else:
                            existing_snapshot = scoring_context

                        session.voice_policy_snapshot = existing_snapshot
                        await db_session.commit()

                        logger.info(
                            "scoring_context_saved_to_db",
                            session_id=session_id,
                            final_score=summary["final_score"],
                        )
                    else:
                        logger.warning(
                            "session_not_found_for_scoring_context",
                            session_id=session_id,
                        )

                except Exception as e:
                    logger.error(
                        "failed_to_save_scoring_context_to_db",
                        session_id=session_id,
                        error=str(e),
                    )
                    # Don't fail - return in-memory data even if DB save fails

            logger.info(
                "scoring_context_saved",
                session_id=session_id,
                final_score=summary["final_score"],
                total_turns=summary["total_turns"],
            )

            return Result.ok(summary)

        except Exception as e:
            logger.error(
                "save_scoring_context_error",
                session_id=session_id,
                error=str(e),
            )
            return Result.fail(f"[SAVE_SCORING_CONTEXT_ERROR:{str(e)}]")

    @classmethod
    async def get_scoring_context_from_db(
        cls,
        session_id: str,
        db_session: Any,
    ) -> Result[dict[str, Any]]:
        """Retrieve scoring context from database for report generation.

        This is a class method that Track F can use to fetch scoring data
        without needing an instance of RealtimeScoringService.

        Args:
            session_id: Session ID
            db_session: Database session

        Returns:
            Result with scoring context data
        """
        try:
            from sqlalchemy import select
            from common.db.models import PracticeSession

            result = await db_session.execute(
                select(PracticeSession).where(PracticeSession.session_id == session_id)
            )
            session = result.scalar_one_or_none()

            if not session:
                return Result.fail(f"[SESSION_NOT_FOUND] {session_id}")

            snapshot = session.voice_policy_snapshot or {}
            if isinstance(snapshot, dict) and "realtime_scores" in snapshot:
                return Result.ok(snapshot["realtime_scores"])

            return Result.fail("[SCORING_CONTEXT_NOT_FOUND] No realtime scoring data available")

        except Exception as e:
            logger.error(
                "get_scoring_context_from_db_error",
                session_id=session_id,
                error=str(e),
            )
            return Result.fail(f"[GET_SCORING_CONTEXT_ERROR:{str(e)}]")
