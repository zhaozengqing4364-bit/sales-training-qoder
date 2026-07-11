from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from training_runtime.realtime import (
    ENGINE_STATE_VERSION,
    GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
    ConnectionPhase,
    ConnectionState,
    EvidenceState,
    GroundingCacheDisposition,
    GroundingCacheStats,
    GroundingCitation,
    GroundingDecisionResult,
    GroundingDiagnostics,
    GroundingEvidence,
    GroundingMode,
    GroundingOutcome,
    GroundingPhase,
    GroundingState,
    NoopScenarioTurnHooks,
    RealtimeSessionEngine,
    RealtimeSessionState,
    RealtimeStateTransitionError,
    RealtimeTransition,
    TurnPhase,
    TurnState,
)

REQUIRED_GOLDEN_CONTRACT_IDS = {
    "admission.invalid_session",
    "admission.runtime_gate",
    "admission.unauthorized",
    "admission.owner_scope",
    "conversation.connect_start_text_audio_response_done",
    "transport.binary_audio",
    "transport.timeout_backpressure_degraded",
    "snapshot.frozen_policy_kb_fail_closed",
    "reconnect.epoch_monotonic",
    "evidence.transcript_score_report_idempotent",
    "roleplay.observation_record_only",
    "rollout.single_writer_rollback",
}
GROUNDING_DIAGNOSTIC_STRING_VOCABULARY = {
    "status": {
        "ready",
        "blocked",
        "degraded",
        "skipped",
        "failed",
        "unavailable",
        "healthy",
    },
    "reason_code": {
        "not_applicable",
        "policy_missing",
        "policy_blocked",
        "kb_lock_blocked",
        "retrieval_ready",
        "retrieval_timeout",
        "retrieval_error",
        "retrieval_no_hit",
        "provider_unavailable",
        "snapshot_restored",
        "presentation_feedback_ready",
    },
    "source": {
        "runtime",
        "snapshot",
        "policy",
        "knowledge",
        "provider",
        "cache",
        "presentation",
        "sales",
        "unknown",
    },
    "mode": {
        "grounded",
        "blocked",
        "degraded",
        "skipped",
        "unrestricted",
        "kb_lock",
        "not_applicable",
    },
    "error_type": {
        "timeout",
        "connection",
        "validation",
        "provider",
        "retrieval",
        "configuration",
        "unknown",
        "none",
    },
    "fallback_reason": {
        "none",
        "timeout",
        "no_hit",
        "unavailable",
        "policy_blocked",
        "provider_error",
        "not_applicable",
    },
}
GROUNDING_DIAGNOSTIC_INJECTION_VALUES = {
    "sk-proj-abc123",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.signature",
    "a3f1b7c9d2e4f608a3f1b7c9d2e4f608a3f1b7c9d2e4f608a3f1b7c9d2e4f608",
    "P4ssword:Secret",
    "customerconfirmedbudget",
}
FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "realtime"
    / "golden_conversation_contract_v1.json"
)
GOLDEN_EVIDENCE_BY_CONTRACT = {
    "admission.invalid_session": [
        "tests/unit/test_main_presentation_ws_runtime.py::test_presentation_websocket_route_rejects_invalid_session_before_runtime_side_effects"
    ],
    "admission.runtime_gate": [
        "tests/unit/test_main_presentation_ws_runtime.py::test_presentation_ws_rejects_when_kb_lock_unbound"
    ],
    "admission.unauthorized": [
        "tests/unit/test_main_presentation_ws_runtime.py::test_presentation_ws_rejects_invalid_token_before_registering_session"
    ],
    "admission.owner_scope": [
        "tests/unit/test_main_presentation_ws_runtime.py::test_presentation_ws_rejects_owner_mismatch_before_registering_session"
    ],
    "conversation.connect_start_text_audio_response_done": [
        "tests/unit/test_presentation_realtime_engine_handler.py::test_golden_differential_preserves_external_single_writer_contract"
    ],
    "transport.binary_audio": [
        "tests/unit/test_stepfun_realtime_handler.py::test_binary_audio_disposition_rejects_non_accepted_frames"
    ],
    "transport.timeout_backpressure_degraded": [
        "tests/unit/test_stepfun_realtime_upstream.py::test_upstream_idle_timeout_error_refreshes_connection_before_forwarding_error",
        "tests/unit/test_stepfun_realtime_handler.py::test_binary_audio_quality_does_not_count_backpressure_dropped_audio",
    ],
    "snapshot.frozen_policy_kb_fail_closed": [
        "tests/unit/test_stepfun_realtime_handler.py::test_load_effective_policy_prefers_frozen_session_snapshot_over_live_resolution",
        "tests/unit/test_stepfun_realtime_handler.py::test_prepare_grounding_context_blocks_bound_kb_query_when_retrieval_empty_and_lock_on",
    ],
    "reconnect.epoch_monotonic": [
        "tests/unit/test_presentation_realtime_engine_handler.py::test_golden_differential_preserves_external_single_writer_contract",
        "tests/unit/test_presentation_realtime_engine_handler.py::test_pre_gate_snapshot_derives_engine_state_and_matches_legacy_epoch",
    ],
    "evidence.transcript_score_report_idempotent": [
        "tests/unit/test_stepfun_realtime_handler.py::test_handle_upstream_transcription_completed_ignores_duplicate_transcript_within_window",
        "tests/integration/test_session_lifecycle_api.py::test_sales_end_response_stays_scoring_but_background_finalization_can_complete_session",
        "tests/integration/test_session_lifecycle_api.py::test_lifecycle_api_end_is_idempotent_and_logs_unified_terminal_context",
    ],
    "roleplay.observation_record_only": [
        "tests/unit/test_sales_trainer_roleplay_observation_service.py::test_should_allow_non_blocking_store_failure_without_poisoning_main_flow"
    ],
    "rollout.single_writer_rollback": [
        "tests/unit/test_presentation_realtime_engine_handler.py::test_golden_differential_preserves_external_single_writer_contract"
    ],
}


def test_should_freeze_required_golden_conversation_contracts() -> None:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert payload["version"] == 1
    contracts = payload["contracts"]
    assert {contract["id"] for contract in contracts} == REQUIRED_GOLDEN_CONTRACT_IDS
    assert all(
        set(contract)
        == {
            "id",
            "category",
            "stable_expectation",
            "evidence",
            "rollback_relevance",
        }
        for contract in contracts
    )
    assert all(contract["evidence"] for contract in contracts)
    assert {
        contract["id"]: contract["evidence"] for contract in contracts
    } == GOLDEN_EVIDENCE_BY_CONTRACT

    evidence_reference_pattern = re.compile(
        r"^tests/(?:unit|integration|contract)/[^:]+\.py::test_[A-Za-z0-9_]+$"
    )
    backend_root = Path(__file__).parents[2]
    for references in GOLDEN_EVIDENCE_BY_CONTRACT.values():
        for reference in references:
            assert evidence_reference_pattern.fullmatch(reference)
            relative_path, test_name = reference.split("::", maxsplit=1)
            source_path = backend_root / relative_path
            assert source_path.is_file()
            assert re.search(
                rf"^(?:async )?def {re.escape(test_name)}\(",
                source_path.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            )


def test_should_create_explicit_default_state() -> None:
    state = RealtimeSessionState(scenario_type="presentation")

    assert ENGINE_STATE_VERSION == 1
    assert state.connection == ConnectionState()
    assert state.connection.phase is ConnectionPhase.DISCONNECTED
    assert state.turn == TurnState()
    assert state.turn.phase is TurnPhase.IDLE
    assert state.grounding == GroundingState()
    assert state.grounding.phase is GroundingPhase.EMPTY
    assert state.evidence == EvidenceState()


def test_should_round_trip_state_without_sharing_mutable_data() -> None:
    state = RealtimeSessionState(scenario_type="presentation")
    state.connection.session_id = "session-1"
    state.connection.epoch = 3
    state.grounding.diagnostics["schema_version"] = GROUNDING_DIAGNOSTICS_SCHEMA_VERSION
    state.grounding.diagnostics["source"] = "policy"
    assert state.evidence.record(
        evidence_key="transcript:1:user",
        evidence_type="transcript",
        turn_number=1,
        payload_digest="sha256:learner",
    )
    state.evidence.mark_pending("transcript:1:user")

    payload = state.to_dict()
    restored = RealtimeSessionState.from_dict(payload)

    assert restored == state
    payload["connection"]["epoch"] = 99  # type: ignore[index]
    payload["grounding"]["diagnostics"]["source"] = "mutated"  # type: ignore[index]
    assert state.connection.epoch == 3
    assert state.grounding.diagnostics == {
        "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
        "source": "policy",
    }


def test_should_reject_unsupported_future_state_version() -> None:
    with pytest.raises(ValueError, match="unsupported_engine_state_version"):
        RealtimeSessionState.from_dict(
            {
                "version": ENGINE_STATE_VERSION + 1,
                "scenario_type": "presentation",
            }
        )


@pytest.mark.parametrize("invalid_version", [True, False, 1.0, "1", 2])
def test_should_require_exact_non_boolean_integer_state_version(
    invalid_version: object,
) -> None:
    with pytest.raises(ValueError, match="engine_state_version"):
        RealtimeSessionState.from_dict(
            {
                "version": invalid_version,
                "scenario_type": "presentation",
            }
        )
    with pytest.raises(ValueError, match="engine_state_version"):
        RealtimeSessionState(
            scenario_type="presentation",
            version=invalid_version,  # type: ignore[arg-type]
        )


def test_should_restore_version_one_payload_with_optional_fields_absent() -> None:
    restored = RealtimeSessionState.from_dict(
        {"version": 1, "scenario_type": "presentation"}
    )

    assert restored == RealtimeSessionState(scenario_type="presentation")


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"connection": {"healthy": "false"}}, "connection_healthy_must_be_boolean"),
        (
            {"connection": {"reconnecting": 0}},
            "connection_reconnecting_must_be_boolean",
        ),
        ({"connection": {"epoch": True}}, "connection_epoch_must_be_integer"),
        ({"connection": {"epoch": 1.5}}, "connection_epoch_must_be_integer"),
        ({"turn": {"request_id": True}}, "turn_request_id_must_be_integer"),
        ({"turn": {"request_id": 2.5}}, "turn_request_id_must_be_integer"),
        (
            {
                "evidence": {
                    "records": {
                        "transcript:1:user": {
                            "evidence_key": "transcript:1:user",
                            "evidence_type": "transcript",
                            "turn_number": 1.5,
                            "payload_digest": "sha256:stable",
                        }
                    }
                }
            },
            "evidence_turn_number_must_be_integer",
        ),
    ],
)
def test_should_reject_scalar_type_coercion_when_restoring_engine_snapshot(
    payload: dict[str, object],
    message: str,
) -> None:
    snapshot = {
        "version": ENGINE_STATE_VERSION,
        "scenario_type": "presentation",
        **payload,
    }

    with pytest.raises(ValueError, match=message):
        RealtimeSessionState.from_dict(snapshot)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"scenario_type": 123}, "scenario_type_must_be_string"),
        (
            {"connection": {"session_id": 123}},
            "connection_session_id_must_be_string",
        ),
        ({"turn": {"response_id": 123}}, "turn_response_id_must_be_string"),
        (
            {
                "evidence": {
                    "records": {
                        "transcript:1:user": {
                            "evidence_key": "transcript:1:user",
                            "evidence_type": 123,
                            "turn_number": 1,
                            "payload_digest": "sha256:stable",
                        }
                    }
                }
            },
            "evidence_type_must_be_string",
        ),
    ],
)
def test_should_reject_string_field_coercion_when_restoring_engine_snapshot(
    payload: dict[str, object],
    message: str,
) -> None:
    snapshot = {
        "version": ENGINE_STATE_VERSION,
        "scenario_type": "presentation",
        **payload,
    }

    with pytest.raises(ValueError, match=message):
        RealtimeSessionState.from_dict(snapshot)


def test_should_require_exact_string_keys_in_restored_evidence_records() -> None:
    with pytest.raises(ValueError, match="evidence_record_key_must_be_string"):
        EvidenceState.from_dict(
            {
                "records": {
                    1: {
                        "evidence_key": "1",
                        "evidence_type": "transcript",
                        "turn_number": 1,
                        "payload_digest": "sha256:stable",
                    }
                }
            }
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "message"),
    [
        ("pending_flush_keys", "known", "pending_flush_keys_must_be_list"),
        ("pending_flush_keys", {"known": True}, "pending_flush_keys_must_be_list"),
        ("pending_flush_keys", ("known",), "pending_flush_keys_must_be_list"),
        ("pending_flush_keys", 1, "pending_flush_keys_must_be_list"),
        ("pending_flush_keys", None, "pending_flush_keys_must_be_list"),
        ("pending_flush_keys", [1], "pending_flush_key_must_be_string"),
        ("pending_flush_keys", [True], "pending_flush_key_must_be_string"),
        ("pending_flush_keys", [None], "pending_flush_key_must_be_string"),
        ("pending_flush_keys", [{"nested": True}], "pending_flush_key_must_be_string"),
        ("pending_flush_keys", [""], "pending_flush_key_must_be_non_empty"),
        ("acknowledged_keys", "known", "acknowledged_keys_must_be_list"),
        ("acknowledged_keys", {"known": True}, "acknowledged_keys_must_be_list"),
        ("acknowledged_keys", ("known",), "acknowledged_keys_must_be_list"),
        ("acknowledged_keys", 1, "acknowledged_keys_must_be_list"),
        ("acknowledged_keys", None, "acknowledged_keys_must_be_list"),
        ("acknowledged_keys", [1], "acknowledged_key_must_be_string"),
        ("acknowledged_keys", [True], "acknowledged_key_must_be_string"),
        ("acknowledged_keys", [None], "acknowledged_key_must_be_string"),
        ("acknowledged_keys", [{"nested": True}], "acknowledged_key_must_be_string"),
        ("acknowledged_keys", [""], "acknowledged_key_must_be_non_empty"),
    ],
)
def test_should_require_json_string_arrays_for_restored_evidence_key_sets(
    field_name: str,
    invalid_value: object,
    message: str,
) -> None:
    records = {
        key: {
            "evidence_key": key,
            "evidence_type": "transcript",
            "turn_number": 1,
            "payload_digest": "sha256:stable",
        }
        for key in ("known", "1", "True", "None", "{'nested': True}")
    }

    with pytest.raises(ValueError, match=message):
        EvidenceState.from_dict(
            {
                "records": records,
                field_name: invalid_value,
            }
        )


def test_should_accept_versioned_grounding_diagnostics_allowlist() -> None:
    diagnostics: dict[str, object] = {
        "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
        "status": "ready",
        "reason_code": "retrieval_ready",
        "source": "policy",
        "mode": "grounded",
        "error_type": "none",
        "fallback_reason": "not_applicable",
        "latency_ms": 3.5,
        "result_count": 4,
        "kb_count": 2,
        "hit_count": 3,
        "miss_count": 1,
        "cache_size": 8,
        "cache_hit": False,
        "timeout": False,
        "degraded": True,
        "blocked": False,
        "confidence": 0.75,
        "answerability_score": 1.0,
    }
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")

    engine.resolve_grounding(
        outcome="degraded",
        mode="fail_closed",
        diagnostics=diagnostics,
    )

    assert engine.state.grounding.diagnostics == diagnostics
    json.dumps(engine.snapshot(), allow_nan=False)


@pytest.mark.parametrize(
    ("disposition", "cache_hit"),
    [
        (GroundingCacheDisposition.HIT, True),
        (GroundingCacheDisposition.SHARED, True),
        (GroundingCacheDisposition.MISS, False),
        (GroundingCacheDisposition.BYPASS, False),
    ],
)
def test_grounding_decision_projects_closed_engine_schema_v1_without_free_text(
    disposition: GroundingCacheDisposition,
    cache_hit: bool,
) -> None:
    evidence = GroundingEvidence(
        citations=(
            GroundingCitation(
                knowledge_base_id="kb-secret-id",
                knowledge_base_name="客户私有库",
                document_title="私有文档",
                snippet="不得进入 Engine 的原文",
                claim="不得进入 Engine 的主张",
                score=0.9,
            ),
        ),
        rewritten_queries=("不得进入 Engine 的问题",),
        answerability="sufficient",
        source_status="hit",
        retrieval_mode="vector",
    )
    decision = GroundingDecisionResult(
        decision_id="grounding:4:9",
        frozen_policy_hash="sha256:frozen",
        outcome=GroundingOutcome.READY,
        mode=GroundingMode.GROUNDED,
        allow_generation=True,
        grounding_context="不得进入 Engine 的上下文",
        blocked_response="",
        output_guard_required=False,
        evidence=evidence,
        cache_disposition=disposition,
        diagnostics=GroundingDiagnostics(
            schema_version=1,
            status="grounded",
            reason_code="provider token must not escape",
            source="internal_knowledge",
            mode="grounded",
            degraded=False,
            blocked=False,
            cache_disposition=disposition,
            result_count=1,
            duration_ms=12.5,
        ),
        knowledge_base_count=1,
    )
    stats = GroundingCacheStats(
        hit_count=2,
        miss_count=3,
        shared_count=1,
        bypass_count=4,
        eviction_count=0,
        cache_size=5,
        inflight_count=0,
    )

    diagnostics = decision.to_engine_diagnostics(cache_stats=stats)

    assert diagnostics == {
        "schema_version": 1,
        "status": "ready",
        "reason_code": "retrieval_ready",
        "source": "knowledge",
        "mode": "grounded",
        "error_type": "none",
        "fallback_reason": "none",
        "latency_ms": 12.5,
        "result_count": 1,
        "kb_count": 1,
        "hit_count": 3,
        "miss_count": 3,
        "cache_size": 5,
        "cache_hit": cache_hit,
        "timeout": False,
        "degraded": False,
        "blocked": False,
    }
    assert "cache_disposition" not in diagnostics
    serialized = repr(diagnostics)
    for unsafe in ("kb-secret-id", "客户私有库", "私有文档", "原文", "token"):
        assert unsafe not in serialized


def test_grounding_decision_compatibility_projection_keeps_exact_disposition() -> None:
    decision = GroundingDecisionResult(
        decision_id="grounding:1:2",
        frozen_policy_hash="sha256:frozen",
        outcome=GroundingOutcome.DEGRADED,
        mode=GroundingMode.DEGRADED,
        allow_generation=True,
        grounding_context="",
        blocked_response="",
        output_guard_required=False,
        evidence=GroundingEvidence(
            citations=(),
            rewritten_queries=("改写问题",),
            answerability="insufficient",
            source_status="Bearer raw provider error",
            retrieval_mode="private transcript mode",
        ),
        cache_disposition=GroundingCacheDisposition.BYPASS,
        diagnostics=GroundingDiagnostics(
            schema_version=1,
            status="degraded",
            reason_code="timeout",
            source="retrieval",
            mode="degraded",
            degraded=True,
            blocked=False,
            cache_disposition=GroundingCacheDisposition.BYPASS,
            result_count=0,
            duration_ms=220.0,
        ),
    )

    compatibility = decision.to_compatibility_diagnostics()

    assert compatibility["decision_id"] == "grounding:1:2"
    assert compatibility["outcome"] == "degraded"
    assert compatibility["cache_disposition"] == "bypass"
    assert compatibility["rewritten_queries"] == ["改写问题"]
    assert compatibility["timeout"] is True
    frontend = decision.to_frontend_diagnostics()
    assert frontend["source_status"] == "timeout"
    assert frontend["retrieval_mode"] == "unknown"
    assert "Bearer" not in repr(frontend)
    assert "transcript" not in repr(frontend)


@pytest.mark.parametrize(
    (
        "outcome",
        "mode",
        "reason",
        "output_guard_required",
        "expected_status",
        "expected_reason",
        "expected_fallback",
    ),
    [
        (
            GroundingOutcome.READY,
            GroundingMode.GROUNDED,
            "partial_answerability",
            True,
            "ready",
            "retrieval_ready",
            "none",
        ),
        (
            GroundingOutcome.BLOCKED,
            GroundingMode.BLOCKED,
            "insufficient",
            False,
            "blocked",
            "kb_lock_blocked",
            "policy_blocked",
        ),
        (
            GroundingOutcome.DEGRADED,
            GroundingMode.DEGRADED,
            "timeout",
            False,
            "degraded",
            "retrieval_timeout",
            "timeout",
        ),
        (
            GroundingOutcome.DEGRADED,
            GroundingMode.DEGRADED,
            "raw provider stack",
            False,
            "degraded",
            "provider_unavailable",
            "unavailable",
        ),
        (
            GroundingOutcome.SKIPPED,
            GroundingMode.UNRESTRICTED,
            "arbitrary",
            False,
            "skipped",
            "not_applicable",
            "not_applicable",
        ),
    ],
)
def test_grounding_decision_maps_ready_blocked_degraded_error_partial_and_skipped(
    outcome: GroundingOutcome,
    mode: GroundingMode,
    reason: str,
    output_guard_required: bool,
    expected_status: str,
    expected_reason: str,
    expected_fallback: str,
) -> None:
    blocked = outcome is GroundingOutcome.BLOCKED
    decision = GroundingDecisionResult(
        decision_id=f"decision-{outcome.value}",
        frozen_policy_hash="sha256:frozen",
        outcome=outcome,
        mode=mode,
        allow_generation=not blocked,
        grounding_context="",
        blocked_response="safe blocked copy" if blocked else "",
        output_guard_required=output_guard_required,
        evidence=GroundingEvidence(
            citations=(),
            rewritten_queries=(),
            answerability="partial" if output_guard_required else "insufficient",
            source_status="miss",
            retrieval_mode="unknown",
        ),
        cache_disposition=GroundingCacheDisposition.BYPASS,
        diagnostics=GroundingDiagnostics(
            schema_version=1,
            status=outcome.value,
            reason_code=reason,
            source="retrieval",
            mode=mode.value,
            degraded=outcome is GroundingOutcome.DEGRADED,
            blocked=blocked,
            cache_disposition=GroundingCacheDisposition.BYPASS,
            result_count=0,
            duration_ms=1.0,
        ),
    )

    projected = decision.to_engine_diagnostics()

    assert projected["status"] == expected_status
    assert projected["reason_code"] == expected_reason
    assert projected["fallback_reason"] == expected_fallback


@pytest.mark.parametrize(
    "unknown_field",
    [
        "draw_count",
        "crawl_status",
        "tokenizer_version",
        "credential",
        "bearer",
        "cookie",
        "request_body",
        "note",
    ],
)
def test_should_reject_unknown_grounding_diagnostic_fields_deterministically(
    unknown_field: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=f"grounding_diagnostic_field_unknown:{unknown_field}",
    ):
        GroundingState(
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                unknown_field: "unsafe",
            }
        )


@pytest.mark.parametrize(
    ("field_name", "allowed_value"),
    [
        (field_name, allowed_value)
        for field_name, allowed_values in GROUNDING_DIAGNOSTIC_STRING_VOCABULARY.items()
        for allowed_value in sorted(allowed_values)
    ],
)
def test_should_accept_closed_grounding_diagnostic_vocabulary(
    field_name: str,
    allowed_value: str,
) -> None:
    diagnostics = {
        "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
        field_name: allowed_value,
    }

    assert GroundingState(diagnostics=diagnostics).diagnostics == diagnostics


@pytest.mark.parametrize(
    ("field_name", "injection_value"),
    [
        (field_name, injection_value)
        for field_name in GROUNDING_DIAGNOSTIC_STRING_VOCABULARY
        for injection_value in sorted(GROUNDING_DIAGNOSTIC_INJECTION_VALUES)
    ],
)
def test_should_reject_secret_or_transcript_injection_in_string_fields(
    field_name: str,
    injection_value: str,
) -> None:
    with pytest.raises(
        ValueError, match=f"grounding_diagnostic_vocabulary_invalid:{field_name}"
    ):
        GroundingState(
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                field_name: injection_value,
            }
        )


@pytest.mark.parametrize("field_name", GROUNDING_DIAGNOSTIC_STRING_VOCABULARY)
def test_should_reject_unknown_machine_identifier_in_string_fields(
    field_name: str,
) -> None:
    with pytest.raises(
        ValueError, match=f"grounding_diagnostic_vocabulary_invalid:{field_name}"
    ):
        GroundingState(
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                field_name: "future_contract_value",
            }
        )


def test_should_require_schema_version_for_non_empty_diagnostics() -> None:
    with pytest.raises(
        ValueError, match="grounding_diagnostics_schema_version_required"
    ):
        GroundingState(diagnostics={"status": "ready"})


@pytest.mark.parametrize("invalid_version", [True, False, 1.0, "1", 2, None])
def test_should_require_exact_grounding_diagnostics_schema_version(
    invalid_version: object,
) -> None:
    with pytest.raises(ValueError, match="grounding_diagnostics_schema_version"):
        GroundingState(
            diagnostics={"schema_version": invalid_version}  # type: ignore[dict-item]
        )


@pytest.mark.parametrize(
    "invalid_identifier",
    ["", "contains spaces", "Bearer abc.def", "中文", "x" * 129, b"bytes"],
)
def test_should_reject_free_text_or_invalid_diagnostic_identifiers(
    invalid_identifier: object,
) -> None:
    with pytest.raises(ValueError, match="grounding_diagnostic_identifier"):
        GroundingState(
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                "status": invalid_identifier,
            }  # type: ignore[dict-item]
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("latency_ms", True),
        ("result_count", -1),
        ("kb_count", float("nan")),
        ("hit_count", float("inf")),
        ("miss_count", "1"),
        ("cache_size", -0.1),
    ],
)
def test_should_reject_invalid_count_or_latency_metadata(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError, match="grounding_diagnostic_non_negative_number"):
        GroundingState(
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                field_name: invalid_value,
            }  # type: ignore[dict-item]
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("confidence", True),
        ("confidence", -0.1),
        ("confidence", 1.1),
        ("answerability_score", float("nan")),
        ("answerability_score", float("inf")),
        ("answerability_score", "0.5"),
    ],
)
def test_should_reject_invalid_bounded_score_metadata(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError, match="grounding_diagnostic_unit_interval"):
        GroundingState(
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                field_name: invalid_value,
            }  # type: ignore[dict-item]
        )


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("cache_hit", 1),
        ("timeout", 0),
        ("degraded", "true"),
        ("blocked", None),
    ],
)
def test_should_require_strict_boolean_diagnostic_metadata(
    field_name: str,
    invalid_value: object,
) -> None:
    with pytest.raises(ValueError, match="grounding_diagnostic_boolean"):
        GroundingState(
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                field_name: invalid_value,
            }  # type: ignore[dict-item]
        )


def test_should_reject_non_string_grounding_diagnostic_key() -> None:
    with pytest.raises(ValueError, match="grounding_diagnostic_field_must_be_string"):
        GroundingState(
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                1: "unsafe",
            }  # type: ignore[dict-item]
        )


def test_should_revalidate_diagnostics_during_serialization() -> None:
    grounding = GroundingState(
        diagnostics={"schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION}
    )
    grounding.diagnostics["note"] = "free_text"  # type: ignore[assignment]

    with pytest.raises(ValueError, match="grounding_diagnostic_field_unknown:note"):
        grounding.to_dict()


def test_should_reject_unsafe_diagnostics_before_mutating_grounding_state() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)
    engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")

    with pytest.raises(
        ValueError, match="grounding_diagnostic_field_unknown:authorization"
    ):
        engine.resolve_grounding(
            outcome="ready",
            mode="grounded",
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                "authorization": "unsafe",
            },
        )

    assert engine.state.grounding.phase is GroundingPhase.PREPARING
    assert engine.state.grounding.mode is None
    assert [transition.event_name for transition in hooks.transitions] == [
        "grounding.preparing"
    ]


def test_should_reject_invalid_vocabulary_before_mutating_grounding_state() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)
    engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")

    with pytest.raises(
        ValueError, match="grounding_diagnostic_vocabulary_invalid:status"
    ):
        engine.resolve_grounding(
            outcome="ready",
            mode="grounded",
            diagnostics={
                "schema_version": GROUNDING_DIAGNOSTICS_SCHEMA_VERSION,
                "status": "sk-proj-abc123",
            },
        )

    assert engine.state.grounding.phase is GroundingPhase.PREPARING
    assert engine.state.grounding.mode is None
    assert [transition.event_name for transition in hooks.transitions] == [
        "grounding.preparing"
    ]


def test_should_dedupe_identical_evidence_and_reject_conflicts() -> None:
    evidence = EvidenceState()

    assert evidence.record(
        evidence_key="score:turn-1",
        evidence_type="score",
        turn_number=1,
        payload_digest="sha256:stable",
    )
    assert not evidence.record(
        evidence_key="score:turn-1",
        evidence_type="score",
        turn_number=1,
        payload_digest="sha256:stable",
    )

    with pytest.raises(RealtimeStateTransitionError, match="evidence_key_conflict"):
        evidence.record(
            evidence_key="score:turn-1",
            evidence_type="score",
            turn_number=1,
            payload_digest="sha256:changed",
        )


def test_should_acknowledge_only_pending_evidence() -> None:
    evidence = EvidenceState()
    evidence.record(
        evidence_key="transcript:1:user",
        evidence_type="transcript",
        turn_number=1,
        payload_digest="sha256:stable",
    )

    with pytest.raises(RealtimeStateTransitionError, match="evidence_not_pending"):
        evidence.acknowledge("transcript:1:user")
    with pytest.raises(RealtimeStateTransitionError, match="unknown_evidence_key"):
        evidence.mark_pending("missing")

    evidence.mark_pending("transcript:1:user")
    assert evidence.acknowledge("transcript:1:user")
    assert not evidence.acknowledge("transcript:1:user")
    assert evidence.pending_flush_keys == set()
    assert evidence.acknowledged_keys == {"transcript:1:user"}


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: ConnectionState(epoch=-1), "connection_epoch_must_be_non_negative"),
        (
            lambda: EvidenceState.from_dict(
                {
                    "records": {
                        "bad": {
                            "evidence_key": "bad",
                            "evidence_type": "transcript",
                            "turn_number": -1,
                            "payload_digest": "sha256:bad",
                        }
                    }
                }
            ),
            "evidence_turn_number_must_be_non_negative",
        ),
    ],
)
def test_should_reject_negative_state_counters(
    factory: Callable[[], object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


class RecordingHooks:
    scenario_type = "presentation"

    def __init__(self) -> None:
        self.transitions: list[RealtimeTransition] = []

    def on_transition(self, transition: RealtimeTransition) -> None:
        self.transitions.append(transition)


def test_should_run_legal_session_path_and_emit_post_transition_snapshots() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)

    engine.begin_connection("session-1")
    engine.mark_connected()
    engine.begin_turn(request_id=1, stream_id="stream-1")
    engine.mark_response_started(response_id="response-1")
    engine.mark_streaming()
    engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")
    engine.resolve_grounding(outcome="ready", mode="grounded")
    assert engine.record_evidence(
        evidence_key="transcript:1:user",
        evidence_type="transcript",
        turn_number=1,
        payload=b"learner transcript",
    )
    engine.complete_turn(request_id=1)
    engine.begin_close(reason="client_disconnect")
    engine.mark_disconnected(reason="client_disconnect")

    assert [transition.event_name for transition in hooks.transitions] == [
        "connection.connecting",
        "connection.connected",
        "turn.receiving",
        "turn.generating",
        "turn.streaming",
        "grounding.preparing",
        "grounding.ready",
        "evidence.recorded",
        "turn.completed",
        "connection.closing",
        "connection.disconnected",
    ]
    assert hooks.transitions[0].snapshot["connection"]["phase"] == "connecting"  # type: ignore[index]
    assert hooks.transitions[-1].snapshot == engine.snapshot()
    record = engine.state.evidence.records["transcript:1:user"]
    assert record.payload_digest.startswith("sha256:")
    assert "learner transcript" not in json.dumps(engine.snapshot())


def test_should_reject_active_turn_reentry_and_stale_request_ids() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    engine.begin_turn(request_id=2, stream_id="stream-2")

    with pytest.raises(RealtimeStateTransitionError, match="active_turn_reentry"):
        engine.begin_turn(request_id=3, stream_id="stream-3")

    engine.mark_response_started(response_id="response-2")
    engine.mark_streaming()
    with pytest.raises(RealtimeStateTransitionError, match="stale_turn_completion"):
        engine.complete_turn(request_id=1)
    engine.complete_turn(request_id=2)

    with pytest.raises(RealtimeStateTransitionError, match="stale_turn_request"):
        engine.begin_turn(request_id=2, stream_id="stream-replayed")


def test_should_reject_illegal_turn_and_grounding_transitions() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )

    with pytest.raises(
        RealtimeStateTransitionError, match="response_start_not_allowed"
    ):
        engine.mark_response_started(response_id="response-1")
    with pytest.raises(RealtimeStateTransitionError, match="grounding_not_preparing"):
        engine.resolve_grounding(outcome="ready", mode="grounded")

    engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")
    engine.resolve_grounding(outcome="blocked", mode="fail_closed")
    with pytest.raises(RealtimeStateTransitionError, match="stale_grounding_decision"):
        engine.begin_grounding(decision_id="g-1", policy_hash="sha256:policy")


def test_should_increment_connection_epoch_on_reconnect() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )

    engine.begin_connection("session-1")
    engine.mark_connected()
    engine.begin_close(reason="network_reset")
    engine.mark_disconnected(reason="network_reset")
    engine.begin_connection("session-1")

    assert engine.state.connection.epoch == 2
    assert engine.state.connection.reconnecting is True


def test_should_make_evidence_replay_idempotent() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)
    kwargs = {
        "evidence_key": "audio:turn-1",
        "evidence_type": "audio",
        "turn_number": 1,
        "payload": b"audio bytes",
    }

    assert engine.record_evidence(**kwargs)
    assert not engine.record_evidence(**kwargs)
    assert [transition.event_name for transition in hooks.transitions] == [
        "evidence.recorded"
    ]

    with pytest.raises(RealtimeStateTransitionError, match="evidence_key_conflict"):
        engine.record_evidence(**{**kwargs, "payload": b"different audio"})


@pytest.mark.parametrize(
    "invalid_digest",
    [
        "",
        "sha256:stable",
        f"sha256:{'A' * 64}",
        f"sha512:{'a' * 64}",
        f"sha256:{'a' * 63}",
        f"sha256:{'a' * 65}",
    ],
)
def test_should_reject_unvalidated_external_evidence_digest(
    invalid_digest: str,
) -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)

    with pytest.raises(ValueError, match="evidence_payload_digest_must_be_sha256"):
        engine.record_evidence_digest(
            evidence_key="audio:1:chunks:1:bytes:4",
            evidence_type="audio",
            turn_number=1,
            payload_digest=invalid_digest,
        )

    assert engine.state.evidence.records == {}
    assert hooks.transitions == []


def test_should_record_valid_external_evidence_digest_with_existing_boundaries() -> (
    None
):
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)
    digest = f"sha256:{'a' * 64}"
    kwargs = {
        "evidence_key": "audio:1:chunks:1:bytes:4",
        "evidence_type": "audio",
        "turn_number": 1,
        "payload_digest": digest,
    }

    assert engine.record_evidence_digest(**kwargs)
    assert not engine.record_evidence_digest(**kwargs)
    assert (
        engine.state.evidence.records[kwargs["evidence_key"]].payload_digest == digest
    )
    assert [transition.event_name for transition in hooks.transitions] == [
        "evidence.recorded"
    ]

    with pytest.raises(RealtimeStateTransitionError, match="evidence_key_conflict"):
        engine.record_evidence_digest(
            **{**kwargs, "payload_digest": f"sha256:{'b' * 64}"}
        )


def test_should_round_trip_engine_snapshot_and_reject_scenario_mismatch() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    engine.begin_connection("session-1")
    engine.mark_connected()
    payload = engine.snapshot()

    restored = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    restored.restore(payload)
    assert restored.snapshot() == payload

    mismatch = RealtimeSessionEngine(
        scenario_type="sales",
        hooks=NoopScenarioTurnHooks(scenario_type="sales"),
    )
    with pytest.raises(ValueError, match="engine_snapshot_scenario_mismatch"):
        mismatch.restore(payload)


def test_should_reject_stale_restore_after_state_progress() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    engine.begin_connection("session-1")
    engine.mark_connected()
    engine.begin_close(reason="network_reset")
    engine.mark_disconnected(reason="network_reset")
    engine.begin_connection("session-1")
    engine.begin_turn(request_id=2, stream_id="stream-2")
    engine.mark_response_started(response_id="response-2")
    engine.complete_turn(request_id=2)
    engine.record_evidence(
        evidence_key="transcript:2:user",
        evidence_type="transcript",
        turn_number=2,
        payload=b"learner transcript",
    )
    engine.mark_evidence_pending("transcript:2:user")
    engine.acknowledge_evidence("transcript:2:user")
    engine.record_evidence(
        evidence_key="audio:2:user",
        evidence_type="audio",
        turn_number=2,
        payload=b"audio bytes",
    )
    engine.mark_evidence_pending("audio:2:user")
    current = engine.snapshot()
    stale = RealtimeSessionState(scenario_type="presentation").to_dict()

    with pytest.raises(
        RealtimeStateTransitionError, match="engine_restore_requires_pristine_state"
    ):
        engine.restore(stale)

    assert engine.snapshot() == current
    assert engine.state.connection.epoch == 2
    assert engine.state.turn.request_id == 2
    assert set(engine.state.evidence.records) == {
        "transcript:2:user",
        "audio:2:user",
    }
    assert engine.state.evidence.pending_flush_keys == {"audio:2:user"}
    assert engine.state.evidence.acknowledged_keys == {"transcript:2:user"}


def test_should_not_allow_callers_to_mutate_engine_state_outside_boundary() -> None:
    engine = RealtimeSessionEngine(
        scenario_type="presentation",
        hooks=NoopScenarioTurnHooks(scenario_type="presentation"),
    )
    engine.begin_connection("session-1")

    visible_state = engine.state
    visible_state.connection.epoch = 99

    assert engine.state.connection.epoch == 1


def test_should_fail_visibly_when_hook_fails() -> None:
    class FailingHooks:
        scenario_type = "presentation"

        def on_transition(self, transition: RealtimeTransition) -> None:
            raise RuntimeError(transition.event_name)

    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=FailingHooks())

    with pytest.raises(RuntimeError, match="connection.connecting"):
        engine.begin_connection("session-1")
    assert engine.state.connection.phase is ConnectionPhase.CONNECTING


def test_should_reject_mismatched_scenario_hook() -> None:
    with pytest.raises(ValueError, match="scenario_hook_mismatch"):
        RealtimeSessionEngine(
            scenario_type="presentation",
            hooks=NoopScenarioTurnHooks(scenario_type="sales"),
        )


def test_should_expose_degraded_connection_transition_matrix() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)

    with pytest.raises(
        RealtimeStateTransitionError, match="connection_degrade_not_allowed"
    ):
        engine.mark_degraded(reason="backpressure")

    engine.begin_connection("session-1")
    engine.mark_degraded(reason="backpressure")

    assert hooks.transitions[-1].event_name == "connection.degraded"
    assert hooks.transitions[-1].snapshot["connection"]["phase"] == "degraded"  # type: ignore[index]
    assert hooks.transitions[-1].snapshot["connection"]["reason"] == "backpressure"  # type: ignore[index]
    with pytest.raises(
        RealtimeStateTransitionError, match="connection_degrade_not_allowed"
    ):
        engine.mark_degraded(reason="duplicate")


def test_should_expose_interrupted_turn_transition_matrix() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)
    engine.begin_turn(request_id=1, stream_id="stream-1")

    engine.interrupt_turn(request_id=1, reason="learner_barge_in")

    assert hooks.transitions[-1].event_name == "turn.interrupted"
    assert hooks.transitions[-1].snapshot["turn"]["phase"] == "interrupted"  # type: ignore[index]
    with pytest.raises(
        RealtimeStateTransitionError, match="turn_interruption_not_allowed"
    ):
        engine.interrupt_turn(request_id=1, reason="duplicate")
    with pytest.raises(RealtimeStateTransitionError, match="stale_turn_interruption"):
        engine.interrupt_turn(request_id=0, reason="stale")


def test_should_expose_timed_out_turn_transition_matrix() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)
    engine.begin_turn(request_id=1, stream_id="stream-1")

    engine.timeout_turn(request_id=1, reason="provider_timeout")

    assert hooks.transitions[-1].event_name == "turn.timed_out"
    assert hooks.transitions[-1].snapshot["turn"]["phase"] == "timed_out"  # type: ignore[index]
    with pytest.raises(RealtimeStateTransitionError, match="turn_timeout_not_allowed"):
        engine.timeout_turn(request_id=1, reason="duplicate")
    with pytest.raises(RealtimeStateTransitionError, match="stale_turn_timeout"):
        engine.timeout_turn(request_id=0, reason="stale")


def test_should_expose_evidence_pending_and_ack_transition_matrix() -> None:
    hooks = RecordingHooks()
    engine = RealtimeSessionEngine(scenario_type="presentation", hooks=hooks)
    engine.record_evidence(
        evidence_key="transcript:1:user",
        evidence_type="transcript",
        turn_number=1,
        payload=b"learner transcript",
    )

    assert engine.mark_evidence_pending("transcript:1:user")
    assert engine.acknowledge_evidence("transcript:1:user")

    assert [transition.event_name for transition in hooks.transitions] == [
        "evidence.recorded",
        "evidence.flush_pending",
        "evidence.flush_acknowledged",
    ]
    pending_snapshot = hooks.transitions[-2].snapshot["evidence"]  # type: ignore[assignment]
    assert pending_snapshot["pending_flush_keys"] == ["transcript:1:user"]  # type: ignore[index]
    assert pending_snapshot["acknowledged_keys"] == []  # type: ignore[index]
    acknowledged_snapshot = hooks.transitions[-1].snapshot["evidence"]  # type: ignore[assignment]
    assert acknowledged_snapshot["pending_flush_keys"] == []  # type: ignore[index]
    assert acknowledged_snapshot["acknowledged_keys"] == ["transcript:1:user"]  # type: ignore[index]
    assert not engine.mark_evidence_pending("transcript:1:user")
    assert not engine.acknowledge_evidence("transcript:1:user")
    assert len(hooks.transitions) == 3

    with pytest.raises(RealtimeStateTransitionError, match="unknown_evidence_key"):
        engine.mark_evidence_pending("missing")
    engine.record_evidence(
        evidence_key="audio:1:user",
        evidence_type="audio",
        turn_number=1,
        payload=b"audio bytes",
    )
    with pytest.raises(RealtimeStateTransitionError, match="evidence_not_pending"):
        engine.acknowledge_evidence("audio:1:user")
