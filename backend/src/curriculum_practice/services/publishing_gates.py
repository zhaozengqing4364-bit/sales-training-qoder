from __future__ import annotations

from inspect import isawaitable
from typing import Any

from common.business_rules.service import BusinessRuleResolution
from curriculum_practice.schemas import (
    GateResult,
    PracticeTemplatePublishCandidate,
    PublishGateDecision,
    ReferenceReader,
)
from curriculum_practice.services.published_asset_refs import build_published_asset_refs
from curriculum_practice.services.roleplay.situation_pack_repository import (
    SituationPackRepository,
)
from curriculum_practice.services.roleplay_contracts import RoleplayContractCompiler

_REFERENCE_MISSING_FAILURES: dict[str, tuple[str, str]] = {
    "case_item": ("content_asset_reference", "asset_unpublished"),
    "role_profile": ("content_asset_reference", "asset_unpublished"),
    "learning_content": ("content_asset_reference", "asset_unpublished"),
    "knowledge_base": ("content_asset_reference", "asset_unpublished"),
    "scoring_ruleset": ("scoring_rubric_reference", "rubric_missing"),
    "examiner_agent": ("examiner_agent_reference", "examiner_agent_unpublished"),
}


class PublishingGateService:
    def __init__(
        self,
        reference_reader: ReferenceReader,
        *,
        situation_packs: SituationPackRepository | None = None,
        situation_pack_config: BusinessRuleResolution | None = None,
    ) -> None:
        self._reference_reader = reference_reader
        self._situation_packs = situation_packs
        self._situation_pack_config = situation_pack_config

    async def validate(
        self, candidate: PracticeTemplatePublishCandidate
    ) -> PublishGateDecision:
        results: list[GateResult] = []
        if candidate.scenario_type not in ("sales", "presentation"):
            results.append(
                GateResult(
                    gate_name="scenario_type_policy",
                    status="failed",
                    reason_code="scenario_type_not_supported",
                    message="PracticeTemplate publish requires scenario_type=sales or presentation.",
                )
            )

        for asset_type, asset_id in self._required_refs(candidate):
            reference = self._reference_reader(asset_type, asset_id)
            if isawaitable(reference):
                reference = await reference
            if reference is None:
                known_failure = _REFERENCE_MISSING_FAILURES.get(asset_type)
                if known_failure is not None:
                    gate_name, reason_code = known_failure
                    results.append(
                        GateResult(
                            gate_name=gate_name,
                            status="failed",
                            reason_code=reason_code,
                            message=f"{asset_type} reference {asset_id} does not exist or is not published.",
                        )
                    )
                    continue
                results.append(
                    GateResult(
                        gate_name="reference_integrity",
                        status="failed",
                        reason_code="reference_missing",
                        message=f"{asset_type} reference {asset_id} does not exist or is not readable.",
                    )
                )

        if candidate.voice_mode != "stepfun_realtime":
            results.append(
                GateResult(
                    gate_name="voice_runtime_policy",
                    status="failed",
                    reason_code="voice_mode_not_stepfun_realtime",
                    message="PracticeTemplate publish requires voice_mode=stepfun_realtime.",
                )
            )

        if candidate.curriculum_plan is not None:
            results.extend(self._validate_curriculum_graph(candidate))
            runtime_profile_ids: list[str] = []
            role_profile_voice_ids: list[str] = []
            for stage in candidate.curriculum_plan.stages:
                if stage.stage_type in ("study", "exam"):
                    stage_asset = self._reference_reader(
                        stage.template_ref.asset_type, stage.template_ref.asset_id
                    )
                    if isawaitable(stage_asset):
                        stage_asset = await stage_asset
                    stage_status = getattr(stage_asset, "status", None)
                    if isinstance(stage_asset, dict):
                        stage_status = stage_asset.get("status")
                    if stage_status != "published":
                        results.append(
                            GateResult(
                                gate_name="curriculum_plan_stage_asset",
                                status="failed",
                                reason_code="asset_unpublished",
                                message=(
                                    "CurriculumPlan stage "
                                    f"{stage.template_stage_key} references an unpublished "
                                    f"{stage.template_ref.asset_type} asset."
                                ),
                            )
                        )
                    continue
                if (
                    candidate.max_stage_duration_seconds is not None
                    and stage.completion_policy.max_duration_seconds
                    > candidate.max_stage_duration_seconds
                ):
                    results.append(
                        GateResult(
                            gate_name="curriculum_plan_stage_duration",
                            status="failed",
                            reason_code="stage_duration_exceeds_limit",
                            message=(
                                "CurriculumPlan stage "
                                f"{stage.template_stage_key} exceeds the template stage duration limit."
                            ),
                        )
                    )
                child_template = self._reference_reader(
                    "practice_template", stage.template_ref.asset_id
                )
                if isawaitable(child_template):
                    child_template = await child_template
                child_status = getattr(child_template, "status", None)
                if isinstance(child_template, dict):
                    child_status = child_template.get("status")
                if child_status != "published":
                    results.append(
                        GateResult(
                            gate_name="curriculum_plan_child_templates",
                            status="failed",
                            reason_code="template_unpublished",
                            message=(
                                "CurriculumPlan stage "
                                f"{stage.template_stage_key} references an unpublished child template."
                            ),
                        )
                    )
                    continue
                child_voice_mode = getattr(child_template, "voice_mode", None)
                child_runtime_profile_id = getattr(
                    child_template, "runtime_profile_id", None
                )
                if isinstance(child_template, dict):
                    child_voice_mode = child_template.get("voice_mode")
                    child_runtime_profile_id = child_template.get("runtime_profile_id")
                    child_role_profile_voice_id = child_template.get(
                        "role_profile_voice_id"
                    )
                else:
                    child_role_profile_voice_id = getattr(
                        child_template, "role_profile_voice_id", None
                    )
                if child_voice_mode != "stepfun_realtime":
                    results.append(
                        GateResult(
                            gate_name="curriculum_plan_child_voice",
                            status="failed",
                            reason_code="child_template_wrong_voice_mode",
                            message=(
                                "CurriculumPlan stage "
                                f"{stage.template_stage_key} child template must use stepfun_realtime."
                            ),
                        )
                    )
                child_scoring_ruleset_id = getattr(
                    child_template, "scoring_ruleset_id", None
                )
                if isinstance(child_template, dict):
                    child_scoring_ruleset_id = child_template.get("scoring_ruleset_id")
                if child_scoring_ruleset_id is not None:
                    child_ruleset = self._reference_reader(
                        "scoring_ruleset", str(child_scoring_ruleset_id)
                    )
                    if isawaitable(child_ruleset):
                        child_ruleset = await child_ruleset
                    max_score = _scoring_ruleset_max_score(child_ruleset)
                    if (
                        max_score is not None
                        and stage.completion_policy.min_score > max_score
                    ):
                        results.append(
                            GateResult(
                                gate_name="curriculum_plan_completion_policy",
                                status="failed",
                                reason_code="completion_policy_impossible",
                                message=(
                                    "CurriculumPlan stage "
                                    f"{stage.template_stage_key} requires min_score "
                                    "above the child template scoring capability."
                                ),
                            )
                        )
                if child_runtime_profile_id is not None:
                    runtime_profile_ids.append(str(child_runtime_profile_id))
                if child_role_profile_voice_id is not None:
                    normalized_voice_id = str(child_role_profile_voice_id).strip()
                    if normalized_voice_id:
                        role_profile_voice_ids.append(normalized_voice_id)
            if len(set(runtime_profile_ids)) > 1:
                results.append(
                    GateResult(
                        gate_name="curriculum_plan_voice_switch",
                        status="failed",
                        reason_code="cross_stage_voice_hot_switch_unsupported",
                        message="CurriculumPlan cannot hot-switch runtime voices across stages.",
                    )
                )
            if len(set(role_profile_voice_ids)) > 1:
                results.append(
                    GateResult(
                        gate_name="curriculum_plan_voice_switch",
                        status="failed",
                        reason_code="cross_stage_voice_hot_switch_unsupported",
                        message="CurriculumPlan cannot hot-switch role profile voices across stages.",
                    )
                )

        if not results:
            roleplay_gate_results = await RoleplayContractCompiler(
                self._reference_reader,
                situation_packs=self._situation_packs,
            ).validate_template_candidate(candidate, actor_id="publish_gate")
            results.extend(roleplay_gate_results)

        return PublishGateDecision(can_publish=not results, results=results)

    async def build_published_asset_refs(
        self,
        candidate: PracticeTemplatePublishCandidate,
        *,
        resolved_at: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        if self._situation_packs is None:
            raise ValueError("SituationPackRepository is required to freeze published refs.")
        return await build_published_asset_refs(
            candidate,
            reference_reader=self._reference_reader,
            situation_packs=self._situation_packs,
            situation_pack_config=self._situation_pack_config,
            resolved_at=resolved_at,
        )

    def _validate_curriculum_graph(
        self, candidate: PracticeTemplatePublishCandidate
    ) -> list[GateResult]:
        if candidate.curriculum_plan is None:
            return []
        results: list[GateResult] = []
        graph = {
            stage.template_stage_key: [
                _template_stage_key(prerequisite)
                for prerequisite in stage.prerequisites
            ]
            for stage in candidate.curriculum_plan.stages
        }
        for stage_key, prerequisites in graph.items():
            if stage_key in prerequisites:
                results.append(
                    GateResult(
                        gate_name="curriculum_plan_reachability",
                        status="failed",
                        reason_code="curriculum_stage_unreachable",
                        message=f"CurriculumPlan stage {stage_key} depends on itself.",
                    )
                )

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(stage_key: str) -> None:
            if stage_key in visited:
                return
            if stage_key in visiting:
                results.append(
                    GateResult(
                        gate_name="curriculum_plan_graph",
                        status="failed",
                        reason_code="curriculum_plan_cycle",
                        message="CurriculumPlan stage prerequisites contain a cycle.",
                    )
                )
                return
            visiting.add(stage_key)
            for prerequisite_key in graph.get(stage_key, []):
                visit(prerequisite_key)
            visiting.remove(stage_key)
            visited.add(stage_key)

        for stage_key in graph:
            visit(stage_key)
        return results

    def _required_refs(
        self, candidate: PracticeTemplatePublishCandidate
    ) -> list[tuple[str, str]]:
        refs = [
            ("agent", candidate.agent_id),
            ("persona", candidate.persona_id),
            ("voice_runtime_profile", candidate.runtime_profile_id),
            ("scoring_ruleset", candidate.scoring_ruleset_id),
        ]
        refs.extend(("knowledge_base", item) for item in candidate.knowledge_base_refs)
        if candidate.case_item_id:
            refs.append(("case_item", candidate.case_item_id))
        if candidate.role_profile_id:
            refs.append(("role_profile", candidate.role_profile_id))
        if candidate.learning_content_id:
            refs.append(("learning_content", candidate.learning_content_id))
        if candidate.examiner_agent_id:
            refs.append(("examiner_agent", candidate.examiner_agent_id))
        return refs


def _template_stage_key(prerequisite: object) -> str:
    if isinstance(prerequisite, dict):
        return str(prerequisite["template_stage_key"])
    return str(getattr(prerequisite, "template_stage_key"))


def _scoring_ruleset_max_score(ruleset: object | None) -> float | None:
    """Return declared scoring max score when the ruleset exposes one.

    Absence of this metadata means the gate cannot prove impossibility, so publish
    validation stays permissive for legacy scoring rulesets.
    """
    if ruleset is None:
        return None
    definition = getattr(ruleset, "definition_json", None)
    if isinstance(ruleset, dict):
        definition = ruleset.get("definition_json")
    if not isinstance(definition, dict):
        return None

    candidates = [definition.get("max_score"), definition.get("score_max")]
    score_scale = definition.get("score_scale")
    if isinstance(score_scale, dict):
        candidates.extend([score_scale.get("max_score"), score_scale.get("max")])

    for candidate in candidates:
        try:
            if candidate is not None:
                return float(candidate)
        except (TypeError, ValueError):
            continue
    return None
