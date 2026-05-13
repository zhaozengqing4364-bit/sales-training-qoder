from __future__ import annotations

from inspect import isawaitable

from curriculum_practice.schemas import (
    GateResult,
    PracticeTemplatePublishCandidate,
    PublishGateDecision,
    ReferenceReader,
)


class PublishingGateService:
    def __init__(self, reference_reader: ReferenceReader) -> None:
        self._reference_reader = reference_reader

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
                if asset_type in ("case_item", "role_profile"):
                    results.append(
                        GateResult(
                            gate_name="content_asset_reference",
                            status="failed",
                            reason_code=f"{asset_type}_unpublished",
                            message=(
                                f"{asset_type} reference {asset_id} does not exist or is not published."
                            ),
                        )
                    )
                    continue
                if asset_type == "scoring_ruleset":
                    results.append(
                        GateResult(
                            gate_name="scoring_rubric_reference",
                            status="failed",
                            reason_code="scoring_rubric_missing",
                            message=(
                                f"{asset_type} reference {asset_id} does not exist or is not readable."
                            ),
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
            for stage in candidate.curriculum_plan.stages:
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
                            reason_code="child_template_unpublished",
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
                if child_runtime_profile_id is not None:
                    runtime_profile_ids.append(str(child_runtime_profile_id))
            if len(set(runtime_profile_ids)) > 1:
                results.append(
                    GateResult(
                        gate_name="curriculum_plan_voice_switch",
                        status="failed",
                        reason_code="cross_stage_voice_hot_switch_unsupported",
                        message="CurriculumPlan cannot hot-switch runtime voices across stages.",
                    )
                )

        return PublishGateDecision(can_publish=not results, results=results)

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
        return refs


def _template_stage_key(prerequisite: object) -> str:
    if isinstance(prerequisite, dict):
        return str(prerequisite["template_stage_key"])
    return str(getattr(prerequisite, "template_stage_key"))
