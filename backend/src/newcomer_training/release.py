"""Auditable ReleasePlan orchestration owned by newcomer training.

The service coordinates exact revision publication through narrow ports.  It
never imports another business module's ORM or provider implementation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from newcomer_training.application import CommandActor, PathEnrollmentService
from newcomer_training.contracts import PathRevisionDraft
from newcomer_training.errors import NewcomerTrainingError
from newcomer_training.models import (
    NewcomerActivityAttempt,
    NewcomerCommandAudit,
    NewcomerEnrollment,
    NewcomerPath,
    NewcomerPathRevision,
    NewcomerReleasePlan,
)
from newcomer_training.ports import (
    PublishedCompetencyMappingPort,
    ReleaseDependency,
    ReleaseDependencyPort,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid.uuid4())


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _secret_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


PATH_RUNTIME_CONTRACT_HASH = _canonical_hash(PathRevisionDraft.model_json_schema())


class ReleaseValidationIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    severity: Literal["blocker", "warning", "suggestion"]
    code: str
    field: str
    message: str
    activity_id: str | None = None


class ReleasePlanSummary(BaseModel):
    model_config = ConfigDict(frozen=True, from_attributes=True)

    release_plan_id: str
    organization_id: str
    path_id: str
    path_revision_id: str
    previous_release_plan_id: str | None
    status: str
    version: int
    contract_hash: str
    target_revisions: tuple[dict[str, Any], ...]
    dependency_graph: dict[str, Any]
    validation_report: dict[str, Any]
    impact_preview: dict[str, Any]
    impact_hash: str
    reason: str
    created_by: str
    published_by: str | None
    rolled_back_by: str | None
    created_at: datetime
    published_at: datetime | None
    rolled_back_at: datetime | None


class ReleasePlanPreview(ReleasePlanSummary):
    preview_token: str
    preview_expires_at: datetime


class RollbackPreview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    active_release_plan_id: str
    target_release_plan_id: str
    preview_token: str
    impact_hash: str
    impact: dict[str, Any]
    expires_at: datetime


class ReleasePlanService:
    """Sole coordinator for atomic foundation release and rollback commands."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        dependencies: ReleaseDependencyPort,
        path_service: PathEnrollmentService,
        competency_mappings: PublishedCompetencyMappingPort,
    ) -> None:
        self._session = session
        self._dependencies = dependencies
        self._path_service = path_service
        self._competency_mappings = competency_mappings

    async def preview(
        self,
        *,
        actor: CommandActor,
        path_revision_id: str,
        reason: str,
        idempotency_key: str,
    ) -> ReleasePlanPreview:
        self._require(actor, "newcomer.path.publish")
        if not reason.strip():
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_REASON_REQUIRED]", "请填写发布依据。", 422
            )
        revision = await self._load_revision(actor, path_revision_id)
        if revision.status != "working":
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_WORKING_REVISION_REQUIRED]",
                "只有工作修订可以创建发布计划。",
                422,
            )
        path = await self._load_path(actor, revision.path_id)
        fingerprint = _canonical_hash(
            {
                "organization_id": actor.organization_id,
                "path_revision_id": path_revision_id,
                "revision_version": revision.version,
                "content_hash": revision.content_hash,
                "reason": reason.strip(),
            }
        )
        deterministic_token = _canonical_hash(
            {
                "purpose": "foundation-release-preview",
                "organization_id": actor.organization_id,
                "idempotency_key": idempotency_key,
            }
        )
        replay = await self._session.scalar(
            select(NewcomerReleasePlan)
            .where(NewcomerReleasePlan.organization_id == actor.organization_id)
            .where(
                NewcomerReleasePlan.creation_idempotency_key_hash
                == _secret_hash(idempotency_key)
            )
            .limit(1)
        )
        if replay is not None:
            if replay.creation_fingerprint != fingerprint:
                self._idempotency_conflict()
            return self._preview_summary(replay, deterministic_token)

        draft = PathRevisionDraft.model_validate(revision.snapshot_json)
        issues: list[ReleaseValidationIssue] = []
        targets: list[dict[str, Any]] = [
            {
                "resource_type": "path",
                "resource_id": path.path_id,
                "revision_id": revision.revision_id,
                "status": revision.status,
                "content_hash": revision.content_hash,
                "expected_revision_version": revision.version,
                "publish_required": True,
            }
        ]
        graph_nodes: list[dict[str, Any]] = [
            {
                "id": f"path_revision:{revision.revision_id}",
                "type": "path_revision",
                "revision_id": revision.revision_id,
            }
        ]
        graph_edges: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        nested_queue: list[tuple[str, dict[str, str]]] = []
        for stage_index, stage in enumerate(draft.stages):
            for activity_index, activity in enumerate(stage.activities):
                field_prefix = f"stages.{stage_index}.activities.{activity_index}"
                if not activity.competency_keys:
                    issues.append(
                        ReleaseValidationIssue(
                            severity="blocker",
                            code="competency_mapping_required",
                            field=f"{field_prefix}.competency_keys",
                            activity_id=activity.activity_id,
                            message="每个训练活动必须映射至少一项基础能力。",
                        )
                    )
                else:
                    try:
                        await self._competency_mappings.require_valid(
                            organization_id=actor.organization_id,
                            path_revision_id=revision.revision_id,
                            activity_id=activity.activity_id,
                            activity_type=str(activity.type),
                            competency_keys=activity.competency_keys,
                        )
                    except NewcomerTrainingError as exc:
                        issues.append(
                            ReleaseValidationIssue(
                                severity="blocker",
                                code=exc.code.strip("[]").lower(),
                                field=f"{field_prefix}.competency_keys",
                                activity_id=activity.activity_id,
                                message=exc.message,
                            )
                        )
                for field_name, resource_revision_id in self._resource_refs(activity):
                    if not resource_revision_id.strip():
                        issues.append(
                            ReleaseValidationIssue(
                                severity="blocker",
                                code="activity_resource_required",
                                field=f"{field_prefix}.config.{field_name}",
                                activity_id=activity.activity_id,
                                message="请选择此活动需要的已治理资源修订。",
                            )
                        )
                        continue
                    dependency = await self._dependencies.inspect(
                        organization_id=actor.organization_id,
                        activity_type=str(activity.type),
                        revision_id=resource_revision_id,
                    )
                    key = (dependency.resource_type, dependency.revision_id)
                    node_id = (
                        f"{dependency.resource_type}:{dependency.revision_id}"
                    )
                    graph_edges.append(
                        {
                            "from": f"path_revision:{revision.revision_id}",
                            "to": node_id,
                            "activity_id": activity.activity_id,
                            "field": field_name,
                        }
                    )
                    if key not in seen:
                        seen.add(key)
                        target = dependency.model_dump(mode="json")
                        targets.append(target)
                        graph_nodes.append(
                            {
                                "id": node_id,
                                "type": dependency.resource_type,
                                "revision_id": dependency.revision_id,
                            }
                        )
                        for nested in dependency.dependencies:
                            nested_id = (
                                f"{nested['resource_type']}:{nested['revision_id']}"
                            )
                            graph_nodes.append(
                                {
                                    "id": nested_id,
                                    "type": nested["resource_type"],
                                    "revision_id": nested["revision_id"],
                                }
                            )
                            graph_edges.append(
                                {"from": node_id, "to": nested_id, "field": "dependency"}
                            )
                            nested_queue.append((node_id, nested))
                    for raw_issue in dependency.issues:
                        issues.append(
                            ReleaseValidationIssue(
                                severity="blocker",
                                code=raw_issue.get("code", "dependency_invalid"),
                                field=f"{field_prefix}.config.{field_name}",
                                activity_id=activity.activity_id,
                                message=raw_issue.get(
                                    "message", "引用修订未通过发布检查。"
                                ),
                            )
                        )
        while nested_queue:
            _parent_node_id, nested_ref = nested_queue.pop(0)
            resource_type = nested_ref["resource_type"]
            nested_revision_id = nested_ref["revision_id"]
            key = (resource_type, nested_revision_id)
            node_id = f"{resource_type}:{nested_revision_id}"
            if key in seen:
                continue
            seen.add(key)
            dependency = await self._dependencies.inspect_resource(
                organization_id=actor.organization_id,
                resource_type=resource_type,
                revision_id=nested_revision_id,
            )
            targets.append(dependency.model_dump(mode="json"))
            graph_nodes.append(
                {
                    "id": node_id,
                    "type": dependency.resource_type,
                    "revision_id": dependency.revision_id,
                }
            )
            for raw_issue in dependency.issues:
                issues.append(
                    ReleaseValidationIssue(
                        severity="blocker",
                        code=raw_issue.get("code", "dependency_invalid"),
                        field="dependencies",
                        message=raw_issue.get(
                            "message", "发布依赖未通过完整性检查。"
                        ),
                    )
                )
            for child in dependency.dependencies:
                child_id = f"{child['resource_type']}:{child['revision_id']}"
                graph_nodes.append(
                    {
                        "id": child_id,
                        "type": child["resource_type"],
                        "revision_id": child["revision_id"],
                    }
                )
                graph_edges.append(
                    {"from": node_id, "to": child_id, "field": "dependency"}
                )
                nested_queue.append((node_id, child))
        graph = {
            "nodes": self._dedupe_nodes(graph_nodes),
            "edges": graph_edges,
            "acyclic": self._is_acyclic(graph_edges),
        }
        if not graph["acyclic"]:
            issues.append(
                ReleaseValidationIssue(
                    severity="blocker",
                    code="dependency_cycle",
                    field="dependencies",
                    message="发布依赖存在循环引用，请先解除循环。",
                )
            )
        impact = await self._impact(path=path, target_revision=revision)
        report = {
            "valid": not any(item.severity == "blocker" for item in issues),
            "contract_compatible": True,
            "issues": [item.model_dump(mode="json") for item in issues],
            "checked_at": _now().isoformat(),
        }
        impact_hash = _canonical_hash(impact)
        now = _now()
        plan = NewcomerReleasePlan(
            release_plan_id=_id(),
            organization_id=actor.organization_id,
            path_id=path.path_id,
            path_revision_id=revision.revision_id,
            previous_release_plan_id=path.active_release_plan_id,
            status="ready" if report["valid"] else "blocked",
            version=1,
            contract_hash=PATH_RUNTIME_CONTRACT_HASH,
            target_revisions_json=targets,
            dependency_graph_json=graph,
            validation_report_json=report,
            impact_preview_json=impact,
            impact_hash=impact_hash,
            preview_token_hash=_secret_hash(deterministic_token),
            preview_expires_at=now + timedelta(minutes=30),
            reason=reason.strip(),
            creation_idempotency_key_hash=_secret_hash(idempotency_key),
            creation_fingerprint=fingerprint,
            created_by=actor.actor_id,
            created_at=now,
        )
        self._session.add(plan)
        await self._session.flush([plan])
        await self._audit(
            actor=actor,
            plan=plan,
            command="preview_release_plan",
            result=plan.status,
            idempotency_key=idempotency_key,
            details={"blocker_count": len(issues), "impact": impact},
        )
        return self._preview_summary(plan, deterministic_token)

    async def publish(
        self,
        *,
        actor: CommandActor,
        release_plan_id: str,
        preview_token: str,
        impact_hash: str,
        expected_version: int,
        idempotency_key: str,
    ) -> ReleasePlanSummary:
        self._require(actor, "newcomer.path.publish")
        plan = await self._load_plan_for_update(actor, release_plan_id)
        fingerprint = _canonical_hash(
            {
                "release_plan_id": release_plan_id,
                "impact_hash": impact_hash,
                "expected_version": expected_version,
            }
        )
        if plan.status == "published":
            if (
                plan.publish_idempotency_key_hash == _secret_hash(idempotency_key)
                and plan.publish_fingerprint == fingerprint
            ):
                return self._summary(plan)
            self._idempotency_conflict()
        self._require_version(plan.version, expected_version, "发布计划")
        if plan.status != "ready":
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_NOT_READY]",
                "发布计划仍有阻塞项，请重新预览并处理。",
                409,
                details={"status": plan.status},
            )
        if plan.preview_token_hash != _secret_hash(preview_token):
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_PREVIEW_NOT_FOUND]",
                "发布预览不存在、已过期或不可访问。",
                404,
            )
        if self._is_expired(plan.preview_expires_at):
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_PREVIEW_EXPIRED]",
                "发布预览已过期，请重新创建发布计划。",
                409,
            )
        if plan.impact_hash != impact_hash:
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_IMPACT_MISMATCH]",
                "发布影响已经变化，请重新预览。",
                409,
            )
        if plan.contract_hash != PATH_RUNTIME_CONTRACT_HASH:
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_CONTRACT_CHANGED]",
                "运行时契约已经变化，请重新预览。",
                409,
            )
        revision = await self._load_revision(actor, plan.path_revision_id)
        path_target = plan.target_revisions_json[0]
        if (
            revision.status != "working"
            or revision.version != path_target["expected_revision_version"]
            or revision.content_hash != path_target["content_hash"]
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_TARGET_CHANGED]",
                "路径或引用修订已经变化，请重新预览。",
                409,
            )
        checked_dependencies: list[ReleaseDependency] = []
        for raw in plan.target_revisions_json[1:]:
            original = ReleaseDependency.model_validate(raw)
            if original.resource_type in {
                "audio_material",
                "audio_scoring_scheme",
                "audio_scenario",
                "coach_profile",
            }:
                inspected = await self._dependencies.inspect(
                    organization_id=actor.organization_id,
                    activity_type=self._activity_type_for_dependency(
                        plan.dependency_graph_json, original
                    ),
                    revision_id=original.revision_id,
                )
            else:
                inspected = await self._dependencies.inspect_resource(
                    organization_id=actor.organization_id,
                    resource_type=original.resource_type,
                    revision_id=original.revision_id,
                )
            if (
                inspected.content_hash != original.content_hash
                or inspected.resource_id != original.resource_id
                or inspected.issues
            ):
                raise NewcomerTrainingError(
                    "[NEWCOMER_RELEASE_TARGET_CHANGED]",
                    "引用资源状态已经变化，请重新预览。",
                    409,
                    details={"revision_id": original.revision_id},
                )
            checked_dependencies.append(inspected)

        before_version = plan.version
        plan.status = "publishing"
        plan.version += 1
        await self._session.flush([plan])
        try:
            async with self._session.begin_nested():
                for dependency in sorted(
                    checked_dependencies, key=self._publish_priority
                ):
                    if not dependency.publish_required:
                        continue
                    published = await self._dependencies.publish(
                        organization_id=actor.organization_id,
                        actor_id=actor.actor_id,
                        capability_set=actor.capabilities,
                        dependency=dependency,
                        idempotency_key=(
                            f"{idempotency_key}:resource:{dependency.revision_id}"
                        ),
                        reason=plan.reason,
                        trace_id=actor.trace_id,
                    )
                    if published.status != "published":
                        raise NewcomerTrainingError(
                            "[NEWCOMER_RELEASE_DEPENDENCY_PUBLISH_FAILED]",
                            "引用资源未能完成发布。",
                            422,
                            details={"revision_id": dependency.revision_id},
                        )
                published_path = await self._path_service.publish_revision(
                    actor=actor,
                    revision_id=revision.revision_id,
                    expected_revision_version=revision.version,
                    idempotency_key=f"{idempotency_key}:path",
                    reason=plan.reason,
                )
                path = await self._load_path_for_update(actor, plan.path_id)
                previous = None
                if path.active_release_plan_id:
                    previous = await self._session.get(
                        NewcomerReleasePlan, path.active_release_plan_id
                    )
                    if previous is not None and previous.release_plan_id != plan.release_plan_id:
                        previous.status = "superseded"
                        previous.version += 1
                now = _now()
                path.active_release_plan_id = plan.release_plan_id
                plan.status = "published"
                plan.version += 1
                plan.publish_idempotency_key_hash = _secret_hash(idempotency_key)
                plan.publish_fingerprint = fingerprint
                plan.published_by = actor.actor_id
                plan.published_at = now
                await self._session.flush(
                    [item for item in (path, plan, previous) if item is not None]
                )
                if published_path.revision_id != plan.path_revision_id:
                    raise NewcomerTrainingError(
                        "[NEWCOMER_RELEASE_PATH_MISMATCH]",
                        "路径发布结果与发布计划不一致。",
                        409,
                    )
        except NewcomerTrainingError as exc:
            plan.status = "failed"
            plan.version += 1
            plan.failed_at = _now()
            plan.validation_report_json = {
                **dict(plan.validation_report_json),
                "publish_failure": {"code": exc.code, "message": exc.message},
            }
            await self._session.flush([plan])
            await self._audit(
                actor=actor,
                plan=plan,
                command="publish_release_plan",
                result="failed",
                idempotency_key=idempotency_key,
                before_version=before_version,
                details={"failure_code": exc.code},
            )
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_PUBLISH_FAILED]",
                "发布未完成，原有生效版本保持不变。",
                422,
                details={
                    "release_plan_id": plan.release_plan_id,
                    "cause": exc.code,
                    "failure_persisted": True,
                },
            ) from exc
        await self._audit(
            actor=actor,
            plan=plan,
            command="publish_release_plan",
            result="succeeded",
            idempotency_key=idempotency_key,
            before_version=before_version,
            details={"previous_release_plan_id": plan.previous_release_plan_id},
        )
        return self._summary(plan)

    async def preview_rollback(
        self,
        *,
        actor: CommandActor,
        active_release_plan_id: str,
        target_release_plan_id: str,
        reason: str,
    ) -> RollbackPreview:
        self._require(actor, "newcomer.path.publish")
        if not reason.strip():
            raise NewcomerTrainingError(
                "[NEWCOMER_ROLLBACK_REASON_REQUIRED]", "请填写回滚原因。", 422
            )
        active = await self._load_plan_for_update(actor, active_release_plan_id)
        target = await self._load_plan(actor, target_release_plan_id)
        path = await self._load_path(actor, active.path_id)
        if (
            path.active_release_plan_id != active.release_plan_id
            or active.status != "published"
            or target.path_id != active.path_id
            or target.status not in {"published", "superseded"}
            or target.release_plan_id == active.release_plan_id
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_ROLLBACK_TARGET_INVALID]",
                "只能回滚到同一路径已知稳定的历史发布。",
                422,
            )
        impact = {
            "active_release_plan_id": active.release_plan_id,
            "target_release_plan_id": target.release_plan_id,
            "current_path_revision_id": active.path_revision_id,
            "target_path_revision_id": target.path_revision_id,
            "active_enrollments_unchanged": True,
            "future_enrollments_use_target": True,
            "reason": reason.strip(),
        }
        token = _id()
        impact_hash = _canonical_hash(impact)
        expires_at = _now() + timedelta(minutes=30)
        active.rollback_preview_token_hash = _secret_hash(token)
        active.rollback_impact_hash = impact_hash
        active.rollback_preview_json = impact
        active.rollback_preview_expires_at = expires_at
        active.version += 1
        await self._session.flush([active])
        await self._audit(
            actor=actor,
            plan=active,
            command="preview_release_rollback",
            result="previewed",
            idempotency_key=None,
            details=impact,
        )
        return RollbackPreview(
            active_release_plan_id=active.release_plan_id,
            target_release_plan_id=target.release_plan_id,
            preview_token=token,
            impact_hash=impact_hash,
            impact=impact,
            expires_at=expires_at,
        )

    async def confirm_rollback(
        self,
        *,
        actor: CommandActor,
        active_release_plan_id: str,
        preview_token: str,
        impact_hash: str,
        expected_version: int,
        idempotency_key: str,
    ) -> ReleasePlanSummary:
        self._require(actor, "newcomer.path.publish")
        active = await self._load_plan_for_update(actor, active_release_plan_id)
        self._require_version(active.version, expected_version, "当前发布")
        fingerprint = _canonical_hash(
            {
                "active_release_plan_id": active_release_plan_id,
                "impact_hash": impact_hash,
                "expected_version": expected_version,
            }
        )
        if active.rollback_confirm_idempotency_key_hash is not None:
            if (
                active.rollback_confirm_idempotency_key_hash
                != _secret_hash(idempotency_key)
                or active.rollback_confirm_fingerprint != fingerprint
            ):
                self._idempotency_conflict()
            if active.rollback_preview_json is None:
                raise NewcomerTrainingError(
                    "[NEWCOMER_ROLLBACK_PREVIEW_MISMATCH]",
                    "回滚记录不完整，请重新预览。",
                    409,
                )
            target_id = str(active.rollback_preview_json["target_release_plan_id"])
            return self._summary(await self._load_plan(actor, target_id))
        if (
            active.rollback_preview_token_hash != _secret_hash(preview_token)
            or active.rollback_impact_hash != impact_hash
            or active.rollback_preview_json is None
            or active.rollback_preview_expires_at is None
        ):
            raise NewcomerTrainingError(
                "[NEWCOMER_ROLLBACK_PREVIEW_MISMATCH]",
                "回滚影响已经变化，请重新预览。",
                409,
            )
        if self._is_expired(active.rollback_preview_expires_at):
            raise NewcomerTrainingError(
                "[NEWCOMER_ROLLBACK_PREVIEW_EXPIRED]",
                "回滚预览已过期，请重新预览。",
                409,
            )
        target_id = str(active.rollback_preview_json["target_release_plan_id"])
        target = await self._load_plan_for_update(actor, target_id)
        path = await self._load_path_for_update(actor, active.path_id)
        if path.active_release_plan_id != active.release_plan_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_CONFLICT]",
                "当前生效发布已经变化，请刷新后重试。",
                412,
            )
        before_version = active.version
        now = _now()
        active.status = "superseded"
        active.version += 1
        active.rolled_back_by = actor.actor_id
        active.rolled_back_at = now
        active.rollback_confirm_idempotency_key_hash = _secret_hash(idempotency_key)
        active.rollback_confirm_fingerprint = fingerprint
        target.status = "published"
        target.version += 1
        path.active_release_plan_id = target.release_plan_id
        path.published_revision_id = target.path_revision_id
        path.version += 1
        path.updated_at = now
        await self._session.flush([active, target, path])
        await self._audit(
            actor=actor,
            plan=active,
            command="rollback_release_plan",
            result="succeeded",
            idempotency_key=idempotency_key,
            before_version=before_version,
            details={
                "target_release_plan_id": target.release_plan_id,
                "active_enrollments_unchanged": True,
            },
        )
        return self._summary(target)

    async def list_plans(
        self,
        *,
        actor: CommandActor,
        path_id: str | None = None,
        limit: int = 50,
    ) -> tuple[ReleasePlanSummary, ...]:
        self._require(actor, "newcomer.path.publish")
        query = (
            select(NewcomerReleasePlan)
            .where(NewcomerReleasePlan.organization_id == actor.organization_id)
            .order_by(NewcomerReleasePlan.created_at.desc())
            .limit(max(1, min(limit, 100)))
        )
        if path_id:
            query = query.where(NewcomerReleasePlan.path_id == path_id)
        rows = (await self._session.execute(query)).scalars()
        return tuple(self._summary(row) for row in rows)

    async def _impact(
        self, *, path: NewcomerPath, target_revision: NewcomerPathRevision
    ) -> dict[str, Any]:
        current_revision_id = path.published_revision_id
        current_active_enrollments = 0
        if current_revision_id:
            current_active_enrollments = int(
                await self._session.scalar(
                    select(func.count(NewcomerEnrollment.enrollment_id))
                    .where(
                        NewcomerEnrollment.organization_id == path.organization_id
                    )
                    .where(NewcomerEnrollment.status == "active")
                    .where(
                        NewcomerEnrollment.path_revision_id == current_revision_id
                    )
                )
                or 0
            )
        target_active_enrollments = int(
            await self._session.scalar(
                select(func.count(NewcomerEnrollment.enrollment_id))
                .where(NewcomerEnrollment.organization_id == path.organization_id)
                .where(NewcomerEnrollment.status == "active")
                .where(
                    NewcomerEnrollment.path_revision_id == target_revision.revision_id
                )
            )
            or 0
        )
        active_attempts = int(
            await self._session.scalar(
                select(func.count(NewcomerActivityAttempt.attempt_id))
                .where(NewcomerActivityAttempt.organization_id == path.organization_id)
                .where(
                    NewcomerActivityAttempt.status.in_(
                        ("started", "in_progress", "waiting_external")
                    )
                )
            )
            or 0
        )
        return {
            "path_id": path.path_id,
            "current_release_plan_id": path.active_release_plan_id,
            "current_path_revision_id": current_revision_id,
            "target_path_revision_id": target_revision.revision_id,
            "active_enrollments_on_current_revision": current_active_enrollments,
            "active_enrollments_already_on_target_revision": target_active_enrollments,
            "active_attempts": active_attempts,
            "active_enrollments_unchanged": True,
            "automatic_migration": False,
            "future_enrollments_use_target": True,
            "rollback_available": path.active_release_plan_id is not None,
        }

    @staticmethod
    def _resource_refs(activity: Any) -> tuple[tuple[str, str], ...]:
        fields_by_type = {
            "lesson": ("learning_unit_revision_id",),
            "quiz": ("quiz_revision_id",),
            "audio_assessment": (
                "audio_material_revision_id",
                "scoring_scheme_revision_id",
            ),
            "ai_coach": ("coach_profile_revision_id",),
            "assignment": (
                "scenario_revision_id",
                "scoring_scheme_revision_id",
            ),
        }
        return tuple(
            (field, str(getattr(activity.config, field)))
            for field in fields_by_type[str(activity.type)]
        )

    @staticmethod
    def _dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return list({str(node["id"]): node for node in nodes}.values())

    @staticmethod
    def _is_acyclic(edges: list[dict[str, str]]) -> bool:
        adjacent: dict[str, set[str]] = {}
        for edge in edges:
            adjacent.setdefault(edge["from"], set()).add(edge["to"])
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> bool:
            if node in visiting:
                return False
            if node in visited:
                return True
            visiting.add(node)
            for child in adjacent.get(node, set()):
                if not visit(child):
                    return False
            visiting.remove(node)
            visited.add(node)
            return True

        return all(visit(node) for node in tuple(adjacent))

    @staticmethod
    def _activity_type_for_dependency(
        graph: dict[str, Any], dependency: ReleaseDependency
    ) -> str:
        node_id = f"{dependency.resource_type}:{dependency.revision_id}"
        edge = next(
            (
                item
                for item in graph.get("edges", [])
                if item.get("to") == node_id and item.get("activity_id")
            ),
            None,
        )
        if edge is None:
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_DEPENDENCY_GRAPH_INVALID]",
                "发布依赖图不完整，请重新预览。",
                409,
            )
        resource_type = dependency.resource_type
        return {
            "learning_unit": "lesson",
            "quiz": "quiz",
            "coach_profile": "ai_coach",
            "audio_material": "audio_assessment",
            "audio_scoring_scheme": "audio_assessment",
            "audio_scenario": "assignment",
        }.get(resource_type, "assignment")

    @staticmethod
    def _publish_priority(dependency: ReleaseDependency) -> int:
        return {
            "source_document": 10,
            "question": 20,
            "learning_unit": 30,
            "quiz": 40,
        }.get(dependency.resource_type, 50)

    async def _load_path(
        self, actor: CommandActor, path_id: str
    ) -> NewcomerPath:
        row = await self._session.get(NewcomerPath, path_id)
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_NOT_FOUND]", "训练路径不存在或不可访问。", 404
            )
        return row

    async def _load_path_for_update(
        self, actor: CommandActor, path_id: str
    ) -> NewcomerPath:
        row = await self._session.scalar(
            select(NewcomerPath)
            .where(NewcomerPath.path_id == path_id)
            .with_for_update()
            .limit(1)
        )
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_NOT_FOUND]", "训练路径不存在或不可访问。", 404
            )
        return row

    async def _load_revision(
        self, actor: CommandActor, revision_id: str
    ) -> NewcomerPathRevision:
        row = await self._session.get(NewcomerPathRevision, revision_id)
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_PATH_REVISION_NOT_FOUND]",
                "训练路径修订不存在或不可访问。",
                404,
            )
        return row

    async def _load_plan(
        self, actor: CommandActor, release_plan_id: str
    ) -> NewcomerReleasePlan:
        row = await self._session.get(NewcomerReleasePlan, release_plan_id)
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_NOT_FOUND]", "发布记录不存在或不可访问。", 404
            )
        return row

    async def _load_plan_for_update(
        self, actor: CommandActor, release_plan_id: str
    ) -> NewcomerReleasePlan:
        row = await self._session.scalar(
            select(NewcomerReleasePlan)
            .where(NewcomerReleasePlan.release_plan_id == release_plan_id)
            .with_for_update()
            .limit(1)
        )
        if row is None or row.organization_id != actor.organization_id:
            raise NewcomerTrainingError(
                "[NEWCOMER_RELEASE_NOT_FOUND]", "发布记录不存在或不可访问。", 404
            )
        return row

    @staticmethod
    def _require(actor: CommandActor, capability: str) -> None:
        if capability not in actor.capabilities:
            raise NewcomerTrainingError(
                "[NEWCOMER_PERMISSION_DENIED]", "没有执行此操作的权限。", 403
            )

    @staticmethod
    def _require_version(actual: int, expected: int, label: str) -> None:
        if actual != expected:
            raise NewcomerTrainingError(
                "[NEWCOMER_VERSION_CONFLICT]",
                f"{label}已被其他人更新，请刷新后重试。",
                412,
                details={"expected_version": expected, "actual_version": actual},
            )

    @staticmethod
    def _is_expired(value: datetime) -> bool:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value <= _now()

    @staticmethod
    def _idempotency_conflict() -> None:
        raise NewcomerTrainingError(
            "[NEWCOMER_IDEMPOTENCY_CONFLICT]",
            "相同幂等键对应了不同请求。",
            409,
        )

    @staticmethod
    def _summary(plan: NewcomerReleasePlan) -> ReleasePlanSummary:
        return ReleasePlanSummary(
            release_plan_id=plan.release_plan_id,
            organization_id=plan.organization_id,
            path_id=plan.path_id,
            path_revision_id=plan.path_revision_id,
            previous_release_plan_id=plan.previous_release_plan_id,
            status=plan.status,
            version=plan.version,
            contract_hash=plan.contract_hash,
            target_revisions=tuple(plan.target_revisions_json),
            dependency_graph=dict(plan.dependency_graph_json),
            validation_report=dict(plan.validation_report_json),
            impact_preview=dict(plan.impact_preview_json),
            impact_hash=plan.impact_hash,
            reason=plan.reason,
            created_by=plan.created_by,
            published_by=plan.published_by,
            rolled_back_by=plan.rolled_back_by,
            created_at=plan.created_at,
            published_at=plan.published_at,
            rolled_back_at=plan.rolled_back_at,
        )

    @classmethod
    def _preview_summary(
        cls, plan: NewcomerReleasePlan, token: str
    ) -> ReleasePlanPreview:
        return ReleasePlanPreview(
            **cls._summary(plan).model_dump(),
            preview_token=token,
            preview_expires_at=plan.preview_expires_at,
        )

    async def _audit(
        self,
        *,
        actor: CommandActor,
        plan: NewcomerReleasePlan,
        command: str,
        result: str,
        idempotency_key: str | None,
        before_version: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            NewcomerCommandAudit(
                audit_id=_id(),
                organization_id=actor.organization_id,
                actor_id=actor.actor_id,
                capability="newcomer.path.publish",
                object_type="release_plan",
                object_id=plan.release_plan_id,
                command=command,
                before_version=before_version,
                after_version=plan.version,
                idempotency_key_hash=(
                    _secret_hash(idempotency_key) if idempotency_key else None
                ),
                expected_version=before_version,
                actual_version=plan.version,
                reason=plan.reason,
                preview_token_hash=plan.preview_token_hash,
                impact_hash=plan.impact_hash,
                trace_id=actor.trace_id,
                result=result,
                details_json=details or {},
                occurred_at=_now(),
            )
        )
        await self._session.flush()


__all__ = [
    "PATH_RUNTIME_CONTRACT_HASH",
    "ReleasePlanPreview",
    "ReleasePlanService",
    "ReleasePlanSummary",
    "ReleaseValidationIssue",
    "RollbackPreview",
]
