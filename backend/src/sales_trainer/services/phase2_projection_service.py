from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.regrade_models import SalesTrainerRegradeRun
from sales_trainer.services.phase2_policy import SalesTrainerPhase2Policy


class SalesTrainerPhase2ProjectionService:
    def __init__(
        self,
        db: AsyncSession,
        *,
        policy: SalesTrainerPhase2Policy,
    ) -> None:
        self._db = db
        self._policy = policy

    async def enrich_records(
        self,
        records: Sequence[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        latest_regrades = await self._latest_regrades(records)
        return [
            self.enrich_record(
                record,
                latest_regrade=latest_regrades.get(
                    (str(record.get("record_type")), str(record.get("record_id")))
                ),
            )
            for record in records
        ]

    async def enrich_record_from_database(
        self,
        record: dict[str, Any],
    ) -> dict[str, Any]:
        return self.enrich_record(
            record,
            latest_regrade=await self._latest_regrade(record),
        )

    def enrich_record(
        self,
        record: dict[str, Any],
        *,
        latest_regrade: SalesTrainerRegradeRun | None,
    ) -> dict[str, Any]:
        effective_score = self._effective_score(record, latest_regrade)
        record["effective_score"] = effective_score
        record["latest_regrade"] = self._regrade_payload(latest_regrade)
        record["score_explanation"] = self._score_explanation(
            record,
            effective_score,
            latest_regrade,
        )
        record["ability_profile"] = self._ability_profile(record)
        record["remediation"] = self._remediation(record, effective_score)
        return record

    async def _latest_regrades(
        self,
        records: Sequence[dict[str, Any]],
    ) -> dict[tuple[str, str], SalesTrainerRegradeRun]:
        target_pairs = {
            (target_type, str(record["record_id"]))
            for record in records
            if (
                target_type := {
                    "audio_submission": "audio_submission",
                    "quiz_attempt": "quiz_attempt",
                }.get(str(record.get("record_type") or ""))
            )
        }
        if not target_pairs:
            return {}
        target_types = {item[0] for item in target_pairs}
        target_ids = {item[1] for item in target_pairs}
        result = await self._db.execute(
            select(SalesTrainerRegradeRun)
            .where(
                SalesTrainerRegradeRun.target_type.in_(target_types),
                SalesTrainerRegradeRun.target_id.in_(target_ids),
                SalesTrainerRegradeRun.status == "completed",
            )
            .order_by(SalesTrainerRegradeRun.created_at.desc())
        )
        latest: dict[tuple[str, str], SalesTrainerRegradeRun] = {}
        for run in result.scalars().all():
            key = (str(run.target_type), str(run.target_id))
            if key in target_pairs and key not in latest:
                latest[key] = run
        return latest

    async def _latest_regrade(
        self,
        record: dict[str, Any],
    ) -> SalesTrainerRegradeRun | None:
        target_type = {
            "audio_submission": "audio_submission",
            "quiz_attempt": "quiz_attempt",
        }.get(str(record.get("record_type") or ""))
        if target_type is None:
            return None
        result = await self._db.execute(
            select(SalesTrainerRegradeRun)
            .where(
                SalesTrainerRegradeRun.target_type == target_type,
                SalesTrainerRegradeRun.target_id == record["record_id"],
                SalesTrainerRegradeRun.status == "completed",
            )
            .order_by(SalesTrainerRegradeRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    def _effective_score(
        self,
        record: dict[str, Any],
        latest_regrade: SalesTrainerRegradeRun | None,
    ) -> dict[str, Any]:
        original_score = _float_value(record.get("score"))
        original_max_score = _float_value(record.get("max_score"))
        original_passed = record.get("passed")
        score = original_score
        max_score = original_max_score
        passed = original_passed if isinstance(original_passed, bool) else None
        source = "original_record"
        error_code = None
        if latest_regrade is not None:
            after_snapshot = _snapshot(latest_regrade.after_snapshot_json)
            error_code = _optional_str(after_snapshot.get("error_code"))
            regrade_score = _float_value(after_snapshot.get("total_score"))
            if error_code is None and regrade_score is not None:
                score = regrade_score
                max_score = _float_value(after_snapshot.get("max_score")) or max_score
                if isinstance(after_snapshot.get("passed"), bool):
                    passed = bool(after_snapshot["passed"])
                source = "latest_regrade"
        return {
            "score": score,
            "max_score": max_score,
            "passed": passed,
            "source": source,
            "original_score": original_score,
            "original_max_score": original_max_score,
            "original_passed": original_passed,
            "score_delta": _score_delta(score, original_score),
            "latest_regrade_run_id": latest_regrade.run_id if latest_regrade else None,
            "latest_regrade_error_code": error_code,
            "history_overwrite": False,
        }

    def _score_explanation(
        self,
        record: dict[str, Any],
        effective_score: dict[str, Any],
        latest_regrade: SalesTrainerRegradeRun | None,
    ) -> dict[str, Any]:
        if record["record_type"] == "audio_submission":
            return self._audio_score_explanation(record, latest_regrade)
        if record["record_type"] == "quiz_attempt":
            return self._quiz_score_explanation(record, latest_regrade)
        if record["record_type"] == "business_etiquette_quiz_attempt":
            return self._business_etiquette_quiz_score_explanation(
                record,
                effective_score,
            )
        if record["record_type"] == "ai_coach_session":
            return self._ai_coach_score_explanation(record, effective_score)
        if record["record_type"] == "realtime_roleplay_session":
            return self._realtime_roleplay_score_explanation(record, effective_score)
        return {
            "basis": "sales_trainer_phase2_projection_v1",
            "summary": None,
            "dimensions": [],
            "evidence": [],
            "issues": [],
            "next_actions": [],
        }

    def _audio_score_explanation(
        self,
        record: dict[str, Any],
        latest_regrade: SalesTrainerRegradeRun | None,
    ) -> dict[str, Any]:
        source = _snapshot(record.get("audio_submission")).get("score_result") or {}
        if latest_regrade is not None:
            after_snapshot = _snapshot(latest_regrade.after_snapshot_json)
            if after_snapshot.get("error_code") is None and after_snapshot.get("total_score") is not None:
                source = after_snapshot
        source = _snapshot(source)
        dimensions = _dimension_items(source.get("dimension_scores"), self._policy)
        improvements = _string_list(source.get("improvements"))
        evidence = []
        transcript = _optional_str(source.get("transcript_snapshot"))
        if transcript:
            evidence.append({
                "type": "transcript_snapshot",
                "text": transcript[:240],
            })
        return {
            "basis": "audio_score_result_v1",
            "summary": _optional_str(source.get("summary")),
            "dimensions": dimensions,
            "evidence": evidence,
            "strengths": _string_list(source.get("strengths")),
            "issues": [
                {"type": "improvement", "text": item}
                for item in improvements
            ],
            "next_actions": [
                {
                    "kind": "retry_audio",
                    "label": "按建议重录",
                    "href": _record_retry_href(record),
                }
            ],
        }

    def _quiz_score_explanation(
        self,
        record: dict[str, Any],
        latest_regrade: SalesTrainerRegradeRun | None,
    ) -> dict[str, Any]:
        answers = self._quiz_explanation_answers(record, latest_regrade)
        issues = [
            {
                "type": "incorrect_answer",
                "question_id": answer.get("question_id"),
                "title": answer.get("question_title"),
                "feedback": answer.get("scoring_feedback") or answer.get("explanation"),
            }
            for answer in answers
            if answer.get("is_correct") is False
            or _is_low_answer_score(answer, self._policy)
        ]
        return {
            "basis": "quiz_attempt_snapshot_v1",
            "summary": f"本次考试共 {len(answers)} 题，发现 {len(issues)} 个需复习点。",
            "dimensions": self._quiz_dimensions(answers),
            "evidence": [
                {
                    "type": "quiz_answer",
                    "question_id": answer.get("question_id"),
                    "title": answer.get("question_title"),
                    "score": answer.get("score"),
                    "max_score": answer.get("max_score"),
                }
                for answer in answers
            ],
            "issues": issues,
            "next_actions": [
                {
                    "kind": "retry_quiz",
                    "label": "重做薄弱题",
                    "href": _record_retry_href(record),
                }
            ],
        }

    def _quiz_explanation_answers(
        self,
        record: dict[str, Any],
        latest_regrade: SalesTrainerRegradeRun | None,
    ) -> list[dict[str, Any]]:
        if latest_regrade is not None:
            after_snapshot = _snapshot(latest_regrade.after_snapshot_json)
            if after_snapshot.get("error_code") is None:
                regrade_answers = [
                    _normalize_regrade_answer(answer)
                    for answer in after_snapshot.get("answers") or []
                    if isinstance(answer, dict)
                ]
                if regrade_answers:
                    return regrade_answers
        attempt = _snapshot(record.get("quiz_attempt"))
        return [
            answer for answer in attempt.get("answers") or []
            if isinstance(answer, dict)
        ]

    def _ai_coach_score_explanation(
        self,
        record: dict[str, Any],
        effective_score: dict[str, Any],
    ) -> dict[str, Any]:
        session = _snapshot(record.get("ai_coach_session"))
        return {
            "basis": "ai_coach_session_snapshot_v1",
            "summary": "AI 教练训练局已形成训练状态和掌握度记录。",
            "dimensions": [
                {
                    "key": "business_skills_ai_coach",
                    "label": "商务技巧 AI 教练",
                    "score": effective_score.get("score"),
                    "max_score": effective_score.get("max_score"),
                    "is_weak": _score_is_weak(effective_score.get("score"), self._policy),
                }
            ],
            "evidence": [{
                "type": "ai_coach_session",
                "session_id": session.get("session_id"),
                "mastery_state": session.get("mastery_state"),
            }],
            "issues": [] if effective_score.get("passed") is not False else [{
                "type": "not_mastered",
                "text": "AI 教练训练局尚未达到掌握状态。",
            }],
            "next_actions": [{
                "kind": "continue_ai_coach",
                "label": "继续 AI 教练训练",
                "href": "/sales-trainer/business-skills/coach",
            }],
        }

    def _business_etiquette_quiz_score_explanation(
        self,
        record: dict[str, Any],
        effective_score: dict[str, Any],
    ) -> dict[str, Any]:
        attempt = _snapshot(record.get("business_etiquette_quiz_attempt"))
        capability_scores = [
            item for item in attempt.get("capability_scores") or []
            if isinstance(item, dict)
        ]
        answers = [
            item for item in attempt.get("answers") or []
            if isinstance(item, dict)
        ]
        weak_keys = set(_string_list(attempt.get("weak_capability_keys")))
        dimensions = [
            {
                "key": str(item.get("capability_key") or ""),
                "label": _optional_str(item.get("display_name")) or _dimension_label(
                    str(item.get("capability_key") or "")
                ),
                "score": _float_value(item.get("normalized_score") or item.get("score")),
                "max_score": 100.0,
                "is_weak": (
                    item.get("mastered") is False
                    or str(item.get("capability_key") or "") in weak_keys
                    or _score_is_weak(
                        item.get("normalized_score") or item.get("score"),
                        self._policy,
                    )
                ),
            }
            for item in capability_scores
            if item.get("capability_key")
        ]
        failed_answers = [
            answer for answer in answers
            if answer.get("is_correct") is False
            or _is_low_answer_score(answer, self._policy)
        ]
        return {
            "basis": "business_etiquette_quiz_attempt_snapshot_v1",
            "summary": (
                f"本次商务礼仪小测共 {len(answers)} 题，"
                f"发现 {len(failed_answers)} 个需复习点。"
            ),
            "dimensions": dimensions,
            "evidence": [
                {
                    "type": "business_etiquette_quiz_answer",
                    "question_id": answer.get("question_id"),
                    "question_type": answer.get("question_type"),
                    "score": answer.get("score"),
                    "max_score": answer.get("max_score"),
                    "capability_keys": answer.get("capability_keys"),
                }
                for answer in answers
            ],
            "issues": [
                {
                    "type": "weak_business_etiquette_capability",
                    "capability_key": key,
                    "text": f"商务礼仪能力点 {key} 未达当前闭环策略要求。",
                }
                for key in sorted(weak_keys)
            ] + [
                {
                    "type": "incorrect_answer",
                    "question_id": answer.get("question_id"),
                    "feedback": answer.get("analysis"),
                }
                for answer in failed_answers
            ],
            "next_actions": [{
                "kind": "retry_business_etiquette_quiz",
                "label": "复习后重做小测",
                "href": _record_retry_href(record),
            }],
        }

    def _realtime_roleplay_score_explanation(
        self,
        record: dict[str, Any],
        effective_score: dict[str, Any],
    ) -> dict[str, Any]:
        session = _snapshot(record.get("realtime_roleplay_session"))
        snapshot = _snapshot(session.get("snapshot"))
        scores = _snapshot(snapshot.get("scores"))
        dimensions = [
            {
                "key": key,
                "label": _dimension_label(key),
                "score": _float_value(scores.get(key)),
                "max_score": 100.0 if scores.get(key) is not None else None,
                "is_weak": _score_is_weak(scores.get(key), self._policy),
            }
            for key in ("logic_score", "accuracy_score", "completeness_score")
            if scores.get(key) is not None
        ]
        return {
            "basis": "realtime_roleplay_runtime_outcome_snapshot_v1",
            "summary": "实时对练已形成运行时结果快照。",
            "dimensions": dimensions,
            "evidence": [{
                "type": "realtime_roleplay_session",
                "session_id": session.get("session_id"),
                "module_key": session.get("module_key"),
            }],
            "issues": []
            if not _score_is_weak(effective_score.get("score"), self._policy)
            else [{
                "type": "low_realtime_roleplay_score",
                "text": "实时对练综合得分低于当前闭环策略阈值。",
            }],
            "next_actions": [{
                "kind": "retry_realtime_roleplay",
                "label": "再次进行实时对练",
                "href": "/sales-trainer/realtime-roleplay",
            }],
        }

    def _ability_profile(self, record: dict[str, Any]) -> dict[str, Any]:
        explanation = _snapshot(record.get("score_explanation"))
        effective_score = _snapshot(record.get("effective_score"))
        dimensions = [
            dimension for dimension in explanation.get("dimensions") or []
            if isinstance(dimension, dict)
        ]
        weak_dimensions = [
            dimension for dimension in dimensions if dimension.get("is_weak") is True
        ]
        return {
            "basis": "sales_trainer_phase2_projection_v1",
            "overall_score": effective_score.get("score"),
            "overall_passed": effective_score.get("passed"),
            "dimensions": dimensions,
            "weak_dimensions": weak_dimensions,
            "evidence_count": len(explanation.get("evidence") or []),
        }

    def _quiz_dimensions(self, answers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: dict[str, list[tuple[float | None, float | None]]] = defaultdict(list)
        for answer in answers:
            dimensions = answer.get("scoring_dimensions")
            if not isinstance(dimensions, list) or not dimensions:
                dimensions = [answer.get("question_type") or "quiz_answer"]
            for dimension in dimensions:
                key = str(dimension)
                buckets[key].append((
                    _float_value(answer.get("score")),
                    _float_value(answer.get("max_score")),
                ))
        return [
            _dimension_bucket_payload(key, values, self._policy)
            for key, values in sorted(buckets.items())
        ]

    def _remediation(
        self,
        record: dict[str, Any],
        effective_score: dict[str, Any],
    ) -> dict[str, Any]:
        score = _float_value(effective_score.get("score"))
        passed = effective_score.get("passed")
        is_completed = str(record.get("status") or "") in {"scored", "completed"}
        weak_dimensions = _snapshot(record.get("ability_profile")).get("weak_dimensions") or []
        needs_action = (
            not is_completed
            or passed is False
            or _score_is_weak(score, self._policy)
            or bool(weak_dimensions)
        )
        action = self._policy.remediation_action(
            str(record.get("record_type") or "default"),
            needed=needs_action,
        )
        if not needs_action:
            return {
                "needed": False,
                "reason": _render_phase2_template(
                    action["reason_template"],
                    record,
                    score,
                    self._policy.low_score_threshold,
                ),
                "action_label": action["action_label"],
                "target_path": _render_phase2_template(
                    action["target_path_template"],
                    record,
                    score,
                    self._policy.low_score_threshold,
                ),
                "priority": action["priority"],
            }
        return {
            "needed": True,
            "reason": _render_phase2_template(
                action["reason_template"],
                record,
                score,
                self._policy.low_score_threshold,
            ),
            "action_label": action["action_label"],
            "target_path": _render_phase2_template(
                action["target_path_template"],
                record,
                score,
                self._policy.low_score_threshold,
            ),
            "priority": action["priority"],
            "weak_dimension_keys": [
                item.get("key") for item in weak_dimensions if isinstance(item, dict)
            ],
        }

    def _regrade_payload(
        self,
        run: SalesTrainerRegradeRun | None,
    ) -> dict[str, Any] | None:
        if run is None:
            return None
        return {
            "regrade_run_id": run.run_id,
            "target_type": run.target_type,
            "target_revision_id": run.target_revision_id,
            "status": run.status,
            "reason": run.reason,
            "trace_id": run.trace_id,
            "created_at": run.created_at,
            "before_snapshot": run.before_snapshot_json,
            "after_snapshot": run.after_snapshot_json,
        }


def _dimension_items(
    value: object,
    policy: SalesTrainerPhase2Policy,
) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    items: list[dict[str, Any]] = []
    for key, raw_dimension in sorted(value.items()):
        score, max_score, label = _dimension_score(raw_dimension)
        items.append({
            "key": str(key),
            "label": label or _dimension_label(str(key)),
            "score": score,
            "max_score": max_score,
            "is_weak": _score_is_weak(score, policy),
        })
    return items


def _normalize_regrade_answer(answer: dict[str, Any]) -> dict[str, Any]:
    snapshot = _snapshot(answer.get("question_snapshot"))
    return {
        "question_id": answer.get("question_id") or snapshot.get("question_id"),
        "question_type": answer.get("question_type") or snapshot.get("question_type"),
        "answer_payload": answer.get("answer_payload"),
        "question_title": snapshot.get("title") or answer.get("question_title"),
        "question_stem": snapshot.get("stem") or answer.get("question_stem"),
        "correct_answer": snapshot.get("correct_answer") or answer.get("correct_answer"),
        "score": _float_value(answer.get("score")),
        "max_score": _float_value(snapshot.get("points")) or 100.0,
        "is_correct": answer.get("is_correct"),
        "scoring_feedback": (
            answer.get("scoring_feedback")
            or snapshot.get("scoring_feedback")
            or snapshot.get("feedback")
        ),
        "scoring_reason": (
            answer.get("scoring_reason")
            or snapshot.get("scoring_reason")
            or snapshot.get("reason")
        ),
        "scoring_dimensions": [
            str(value) for value in snapshot.get("scoring_dimensions") or []
        ],
    }


def _dimension_score(value: object) -> tuple[float | None, float | None, str | None]:
    if isinstance(value, int | float | Decimal | str):
        return _float_value(value), 100.0, None
    if isinstance(value, dict):
        return (
            _float_value(value.get("score") or value.get("value")),
            _float_value(value.get("max_score")) or 100.0,
            _optional_str(value.get("label") or value.get("name")),
        )
    return None, None, None


def _dimension_bucket_payload(
    key: str,
    values: list[tuple[float | None, float | None]],
    policy: SalesTrainerPhase2Policy,
) -> dict[str, Any]:
    scored = [(score, max_score) for score, max_score in values if score is not None]
    total_score = sum(score for score, _ in scored)
    total_max = sum(max_score or 0 for _, max_score in scored)
    normalized_score = (total_score / total_max * 100) if total_max else None
    return {
        "key": key,
        "label": _dimension_label(key),
        "score": normalized_score,
        "max_score": 100.0 if normalized_score is not None else None,
        "is_weak": _score_is_weak(normalized_score, policy),
        "evidence_count": len(values),
    }


def _score_is_weak(
    score: object,
    policy: SalesTrainerPhase2Policy,
) -> bool:
    value = _float_value(score)
    return value is not None and value < policy.low_score_threshold


def _is_low_answer_score(
    answer: dict[str, Any],
    policy: SalesTrainerPhase2Policy,
) -> bool:
    score = _float_value(answer.get("score"))
    max_score = _float_value(answer.get("max_score"))
    if score is None or max_score is None or max_score == 0:
        return False
    percentage = score / max_score * 100
    return bool(percentage < policy.low_score_threshold)


def _snapshot(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _float_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float | Decimal):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _score_delta(score: float | None, original_score: float | None) -> float | None:
    if score is None or original_score is None:
        return None
    return score - original_score


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None]


def _dimension_label(key: str) -> str:
    return key.replace("_", " ").strip().title() or "训练能力"


def _record_retry_href(record: dict[str, Any]) -> str:
    record_type = record.get("record_type")
    unit_id = str(record.get("unit_id") or "")
    module_key = str(record.get("module_key") or "")
    if record_type == "audio_submission" and unit_id:
        return f"/sales-trainer/audio/{unit_id}"
    if record_type == "quiz_attempt":
        if module_key == "business_skills":
            return "/sales-trainer/business-skills/exam"
        if unit_id:
            return f"/sales-trainer/quiz/{unit_id}"
    if record_type == "business_etiquette_quiz_attempt":
        return f"/sales-trainer/business-skills?learningUnitKey={unit_id}"
    if record_type == "ai_coach_session":
        return "/sales-trainer/business-skills/coach"
    return "/sales-trainer"


def _record_result_href(record: dict[str, Any]) -> str:
    record_type = record.get("record_type")
    record_id = str(record.get("record_id") or "")
    if record_type == "audio_submission":
        return f"/sales-trainer/audio/result/{record_id}"
    if record_type == "quiz_attempt":
        return f"/sales-trainer/quiz/result/{record_id}"
    if record_type == "business_etiquette_quiz_attempt":
        unit_id = str(record.get("unit_id") or "")
        return f"/sales-trainer/business-skills?learningUnitKey={unit_id}"
    if record_type == "ai_coach_session":
        return "/sales-trainer/business-skills/coach"
    return "/sales-trainer"


def _render_phase2_template(
    template: str,
    record: dict[str, Any],
    score: float | None,
    threshold: float,
) -> str:
    return template.format(
        record_id=str(record.get("record_id") or ""),
        record_type=str(record.get("record_type") or ""),
        unit_id=str(record.get("unit_id") or ""),
        module_key=str(record.get("module_key") or ""),
        score=score if score is not None else 0.0,
        threshold=threshold,
        result_path=_record_result_href(record),
    )


def _remediation_action_label(record: dict[str, Any]) -> str:
    if record.get("record_type") == "audio_submission":
        return "安排重录"
    if record.get("record_type") == "quiz_attempt":
        return "安排错题复习"
    if record.get("record_type") == "ai_coach_session":
        return "继续 AI 教练训练"
    return "查看训练记录"


def _remediation_reason(
    record: dict[str, Any],
    score: float | None,
    passed: object,
) -> str:
    if passed is False:
        return "最近一次训练未达通过标准，需要主管跟进补救。"
    if score is not None:
        return "当前有效分低于弱项阈值，需要安排针对性复练。"
    if str(record.get("status") or "") not in {"scored", "completed"}:
        return "训练尚未形成可用评分，需要先完成评分或排查失败任务。"
    return "存在弱项维度，需要安排复习。"
