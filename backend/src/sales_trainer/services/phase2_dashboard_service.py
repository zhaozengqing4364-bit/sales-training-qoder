from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from sales_trainer.services.phase2_policy import resolve_phase2_policy
from sales_trainer.services.training_record_service import TrainingRecordService


class SalesTrainerPhase2DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_dashboard(
        self,
        *,
        team_department: str | None,
    ) -> dict[str, Any]:
        self._policy, self._policy_payload = await resolve_phase2_policy(self._db)
        records, total = await TrainingRecordService(self._db).list_records(
            team_department=team_department,
            limit=self._policy.dashboard_record_limit,
            offset=0,
        )
        return {
            "generated_at": datetime.now(UTC),
            "policy": self._policy_payload,
            "summary": self._summary(records, total),
            "module_summaries": self._module_summaries(records),
            "weak_dimensions": self._weak_dimensions(records),
            "risk_learners": self._risk_learners(records),
            "intervention_suggestions": self._intervention_suggestions(records),
        }

    def _summary(self, records: list[dict[str, Any]], total: int) -> dict[str, Any]:
        learner_ids = {record["user_id"] for record in records}
        completed = [record for record in records if _is_completed(record)]
        passable = [
            record for record in records
            if _effective_passed(record) is not None
        ]
        passed = [record for record in passable if _effective_passed(record) is True]
        low_score = [record for record in records if _is_low_score(record, self._policy.low_score_threshold)]
        repeated = self._repeated_practice_keys(records)
        return {
            "record_count": total,
            "loaded_record_count": len(records),
            "learner_count": len(learner_ids),
            "completed_record_count": len(completed),
            "completion_rate": _rate(len(completed), len(records)),
            "pass_rate": _rate(len(passed), len(passable)),
            "low_score_record_count": len(low_score),
            "repeat_practice_learner_count": len({item[0] for item in repeated}),
        }

    def _module_summaries(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            grouped[_module_key(record)].append(record)
        summaries = []
        for module_key, module_records in grouped.items():
            scores = [
                score for record in module_records
                if (score := _effective_score(record)) is not None
            ]
            passable = [
                record for record in module_records
                if _effective_passed(record) is not None
            ]
            summaries.append({
                "module_key": module_key,
                "module_name": _module_name(module_records),
                "record_count": len(module_records),
                "completed_count": len([record for record in module_records if _is_completed(record)]),
                "pass_rate": _rate(
                    len([record for record in passable if _effective_passed(record) is True]),
                    len(passable),
                ),
                "average_score": sum(scores) / len(scores) if scores else None,
                "weak_record_count": len([
                    record for record in module_records
                    if _is_low_score(record, self._policy.low_score_threshold)
                ]),
            })
        return sorted(summaries, key=lambda item: item["record_count"], reverse=True)

    def _weak_dimensions(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        buckets: dict[str, dict[str, Any]] = {}
        for record in records:
            profile = record.get("ability_profile")
            if not isinstance(profile, dict):
                continue
            for dimension in profile.get("weak_dimensions") or []:
                if not isinstance(dimension, dict):
                    continue
                key = str(dimension.get("key") or "unknown")
                bucket = buckets.setdefault(
                    key,
                    {
                        "dimension_key": key,
                        "dimension_label": dimension.get("label") or key,
                        "record_count": 0,
                        "score_sum": 0.0,
                        "score_count": 0,
                        "learner_ids": set(),
                    },
                )
                bucket["record_count"] += 1
                bucket["learner_ids"].add(record["user_id"])
                score = _float_value(dimension.get("score"))
                if score is not None:
                    bucket["score_sum"] += score
                    bucket["score_count"] += 1
        result = []
        for bucket in buckets.values():
            result.append({
                "dimension_key": bucket["dimension_key"],
                "dimension_label": bucket["dimension_label"],
                "record_count": bucket["record_count"],
                "learner_count": len(bucket["learner_ids"]),
                "average_score": (
                    bucket["score_sum"] / bucket["score_count"]
                    if bucket["score_count"]
                    else None
                ),
            })
        return sorted(result, key=lambda item: item["record_count"], reverse=True)

    def _risk_learners(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        repeated = self._repeated_practice_keys(records)
        repeated_by_user = defaultdict(int)
        for user_id, _ in repeated:
            repeated_by_user[user_id] += 1
        buckets: dict[str, dict[str, Any]] = {}
        for record in records:
            is_risk = (
                _effective_passed(record) is False
                or _is_low_score(record, self._policy.low_score_threshold)
                or repeated_by_user.get(record["user_id"], 0) > 0
            )
            if not is_risk:
                continue
            bucket = buckets.setdefault(
                record["user_id"],
                {
                    "user_id": record["user_id"],
                    "user_name": record.get("user_name"),
                    "user_department": record.get("user_department"),
                    "risk_reasons": set(),
                    "latest_submitted_at": record.get("submitted_at"),
                    "lowest_score": None,
                    "record_count": 0,
                },
            )
            bucket["record_count"] += 1
            score = _effective_score(record)
            if score is not None:
                lowest = bucket["lowest_score"]
                bucket["lowest_score"] = score if lowest is None else min(lowest, score)
            if _effective_passed(record) is False:
                bucket["risk_reasons"].add("not_passed")
            if _is_low_score(record, self._policy.low_score_threshold):
                bucket["risk_reasons"].add("low_score")
            if repeated_by_user.get(record["user_id"], 0) > 0:
                bucket["risk_reasons"].add("repeated_practice")
            if str(record.get("submitted_at") or "") > str(bucket["latest_submitted_at"] or ""):
                bucket["latest_submitted_at"] = record.get("submitted_at")
        return [
            {
                **bucket,
                "risk_reasons": sorted(bucket["risk_reasons"]),
                "suggested_action": self._policy.manager_action(
                    bucket["risk_reasons"]
                )["label"],
                "suggested_action_code": self._policy.manager_action(
                    bucket["risk_reasons"]
                )["code"],
                "priority": self._policy.manager_action(bucket["risk_reasons"])[
                    "priority"
                ],
            }
            for bucket in sorted(
                buckets.values(),
                key=lambda item: str(item["latest_submitted_at"] or ""),
                reverse=True,
            )
        ]

    def _intervention_suggestions(
        self,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        suggestions = []
        for learner in self._risk_learners(records):
            reasons = learner["risk_reasons"]
            suggestions.append({
                "user_id": learner["user_id"],
                "user_name": learner["user_name"],
                "priority": learner["priority"],
                "action": learner["suggested_action"],
                "reason_codes": reasons,
            })
        return suggestions[:20]

    def _repeated_practice_keys(
        self,
        records: list[dict[str, Any]],
    ) -> set[tuple[str, str]]:
        counts: dict[tuple[str, str], int] = defaultdict(int)
        for record in records:
            counts[(record["user_id"], _module_key(record))] += 1
        return {
            key for key, count in counts.items()
            if count >= self._policy.repeat_practice_threshold
        }


def _is_completed(record: dict[str, Any]) -> bool:
    return str(record.get("status") or "") in {"scored", "completed"}


def _is_low_score(record: dict[str, Any], threshold: float) -> bool:
    score = _effective_score(record)
    return score is not None and score < threshold


def _effective_score(record: dict[str, Any]) -> float | None:
    score = _snapshot(record.get("effective_score")).get("score")
    return _float_value(score)


def _effective_passed(record: dict[str, Any]) -> bool | None:
    passed = _snapshot(record.get("effective_score")).get("passed")
    return passed if isinstance(passed, bool) else None


def _snapshot(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _float_value(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator * 100, 2)


def _module_key(record: dict[str, Any]) -> str:
    return str(
        record.get("module_key")
        or record.get("unit_id")
        or record.get("unit_type")
        or "unknown"
    )


def _module_name(records: list[dict[str, Any]]) -> str:
    for record in records:
        if record.get("unit_name"):
            return str(record["unit_name"])
    return _module_key(records[0]) if records else "unknown"
