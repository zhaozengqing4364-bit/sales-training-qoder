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

        return PublishGateDecision(can_publish=not results, results=results)

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
        return refs
