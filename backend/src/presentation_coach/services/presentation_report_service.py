"""Presentation-specific comprehensive report builder."""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    ConversationMessage,
    ForbiddenWord,
    InterruptionEvent,
    Page,
    PracticeSession,
    RequiredTalkingPoint,
)
from common.effectiveness.scoring_rulesets import (
    ScoringRulesetService,
    ScoringRulesetView,
)
from common.error_handling.result import Result
from common.monitoring.logger import get_logger

logger = get_logger(__name__)


def _clamp_score(value: float) -> float:
    return round(max(0.0, min(100.0, value)), 1)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().lower())


class PresentationReportService:
    """Build deterministic six-dimension report for PPT coaching sessions."""

    DIMENSION_WEIGHTS: tuple[tuple[str, float], ...] = (
        ("流畅连贯性", 0.22),
        ("准确性", 0.20),
        ("专业性", 0.18),
        ("生动性", 0.14),
        ("互动问答", 0.12),
        ("其他表现", 0.14),
    )
    FILLER_TERMS = (
        "嗯",
        "呃",
        "啊",
        "这个",
        "那个",
        "就是",
        "然后",
        "然后呢",
        "其实",
        "怎么说呢",
    )
    PROFESSIONAL_TERMS = (
        "架构",
        "接口",
        "数据",
        "平台",
        "系统",
        "方案",
        "模块",
        "权限",
        "集成",
        "流程",
        "部署",
        "api",
        "知识库",
        "rag",
        "向量",
        "推理",
        "模型",
        "私有化",
        "saas",
        "实施",
        "上线",
        "治理",
        "指标",
    )
    VIVID_TERMS = (
        "比如",
        "例如",
        "举个例子",
        "案例",
        "客户",
        "故事",
        "场景",
        "就像",
        "相当于",
        "打个比方",
    )
    INTERACTION_TERMS = (
        "大家可以想象",
        "你可能会问",
        "我们会问自己",
        "是不是",
        "有没有",
        "会不会",
        "为什么",
        "设想一下",
        "如果你是",
    )

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def build_report(self, session_id: str) -> Result[Any]:
        from evaluation.services.comprehensive_report import (
            ComprehensiveReport,
            DimensionScore,
        )

        try:
            review_result = await self.build_presentation_review(session_id)
            if not review_result.is_success or review_result.value is None:
                return Result.fail(
                    review_result.fallback or "[PRESENTATION_REPORT_FAILED]"
                )

            context_result = await self._load_report_context(session_id)
            if not context_result.is_success or context_result.value is None:
                return Result.fail(
                    context_result.fallback or "[PRESENTATION_SESSION_NOT_FOUND]"
                )

            review = review_result.value
            session: PracticeSession = context_result.value["session"]
            scoring_metadata = review.get("scoring_ruleset")
            if not isinstance(scoring_metadata, dict):
                scoring_metadata = None
            dimension_scores = [
                DimensionScore(
                    name=item["name"],
                    score=item["score"],
                    weight=item["weight"],
                    description=item["description"],
                    dimension_id=item.get("dimension_id"),
                )
                for item in review["dimension_scores"]
            ]
            dimension_values = {
                item["name"]: item["score"] for item in review["dimension_scores"]
            }

            session.logic_score = dimension_values.get("流畅连贯性", 0.0)
            session.accuracy_score = dimension_values.get("准确性", 0.0)
            session.completeness_score = round(
                (
                    dimension_values.get("专业性", 0.0)
                    + dimension_values.get("生动性", 0.0)
                    + dimension_values.get("互动问答", 0.0)
                    + dimension_values.get("其他表现", 0.0)
                )
                / 4,
                1,
            )
            await self.db.flush()

            report = ComprehensiveReport(
                session_id=session_id,
                generated_at=datetime.now(UTC),
                overall_score=review["overall_score"],
                dimension_scores=dimension_scores,
                stage_summaries=review["page_summaries"],
                key_strengths=review["strengths"],
                key_improvements=review["improvements"],
                detailed_feedback=review["detailed_feedback"],
                recommendations=review["recommendations"],
                ruleset_id=(
                    scoring_metadata.get("ruleset_id") if scoring_metadata else None
                ),
                ruleset_version=(
                    scoring_metadata.get("version") if scoring_metadata else None
                ),
                score_basis=(
                    scoring_metadata.get("score_basis") if scoring_metadata else None
                ),
                ruleset_source=(
                    scoring_metadata.get("source") if scoring_metadata else None
                ),
                scoring_metadata=scoring_metadata,
            )
            return Result.ok(report)
        except Exception as exc:  # noqa: BLE001
            return Result.fail(f"[PRESENTATION_REPORT_BUILD_FAILED:{exc}]")

    async def build_presentation_review(
        self,
        session_id: str,
    ) -> Result[dict[str, Any]]:
        try:
            context_result = await self._load_report_context(session_id)
            if not context_result.is_success or context_result.value is None:
                return Result.fail(
                    context_result.fallback or "[PRESENTATION_SESSION_NOT_FOUND]"
                )
            scoring_ruleset = await self._resolve_scoring_ruleset_view()
            return Result.ok(
                self._build_presentation_review_payload(
                    **context_result.value,
                    scoring_ruleset=scoring_ruleset,
                )
            )
        except Exception as exc:  # noqa: BLE001
            return Result.fail(f"[PRESENTATION_REVIEW_BUILD_FAILED:{exc}]")

    async def _resolve_scoring_ruleset_view(self) -> ScoringRulesetView:
        try:
            return await ScoringRulesetService(self.db).get_active_or_default(
                "presentation"
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "presentation_report_scoring_ruleset_fallback_default",
                error=str(exc),
            )
            return ScoringRulesetService.build_default_view("presentation")

    async def _load_report_context(self, session_id: str) -> Result[dict[str, Any]]:
        session_result = await self.db.execute(
            select(PracticeSession).where(PracticeSession.session_id == session_id)
        )
        session = session_result.scalar_one_or_none()
        if session is None or not session.presentation_id:
            return Result.fail("[PRESENTATION_SESSION_NOT_FOUND]")

        message_result = await self.db.execute(
            select(ConversationMessage)
            .where(
                ConversationMessage.session_id == session_id,
                ConversationMessage.role == "user",
            )
            .order_by(ConversationMessage.turn_number, ConversationMessage.timestamp)
        )
        user_messages = list(message_result.scalars().all())
        if not user_messages:
            return Result.fail("[NO_PRESENTATION_TRANSCRIPTS]")

        events_result = await self.db.execute(
            select(InterruptionEvent)
            .where(InterruptionEvent.session_id == session_id)
            .order_by(InterruptionEvent.timestamp)
        )
        interruption_events = list(events_result.scalars().all())

        pages_result = await self.db.execute(
            select(Page)
            .where(Page.presentation_id == session.presentation_id)
            .order_by(Page.page_number)
        )
        pages = list(pages_result.scalars().all())
        page_ids = [str(getattr(page, "page_id", "") or "") for page in pages]
        page_number_by_id = {
            str(getattr(page, "page_id", "") or ""): int(
                cast(int, getattr(page, "page_number", 0)) or 0
            )
            for page in pages
        }

        required_points_by_page: dict[int, list[str]] = defaultdict(list)
        if page_ids:
            points_result = await self.db.execute(
                select(RequiredTalkingPoint)
                .where(RequiredTalkingPoint.page_id.in_(page_ids))
                .where(RequiredTalkingPoint.confirmed_by_admin.is_(True))
            )
            for point in list(points_result.scalars().all()):
                point_page_id = cast(str | None, getattr(point, "page_id", None))
                if point_page_id is None:
                    continue
                page_number = page_number_by_id.get(point_page_id)
                if page_number is None:
                    continue
                description = str(getattr(point, "description", "") or "")
                required_points_by_page[page_number].append(description)

        forbidden_words_by_page: dict[int, list[str]] = defaultdict(list)
        global_forbidden_words: list[str] = []
        if session.presentation_id:
            forbidden_words_stmt = select(ForbiddenWord).where(
                ForbiddenWord.presentation_id == session.presentation_id
            )
            if page_ids:
                forbidden_words_stmt = select(ForbiddenWord).where(
                    (ForbiddenWord.presentation_id == session.presentation_id)
                    | (ForbiddenWord.page_id.in_(page_ids))
                )
            forbidden_words_result = await self.db.execute(forbidden_words_stmt)
            for forbidden_word in list(forbidden_words_result.scalars().all()):
                phrase = str(getattr(forbidden_word, "phrase", "") or "").strip()
                if not phrase:
                    continue
                forbidden_page_id = cast(
                    str | None, getattr(forbidden_word, "page_id", None)
                )
                page_number = (
                    page_number_by_id.get(forbidden_page_id)
                    if forbidden_page_id is not None
                    else None
                )
                if page_number is None:
                    global_forbidden_words.append(phrase)
                else:
                    forbidden_words_by_page[page_number].append(phrase)

        return Result.ok(
            {
                "session": session,
                "user_messages": user_messages,
                "interruption_events": interruption_events,
                "total_pages": max(1, len(pages)),
                "required_points_by_page": required_points_by_page,
                "forbidden_words_by_page": forbidden_words_by_page,
                "global_forbidden_words": global_forbidden_words,
            }
        )

    def _build_presentation_review_payload(
        self,
        *,
        session: PracticeSession,
        user_messages: list[ConversationMessage],
        interruption_events: list[InterruptionEvent],
        total_pages: int,
        required_points_by_page: dict[int, list[str]],
        forbidden_words_by_page: dict[int, list[str]],
        global_forbidden_words: list[str],
        scoring_ruleset: ScoringRulesetView | None = None,
    ) -> dict[str, Any]:
        normalized_texts = [
            _normalize_text(str(getattr(message, "content", "") or ""))
            for message in user_messages
        ]
        combined_text = "".join(normalized_texts)

        message_page_numbers = [
            self._extract_page_number(
                message.transcript_metadata
                if isinstance(message.transcript_metadata, dict)
                else None
            )
            for message in user_messages
        ]
        explicit_page_numbers = [
            page_number
            for page_number in message_page_numbers
            if page_number is not None
        ]
        has_page_metadata = bool(message_page_numbers) and all(
            page_number is not None for page_number in message_page_numbers
        )
        scoring_page_numbers = [
            page_number if page_number is not None else 1
            for page_number in message_page_numbers
        ] or [1]
        pages_with_messages = (
            len(set(explicit_page_numbers)) if explicit_page_numbers else 0
        )
        scoring_page_coverage_ratio = round(
            len(set(scoring_page_numbers)) / max(1, total_pages),
            4,
        )
        diagnostic_page_coverage_ratio = round(
            pages_with_messages / max(1, total_pages),
            4,
        )

        coverage = self._build_required_point_coverage(
            normalized_texts=normalized_texts,
            combined_text=combined_text,
            user_messages=user_messages,
            message_page_numbers=message_page_numbers,
            required_points_by_page=required_points_by_page,
            has_page_metadata=has_page_metadata,
        )

        issue_counts = {
            "forbidden_word": sum(
                1
                for event in interruption_events
                if event.interruption_type == "forbidden_word"
            ),
            "missing_point": sum(
                1
                for event in interruption_events
                if event.interruption_type == "missing_point"
            ),
            "vague_response": sum(
                1
                for event in interruption_events
                if event.interruption_type == "vague_response"
            ),
        }
        degraded_reasons = [] if has_page_metadata else ["missing_page_metadata"]
        coverage_status = "complete" if has_page_metadata else "degraded"

        metrics = self._build_metrics(
            session=session,
            user_messages=user_messages,
            normalized_texts=normalized_texts,
            combined_text=combined_text,
            page_coverage_ratio=scoring_page_coverage_ratio,
            required_coverage_ratio=coverage["coverage_ratio"],
            forbidden_count=issue_counts["forbidden_word"],
            missing_count=issue_counts["missing_point"],
            vague_count=issue_counts["vague_response"],
        )

        dimension_weight_pairs = self._dimension_weight_pairs(scoring_ruleset)
        dimension_scores = [
            {
                "name": name,
                "dimension_id": dimension_id,
                "score": metrics["dimension_values"][name],
                "weight": weight,
                "description": self._dimension_description(name),
            }
            for dimension_id, name, weight in dimension_weight_pairs
        ]
        overall_score = round(
            sum(item["score"] * item["weight"] for item in dimension_scores)
            / sum(item["weight"] for item in dimension_scores),
            1,
        )

        issue_clusters_by_page = self._build_page_issue_clusters(
            user_messages=user_messages,
            normalized_texts=normalized_texts,
            message_page_numbers=message_page_numbers,
            interruption_events=interruption_events,
            coverage=coverage,
            required_points_by_page=required_points_by_page,
            forbidden_words_by_page=forbidden_words_by_page,
            global_forbidden_words=global_forbidden_words,
            has_page_metadata=has_page_metadata,
        )
        page_issue_diagnostics = self._build_page_issue_diagnostics(
            issue_clusters_by_page
        )

        page_summaries = self._build_page_summaries(
            user_messages=user_messages,
            message_page_numbers=message_page_numbers,
            total_pages=total_pages,
            coverage=coverage,
            issue_clusters_by_page=issue_clusters_by_page,
            has_page_metadata=has_page_metadata,
        )
        strengths = self._build_strengths(
            metrics["dimension_values"],
            metrics,
            has_page_metadata=has_page_metadata,
        )
        improvements = self._build_improvements(
            metrics["dimension_values"],
            metrics,
            has_page_metadata=has_page_metadata,
        )
        recommendations = self._build_recommendations(
            metrics["dimension_values"],
            metrics,
            has_page_metadata=has_page_metadata,
        )
        detailed_feedback = self._build_detailed_feedback(
            overall_score=overall_score,
            metrics=metrics,
            strengths=strengths,
            improvements=improvements,
            has_page_metadata=has_page_metadata,
        )

        return {
            "overall_score": overall_score,
            "dimension_scores": dimension_scores,
            "page_summaries": page_summaries,
            "required_talking_points": {
                "status": coverage_status,
                "total": coverage["total"],
                "covered": coverage["covered"],
                "missing": coverage["missing"],
                "coverage_ratio": coverage["coverage_ratio"],
            },
            "issue_counts": issue_counts,
            "strengths": strengths,
            "improvements": improvements,
            "recommendations": recommendations,
            "detailed_feedback": detailed_feedback,
            "has_page_metadata": has_page_metadata,
            "coverage_status": coverage_status,
            "diagnostics": {
                "has_page_metadata": has_page_metadata,
                "pages_with_messages": pages_with_messages,
                "total_pages": total_pages,
                "page_coverage_ratio": diagnostic_page_coverage_ratio,
                "required_points_total": coverage["total"],
                "required_points_covered": coverage["covered"],
                "required_points_missing": coverage["missing"],
                "required_coverage_ratio": coverage["coverage_ratio"],
                "degraded_reasons": degraded_reasons,
                "page_issue_cluster_count": page_issue_diagnostics[
                    "page_issue_cluster_count"
                ],
                "page_issue_types": page_issue_diagnostics["page_issue_types"],
            },
            "scoring_ruleset": (
                ScoringRulesetService.report_metadata_for_view(scoring_ruleset)
                if scoring_ruleset is not None
                else None
            ),
        }

    @classmethod
    def _dimension_weight_pairs(
        cls,
        scoring_ruleset: ScoringRulesetView | None,
    ) -> tuple[tuple[str | None, str, float], ...]:
        if scoring_ruleset is None:
            return tuple((None, name, weight) for name, weight in cls.DIMENSION_WEIGHTS)
        total_weight = sum(
            max(0.0, float(dimension.weight))
            for dimension in scoring_ruleset.definition.dimensions
        )
        if total_weight <= 0:
            return tuple((None, name, weight) for name, weight in cls.DIMENSION_WEIGHTS)
        return tuple(
            (
                dimension.dimension_id,
                dimension.label,
                round(float(dimension.weight) / total_weight, 4),
            )
            for dimension in scoring_ruleset.definition.dimensions
        )

    def _build_metrics(
        self,
        *,
        session: PracticeSession,
        user_messages: list[ConversationMessage],
        normalized_texts: list[str],
        combined_text: str,
        page_coverage_ratio: float,
        required_coverage_ratio: float,
        forbidden_count: int,
        missing_count: int,
        vague_count: int,
    ) -> dict[str, Any]:
        total_chars = sum(len(text) for text in normalized_texts)
        filler_count = sum(combined_text.count(term) for term in self.FILLER_TERMS)
        professional_hits = sum(
            combined_text.count(term) for term in self.PROFESSIONAL_TERMS
        )
        vivid_hits = sum(combined_text.count(term) for term in self.VIVID_TERMS)
        interaction_term_hits = sum(
            combined_text.count(term) for term in self.INTERACTION_TERMS
        )
        question_count = sum(
            message.content.count("?") + message.content.count("？")
            for message in user_messages
        )

        duplicate_messages = 0
        previous_text = ""
        for text in normalized_texts:
            if text and text == previous_text:
                duplicate_messages += 1
            previous_text = text

        duration_minutes = 0.0
        if session.start_time and session.end_time:
            duration_minutes = max(
                0.0,
                (session.end_time - session.start_time).total_seconds() / 60.0,
            )

        dimension_values = {
            "流畅连贯性": _clamp_score(
                90
                - filler_count * 2.4
                - duplicate_messages * 8
                - vague_count * 4
                - (10 if total_chars < 600 else 0)
            ),
            "准确性": _clamp_score(
                92
                - forbidden_count * 14
                - vague_count * 5
                - missing_count * 3
                + required_coverage_ratio * 6
            ),
            "专业性": _clamp_score(
                58
                + min(24, professional_hits * 3.5)
                + required_coverage_ratio * 12
                + page_coverage_ratio * 6
                - vague_count * 3
            ),
            "生动性": _clamp_score(
                52 + min(30, vivid_hits * 8) + min(8, page_coverage_ratio * 8)
            ),
            "互动问答": _clamp_score(
                45 + min(28, interaction_term_hits * 9) + min(18, question_count * 5)
            ),
            "其他表现": _clamp_score(
                60
                + min(12, page_coverage_ratio * 12)
                + min(10, required_coverage_ratio * 10)
                + (8 if duration_minutes >= 10 else 3 if duration_minutes > 0 else 0)
                - forbidden_count * 4
            ),
        }

        return {
            "total_chars": total_chars,
            "filler_count": filler_count,
            "professional_hits": professional_hits,
            "vivid_hits": vivid_hits,
            "interaction_term_hits": interaction_term_hits,
            "question_count": question_count,
            "duplicate_messages": duplicate_messages,
            "page_coverage_ratio": page_coverage_ratio,
            "required_coverage_ratio": required_coverage_ratio,
            "forbidden_count": forbidden_count,
            "missing_count": missing_count,
            "vague_count": vague_count,
            "duration_minutes": round(duration_minutes, 1),
            "dimension_values": dimension_values,
        }

    def _build_required_point_coverage(
        self,
        *,
        normalized_texts: list[str],
        combined_text: str,
        user_messages: list[ConversationMessage],
        message_page_numbers: list[int | None],
        required_points_by_page: dict[int, list[str]],
        has_page_metadata: bool,
    ) -> dict[str, Any]:
        total = sum(len(points) for points in required_points_by_page.values())
        covered = 0
        matched_by_page: dict[int, list[str]] = defaultdict(list)
        missing_by_page: dict[int, list[str]] = defaultdict(list)

        if has_page_metadata:
            page_text_by_page: dict[int, str] = defaultdict(str)
            for index, page_number in enumerate(message_page_numbers):
                if page_number is None:
                    continue
                page_text_by_page[page_number] += normalized_texts[index]

            for page_number, points in required_points_by_page.items():
                page_text = page_text_by_page.get(page_number, "")
                for point in points:
                    if self._matches_required_point(point, page_text):
                        covered += 1
                        matched_by_page[page_number].append(point)
                    else:
                        missing_by_page[page_number].append(point)
        else:
            for page_number, points in required_points_by_page.items():
                for point in points:
                    if self._matches_required_point(point, combined_text):
                        covered += 1
                        matched_by_page[page_number].append(point)
                    else:
                        missing_by_page[page_number].append(point)

        missing = max(0, total - covered)
        coverage_ratio = round((covered / total) if total else 1.0, 4)
        return {
            "status": "complete" if has_page_metadata else "degraded",
            "total": total,
            "covered": covered,
            "missing": missing,
            "coverage_ratio": coverage_ratio,
            "matched_by_page": dict(matched_by_page),
            "missing_by_page": dict(missing_by_page),
        }

    @staticmethod
    def _build_issue_cluster(
        *,
        issue_type: str,
        summary: str,
        evidence: list[str],
        turn_numbers: list[int],
        linked_points: list[str] | None = None,
        linked_phrases: list[str] | None = None,
        related_page_numbers: list[int] | None = None,
    ) -> dict[str, Any]:
        return {
            "issue_type": issue_type,
            "summary": summary,
            "evidence": evidence,
            "turn_numbers": turn_numbers,
            "linked_points": linked_points or [],
            "linked_phrases": linked_phrases or [],
            "related_page_numbers": related_page_numbers or [],
        }

    @staticmethod
    def _build_page_issue_diagnostics(
        issue_clusters_by_page: dict[int, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        issue_types = sorted(
            {
                str(issue.get("issue_type"))
                for issues in issue_clusters_by_page.values()
                for issue in issues
                if isinstance(issue, dict) and issue.get("issue_type")
            }
        )
        return {
            "page_issue_cluster_count": sum(
                len(issues) for issues in issue_clusters_by_page.values()
            ),
            "page_issue_types": issue_types,
        }

    @classmethod
    def _resolve_event_page_number(
        cls,
        *,
        trigger_content: str,
        user_messages: list[ConversationMessage],
        normalized_texts: list[str],
        message_page_numbers: list[int | None],
    ) -> int | None:
        normalized_trigger = _normalize_text(trigger_content)
        if normalized_trigger:
            for message, normalized_text, page_number in zip(
                user_messages,
                normalized_texts,
                message_page_numbers,
                strict=False,
            ):
                if page_number is None:
                    continue
                if (
                    normalized_trigger in normalized_text
                    or normalized_text in normalized_trigger
                ):
                    return max(1, page_number)
                message_content = str(getattr(message, "content", "") or "")
                if trigger_content and trigger_content in message_content:
                    return max(1, page_number)
        explicit_pages = [
            page_number
            for page_number in message_page_numbers
            if page_number is not None
        ]
        if len(set(explicit_pages)) == 1:
            return explicit_pages[0]
        return None

    @classmethod
    def _map_interruption_events_to_pages(
        cls,
        *,
        interruption_events: list[InterruptionEvent],
        user_messages: list[ConversationMessage],
        normalized_texts: list[str],
        message_page_numbers: list[int | None],
    ) -> dict[str, dict[int, list[dict[str, Any]]]]:
        event_map: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(list)
        )

        for event in interruption_events:
            interruption_type = str(
                getattr(event, "interruption_type", "") or ""
            ).strip()
            if not interruption_type:
                continue
            trigger_content = str(getattr(event, "trigger_content", "") or "").strip()
            page_number = cls._resolve_event_page_number(
                trigger_content=trigger_content,
                user_messages=user_messages,
                normalized_texts=normalized_texts,
                message_page_numbers=message_page_numbers,
            )
            if page_number is None:
                continue

            matched_turn_numbers: list[int] = []
            normalized_trigger = _normalize_text(trigger_content)
            for message, normalized_text, message_page in zip(
                user_messages,
                normalized_texts,
                message_page_numbers,
                strict=False,
            ):
                if message_page != page_number:
                    continue
                if not normalized_trigger:
                    continue
                if (
                    normalized_trigger in normalized_text
                    or normalized_text in normalized_trigger
                ):
                    matched_turn_numbers.append(int(message.turn_number))

            if not matched_turn_numbers:
                matched_turn_numbers = [
                    int(message.turn_number)
                    for message, message_page in zip(
                        user_messages,
                        message_page_numbers,
                        strict=False,
                    )
                    if message_page == page_number
                ][:1]

            event_map[interruption_type][page_number].append(
                {
                    "trigger_content": trigger_content,
                    "turn_numbers": sorted(set(matched_turn_numbers)),
                }
            )

        return {
            issue_type: {page: list(items) for page, items in pages.items()}
            for issue_type, pages in event_map.items()
        }

    def _build_page_issue_clusters(
        self,
        *,
        user_messages: list[ConversationMessage],
        normalized_texts: list[str],
        message_page_numbers: list[int | None],
        interruption_events: list[InterruptionEvent],
        coverage: dict[str, Any],
        required_points_by_page: dict[int, list[str]],
        forbidden_words_by_page: dict[int, list[str]],
        global_forbidden_words: list[str],
        has_page_metadata: bool,
    ) -> dict[int, list[dict[str, Any]]]:
        if not has_page_metadata:
            return {}

        grouped_messages: dict[int, list[tuple[ConversationMessage, str]]] = (
            defaultdict(list)
        )
        for message, normalized_text, page_number in zip(
            user_messages,
            normalized_texts,
            message_page_numbers,
            strict=False,
        ):
            if page_number is None:
                continue
            grouped_messages[max(1, page_number)].append((message, normalized_text))

        event_map = self._map_interruption_events_to_pages(
            interruption_events=interruption_events,
            user_messages=user_messages,
            normalized_texts=normalized_texts,
            message_page_numbers=message_page_numbers,
        )
        issue_clusters_by_page: dict[int, list[dict[str, Any]]] = defaultdict(list)

        for page_number in sorted(grouped_messages.keys()):
            message_pairs = grouped_messages[page_number]
            matched_points = list(coverage["matched_by_page"].get(page_number, []))
            missing_points = list(coverage["missing_by_page"].get(page_number, []))
            page_turn_numbers = sorted(
                {int(message.turn_number) for message, _ in message_pairs}
            )

            off_page_points: dict[int, set[str]] = defaultdict(set)
            off_page_turns: set[int] = set()
            for message, normalized_text in message_pairs:
                for target_page_number, points in required_points_by_page.items():
                    if target_page_number == page_number:
                        continue
                    for point in points:
                        if self._matches_required_point(point, normalized_text):
                            off_page_points[target_page_number].add(point)
                            off_page_turns.add(int(message.turn_number))
            if off_page_points:
                related_pages = sorted(off_page_points.keys())
                linked_points = sorted(
                    {point for points in off_page_points.values() for point in points}
                )
                evidence = [
                    f"第 {target_page_number} 页要点：{', '.join(sorted(points))}"
                    for target_page_number, points in sorted(off_page_points.items())
                ]
                issue_clusters_by_page[page_number].append(
                    self._build_issue_cluster(
                        issue_type="off_page",
                        summary=(
                            f"第 {page_number} 页讲解带到了其他页内容，"
                            f"优先回到当前页要点。"
                        ),
                        evidence=evidence,
                        turn_numbers=sorted(off_page_turns),
                        linked_points=linked_points,
                        related_page_numbers=related_pages,
                    )
                )

            page_forbidden_words = list(
                dict.fromkeys(
                    [
                        *forbidden_words_by_page.get(page_number, []),
                        *global_forbidden_words,
                    ]
                )
            )
            matched_phrases: set[str] = set()
            forbidden_turns: set[int] = set()
            for message, normalized_text in message_pairs:
                for phrase in page_forbidden_words:
                    normalized_phrase = _normalize_text(phrase)
                    if normalized_phrase and normalized_phrase in normalized_text:
                        matched_phrases.add(phrase)
                        forbidden_turns.add(int(message.turn_number))
            if matched_phrases:
                issue_clusters_by_page[page_number].append(
                    self._build_issue_cluster(
                        issue_type="forbidden_word",
                        summary=(
                            f"第 {page_number} 页触发了禁忌表达，"
                            "建议改成更稳妥、可验证的说法。"
                        ),
                        evidence=[
                            f"触发短语：{phrase}" for phrase in sorted(matched_phrases)
                        ],
                        turn_numbers=sorted(forbidden_turns),
                        linked_phrases=sorted(matched_phrases),
                    )
                )

            if missing_points:
                issue_clusters_by_page[page_number].append(
                    self._build_issue_cluster(
                        issue_type="missing_point",
                        summary=(
                            f"第 {page_number} 页仍缺少 {len(missing_points)} 个必讲点，"
                            "需要补齐再进入下一页。"
                        ),
                        evidence=[f"未覆盖：{point}" for point in missing_points],
                        turn_numbers=page_turn_numbers,
                        linked_points=missing_points,
                    )
                )

            required_points = list(required_points_by_page.get(page_number, []))
            page_char_count = sum(
                len(normalized_text) for _, normalized_text in message_pairs
            )
            long_turn_numbers = sorted(
                {
                    int(message.turn_number)
                    for message, normalized_text in message_pairs
                    if len(normalized_text) >= 60
                }
            )
            coverage_ratio = (
                len(matched_points) / len(required_points) if required_points else 1.0
            )
            if (
                required_points
                and long_turn_numbers
                and page_char_count >= 80
                and coverage_ratio < 0.75
            ):
                issue_clusters_by_page[page_number].append(
                    self._build_issue_cluster(
                        issue_type="overlong_explanation",
                        summary=(
                            f"第 {page_number} 页展开偏长，"
                            f"但当前页 {len(required_points)} 个要点只覆盖了 {len(matched_points)} 个。"
                        ),
                        evidence=[
                            f"累计讲解约 {page_char_count} 个字，优先压缩到当前页必讲点。"
                        ],
                        turn_numbers=long_turn_numbers,
                        linked_points=required_points,
                    )
                )

            vague_events = event_map.get("vague_response", {}).get(page_number, [])
            if vague_events:
                turn_numbers = sorted(
                    {
                        int(turn_number)
                        for event in vague_events
                        for turn_number in event.get("turn_numbers", [])
                    }
                )
                evidence = [
                    str(event.get("trigger_content") or "").strip()
                    for event in vague_events
                    if str(event.get("trigger_content") or "").strip()
                ]
                issue_clusters_by_page[page_number].append(
                    self._build_issue_cluster(
                        issue_type="weak_qa_handling",
                        summary=(
                            f"第 {page_number} 页的问答承接偏弱，"
                            "需要把追问回答得更具体。"
                        ),
                        evidence=evidence,
                        turn_numbers=turn_numbers,
                    )
                )

        return {
            page_number: list(issues)
            for page_number, issues in issue_clusters_by_page.items()
        }

    def _build_page_summaries(
        self,
        *,
        user_messages: list[ConversationMessage],
        message_page_numbers: list[int | None],
        total_pages: int,
        coverage: dict[str, Any],
        issue_clusters_by_page: dict[int, list[dict[str, Any]]],
        has_page_metadata: bool,
    ) -> list[dict[str, Any]]:
        if not has_page_metadata:
            return []

        grouped_messages: dict[int, list[ConversationMessage]] = defaultdict(list)
        for message, page_number in zip(
            user_messages, message_page_numbers, strict=False
        ):
            if page_number is None:
                continue
            grouped_messages[max(1, page_number)].append(message)

        summaries: list[dict[str, Any]] = []
        for page_number in sorted(grouped_messages.keys()):
            messages = grouped_messages[page_number]
            matched_points = list(coverage["matched_by_page"].get(page_number, []))
            missing_points = list(coverage["missing_by_page"].get(page_number, []))
            combined_page_text = "".join(
                _normalize_text(str(getattr(message, "content", "") or ""))
                for message in messages
            )
            page_content = "".join(
                str(getattr(message, "content", "") or "") for message in messages
            )
            avg_score = _clamp_score(
                58
                + min(18, len(combined_page_text) / 80)
                + min(12, len(matched_points) * 6)
                + (8 if ("?" in page_content or "？" in page_content) else 0)
            )
            summaries.append(
                {
                    "page_number": min(page_number, total_pages),
                    "stage_number": min(page_number, total_pages),
                    "start_turn": min(message.turn_number for message in messages),
                    "end_turn": max(message.turn_number for message in messages),
                    "average_score": avg_score,
                    "key_points": matched_points[:3],
                    "matched_required_points": matched_points,
                    "missing_required_points": missing_points,
                    "issue_clusters": list(issue_clusters_by_page.get(page_number, [])),
                    "summary": self._build_page_summary(
                        page_number=page_number,
                        messages=messages,
                        matched_points=matched_points,
                        missing_points=missing_points,
                    ),
                }
            )

        return summaries

    @staticmethod
    def _build_page_summary(
        *,
        page_number: int,
        messages: list[ConversationMessage],
        matched_points: list[str],
        missing_points: list[str],
    ) -> str:
        if matched_points and not missing_points:
            return (
                f"第 {page_number} 页讲解覆盖了 {len(matched_points)} 个核心要点，"
                "整体表达较完整。"
            )
        if matched_points and missing_points:
            return (
                f"第 {page_number} 页已覆盖 {len(matched_points)} 个关键点，"
                f"仍缺少 {len(missing_points)} 个要点可以继续补强。"
            )
        if len(messages) >= 2:
            return f"第 {page_number} 页有连续讲解，但核心要点覆盖仍可继续加强。"
        return f"第 {page_number} 页有讲解记录，建议补充更明确的关键点表达。"

    def _build_strengths(
        self,
        dimension_values: dict[str, float],
        metrics: dict[str, Any],
        *,
        has_page_metadata: bool,
    ) -> list[str]:
        strengths: list[str] = []
        for name, score in sorted(
            dimension_values.items(),
            key=lambda item: item[1],
            reverse=True,
        ):
            if score >= 78:
                strengths.append(f"{name}表现较强")
        if metrics["required_coverage_ratio"] >= 0.75:
            strengths.append("PPT 核心要点覆盖较完整")
        if metrics["professional_hits"] >= 4:
            strengths.append("讲解中体现出一定产品与技术术语")
        if not has_page_metadata:
            strengths.append("整场讲解记录仍可用于保留总分与整体建议")
        return strengths[:5] or ["整体讲解结构较稳定"]

    def _build_improvements(
        self,
        dimension_values: dict[str, float],
        metrics: dict[str, Any],
        *,
        has_page_metadata: bool,
    ) -> list[str]:
        improvements: list[str] = []
        for name, score in sorted(
            dimension_values.items(),
            key=lambda item: item[1],
        ):
            if score < 78:
                improvements.append(f"{name}还有提升空间")
        if metrics["filler_count"] >= 4:
            improvements.append("需要进一步减少口头语和重复衔接词")
        if metrics["required_coverage_ratio"] < 0.65:
            improvements.append("部分页面的关键点覆盖还不够完整")
        if not has_page_metadata:
            improvements.append(
                "历史记录缺少页码元数据，逐页总结与覆盖判断只能降级展示"
            )
        return improvements[:5] or ["可以继续增加更多案例与互动设计"]

    def _build_recommendations(
        self,
        dimension_values: dict[str, float],
        metrics: dict[str, Any],
        *,
        has_page_metadata: bool,
    ) -> list[str]:
        recommendations: list[str] = []
        if dimension_values["流畅连贯性"] < 80:
            recommendations.append(
                "按页做 60 秒小段脱稿复述训练，重点减少“嗯、然后、这个”等口头语。"
            )
        if dimension_values["准确性"] < 80:
            recommendations.append(
                "逐页对照石犀资料和讲稿自检一次，重点核对产品功能、版本和术语表述。"
            )
        if dimension_values["专业性"] < 80:
            recommendations.append(
                "每页至少补入 1 个产品术语或技术原理解释，再用通俗语言复述一遍。"
            )
        if dimension_values["生动性"] < 80:
            recommendations.append(
                "每 2-3 页补一个客户案例、业务场景或类比，提升讲解画面感。"
            )
        if dimension_values["互动问答"] < 80:
            recommendations.append(
                "每个主题段主动加入 1 个引导性问题或自问自答，带动听众参与。"
            )
        if metrics["required_coverage_ratio"] < 0.7:
            recommendations.append(
                "给每页整理 2-3 个必须讲到的关键词，演练时逐页打勾确认。"
            )
        if not has_page_metadata:
            recommendations.append(
                "后续请沿用支持页码落库的新版运行链路完成一轮翻页演练，补齐逐页证据。"
            )
        return recommendations[:6] or ["保持当前节奏，继续通过整场演练巩固表达稳定性。"]

    def _build_detailed_feedback(
        self,
        *,
        overall_score: float,
        metrics: dict[str, Any],
        strengths: list[str],
        improvements: list[str],
        has_page_metadata: bool,
    ) -> str:
        duration_text = (
            f"本次演讲训练累计约 {metrics['duration_minutes']:.1f} 分钟，"
            if metrics["duration_minutes"] > 0
            else "本次演讲训练已形成完整讲解记录，"
        )
        coverage_text = (
            f"关键点命中率约 {metrics['required_coverage_ratio'] * 100:.0f}%，"
            if has_page_metadata
            else "由于缺少页码元数据，逐页总结与要点覆盖按降级模式展示，"
        )
        return (
            f"{duration_text}综合得分 {overall_score:.1f} 分。"
            f"当前优势集中在：{'；'.join(strengths[:3])}。"
            f"需要优先改进的方向是：{'；'.join(improvements[:3])}。"
            f"从过程数据看，你覆盖了约 {metrics['page_coverage_ratio'] * 100:.0f}% 的页面，"
            f"{coverage_text}"
            f"口头语/重复触发约 {metrics['filler_count']} 次。"
        )

    @staticmethod
    def _extract_page_number(transcript_metadata: dict[str, Any] | None) -> int | None:
        if not isinstance(transcript_metadata, dict):
            return None
        raw_page_number = transcript_metadata.get("page_number")
        if raw_page_number is None:
            return None
        try:
            page_number = int(raw_page_number)
        except (TypeError, ValueError):
            return None
        return max(1, page_number)

    @staticmethod
    def _matches_required_point(point: str, text: str) -> bool:
        normalized_point = _normalize_text(point)
        if not normalized_point or not text:
            return False
        if normalized_point in text:
            return True
        short_anchor = normalized_point[: min(len(normalized_point), 8)]
        return bool(short_anchor and short_anchor in text)

    @staticmethod
    def _dimension_description(name: str) -> str:
        mapping = {
            "流畅连贯性": "讲解节奏、重复情况与口头语控制",
            "准确性": "内容与资料一致性、错误信息控制",
            "专业性": "产品术语、技术表达与专业可信度",
            "生动性": "案例、类比和故事化表达能力",
            "互动问答": "主动发问、自问自答与听众参与感",
            "其他表现": "普通话、通俗易懂性与整体吸引力",
        }
        return mapping.get(name, "")
