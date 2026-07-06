import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiRequestError } from "@/lib/api/client";

import SalesTrainerPage from "./page";

const { getJourneyMock, listPathsMock, listUnitsMock, routerPushMock, startRealtimeRoleplayMock } = vi.hoisted(() => ({
    getJourneyMock: vi.fn(),
    listUnitsMock: vi.fn(),
    listPathsMock: vi.fn(),
    routerPushMock: vi.fn(),
    startRealtimeRoleplayMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: routerPushMock,
    }),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => <div className={className}>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/components/sales-trainer/sales-trainer-module-grid", () => ({
    SalesTrainerModuleGrid: ({ path }: { path: { path_key: string } }) => <div>{`legacy-module-grid:${path.path_key}`}</div>,
}));

vi.mock("@/components/sales-trainer/sales-trainer-module-mission-panel", () => ({
    SalesTrainerModuleMissionPanel: ({ path }: { path: { path_key: string } }) => <div>{`legacy-module-mission:${path.path_key}`}</div>,
}));

vi.mock("./path-mission-panel", () => ({
    PathMissionPanel: ({ path }: { path: { path_key: string } }) => <div>{`legacy-path-mission:${path.path_key}`}</div>,
}));

vi.mock("./path-level-timeline", () => ({
    PathLevelTimeline: ({ path }: { path: { path_key: string } }) => <div>{`legacy-path-timeline:${path.path_key}`}</div>,
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
    });

    it("优先渲染 Journey 状态，并不再读取 /paths 兼容入口卡片", async () => {
        render(<SalesTrainerPage />);

        expect(await screen.findByText("当前训练闭环状态")).toBeTruthy();
        expect(screen.getByText("学员等级：新人销售")).toBeTruthy();
        expect(screen.getByText("来源：training_projection")).toBeTruthy();
        expect(screen.getByText("Journey 已按 active revision 更新。")).toBeTruthy();
        expect(screen.getByText("PPT 讲解录音")).toBeTruthy();
        expect(screen.getByText("商务技巧")).toBeTruthy();
        expect(screen.queryByText("兼容入口卡片")).toBeNull();
        expect(screen.queryByText("legacy-module-mission:newcomer_training_path_v1")).toBeNull();
        expect(screen.queryByText("legacy-module-grid:newcomer_training_path_v1")).toBeNull();
        expect(listUnitsMock).not.toHaveBeenCalled();
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("在无 active revision 时 fail-closed，并展示错误码与 trace_id", async () => {
        getJourneyMock.mockRejectedValue(
            buildJourneyError(
                "[NEWCOMER_PATH_ACTIVE_REVISION_MISSING]",
                "当前没有生效中的训练路径版本。",
                "trace-journey-missing",
            ),
        );

        render(<SalesTrainerPage />);

        expect(await screen.findByText("Journey 读取失败")).toBeTruthy();
        expect(screen.getByText("当前没有生效中的训练路径版本。 (trace_id: trace-journey-missing)")).toBeTruthy();
        expect(screen.getByText("后端信息：当前没有生效中的训练路径版本。")).toBeTruthy();
        expect(screen.getByText("error_code: [NEWCOMER_PATH_ACTIVE_REVISION_MISSING]")).toBeTruthy();
        expect(screen.getByText("trace_id: trace-journey-missing")).toBeTruthy();
        expect(screen.queryByText("legacy-module-mission:newcomer_training_path_v1")).toBeNull();
        expect(listUnitsMock).not.toHaveBeenCalled();
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("Journey 报错时不会回退成 catalog 伪成功", async () => {
        getJourneyMock.mockRejectedValue(
            buildJourneyError(
                "[HTTP_500]",
                "Journey 服务暂时不可用。",
                "trace-journey-500",
                500,
            ),
        );

        render(<SalesTrainerPage />);

        expect(await screen.findByText("Journey 读取失败")).toBeTruthy();
        expect(screen.getByText("Journey 服务暂时不可用。 (trace_id: trace-journey-500)")).toBeTruthy();
        expect(screen.queryByText("当前训练闭环状态")).toBeNull();
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

    it("实时对练启动失败时展示后端错误码与 trace_id", async () => {
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

        expect(await screen.findByText("实时对练启动失败")).toBeTruthy();
        expect(screen.getByText("error_code: [NEWCOMER_REALTIME_PROVIDER_NOT_READY]")).toBeTruthy();
        expect(screen.getByText("trace_id: trace-realtime-start")).toBeTruthy();
    });

    it("首屏只请求 Journey，不再并行读取 units 和 paths 伪装入口成功", async () => {
        render(<SalesTrainerPage />);

        await waitFor(() => {
            expect(getJourneyMock).toHaveBeenCalledTimes(1);
            expect(listUnitsMock).not.toHaveBeenCalled();
            expect(listPathsMock).not.toHaveBeenCalled();
        });
    });
});
