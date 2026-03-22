"""Presentation-specific comprehensive report builder."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.db.models import (
    ConversationMessage,
    InterruptionEvent,
    Page,
    PracticeSession,
    RequiredTalkingPoint,
)
from common.error_handling.result import Result


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

    async def build_report(self, session_id: str):
        from evaluation.services.comprehensive_report import (
            ComprehensiveReport,
            DimensionScore,
        )

        try:
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
            events = list(events_result.scalars().all())

            pages_result = await self.db.execute(
                select(Page)
                .where(Page.presentation_id == session.presentation_id)
                .order_by(Page.page_number)
            )
            pages = list(pages_result.scalars().all())
            page_ids = [page.page_id for page in pages]

            required_points_by_page: dict[int, list[str]] = defaultdict(list)
            if page_ids:
                point_result = await self.db.execute(
                    select(RequiredTalkingPoint)
                    .where(RequiredTalkingPoint.page_id.in_(page_ids))
                    .where(RequiredTalkingPoint.confirmed_by_admin.is_(True))
                )
                points = list(point_result.scalars().all())
                page_number_by_id = {page.page_id: page.page_number for page in pages}
                for point in points:
                    page_number = page_number_by_id.get(point.page_id)
                    if page_number is None:
                        continue
                    required_points_by_page[page_number].append(point.description)

            metrics = self._build_metrics(
                session=session,
                user_messages=user_messages,
                interruption_events=events,
                total_pages=max(1, len(pages)),
                required_points_by_page=required_points_by_page,
            )

            dimension_scores = [
                DimensionScore(
                    name=name,
                    score=metrics["dimension_values"][name],
                    weight=weight,
                    description=self._dimension_description(name),
                )
                for name, weight in self.DIMENSION_WEIGHTS
            ]

            overall_score = round(
                sum(item.score * item.weight for item in dimension_scores)
                / sum(item.weight for item in dimension_scores),
                1,
            )

            stage_summaries = self._build_stage_summaries(
                user_messages=user_messages,
                required_points_by_page=required_points_by_page,
                total_pages=max(1, len(pages)),
            )
            key_strengths = self._build_strengths(metrics["dimension_values"], metrics)
            key_improvements = self._build_improvements(
                metrics["dimension_values"],
                metrics,
            )
            recommendations = self._build_recommendations(
                metrics["dimension_values"],
                metrics,
            )
            detailed_feedback = self._build_detailed_feedback(
                overall_score=overall_score,
                metrics=metrics,
                strengths=key_strengths,
                improvements=key_improvements,
            )

            session.logic_score = metrics["dimension_values"]["流畅连贯性"]
            session.accuracy_score = metrics["dimension_values"]["准确性"]
            session.completeness_score = round(
                (
                    metrics["dimension_values"]["专业性"]
                    + metrics["dimension_values"]["生动性"]
                    + metrics["dimension_values"]["互动问答"]
                    + metrics["dimension_values"]["其他表现"]
                )
                / 4,
                1,
            )
            await self.db.flush()

            report = ComprehensiveReport(
                session_id=session_id,
                generated_at=datetime.now(timezone.utc),
                overall_score=overall_score,
                dimension_scores=dimension_scores,
                stage_summaries=stage_summaries,
                key_strengths=key_strengths,
                key_improvements=key_improvements,
                detailed_feedback=detailed_feedback,
                recommendations=recommendations,
            )
            return Result.ok(report)
        except Exception as exc:  # noqa: BLE001
            return Result.fail(f"[PRESENTATION_REPORT_BUILD_FAILED:{exc}]")

    def _build_metrics(
        self,
        *,
        session: PracticeSession,
        user_messages: list[ConversationMessage],
        interruption_events: list[InterruptionEvent],
        total_pages: int,
        required_points_by_page: dict[int, list[str]],
    ) -> dict[str, Any]:
        normalized_texts = [_normalize_text(message.content) for message in user_messages]
        combined_text = "".join(normalized_texts)
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

        page_numbers: list[int] = []
        for message in user_messages:
            metadata = (
                message.transcript_metadata
                if isinstance(message.transcript_metadata, dict)
                else {}
            )
            try:
                page_number = int(metadata.get("page_number") or 1)
            except (TypeError, ValueError):
                page_number = 1
            page_numbers.append(max(1, page_number))

        distinct_pages = len(set(page_numbers)) if page_numbers else 1
        page_coverage_ratio = distinct_pages / max(1, total_pages)

        matched_required_points = 0
        total_required_points = 0
        for page_number, points in required_points_by_page.items():
            page_text = "".join(
                normalized_texts[index]
                for index, candidate_page in enumerate(page_numbers)
                if candidate_page == page_number
            )
            for point in points:
                normalized_point = _normalize_text(point)
                if not normalized_point:
                    continue
                total_required_points += 1
                if normalized_point in page_text:
                    matched_required_points += 1
                    continue
                short_anchor = normalized_point[: min(len(normalized_point), 8)]
                if short_anchor and short_anchor in page_text:
                    matched_required_points += 1

        required_coverage_ratio = (
            matched_required_points / total_required_points
            if total_required_points > 0
            else 1.0
        )

        forbidden_count = sum(
            1 for event in interruption_events if event.interruption_type == "forbidden_word"
        )
        missing_count = sum(
            1 for event in interruption_events if event.interruption_type == "missing_point"
        )
        vague_count = sum(
            1 for event in interruption_events if event.interruption_type == "vague_response"
        )

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
            "page_coverage_ratio": round(page_coverage_ratio, 4),
            "required_coverage_ratio": round(required_coverage_ratio, 4),
            "forbidden_count": forbidden_count,
            "missing_count": missing_count,
            "vague_count": vague_count,
            "duration_minutes": round(duration_minutes, 1),
            "dimension_values": dimension_values,
        }

    def _build_stage_summaries(
        self,
        *,
        user_messages: list[ConversationMessage],
        required_points_by_page: dict[int, list[str]],
        total_pages: int,
    ) -> list[dict[str, Any]]:
        grouped_messages: dict[int, list[ConversationMessage]] = defaultdict(list)
        for message in user_messages:
            metadata = (
                message.transcript_metadata
                if isinstance(message.transcript_metadata, dict)
                else {}
            )
            try:
                page_number = int(metadata.get("page_number") or 1)
            except (TypeError, ValueError):
                page_number = 1
            grouped_messages[max(1, page_number)].append(message)

        summaries: list[dict[str, Any]] = []
        for page_number in sorted(grouped_messages.keys()):
            messages = grouped_messages[page_number]
            page_text = "".join(_normalize_text(message.content) for message in messages)
            matched_points: list[str] = []
            for point in required_points_by_page.get(page_number, []):
                normalized_point = _normalize_text(point)
                if not normalized_point:
                    continue
                if normalized_point in page_text or normalized_point[:8] in page_text:
                    matched_points.append(point)

            avg_score = _clamp_score(
                58
                + min(18, len(page_text) / 80)
                + min(12, len(matched_points) * 6)
                + (8 if ("?" in "".join(message.content for message in messages) or "？" in "".join(message.content for message in messages)) else 0)
            )
            summaries.append(
                {
                    "stage_number": min(page_number, total_pages),
                    "start_turn": min(message.turn_number for message in messages),
                    "end_turn": max(message.turn_number for message in messages),
                    "average_score": avg_score,
                    "key_points": matched_points[:3],
                    "summary": self._build_page_summary(
                        page_number=page_number,
                        messages=messages,
                        matched_points=matched_points,
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
    ) -> str:
        if matched_points:
            return (
                f"第 {page_number} 页讲解覆盖了 {len(matched_points)} 个核心要点，"
                "整体表达较完整。"
            )
        if len(messages) >= 2:
            return f"第 {page_number} 页有连续讲解，但核心要点覆盖仍可继续加强。"
        return f"第 {page_number} 页有讲解记录，建议补充更明确的关键点表达。"

    def _build_strengths(
        self,
        dimension_values: dict[str, float],
        metrics: dict[str, Any],
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
        return strengths[:5] or ["整体讲解结构较稳定"]

    def _build_improvements(
        self,
        dimension_values: dict[str, float],
        metrics: dict[str, Any],
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
        return improvements[:5] or ["可以继续增加更多案例与互动设计"]

    def _build_recommendations(
        self,
        dimension_values: dict[str, float],
        metrics: dict[str, Any],
    ) -> list[str]:
        recommendations: list[str] = []
        if dimension_values["流畅连贯性"] < 80:
            recommendations.append("按页做 60 秒小段脱稿复述训练，重点减少“嗯、然后、这个”等口头语。")
        if dimension_values["准确性"] < 80:
            recommendations.append("逐页对照石犀资料和讲稿自检一次，重点核对产品功能、版本和术语表述。")
        if dimension_values["专业性"] < 80:
            recommendations.append("每页至少补入 1 个产品术语或技术原理解释，再用通俗语言复述一遍。")
        if dimension_values["生动性"] < 80:
            recommendations.append("每 2-3 页补一个客户案例、业务场景或类比，提升讲解画面感。")
        if dimension_values["互动问答"] < 80:
            recommendations.append("每个主题段主动加入 1 个引导性问题或自问自答，带动听众参与。")
        if metrics["required_coverage_ratio"] < 0.7:
            recommendations.append("给每页整理 2-3 个必须讲到的关键词，演练时逐页打勾确认。")
        return recommendations[:6] or ["保持当前节奏，继续通过整场演练巩固表达稳定性。"]

    def _build_detailed_feedback(
        self,
        *,
        overall_score: float,
        metrics: dict[str, Any],
        strengths: list[str],
        improvements: list[str],
    ) -> str:
        duration_text = (
            f"本次演讲训练累计约 {metrics['duration_minutes']:.1f} 分钟，"
            if metrics["duration_minutes"] > 0
            else "本次演讲训练已形成完整讲解记录，"
        )
        return (
            f"{duration_text}综合得分 {overall_score:.1f} 分。"
            f"当前优势集中在：{ '；'.join(strengths[:3]) }。"
            f"需要优先改进的方向是：{ '；'.join(improvements[:3]) }。"
            f"从过程数据看，你覆盖了约 {metrics['page_coverage_ratio'] * 100:.0f}% 的页面，"
            f"关键点命中率约 {metrics['required_coverage_ratio'] * 100:.0f}%，"
            f"口头语/重复触发约 {metrics['filler_count']} 次。"
        )

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
