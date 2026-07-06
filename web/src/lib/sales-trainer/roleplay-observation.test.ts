import { describe, expect, it } from "vitest";

import type {
    SalesTrainerRealtimeRecordVoicePolicySnapshot,
    SalesTrainerRoleplayObservationSessionResponse,
    SalesTrainerTrainingRecord,
} from "@/lib/api/types";

import {
    buildRoleplayObservationAnalyticsViewModel,
    buildRoleplayObservationPanelState,
} from "./roleplay-observation";

const realtimeExternalBinding = {
    owner: "sales_trainer",
    binding_key: "newcomer_realtime_roleplay_v1",
    module_key: "realtime_roleplay",
} as const;

function realtimeRecord(
    voicePolicySnapshot: SalesTrainerRealtimeRecordVoicePolicySnapshot = {
        external_binding: realtimeExternalBinding,
        voice_mode: "stepfun_realtime",
        runtime_metrics: {
            it_leader_roleplay_v1: {
                roleplay_contract_hash: "sha256:runtime-contract",
                knowledge_timeout_count: 0,
                manual_review_required: false,
                manual_review_reasons: ["runtime-review"],
                quality_flags: ["knowledge_gap_degradation"],
            },
        },
    },
): SalesTrainerTrainingRecord {
    return {
        record_id: "record-rt-1",
        record_type: "realtime_roleplay_session",
        path_key: "newcomer_training_path_v1",
        path_revision_id: "path-revision-1",
        path_revision_no: 1,
        module_key: "realtime_roleplay",
        legacy_snapshot_only: false,
        unit_id: "unit-realtime",
        unit_name: "实时角色扮演",
        unit_type: "realtime_roleplay",
        user_id: "learner-1",
        user_name: "张三",
        user_email: "zhangsan@example.com",
        user_department: "销售一部",
        status: "scored",
        score: 82,
        max_score: 100,
        passed: null,
        submitted_at: "2026-06-27T09:00:00Z",
        material_snapshot: null,
        score_scheme_snapshot: null,
        task_brief_snapshot: null,
        audio_submission: null,
        quiz_attempt: null,
        ai_coach_session: null,
        business_etiquette_quiz_attempt: null,
        realtime_roleplay_session: {
            session_id: "rt-1",
            module_key: "realtime_roleplay",
            status: "scored",
            score: 82,
            max_score: 100,
            passed: null,
            submitted_at: "2026-06-27T09:00:00Z",
            completed_at: "2026-06-27T09:12:00Z",
            external_binding: realtimeExternalBinding,
            snapshot: {
                external_binding: realtimeExternalBinding,
                voice_policy_snapshot: voicePolicySnapshot,
                effectiveness_snapshot: {
                    summary: "完成实时对练",
                },
                runtime_state: {
                    state: "completed",
                    session_status: "completed",
                    turn_count: 4,
                },
                scores: {
                    logic_score: 88,
                    accuracy_score: 82,
                    completeness_score: 76,
                },
            },
        },
        operation_logs: [],
    };
}

function endpointObservation(): SalesTrainerRoleplayObservationSessionResponse {
    return {
        session_id: "rt-1",
        source_record_id: "record-rt-1",
        total: 2,
        latest_turn_index: 3,
        source_counts: {
            heuristic: 1,
            llm_evaluator: 1,
        },
        status_counts: {
            pending: 0,
            completed: 1,
            failed: 1,
            ignored: 0,
        },
        items: [
            {
                observation_id: "obs-heuristic",
                session_id: "rt-1",
                source_record_id: "record-rt-1",
                source: "heuristic",
                turn_index: 2,
                evaluator_status: "completed",
                dimensions: [
                    {
                        key: "capture_context",
                        instruction_contract_hash: "sha256:endpoint-contract",
                        template_stage_key: "discovery",
                    },
                    {
                        key: "evaluation_runtime",
                        llm: {
                            status: "disabled",
                        },
                    },
                ],
                signals: [
                    {
                        key: "prompt_leak_risk",
                        source: "heuristic",
                        severity: "high",
                        evidence: [
                            {
                                kind: "keyword",
                                value: "Authorization: Bearer live-token-123",
                            },
                        ],
                    },
                ],
                error: null,
                trace_id: "trace-heuristic",
                created_at: "2026-06-27T09:06:00Z",
                updated_at: "2026-06-27T09:06:00Z",
            },
            {
                observation_id: "obs-llm-timeout",
                session_id: "rt-1",
                source_record_id: "record-rt-1",
                source: "llm_evaluator",
                turn_index: 3,
                evaluator_status: "failed",
                dimensions: [
                    {
                        key: "evaluation_runtime",
                        llm: {
                            status: "timeout",
                        },
                    },
                ],
                signals: [],
                error: {
                    code: "[ROLEPLAY_OBSERVATION_LLM_TIMEOUT]",
                    message: "timeout while evaluating roleplay observation",
                },
                trace_id: "trace-llm-timeout",
                created_at: "2026-06-27T09:08:00Z",
                updated_at: "2026-06-27T09:08:00Z",
            },
        ],
    };
}

function emptyObservation(): SalesTrainerRoleplayObservationSessionResponse {
    return {
        session_id: "rt-1",
        source_record_id: "record-rt-1",
        total: 0,
        latest_turn_index: null,
        source_counts: {
            heuristic: 0,
            llm_evaluator: 0,
        },
        status_counts: {
            pending: 0,
            completed: 0,
            failed: 0,
            ignored: 0,
        },
        items: [],
    };
}

describe("roleplay observation view models", () => {
    it("parses endpoint observations as record-only admin diagnostics", () => {
        const state = buildRoleplayObservationPanelState(
            realtimeRecord(),
            endpointObservation(),
        );

        expect(state.sourceKind).toBe("endpoint");
        expect(state.emptyState).toBeNull();
        expect(state.sourceDescription).toContain("不会打断 learner 实时对练");

        const observation = state.observation;
        expect(observation).not.toBeNull();
        expect(observation?.summaryStatusLabel).toBe("观测已记录");
        expect(observation?.contractHash).toBe("sha256:endpoint-contract");
        expect(observation?.runtimeDisposition).toBe("record_only");
        expect(observation?.mainChainEffect).toBe("none");
        expect(observation?.dimensionScores).toEqual([
            { key: "logic_score", label: "逻辑结构", score: 88, maxScore: 100 },
            { key: "accuracy_score", label: "事实准确", score: 82, maxScore: 100 },
            { key: "completeness_score", label: "覆盖完整", score: 76, maxScore: 100 },
        ]);
        expect(observation?.detectionSources).toEqual(["heuristic", "llm_evaluator"]);
        expect(observation?.detectionSourceLabels).toEqual(["Heuristic 规则", "LLM 辅助"]);
        expect(observation?.heuristicOnly).toBe(false);
        expect(observation?.llmTimedOut).toBe(true);
        expect(observation?.manualReviewRequired).toBe(true);
        expect(observation?.manualReviewReasons).toEqual([
            "runtime-review",
            "prompt_leak_risk",
            "[ROLEPLAY_OBSERVATION_LLM_TIMEOUT]",
        ]);
        expect(observation?.riskTagLabels).toContain("知识 / LLM 降级");
        expect(observation?.violationCount).toBe(1);
        expect(observation?.blockingViolationCount).toBe(1);
        expect(observation?.lastObservedAt).toBe("2026-06-27T09:08:00Z");

        expect(observation?.findings).toHaveLength(1);
        expect(observation?.findings[0]).toMatchObject({
            turnNumber: 2,
            action: "mark_for_report",
            actionLabel: "记入旁路观察",
            severity: "high",
            severityLabel: "高风险",
            violationCode: "prompt_leak_risk",
            violationLabel: "提示词泄露风险",
            matchedPattern: "Authorization=<redacted> <redacted>",
        });
        expect(observation?.findings[0]?.matchedPattern).not.toContain("live-token");
    });

    it("falls back to frozen legacy compliance snapshots without implying runtime failure", () => {
        const record = realtimeRecord({
            external_binding: realtimeExternalBinding,
            voice_mode: "stepfun_realtime",
            roleplay_contract_hash: "sha256:legacy-contract",
            runtime_metrics: {
                it_leader_roleplay_v1: {
                    roleplay_contract_hash: "sha256:runtime-contract",
                    knowledge_timeout_count: 1,
                    manual_review_required: true,
                    manual_review_reasons: ["manual-review"],
                    quality_flags: ["low_confidence"],
                },
                roleplay_compliance: {
                    violation_count: 2,
                    blocking_violation_count: 1,
                    regenerate_count: 1,
                    cancel_stream_count: 1,
                    hidden_leak_prevented_count: 1,
                    last_action_at: "2026-06-27T09:07:30Z",
                    llm_status: "timeout",
                    manual_review_reasons: ["summary-review"],
                    blocking_issues: ["blocking_roleplay_violation"],
                    timeline: [
                        {
                            event_type: "compliance_decision",
                            turn_number: 4,
                            action: "regenerate_once",
                            violation_code: "ROLEPLAY_HIDDEN_INFORMATION_LEAK",
                            severity: "blocking",
                            matched_pattern: "token=secret-value",
                            created_at: "2026-06-27T09:07:30Z",
                            trace_id: "trace-legacy",
                            decision: {
                                audit_payload: {
                                    signal_source: "heuristic",
                                },
                            },
                        },
                    ],
                },
            },
        });

        const state = buildRoleplayObservationPanelState(record, emptyObservation());

        expect(state.sourceKind).toBe("legacy_fallback");
        expect(state.sourceDescription).toContain("仅用于历史复盘兼容");

        const observation = state.observation;
        expect(observation?.summaryStatusLabel).toBe("配置正常");
        expect(observation?.contractHash).toBe("sha256:legacy-contract");
        expect(observation?.runtimeDisposition).toBe("record_only");
        expect(observation?.mainChainEffect).toBe("none");
        expect(observation?.detectionSources).toEqual(["heuristic"]);
        expect(observation?.detectionSourceLabels).toEqual(["Heuristic 规则"]);
        expect(observation?.llmTimedOut).toBe(true);
        expect(observation?.manualReviewReasons).toEqual([
            "manual-review",
            "summary-review",
        ]);
        expect(observation?.manualReviewRequired).toBe(true);
        expect(observation?.repairCount).toBe(0);
        expect(observation?.hiddenLeakPreventedCount).toBe(1);
        expect(observation?.violationCount).toBe(2);
        expect(observation?.blockingViolationCount).toBe(1);
        expect(observation?.riskTagLabels).toEqual(expect.arrayContaining([
            "需人工复核：低置信度",
            "需人工复核：高风险角色违规",
            "高风险角色违规 1 次",
            "隐藏信息泄露",
        ]));
        expect(observation?.findings[0]).toMatchObject({
            actionLabel: "记入旁路观察",
            severityLabel: "高风险复盘",
            matchedPattern: "token=<redacted>",
        });
        expect(observation?.riskTagLabels.join(" ")).not.toContain("阻断级");
        expect(observation?.findings[0]?.actionLabel).not.toBe("重生成一次");
    });

    it("distinguishes LLM-disabled empty sidecar state from missing persistence", () => {
        const record = realtimeRecord({
            external_binding: realtimeExternalBinding,
            voice_mode: "stepfun_realtime",
            runtime_metrics: {
                roleplay_compliance: {
                    llm_status: "disabled",
                    heuristic_only: true,
                    violation_count: 0,
                    timeline: [],
                },
            },
        });

        const state = buildRoleplayObservationPanelState(record, emptyObservation());

        expect(state.sourceKind).toBe("none");
        expect(state.observation).toBeNull();
        expect(state.emptyState).toMatchObject({
            kind: "llm_disabled",
            title: "LLM 默认关闭，当前没有新增 observation 行",
        });
    });

    it("normalizes analytics aggregate aliases into count badges", () => {
        const viewModel = buildRoleplayObservationAnalyticsViewModel({
            observation_aggregate: {
                coverage_status: "partial",
                eligible_session_count: "5",
                endpoint_session_count: 3,
                sidecar_missing_session_count: "2",
                manual_review_required_session_count: 1,
                heuristic_only_session_count: 1,
                timeout_session_count: "1",
                total_observation_count: 4,
                total_signal_count: "6",
                detection_source_counts: {
                    heuristic: 3,
                    llm_evaluator: 1,
                    ignored: 0,
                },
                evaluator_status_counts: {
                    completed: 3,
                    failed: 1,
                },
                latest_observed_at: "2026-06-27T09:08:00Z",
                fallback_applied: true,
                fallback_reason: "sidecar_missing",
            },
        });

        expect(viewModel).toEqual({
            status: "partial",
            totalSessionCount: 5,
            observedSessionCount: 3,
            legacyFallbackSessionCount: null,
            notPersistedSessionCount: 2,
            manualReviewSessionCount: 1,
            llmDisabledSessionCount: 1,
            llmTimeoutSessionCount: 1,
            observationCount: 4,
            signalCount: 6,
            sourceCounts: [
                { key: "heuristic", label: "Heuristic 规则", count: 3 },
                { key: "llm_evaluator", label: "LLM 辅助", count: 1 },
            ],
            statusCounts: [
                { key: "completed", label: "观测完成", count: 3 },
                { key: "failed", label: "观测失败", count: 1 },
            ],
            generatedAt: "2026-06-27T09:08:00Z",
            fallbackApplied: true,
            fallbackReason: "sidecar_missing",
        });
        expect(buildRoleplayObservationAnalyticsViewModel({})).toBeNull();
    });
});
