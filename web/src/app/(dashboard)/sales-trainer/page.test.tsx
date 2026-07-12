import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api/client";
import type { TrainingJourneyRetrainingRequest } from "@/lib/api/types/training-journey";

import SalesTrainerPage from "./page";

const { getJourneyMock, listPathsMock, listUnitsMock, routerPushMock, startRealtimeRoleplayMock, useMyAudioSubmissionsMock } =
    vi.hoisted(() => ({
        getJourneyMock: vi.fn(),
        listUnitsMock: vi.fn(),
        listPathsMock: vi.fn(),
        routerPushMock: vi.fn(),
        startRealtimeRoleplayMock: vi.fn(),
        useMyAudioSubmissionsMock: vi.fn(),
    }));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: routerPushMock,
    }),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/components/sales-trainer/sales-trainer-module-grid", () => ({
    SalesTrainerModuleGrid: ({ path }: { path: { path_key: string } }) => (
        <div>{`legacy-module-grid:${path.path_key}`}</div>
    ),
}));

vi.mock("@/components/sales-trainer/sales-trainer-module-mission-panel", () => ({
    SalesTrainerModuleMissionPanel: ({ path }: { path: { path_key: string } }) => (
        <div>{`legacy-module-mission:${path.path_key}`}</div>
    ),
}));

vi.mock("./path-mission-panel", () => ({
    PathMissionPanel: ({ path }: { path: { path_key: string } }) => (
        <div>{`legacy-path-mission:${path.path_key}`}</div>
    ),
}));

vi.mock("./path-level-timeline", () => ({
    PathLevelTimeline: ({ path }: { path: { path_key: string } }) => (
        <div>{`legacy-path-timeline:${path.path_key}`}</div>
    ),
}));

vi.mock("@/hooks/use-my-audio-submissions", () => ({
    useMyAudioSubmissions: useMyAudioSubmissionsMock,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                getJourney: getJourneyMock,
                listUnits: listUnitsMock,
                listPaths: listPathsMock,
                startRealtimeRoleplay: startRealtimeRoleplayMock,
            },
        },
    };
});

const baseTimestamp = "2026-06-27T00:00:00Z";

function buildJourneyError(errorCode: string, message: string, traceId: string, status = 409) {
    return new ApiRequestError({
        status,
        errorCode,
        message,
        traceId,
    });
}

function buildJourney(overrides?: Partial<ReturnType<typeof createJourneyFixture>>) {
    return {
        ...createJourneyFixture(),
        ...overrides,
    };
}

function createJourneyFixture() {
    return {
        journey_id: "journey-1",
        learner_id: "learner-1",
        learner_name: "张三",
        department: "销售一部",
        path_key: "newcomer_training_path_v1" as const,
        path_revision_id: "path-rev-1",
        path_revision_no: 3,
        source: "active_revision" as const,
        legacy_snapshot_only: false as const,
        role_capabilities: [
            {
                capability_key: "learner_enter" as const,
                allowed: true,
                scope: "own" as const,
                reason_code: null,
            },
            {
                capability_key: "sales_trainer.enter_realtime" as const,
                allowed: true,
                scope: "own" as const,
                reason_code: null,
            },
        ],
        learner_level: {
            level_key: "newcomer",
            label: "新人销售",
            source: "training_projection" as const,
            rank: 1,
            effective_from: null,
            effective_to: null,
            config_revision_id: null,
            description: null,
        },
        role_level: {
            level_key: "learner",
            label: "普通学员",
            source: "training_projection" as const,
            rank: 0,
            effective_from: null,
            effective_to: null,
            config_revision_id: null,
            description: null,
        },
        training_stage: "in_progress" as const,
        modules: [
            {
                module_key: "ppt_explanation",
                module_type: "audio_scoring" as const,
                display_name: "PPT 讲解录音",
                order_index: 1,
                enabled: true,
                stage: "passed" as const,
                completion_rule: "scored" as const,
                learner_level_required: ["newcomer"],
                unmet_reasons: [],
                next_action: {
                    action_key: "review_audio",
                    label: "查看录音结果",
                    target_path: "/sales-trainer/audio/result/submission-1",
                    disabled: false,
                    disabled_reason: null,
                },
                latest_outcome: {
                    outcome_id: "outcome-1",
                    record_type: "audio_submission" as const,
                    source_record_id: "submission-1",
                    module_key: "ppt_explanation",
                    module_type: "audio_scoring" as const,
                    status: "passed" as const,
                    score: null,
                    max_score: null,
                    passed: true,
                    failure_type: null,
                    failure_code: null,
                    submitted_at: baseTimestamp,
                    completed_at: baseTimestamp,
                    path_revision_id: "path-rev-1",
                    path_revision_no: 3,
                    snapshot_ref: {
                        snapshot_type: "submission_snapshot" as const,
                        legacy_snapshot_only: false,
                    },
                },
                outcome_history: [],
            },
            {
                module_key: "business_skills",
                module_type: "article_exam" as const,
                display_name: "商务技巧",
                order_index: 2,
                enabled: true,
                stage: "processing" as const,
                completion_rule: "passed" as const,
                learner_level_required: null,
                unmet_reasons: [
                    {
                        code: "WAITING_REVIEW",
                        message: "系统正在处理最近一次结果。",
                        terminal: false,
                    },
                ],
                next_action: {
                    action_key: "wait_result",
                    label: "等待处理完成",
                    target_path: null,
                    disabled: true,
                    disabled_reason: "最近一次训练结果仍在处理中。",
                },
                latest_outcome: {
                    outcome_id: "outcome-2",
                    record_type: "quiz_attempt" as const,
                    source_record_id: "attempt-2",
                    module_key: "business_skills",
                    module_type: "article_exam" as const,
                    status: "processing" as const,
                    score: null,
                    max_score: null,
                    passed: null,
                    failure_type: null,
                    failure_code: null,
                    submitted_at: baseTimestamp,
                    completed_at: null,
                    path_revision_id: "path-rev-1",
                    path_revision_no: 3,
                    snapshot_ref: {
                        snapshot_type: "attempt_snapshot" as const,
                        legacy_snapshot_only: false,
                    },
                },
                outcome_history: [],
            },
            {
                module_key: "realtime_roleplay",
                module_type: "realtime_roleplay" as const,
                display_name: "实时对练",
                order_index: 3,
                enabled: true,
                stage: "not_started" as const,
                completion_rule: "submitted" as const,
                learner_level_required: null,
                unmet_reasons: [],
                next_action: {
                    action_key: "start_realtime_roleplay",
                    label: "开始实时对练",
                    target_path: null,
                    disabled: false,
                    disabled_reason: null,
                },
                latest_outcome: null,
                outcome_history: [],
            },
        ],
        overall_progress: {
            total_modules: 3,
            completed_modules: 1,
            passed_modules: 1,
            failed_modules: 0,
            needs_remediation_modules: 0,
        },
        retraining_requests: [] as TrainingJourneyRetrainingRequest[],
        diagnostics: [
            {
                code: "JOURNEY_ACTIVE_REVISION",
                message: "Journey 已按 active revision 更新。",
                severity: "info" as const,
                terminal: false,
            },
        ],
        generated_at: baseTimestamp,
    };
}

function createPathFixture() {
    return {
        path_key: "newcomer_training_path_v1",
        title: "新人训练路径",
        goal_title: "掌握新人训练闭环",
        total_levels: 1,
        completed_levels: 0,
        current_level_id: "module-1",
        next_level_id: "module-1",
        goal_context: {
            goal_title: "掌握新人训练闭环",
            score_basis: "sales_trainer_path_projection_v1" as const,
            evidence_items: [],
            weak_points: [],
            next_recommendation: null,
        },
        levels: [
            {
                unit_id: "module-1",
                name: "PPT 讲解录音",
                description: "兼容入口卡片",
                unit_type: "audio_scoring" as const,
                module_key: "ppt_explanation" as const,
                module_type: "audio_scoring" as const,
                order_index: 1,
                level_title: "第1关：PPT 讲解录音",
                level_description: "兼容入口卡片",
                locked: false,
                lock_reason: null,
                status: "available" as const,
                completion_rule: "scored" as const,
                primary_action_label: "开始训练",
                retry_action_label: "重新训练",
                review_action_label: "查看结果",
                target_path: "/sales-trainer/audio/module-1",
                latest_result: null,
            },
        ],
    };
}

function createUnitsFixture() {
    return [
        {
            unit_id: "module-1",
            name: "PPT 讲解录音",
            description: "兼容单元",
            unit_type: "audio_scoring" as const,
            config: {},
            status: "published" as const,
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: baseTimestamp,
            updated_at: baseTimestamp,
            questions: [],
        },
    ];
}

describe("SalesTrainerPage", () => {
    beforeEach(() => {
        getJourneyMock.mockReset();
        listPathsMock.mockReset();
        listUnitsMock.mockReset();
        routerPushMock.mockReset();
        startRealtimeRoleplayMock.mockReset();

        getJourneyMock.mockResolvedValue(buildJourney());
        startRealtimeRoleplayMock.mockResolvedValue({
            session_id: "session-realtime-1",
            module_key: "realtime_roleplay",
            path_key: "newcomer_training_path_v1",
            path_revision_id: "path-rev-1",
            path_revision_no: 3,
            practice_url: "/practice/session-realtime-1",
            runtime_descriptor_id: "newcomer-realtime-runtime",
            provider_readiness_snapshot: {},
            external_binding: {},
        });
        listPathsMock.mockResolvedValue({
            items: [createPathFixture()],
            total: 1,
        });
        listUnitsMock.mockResolvedValue({
            items: createUnitsFixture(),
            total: 1,
        });
        useMyAudioSubmissionsMock.mockReturnValue({
            submissions: [],
            total: 0,
            isLoading: false,
            isError: false,
            error: null,
            refetch: vi.fn(),
        });
    });

    it("优先渲染训练状态，并不再读取 /paths 兼容入口卡片", async () => {
        render(<SalesTrainerPage />);

        expect(await screen.findByText("当前训练状态")).toBeTruthy();
        expect(screen.getByText("学员等级：新人销售")).toBeTruthy();
        expect(screen.getByText("训练路径已按当前发布版本更新。")).toBeTruthy();
        expect(screen.getByText("PPT 讲解录音")).toBeTruthy();
        expect(screen.getByText("商务技巧")).toBeTruthy();
        expect(screen.queryByText("兼容入口卡片")).toBeNull();
        expect(screen.queryByText("legacy-module-mission:newcomer_training_path_v1")).toBeNull();
        expect(screen.queryByText("legacy-module-grid:newcomer_training_path_v1")).toBeNull();
        expect(listUnitsMock).not.toHaveBeenCalled();
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("在无 active revision 时 fail-closed，并展示用户可理解的修复提示", async () => {
        getJourneyMock.mockRejectedValue(
            buildJourneyError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "当前没有生效中的训练路径版本。",
                "trace-journey-missing",
            ),
        );

        render(<SalesTrainerPage />);

        expect(await screen.findByText("训练路径暂不可用")).toBeTruthy();
        expect(
            screen.getByText("当前训练路径还没有发布完成，请联系培训负责人处理后再继续。"),
        ).toBeTruthy();
        expect(
            screen.queryByText("error_code: [NEWCOMER_PATH_ACTIVE_REVISION_MISSING]"),
        ).toBeNull();
        expect(screen.queryByText("trace_id: trace-journey-missing")).toBeNull();
        expect(screen.queryByText("legacy-module-mission:newcomer_training_path_v1")).toBeNull();
        expect(listUnitsMock).not.toHaveBeenCalled();
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("Journey 报错时不会回退成 catalog 伪成功", async () => {
        getJourneyMock.mockRejectedValue(
            buildJourneyError("[HTTP_500]", "Journey 服务暂时不可用。", "trace-journey-500", 500),
        );

        render(<SalesTrainerPage />);

        expect(await screen.findByText("训练路径暂不可用")).toBeTruthy();
        expect(screen.getByText("训练路径服务暂时不可用。")).toBeTruthy();
        expect(screen.queryByText("trace_id: trace-journey-500")).toBeNull();
        expect(screen.queryByText("当前训练状态")).toBeNull();
        expect(screen.queryByText("legacy-module-grid:newcomer_training_path_v1")).toBeNull();
        expect(listUnitsMock).not.toHaveBeenCalled();
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("对 passed=null 维持三态展示，不渲染失败 verdict", async () => {
        getJourneyMock.mockResolvedValue(buildJourney());

        render(<SalesTrainerPage />);

        expect(await screen.findByText("商务技巧")).toBeTruthy();
        expect(screen.getByText("待判定")).toBeTruthy();
        expect(screen.queryByText(/^未通过$/)).toBeNull();
        expect(screen.getByText("系统正在处理最近一次结果。")).toBeTruthy();
    });

    it("展示培训负责人要求重练的能力和入口，但不暴露后台审计字段", async () => {
        getJourneyMock.mockResolvedValue(
            buildJourney({
                retraining_requests: [
                    {
                        request_id: "review-action-1",
                        task_id: "retraining-task-1",
                        status: "pending",
                        reason: "商务礼仪表达还需要再练一次。",
                        capability_keys: ["business_etiquette"],
                        capability_labels: ["商务礼仪与职业表达"],
                        source_evidence_count: 1,
                        target_modules: [
                            {
                                module_key: "business_skills",
                                title: "商务技巧 AI 教练",
                                kind: "ai_coach",
                                module_type: "ai_coach",
                                status: "failed",
                                action_label: "继续 AI 教练",
                                target_path: "/sales-trainer/business-skills/coach",
                                disabled: false,
                                disabled_reason: null,
                            },
                        ],
                        primary_target_path: "/sales-trainer/business-skills/coach",
                        created_at: baseTimestamp,
                    },
                ],
            }),
        );

        render(<SalesTrainerPage />);

        expect(await screen.findByText("培训负责人已要求重练")).toBeTruthy();
        expect(screen.getByText("商务礼仪与职业表达")).toBeTruthy();
        expect(screen.getByText("商务礼仪表达还需要再练一次。")).toBeTruthy();
        expect(screen.getByText("关联了 1 份你提交过的训练结果。")).toBeTruthy();
        expect(screen.getByRole("link", { name: "继续 AI 教练" }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills/coach",
        );
        expect(screen.queryByText(/operation_log/)).toBeNull();
        expect(screen.queryByText(/retraining-task-1/)).toBeNull();
        expect(screen.queryByText(/business_etiquette/)).toBeNull();
        expect(screen.queryByText(/ai_coach_session/)).toBeNull();
    });

    it("不会向学员暴露后台失败分类和配置术语", async () => {
        const journey = createJourneyFixture();
        const realtimeModule = journey.modules[2];
        getJourneyMock.mockResolvedValue({
            ...journey,
            modules: [
                {
                    ...realtimeModule,
                    stage: "error_terminal" as const,
                    unmet_reasons: [
                        {
                            code: "NEWCOMER_REALTIME_BINDING_INVALID",
                            message: "active path revision 中该模块缺少受治理的 runtime binding。",
                            terminal: true,
                        },
                    ],
                    next_action: {
                        ...realtimeModule.next_action,
                        disabled: true,
                        disabled_reason: "实时对练 provider readiness 未通过。",
                    },
                    latest_outcome: {
                        outcome_id: "outcome-failed",
                        record_type: "ai_coach_session" as const,
                        source_record_id: "session-failed",
                        module_key: "realtime_roleplay",
                        module_type: "realtime_roleplay" as const,
                        status: "error_terminal" as const,
                        score: null,
                        max_score: null,
                        passed: null,
                        failure_type: "terminal" as const,
                        failure_code: "[AI_COACH_SESSION_FAILED]",
                        submitted_at: baseTimestamp,
                        completed_at: null,
                        path_revision_id: "path-rev-1",
                        path_revision_no: 3,
                        snapshot_ref: {
                            snapshot_type: "session_snapshot" as const,
                            legacy_snapshot_only: false,
                        },
                    },
                },
            ],
        });

        render(<SalesTrainerPage />);

        expect(await screen.findByText("最近记录：AI 教练 · 需要人工处理")).toBeTruthy();
        expect(
            screen.getByText("真实语音对练还没有完成后台接入，请联系培训负责人处理。"),
        ).toBeTruthy();
        expect(screen.getByText("真实语音对练暂未开放，请先完成前置训练或稍后再试。")).toBeTruthy();
        expect(screen.queryByText(/provider readiness/)).toBeNull();
        expect(screen.queryByText(/runtime binding/)).toBeNull();
        expect(screen.queryByText(/active path revision/)).toBeNull();
        expect(screen.queryByText(/AI_COACH_SESSION_FAILED/)).toBeNull();
    });

    it("点击实时对练 action 会调用 start API 并跳转到 practice_url", async () => {
        render(<SalesTrainerPage />);

        fireEvent.click(await screen.findByText("开始实时对练"));

        await waitFor(() => {
            expect(startRealtimeRoleplayMock).toHaveBeenCalledWith({
                module_key: "realtime_roleplay",
            });
            expect(routerPushMock).toHaveBeenCalledWith("/practice/session-realtime-1");
        });
    });

    it("实时对练启动失败时展示用户可理解的锁定原因", async () => {
        startRealtimeRoleplayMock.mockRejectedValue(
            buildJourneyError(
                "[NEWCOMER_REALTIME_PROVIDER_NOT_READY]",
                "实时对练 provider readiness 未通过。",
                "trace-realtime-start",
                503,
            ),
        );

        render(<SalesTrainerPage />);

        fireEvent.click(await screen.findByText("开始实时对练"));

        expect(await screen.findByText("真实语音对练暂不可用")).toBeTruthy();
        expect(
            screen.getByText("真实语音对练暂未开放，不影响你继续完成前置训练和查看已有结果。"),
        ).toBeTruthy();
        expect(screen.queryByText("error_code: [NEWCOMER_REALTIME_PROVIDER_NOT_READY]")).toBeNull();
        expect(screen.queryByText("trace_id: trace-realtime-start")).toBeNull();
    });

    it("首屏只请求 Journey，不再并行读取 units 和 paths 伪装入口成功", async () => {
        render(<SalesTrainerPage />);

        await waitFor(() => {
            expect(getJourneyMock).toHaveBeenCalledTimes(1);
            expect(listUnitsMock).not.toHaveBeenCalled();
            expect(listPathsMock).not.toHaveBeenCalled();
        });
    });

    it("renders my audio submissions section with score and review link", async () => {
        useMyAudioSubmissionsMock.mockReturnValue({
            submissions: [
                {
                    submission_id: "submission-1",
                    unit_id: "module-1",
                    user_id: "learner-1",
                    user_name: null,
                    user_email: null,
                    user_department: null,
                    purpose: "ppt_pitch",
                    original_filename: "pitch-1.wav",
                    content_type: "audio/wav",
                    size_bytes: 1024,
                    storage_key: "private/audio/pitch-1.wav",
                    file_hash: null,
                    duration_seconds: null,
                    source_page: null,
                    confirmed_material_version_id: null,
                    confirmed_material_at: null,
                    material_snapshot: null,
                    score_scheme_snapshot: null,
                    task_brief_snapshot: null,
                    path_key: null,
                    path_revision_id: null,
                    path_revision_no: null,
                    module_key: null,
                    legacy_snapshot_only: false,
                    status: "scored",
                    error_code: null,
                    error_message: null,
                    created_at: "2026-07-01T00:00:00Z",
                    updated_at: "2026-07-01T00:05:00Z",
                    transcript: null,
                    score_result: {
                        score_id: "score-1",
                        submission_id: "submission-1",
                        prompt_id: "prompt-1",
                        prompt_version: 1,
                        prompt_hash: "hash",
                        deucate_model: "model",
                        transcript_snapshot: null,
                        total_score: 88,
                        passed: true,
                        summary: "表达清楚",
                        strengths: [],
                        improvements: [],
                        dimension_scores: {},
                        raw_response: null,
                        error_code: null,
                        error_message: null,
                        latency_ms: null,
                        path_key: null,
                        path_revision_id: null,
                        path_revision_no: null,
                        module_key: null,
                        legacy_snapshot_only: false,
                        created_at: "2026-07-01T00:05:00Z",
                    },
                },
            ],
            total: 1,
            isLoading: false,
            isError: false,
            error: null,
            refetch: vi.fn(),
        });

        render(<SalesTrainerPage />);

        expect(await screen.findByText("我的录音")).toBeTruthy();
        expect(screen.getByText("pitch-1.wav")).toBeTruthy();
        expect(screen.getByText("88")).toBeTruthy();
        expect(screen.getByText("通过")).toBeTruthy();
        const reviewLink = screen.getByRole("link", { name: /回看/ });
        expect(reviewLink.getAttribute("href")).toBe("/sales-trainer/audio/result/submission-1");
    });

    it("shows empty hint when no audio submissions exist", async () => {
        render(<SalesTrainerPage />);

        expect(await screen.findByText("我的录音")).toBeTruthy();
        expect(screen.getByText("还没有录音，完成语音作业后这里会显示。")).toBeTruthy();
    });

    it("does not render my audio section when journey fails to load", async () => {
        getJourneyMock.mockRejectedValue(
            buildJourneyError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "训练路径未发布",
                "trace-1",
            ),
        );

        render(<SalesTrainerPage />);

        await waitFor(() => {
            expect(screen.getByText("训练路径暂不可用")).toBeTruthy();
        });
        expect(screen.queryByText("我的录音")).toBeNull();
        // hook 仍被调用，但 enabled=false（journey 为空），不会发起请求
        expect(useMyAudioSubmissionsMock).toHaveBeenCalledWith(
            expect.objectContaining({ enabled: false }),
        );
    });
});
