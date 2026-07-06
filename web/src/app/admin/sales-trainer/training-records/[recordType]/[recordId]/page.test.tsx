import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerTrainingRecordDetailPage from "./page";
import type { SalesTrainerTrainingRecordType } from "@/lib/api/types";

const {
    getCapabilitiesMock,
    getTrainingRecordDetailMock,
    getRealtimeRoleplayObservationsMock,
    navigationState,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
    getTrainingRecordDetailMock: vi.fn(),
    getRealtimeRoleplayObservationsMock: vi.fn(),
    navigationState: {
        params: {
            recordType: "audio_submission",
            recordId: "audio-1",
        },
        pathname: "/admin/sales-trainer/training-records/audio_submission/audio-1",
    },
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    useParams: () => navigationState.params,
    usePathname: () => navigationState.pathname,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                    getTrainingRecordDetail: getTrainingRecordDetailMock,
                    getRealtimeRoleplayObservations: getRealtimeRoleplayObservationsMock,
                },
            },
        },
    };
});

function recordPayload(recordType: SalesTrainerTrainingRecordType, recordId: string) {
    const rawPayloads = {
        audio_submission: {
            audio_submission: {
                submission_id: recordId,
                original_filename: "ppt.wav",
                transcript: "介绍产品价值。",
                score_scheme_snapshot: {
                    prompt_id: "prompt-frozen",
                    learner_rubric: {},
                    pass_threshold: 70,
                    prompt_snapshot: {
                        prompt_id: "prompt-frozen",
                        name: "冻结评分 Prompt",
                        version: 2,
                        scoring_template: "历史回放快照基线：PPT 讲解评分 v2\n请按提交时标准评分。",
                        output_schema: {},
                        learner_rubric: {},
                    },
                },
                material_snapshot: {
                    version: 1,
                    items: [{ material_id: "material-1" }],
                    confirmed_material_version_id: "material-version-frozen",
                },
                task_brief_snapshot: {
                    title: "冻结 PPT 讲解任务",
                    instructions: [],
                    success_criteria: [],
                    common_mistakes: [],
                },
            },
            quiz_attempt: null,
            ai_coach_session: null,
            business_etiquette_quiz_attempt: null,
            realtime_roleplay_session: null,
            unit_type: "audio_scoring",
        },
        quiz_attempt: {
            audio_submission: null,
            quiz_attempt: {
                attempt_id: recordId,
                paper_id: "paper-1",
                answer_count: 3,
            },
            ai_coach_session: null,
            business_etiquette_quiz_attempt: null,
            realtime_roleplay_session: null,
            unit_type: "quiz",
        },
        business_etiquette_quiz_attempt: {
            audio_submission: null,
            quiz_attempt: null,
            ai_coach_session: null,
            business_etiquette_quiz_attempt: {
                attempt_id: recordId,
                training_pack_key: "business_etiquette_v1",
                learning_unit_key: "trust_opening",
                learning_unit_title: "建立信任",
                user_id: "user-1",
                path_revision_id: "path-revision-business",
                path_revision_no: 6,
                training_pack_revision_id: "pack-revision-business",
                training_pack_revision_no: 3,
                capability_snapshot: {
                    capabilities: [],
                    chapter_bindings: [],
                },
                question_snapshots: [
                    {
                        question_id: "beq-1",
                        title: "开场题",
                        stem: "如何开场？",
                        question_type: "single_choice",
                        options: [],
                        points: 10,
                        order_index: 1,
                    },
                ],
                weak_capability_keys: ["business_etiquette_trust"],
                recommended_chapter_orders: [1],
                capability_scores: [
                    {
                        capability_key: "business_etiquette_trust",
                        display_name: "建立信任",
                        score: 4,
                        max_score: 10,
                        normalized_score: 40,
                        threshold: 80,
                        mastered: false,
                    },
                ],
                answers: [
                    {
                        question_id: "beq-1",
                        question_type: "single_choice",
                        score: 4,
                        max_score: 10,
                        is_correct: false,
                        capability_keys: ["business_etiquette_trust"],
                        analysis: "需要先确认客户上下文。",
                    },
                ],
                total_score: 4,
                max_score: 10,
                passed: false,
                status: "scored",
                submitted_at: "2026-06-27T10:00:00Z",
            },
            realtime_roleplay_session: null,
            unit_type: "business_etiquette_quiz",
        },
        business_etiquette_quiz_attempt_legacy: {
            audio_submission: null,
            quiz_attempt: null,
            ai_coach_session: null,
            business_etiquette_quiz_attempt: {
                attempt_id: recordId,
                training_pack_key: "business_etiquette_v1",
                learning_unit_key: "trust_opening",
                learning_unit_title: "建立信任",
                user_id: "user-1",
                path_revision_id: null,
                path_revision_no: null,
                training_pack_revision_id: null,
                training_pack_revision_no: null,
                capability_snapshot: {
                    capabilities: [],
                    chapter_bindings: [],
                },
                question_snapshots: [],
                weak_capability_keys: [],
                recommended_chapter_orders: [],
                capability_scores: [],
                answers: [],
                total_score: null,
                max_score: null,
                passed: null,
                status: "submitted",
                submitted_at: "2026-06-27T10:00:00Z",
            },
            realtime_roleplay_session: null,
            unit_type: "business_etiquette_quiz",
        },
        ai_coach_session: {
            audio_submission: null,
            quiz_attempt: null,
            ai_coach_session: {
                session_id: recordId,
                module_key: "business_skills",
                path_key: "newcomer_training_path_v1",
                path_revision_id: "path-revision-1",
                path_revision_no: 1,
                article_snapshot: {
                    title: "商务礼仪",
                    chapters: [{ title: "建立信任" }],
                },
                config_snapshot: {
                    mastery_threshold: 80,
                    min_turns: 3,
                },
                coach_state: {
                    last_action: "remediate",
                },
                prompt_template_id: "prompt-template-1",
                prompt_revision_id: "prompt-revision-1",
                prompt_contract_hash: "hash-ai-coach-contract",
                mastery_state: "not_mastered",
                total_score: 62,
                max_score: 100,
                status: "completed",
                trace_id: "trace-ai-coach-detail",
            },
            business_etiquette_quiz_attempt: null,
            realtime_roleplay_session: null,
            unit_type: "ai_coach",
        },
        realtime_roleplay_session: {
            audio_submission: null,
            quiz_attempt: null,
            ai_coach_session: null,
            business_etiquette_quiz_attempt: null,
            realtime_roleplay_session: {
                session_id: recordId,
                module_key: "realtime_roleplay",
                status: "scored",
                score: 82,
                max_score: 100,
                passed: null,
                submitted_at: "2026-06-27T09:00:00Z",
                completed_at: "2026-06-27T09:12:00Z",
                external_binding: {
                    owner: "sales_trainer",
                    binding_key: "newcomer_realtime_roleplay_v1",
                    module_key: "realtime_roleplay",
                },
                snapshot: {
                    external_binding: {
                        owner: "sales_trainer",
                        binding_key: "newcomer_realtime_roleplay_v1",
                        module_key: "realtime_roleplay",
                    },
                    voice_policy_snapshot: {
                        external_binding: {
                            owner: "sales_trainer",
                            binding_key: "newcomer_realtime_roleplay_v1",
                            module_key: "realtime_roleplay",
                        },
                        voice_mode: "stepfun_realtime",
                    },
                    effectiveness_snapshot: {
                        summary: "完成实时对练",
                    },
                    runtime_state: {
                        state: "completed",
                    },
                    scores: {
                        logic_score: 88,
                        accuracy_score: 82,
                        completeness_score: 76,
                    },
                },
            },
            unit_type: "realtime_roleplay",
        },
    }[recordId === "beq-legacy" ? "business_etiquette_quiz_attempt_legacy" : recordType];
    const isLegacyBusinessEtiquette = recordId === "beq-legacy";

    return {
        record_id: recordId,
        record_type: recordType,
        path_key: "newcomer_training_path_v1",
        path_revision_id: isLegacyBusinessEtiquette ? null : "path-revision-1",
        path_revision_no: isLegacyBusinessEtiquette ? null : 1,
        module_key: "business_skills",
        legacy_snapshot_only: isLegacyBusinessEtiquette,
        unit_id: "unit-1",
        unit_name: "商务技巧训练",
        user_id: "user-1",
        user_name: "张三",
        user_email: "zhangsan@example.com",
        user_department: "销售一部",
        status: isLegacyBusinessEtiquette ? "submitted" : "scored",
        score: isLegacyBusinessEtiquette ? null : 16,
        max_score: isLegacyBusinessEtiquette ? null : 20,
        passed: isLegacyBusinessEtiquette ? null : false,
        submitted_at: "2026-05-28T00:00:00Z",
        material_snapshot: recordType === "audio_submission" ? {
            version: 1,
            items: [{ material_id: "material-1" }],
            confirmed_material_version_id: "material-version-frozen",
        } : null,
        score_scheme_snapshot: recordType === "audio_submission" ? {
            prompt_id: "prompt-frozen",
            learner_rubric: {},
            pass_threshold: 70,
            prompt_snapshot: {
                prompt_id: "prompt-frozen",
                name: "冻结评分 Prompt",
                version: 2,
                scoring_template: "历史回放快照基线：PPT 讲解评分 v2\n请按提交时标准评分。",
                output_schema: {},
                learner_rubric: {},
            },
        } : null,
        task_brief_snapshot: recordType === "audio_submission" ? {
            title: "冻结 PPT 讲解任务",
            instructions: [],
            success_criteria: [],
            common_mistakes: [],
        } : null,
        effective_score: {
            score: 18,
            max_score: 20,
            passed: true,
            source: "latest_regrade",
            original_score: 16,
            original_max_score: 20,
            original_passed: false,
            score_delta: 2,
            latest_regrade_run_id: "run-1",
            history_overwrite: false,
        },
        latest_regrade: {
            regrade_run_id: "run-1",
            status: "completed",
        },
        score_explanation: {
            basis: "sales_trainer_phase2_projection_v1",
            summary: "重评后结构更清晰。",
            dimensions: [
                {
                    key: "structure",
                    label: "结构表达",
                    score: 8,
                    max_score: 10,
                    is_weak: false,
                },
            ],
            evidence: [
                {
                    type: "quote",
                    text: "引用了客户案例。",
                },
            ],
            issues: [
                {
                    type: "weak_detail",
                    text: "客户痛点不够具体。",
                },
            ],
            next_actions: [],
        },
        ability_profile: {
            basis: "sales_trainer_phase2_projection_v1",
            overall_score: 18,
            overall_passed: true,
            dimensions: [],
            weak_dimensions: [],
            evidence_count: 1,
        },
        remediation: {
            needed: true,
            reason: "需要补强结构表达。",
            action_label: "安排弱项复习",
            target_path: "/admin/sales-trainer/training-records",
            priority: "medium",
            weak_dimension_keys: ["structure"],
        },
        operation_logs: [
            {
                log_id: "log-1",
                action: "historical_regrade.completed",
                actor_id: "admin-1",
                actor_role: "admin",
                target_type: "quiz_attempt",
                target_id: recordId,
                request_id: "trace-1",
                ip_address: null,
                user_agent: null,
                metadata: {},
                created_at: "2026-05-28T01:00:00Z",
                training_context: {
                    path_key: "newcomer_training_path_v1",
                    path_revision_id: "path-revision-1",
                    path_revision_no: 3,
                    training_stage: "needs_remediation",
                    learner_level: {
                        level_key: "needs_coaching",
                        label: "重点辅导",
                        source: "org_rule",
                        rank: 20,
                    },
                    role_level: {
                        level_key: "field_sales",
                        label: "一线销售",
                        source: "org_rule",
                        rank: 10,
                    },
                },
            },
        ],
        ...rawPayloads,
    };
}

function roleplayObservationPayload(
    overrides: Record<string, unknown> = {},
) {
    return {
        session_id: "rt-1",
        source_record_id: "rt-1",
        total: 2,
        latest_turn_index: 3,
        source_counts: {
            heuristic: 2,
            llm_evaluator: 0,
        },
        status_counts: {
            pending: 0,
            completed: 2,
            failed: 0,
            ignored: 0,
        },
        items: [
            {
                observation_id: "obs-1",
                session_id: "rt-1",
                source_record_id: "rt-1",
                source: "heuristic",
                turn_index: 2,
                evaluator_status: "completed",
                dimensions: [
                    {
                        key: "capture_context",
                        instruction_contract_hash: "sha256:roleplay-contract",
                        template_stage_key: "discovery",
                        main_chain_effect: "none",
                    },
                    {
                        key: "evaluation_runtime",
                        realtime_disposition: "record_only",
                        main_chain_effect: "none",
                        llm: {
                            status: "disabled",
                        },
                    },
                ],
                signals: [
                    {
                        key: "prompt_leak_risk",
                        source: "heuristic",
                        dimension: "instruction_boundary",
                        severity: "high",
                        confidence: 0.94,
                        detector: "heuristic.prompt_leak_risk",
                        evidence: [
                            {
                                kind: "keyword",
                                value: "系统提示",
                                metadata: {},
                            },
                        ],
                    },
                ],
                error: null,
                trace_id: "trace-rt-2",
                created_at: "2026-06-27T09:06:00Z",
                updated_at: "2026-06-27T09:06:00Z",
            },
            {
                observation_id: "obs-2",
                session_id: "rt-1",
                source_record_id: "rt-1",
                source: "heuristic",
                turn_index: 3,
                evaluator_status: "completed",
                dimensions: [
                    {
                        key: "capture_context",
                        template_stage_key: "proposal",
                        main_chain_effect: "none",
                    },
                ],
                signals: [
                    {
                        key: "kb_fact_without_evidence",
                        source: "heuristic",
                        dimension: "grounding",
                        severity: "medium",
                        confidence: 0.7,
                        detector: "heuristic.kb_fact_without_evidence",
                        evidence: [
                            {
                                kind: "keyword",
                                value: "私有化",
                                metadata: {},
                            },
                        ],
                    },
                ],
                error: null,
                trace_id: "trace-rt-3",
                created_at: "2026-06-27T09:07:30Z",
                updated_at: "2026-06-27T09:07:30Z",
            },
        ],
        ...overrides,
    };
}

describe("SalesTrainerTrainingRecordDetailPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        getTrainingRecordDetailMock.mockReset();
        getRealtimeRoleplayObservationsMock.mockReset();
        getCapabilitiesMock.mockResolvedValue({
            role: "ops",
            role_label: "运维人员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: true,
                view_global_records: true,
                retry_jobs: true,
                regrade_history: true,
                view_settings: true,
                view_logs: true,
            },
        });
        getTrainingRecordDetailMock.mockImplementation((recordType: SalesTrainerTrainingRecordType, recordId: string) =>
            Promise.resolve(recordPayload(recordType, recordId)),
        );
        getRealtimeRoleplayObservationsMock.mockResolvedValue(roleplayObservationPayload());
    });

    it.each([
        ["audio_submission", "audio-1", /ppt\.wav/],
        ["quiz_attempt", "attempt-1", /paper-1/],
        ["business_etiquette_quiz_attempt", "beq-1", /business_etiquette_v1/],
        ["ai_coach_session", "coach-1", /session_id/],
        ["realtime_roleplay_session", "rt-1", /newcomer_realtime_roleplay_v1/],
    ] as const)("loads %s through the unified detail API", async (recordType, recordId, rawText) => {
        navigationState.params = { recordType, recordId };
        navigationState.pathname = `/admin/sales-trainer/training-records/${recordType}/${recordId}`;

        render(<SalesTrainerTrainingRecordDetailPage />);

        await waitFor(() => {
            expect(getTrainingRecordDetailMock).toHaveBeenCalledWith(recordType, recordId);
        });

        expect(await screen.findByText("训练记录详情")).toBeTruthy();
        expect(screen.getByText("张三 · 销售一部")).toBeTruthy();
        expect(screen.getAllByText("18 / 20").length).toBeGreaterThan(0);
        expect(screen.getByText("原始分 16 / 20")).toBeTruthy();
        expect(screen.getByText("run-1")).toBeTruthy();
        expect(screen.getAllByText("安排弱项复习").length).toBeGreaterThan(0);
        expect(screen.getByText("重评后结构更清晰。")).toBeTruthy();
        expect(screen.getByText("结构表达")).toBeTruthy();
        expect(screen.getByText("客户痛点不够具体。")).toBeTruthy();
        expect(screen.getByText("引用了客户案例。")).toBeTruthy();
        expect(screen.getByText("historical_regrade.completed")).toBeTruthy();
        expect(screen.getByText("路径版本：v3")).toBeTruthy();
        expect(screen.getByText("训练阶段：needs_remediation")).toBeTruthy();
        expect(screen.getByText("学员等级：重点辅导")).toBeTruthy();
        expect(screen.getByText("角色等级：一线销售")).toBeTruthy();
        expect(screen.getAllByText(rawText).length).toBeGreaterThan(0);
    });

    it("shows AI Coach snapshot fields as first-class detail content", async () => {
        navigationState.params = { recordType: "ai_coach_session", recordId: "coach-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/ai_coach_session/coach-1";

        render(<SalesTrainerTrainingRecordDetailPage />);

        await waitFor(() => {
            expect(getTrainingRecordDetailMock).toHaveBeenCalledWith("ai_coach_session", "coach-1");
        });

        expect(await screen.findByText("AI Coach 快照")).toBeTruthy();
        expect(screen.getByText("未达标")).toBeTruthy();
        expect(screen.getByText("商务礼仪")).toBeTruthy();
        expect(screen.getByText("prompt-revision-1")).toBeTruthy();
        expect(screen.getByText("path-revision-1 · v1")).toBeTruthy();
        expect(screen.getByText("80")).toBeTruthy();
        expect(screen.getByText("last_action")).toBeTruthy();
        expect(screen.getByText("remediate")).toBeTruthy();
        expect(screen.getByText("trace-ai-coach-detail")).toBeTruthy();
    });

    it("shows business etiquette quiz snapshot fields as first-class detail content", async () => {
        navigationState.params = {
            recordType: "business_etiquette_quiz_attempt",
            recordId: "beq-1",
        };
        navigationState.pathname = "/admin/sales-trainer/training-records/business_etiquette_quiz_attempt/beq-1";

        render(<SalesTrainerTrainingRecordDetailPage />);

        await waitFor(() => {
            expect(getTrainingRecordDetailMock).toHaveBeenCalledWith(
                "business_etiquette_quiz_attempt",
                "beq-1",
            );
        });

        expect(await screen.findByText("商务礼仪小测快照")).toBeTruthy();
        expect(screen.getAllByText("business_etiquette_v1").length).toBeGreaterThan(0);
        expect(screen.getAllByText("建立信任").length).toBeGreaterThan(0);
        expect(screen.getByText(/path-revision-business · v6/)).toBeTruthy();
        expect(screen.getByText(/pack-revision-business · v3/)).toBeTruthy();
        expect(screen.getAllByText("建立信任").length).toBeGreaterThan(0);
        expect(screen.getByText(/4 \/ 10 · 40%/)).toBeTruthy();
        expect(screen.getByText("需要先确认客户上下文。")).toBeTruthy();
    });

    it("keeps legacy business etiquette quiz snapshots replayable in detail UI", async () => {
        navigationState.params = {
            recordType: "business_etiquette_quiz_attempt",
            recordId: "beq-legacy",
        };
        navigationState.pathname = "/admin/sales-trainer/training-records/business_etiquette_quiz_attempt/beq-legacy";

        render(<SalesTrainerTrainingRecordDetailPage />);

        await waitFor(() => {
            expect(getTrainingRecordDetailMock).toHaveBeenCalledWith(
                "business_etiquette_quiz_attempt",
                "beq-legacy",
            );
        });

        expect(await screen.findByText("商务礼仪小测快照")).toBeTruthy();
        expect(screen.getByText("小测得分")).toBeTruthy();
        expect(screen.getAllByText("--").length).toBeGreaterThan(0);
        expect(screen.getByText("弱项能力")).toBeTruthy();
        expect(screen.getByText("无")).toBeTruthy();
        expect(screen.getByText("推荐章节")).toBeTruthy();
    });

    it("shows historical replay snapshots as first-class detail content", async () => {
        navigationState.params = { recordType: "audio_submission", recordId: "audio-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/audio_submission/audio-1";

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("历史回放快照")).toBeTruthy();
        expect(screen.getByText("冻结评分 Prompt")).toBeTruthy();
        expect(screen.getByText("material-version-frozen")).toBeTruthy();
        expect(screen.getByText("冻结 PPT 讲解任务")).toBeTruthy();
        expect(screen.getAllByText(/历史回放快照基线：PPT 讲解评分 v2/).length).toBeGreaterThan(0);
        expect(screen.queryByText(/当前 Prompt 漂移哨兵/)).toBeNull();
    });

    it("renders roleplay observation as a sidecar admin-only card without implying realtime interruption", async () => {
        navigationState.params = { recordType: "realtime_roleplay_session", recordId: "rt-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/realtime_roleplay_session/rt-1";

        render(<SalesTrainerTrainingRecordDetailPage />);

        await waitFor(() => {
            expect(getTrainingRecordDetailMock).toHaveBeenCalledWith("realtime_roleplay_session", "rt-1");
            expect(getRealtimeRoleplayObservationsMock).toHaveBeenCalledWith("rt-1");
        });

        expect(await screen.findByText("角色一致性观察")).toBeTruthy();
        expect(screen.getByText("新 observation endpoint")).toBeTruthy();
        expect(screen.getByText(/只记录旁路风险信号/)).toBeTruthy();
        expect(screen.getByText("record_only")).toBeTruthy();
        expect(screen.getByText("main_chain_effect=none")).toBeTruthy();
        expect(screen.getByText("逻辑结构")).toBeTruthy();
        expect(screen.getByText("88 / 100")).toBeTruthy();
        expect(screen.getByText("事实准确")).toBeTruthy();
        expect(screen.getByText("82 / 100")).toBeTruthy();
        expect(screen.getByText("覆盖完整")).toBeTruthy();
        expect(screen.getByText("76 / 100")).toBeTruthy();
        expect(screen.getAllByText("Heuristic 规则").length).toBeGreaterThan(0);
        expect(screen.getByText("需人工复核")).toBeTruthy();
        expect(screen.getAllByText("提示词泄露风险").length).toBeGreaterThan(0);
        expect(screen.getAllByText("缺少证据的事实承诺").length).toBeGreaterThan(0);
        expect(screen.getByText("Turn 2")).toBeTruthy();
        expect(screen.getAllByText("提示词泄露风险").length).toBeGreaterThan(0);
        expect(screen.getAllByText("记入旁路观察").length).toBeGreaterThan(0);
        expect(screen.queryByText(/已阻断|已取消输出|重生成一次|取消当前输出|阻断级事件|系统修复/)).toBeNull();
    });

    it("redacts secret-like observation evidence before rendering it in the admin detail card", async () => {
        navigationState.params = { recordType: "realtime_roleplay_session", recordId: "rt-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/realtime_roleplay_session/rt-1";
        getRealtimeRoleplayObservationsMock.mockResolvedValueOnce(roleplayObservationPayload({
            items: [
                {
                    observation_id: "obs-secret",
                    session_id: "rt-1",
                    source_record_id: "rt-1",
                    source: "heuristic",
                    turn_index: 2,
                    evaluator_status: "completed",
                    dimensions: [
                        {
                            key: "capture_context",
                            template_stage_key: "discovery",
                            main_chain_effect: "none",
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
                                    value: "api_key=should-not-leak",
                                },
                            ],
                        },
                    ],
                    error: null,
                    trace_id: "trace-secret",
                    created_at: "2026-06-27T09:06:00Z",
                    updated_at: "2026-06-27T09:06:00Z",
                },
            ],
        }));

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("角色一致性观察")).toBeTruthy();
        expect(await screen.findByText(/api_key=<redacted>/)).toBeTruthy();
        expect(screen.queryByText(/should-not-leak/)).toBeNull();
    });

    it("falls back to legacy compliance snapshot when the new observation endpoint has no rows", async () => {
        navigationState.params = { recordType: "realtime_roleplay_session", recordId: "rt-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/realtime_roleplay_session/rt-1";
        getTrainingRecordDetailMock.mockResolvedValueOnce({
            ...recordPayload("realtime_roleplay_session", "rt-1"),
            realtime_roleplay_session: {
                ...recordPayload("realtime_roleplay_session", "rt-1").realtime_roleplay_session,
                snapshot: {
                    ...recordPayload("realtime_roleplay_session", "rt-1").realtime_roleplay_session?.snapshot,
                    voice_policy_snapshot: {
                        external_binding: {
                            owner: "sales_trainer",
                            binding_key: "newcomer_realtime_roleplay_v1",
                            module_key: "realtime_roleplay",
                        },
                        voice_mode: "stepfun_realtime",
                        roleplay_contract_hash: "sha256:legacy-contract",
                        runtime_metrics: {
                            roleplay_compliance: {
                                violation_count: 1,
                                blocking_violation_count: 0,
                                hidden_leak_prevented_count: 1,
                                last_action_at: "2026-06-27T09:07:30Z",
                                signal_sources: ["heuristic"],
                                timeline: [
                                    {
                                        event_type: "compliance_decision",
                                        turn_number: 2,
                                        action: "mark_for_report",
                                        violation_code: "prompt_leak_risk",
                                        severity: "warning",
                                        created_at: "2026-06-27T09:07:30Z",
                                        trace_id: "trace-legacy",
                                    },
                                ],
                            },
                        },
                    },
                },
            },
        });
        getRealtimeRoleplayObservationsMock.mockResolvedValueOnce(roleplayObservationPayload({
            total: 0,
            latest_turn_index: null,
            source_counts: { heuristic: 0, llm_evaluator: 0 },
            status_counts: { pending: 0, completed: 0, failed: 0, ignored: 0 },
            items: [],
        }));

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("legacy compliance fallback")).toBeTruthy();
        expect(screen.getByText(/当前没有 sidecar 观测行/)).toBeTruthy();
        expect(screen.getAllByText("提示词泄露风险").length).toBeGreaterThan(0);
        expect(screen.queryByText("新 observation endpoint")).toBeNull();
    });

    it("shows observation empty state when admin endpoint returns no sidecar findings", async () => {
        navigationState.params = { recordType: "realtime_roleplay_session", recordId: "rt-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/realtime_roleplay_session/rt-1";
        getTrainingRecordDetailMock.mockResolvedValueOnce({
            ...recordPayload("realtime_roleplay_session", "rt-1"),
            realtime_roleplay_session: {
                ...recordPayload("realtime_roleplay_session", "rt-1").realtime_roleplay_session,
                snapshot: {
                    ...recordPayload("realtime_roleplay_session", "rt-1").realtime_roleplay_session?.snapshot,
                    scores: {
                        logic_score: null,
                        accuracy_score: null,
                        completeness_score: null,
                    },
                    voice_policy_snapshot: {
                        external_binding: {
                            owner: "sales_trainer",
                        },
                    },
                },
            },
        });
        getRealtimeRoleplayObservationsMock.mockResolvedValueOnce(roleplayObservationPayload({
            total: 0,
            latest_turn_index: null,
            source_counts: { heuristic: 0, llm_evaluator: 0 },
            status_counts: { pending: 0, completed: 0, failed: 0, ignored: 0 },
            items: [],
        }));

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("观测尚未落库")).toBeTruthy();
        expect(screen.getByText(/当前实时对练已支持新 observation endpoint/)).toBeTruthy();
    });

    it("shows a dedicated empty state when the session used legacy runtime semantics", async () => {
        navigationState.params = { recordType: "realtime_roleplay_session", recordId: "rt-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/realtime_roleplay_session/rt-1";
        getTrainingRecordDetailMock.mockResolvedValueOnce({
            ...recordPayload("realtime_roleplay_session", "rt-1"),
            realtime_roleplay_session: {
                ...recordPayload("realtime_roleplay_session", "rt-1").realtime_roleplay_session,
                snapshot: {
                    ...recordPayload("realtime_roleplay_session", "rt-1").realtime_roleplay_session?.snapshot,
                    voice_policy_snapshot: {
                        voice_mode: "legacy",
                    },
                },
            },
        });
        getRealtimeRoleplayObservationsMock.mockResolvedValueOnce(roleplayObservationPayload({
            total: 0,
            latest_turn_index: null,
            source_counts: { heuristic: 0, llm_evaluator: 0 },
            status_counts: { pending: 0, completed: 0, failed: 0, ignored: 0 },
            items: [],
        }));

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("历史旧记录尚未接入新 observation endpoint")).toBeTruthy();
        expect(screen.getByText(/旧版 legacy compliance 时段/)).toBeTruthy();
    });

    it("distinguishes the LLM-disabled empty state from generic missing sidecar data", async () => {
        navigationState.params = { recordType: "realtime_roleplay_session", recordId: "rt-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/realtime_roleplay_session/rt-1";
        getTrainingRecordDetailMock.mockResolvedValueOnce({
            ...recordPayload("realtime_roleplay_session", "rt-1"),
            realtime_roleplay_session: {
                ...recordPayload("realtime_roleplay_session", "rt-1").realtime_roleplay_session,
                snapshot: {
                    ...recordPayload("realtime_roleplay_session", "rt-1").realtime_roleplay_session?.snapshot,
                    voice_policy_snapshot: {
                        external_binding: {
                            owner: "sales_trainer",
                            binding_key: "newcomer_realtime_roleplay_v1",
                            module_key: "realtime_roleplay",
                        },
                        voice_mode: "stepfun_realtime",
                        runtime_metrics: {
                            roleplay_compliance: {
                                llm_status: "disabled",
                                heuristic_only: true,
                                violation_count: 0,
                                timeline: [],
                            },
                        },
                    },
                },
            },
        });
        getRealtimeRoleplayObservationsMock.mockResolvedValueOnce(roleplayObservationPayload({
            total: 0,
            latest_turn_index: null,
            source_counts: { heuristic: 0, llm_evaluator: 0 },
            status_counts: { pending: 0, completed: 0, failed: 0, ignored: 0 },
            items: [],
        }));

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("LLM 默认关闭，当前没有新增 observation 行")).toBeTruthy();
        expect(screen.getByText(/背景 LLM 评估默认关闭/)).toBeTruthy();
    });

    it("surfaces observation API errors without blocking the rest of the detail page", async () => {
        navigationState.params = { recordType: "realtime_roleplay_session", recordId: "rt-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/realtime_roleplay_session/rt-1";
        getRealtimeRoleplayObservationsMock.mockRejectedValueOnce(
            new Error("observation endpoint unavailable"),
        );

        render(<SalesTrainerTrainingRecordDetailPage />);

        await waitFor(() => {
            expect(getTrainingRecordDetailMock).toHaveBeenCalledWith("realtime_roleplay_session", "rt-1");
        });

        expect(await screen.findByText("角色一致性观察加载失败")).toBeTruthy();
        expect(screen.getByText("observation endpoint unavailable")).toBeTruthy();
        expect(screen.getByText("训练记录详情")).toBeTruthy();
        expect(screen.getByText("原始分 16 / 20")).toBeTruthy();
        expect(screen.getByText("run-1")).toBeTruthy();
    });

    it("shows loading state before the detail request resolves", async () => {
        navigationState.params = { recordType: "ai_coach_session", recordId: "coach-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/ai_coach_session/coach-1";
        getTrainingRecordDetailMock.mockReturnValue(new Promise(() => undefined));

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("正在加载训练记录...")).toBeTruthy();
    });

    it("shows API errors without rendering a stale record and recovers on retry", async () => {
        navigationState.params = { recordType: "ai_coach_session", recordId: "coach-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/ai_coach_session/coach-1";
        getTrainingRecordDetailMock
            .mockRejectedValueOnce(new Error("无权查看该训练记录"))
            .mockResolvedValueOnce(recordPayload("ai_coach_session", "coach-1"));

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("训练记录加载失败")).toBeTruthy();
        expect(await screen.findByText("无权查看该训练记录")).toBeTruthy();
        expect(screen.queryByText("AI Coach 快照")).toBeNull();

        const callsBeforeRetry = getTrainingRecordDetailMock.mock.calls.length;
        fireEvent.click(screen.getByRole("button", { name: "重新加载训练记录" }));

        expect(await screen.findByText("AI Coach 快照")).toBeTruthy();
        await waitFor(() => {
            expect(getTrainingRecordDetailMock.mock.calls.length).toBeGreaterThan(callsBeforeRetry);
        });
    });

    it("fails closed for unsupported record types", async () => {
        navigationState.params = { recordType: "unknown_record", recordId: "record-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/unknown_record/record-1";

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("训练记录类型无效。")).toBeTruthy();
        expect(getTrainingRecordDetailMock).not.toHaveBeenCalled();
    });

    it("does not request record detail before view_records capability is confirmed", async () => {
        navigationState.params = { recordType: "ai_coach_session", recordId: "coach-1" };
        navigationState.pathname = "/admin/sales-trainer/training-records/ai_coach_session/coach-1";
        getCapabilitiesMock.mockResolvedValue({
            role: "content_admin",
            role_label: "内容管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: true,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_settings: false,
                view_logs: false,
            },
        });

        render(<SalesTrainerTrainingRecordDetailPage />);

        expect(await screen.findByText("训练记录权限不足")).toBeTruthy();
        expect(screen.queryByText("未找到训练记录。")).toBeNull();
        expect(getTrainingRecordDetailMock).not.toHaveBeenCalled();
    });
});
