import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerJourneyAnalyticsPage from "./page";
import { ApiRequestError } from "@/lib/api/client";
import type { TrainingJourneyAnalyticsResponse } from "@/lib/api/types";

function renderPage() {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(
        <QueryClientProvider client={queryClient}>
            <SalesTrainerJourneyAnalyticsPage />
        </QueryClientProvider>,
    );
}

const { getCapabilitiesMock, getJourneyAnalyticsMock } = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
    getJourneyAnalyticsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/analytics",
}));

vi.mock("@/components/admin/admin-layout-shells", () => ({
    AdminIndexShell: ({
        header,
        contextBar,
        children,
    }: {
        header: ReactNode;
        contextBar?: ReactNode;
        children: ReactNode;
    }) => (
        <div>
            {header}
            {contextBar}
            {children}
        </div>
    ),
    AdminContextBar: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    AdminPageHeader: ({
        title,
        description,
        primaryAction,
        secondaryActions,
    }: {
        title: string;
        description?: string;
        primaryAction?: ReactNode;
        secondaryActions?: ReactNode;
    }) => (
        <header>
            <h1>{title}</h1>
            {description ? <p>{description}</p> : null}
            {secondaryActions}
            {primaryAction}
        </header>
    ),
}));

vi.mock("@/components/admin/sales-trainer/module-nav", () => ({
    SalesTrainerAdminModuleNav: () => <nav aria-label="新人训练路径导航" />,
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
                    getJourneyAnalytics: getJourneyAnalyticsMock,
                },
            },
        },
    };
});

function makeAnalytics(
    overrides: Partial<TrainingJourneyAnalyticsResponse> = {},
): TrainingJourneyAnalyticsResponse {
    return {
        generated_at: "2026-06-27T10:20:00Z",
        summary: {
            learner_count: 8,
            loaded_learner_count: 8,
            passed_learner_count: 5,
            risk_learner_count: 2,
            pass_rate: 62.5,
        },
        funnel: [
            { stage: "not_started", learner_count: 2, rate: 25 },
            { stage: "in_progress", learner_count: 1, rate: 12.5 },
            { stage: "needs_remediation", learner_count: 2, rate: 25 },
            { stage: "passed", learner_count: 3, rate: 37.5 },
        ],
        module_summaries: [
            {
                module_key: "ppt_explanation",
                title: "PPT 讲解录音",
                kind: "audio_submission",
                learner_count: 8,
                passed_count: 5,
                failed_count: 2,
                status_counts: {
                    passed: 5,
                    needs_remediation: 2,
                    in_progress: 1,
                },
                pass_rate: 62.5,
                average_score: 78.4,
            },
            {
                module_key: "business_skills",
                title: "商务技巧",
                kind: "quiz_attempt",
                learner_count: 8,
                passed_count: 4,
                failed_count: 3,
                status_counts: {
                    passed: 4,
                    failed: 3,
                    not_started: 1,
                },
                pass_rate: 50,
                average_score: 74,
            },
        ],
        weakness_heatmap: [
            {
                heatmap_key: "business_skills:quiz_attempt",
                module_key: "business_skills",
                title: "商务技巧",
                kind: "quiz_attempt",
                learner_count: 8,
                risk_count: 3,
                passed_count: 4,
                status_counts: {
                    failed: 3,
                    passed: 4,
                    not_started: 1,
                },
                risk_rate: 37.5,
                pass_rate: 50,
                average_score: 74,
            },
            {
                heatmap_key: "ppt_explanation:audio_submission",
                module_key: "ppt_explanation",
                title: "PPT 讲解录音",
                kind: "audio_submission",
                learner_count: 8,
                risk_count: 2,
                passed_count: 5,
                status_counts: {
                    passed: 5,
                    needs_remediation: 2,
                    in_progress: 1,
                },
                risk_rate: 25,
                pass_rate: 62.5,
                average_score: 78.4,
            },
        ],
        trend_data: [
            {
                date: "2026-06-26",
                outcome_count: 2,
                passed_outcome_count: 1,
                risk_outcome_count: 1,
                active_learner_count: 2,
                pass_rate: 50,
                average_score: 72,
            },
            {
                date: "2026-06-27",
                outcome_count: 4,
                passed_outcome_count: 3,
                risk_outcome_count: 1,
                active_learner_count: 3,
                pass_rate: 75,
                average_score: 84.5,
            },
        ],
        learner_level_summaries: [
            {
                key: "l1",
                label: "L1 新人",
                learner_count: 6,
                source: "training_projection",
            },
            {
                key: "l2",
                label: "L2 进阶",
                learner_count: 2,
            },
        ],
        role_level_summaries: [
            {
                key: "field_sales",
                label: "一线销售",
                learner_count: 6,
            },
            {
                key: "sales_manager",
                label: "销售主管",
                learner_count: 2,
            },
        ],
        risk_learners: [
            {
                learner_id: "user-1",
                learner_name: "张三",
                department: "销售一部",
                training_stage: "needs_remediation",
                risk_module_count: 2,
                risk_reasons: [
                    "ppt_explanation:not_passed",
                    "business_skills:not_passed",
                ],
                risk_module_keys: ["ppt_explanation", "business_skills"],
            },
            {
                learner_id: "user-2",
                learner_name: "李四",
                department: "销售一部",
                training_stage: "error_terminal",
                risk_module_count: 1,
                risk_reasons: ["ai_coach_failed"],
            },
        ],
        roleplay_observation_aggregate: {
            status: "ready",
            total_session_count: 6,
            observed_session_count: 4,
            legacy_fallback_session_count: 1,
            not_persisted_session_count: 1,
            manual_review_session_count: 2,
            llm_disabled_session_count: 3,
            llm_timeout_session_count: 1,
            observation_count: 5,
            signal_count: 3,
            source_counts: {
                heuristic: 4,
                llm_evaluator: 1,
            },
            status_counts: {
                completed: 4,
                failed: 1,
            },
            generated_at: "2026-06-27T10:18:00Z",
        },
        filters: {
            department: "销售一部",
            limit: 500,
        },
        ...overrides,
    };
}

describe("SalesTrainerJourneyAnalyticsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_questions: false,
                manage_modules: false,
                manage_prompts: false,
                view_records: true,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_logs: false,
                view_settings: false,
            },
            capability_keys: ["view_records"],
        });
        getJourneyAnalyticsMock.mockResolvedValue(makeAnalytics());
    });

    it("renders summary, funnel, module summaries, level summaries and risk learners", async () => {
        renderPage();

        await waitFor(() => {
            expect(getJourneyAnalyticsMock).toHaveBeenCalledWith({
                department: undefined,
                training_stage: undefined,
                module_key: undefined,
                learner_level: undefined,
                role_level: undefined,
                limit: 500,
            });
        });

        expect(screen.getByRole("heading", { name: "Journey Analytics" })).toBeTruthy();
        expect(screen.getByText("总样本 8 人")).toBeTruthy();
        expect(screen.getAllByText("62.5%").length).toBeGreaterThan(0);
        expect(screen.getByRole("heading", { name: "Journey 漏斗" })).toBeTruthy();
        expect(screen.getByRole("heading", { name: "角色一致性观测聚合" })).toBeTruthy();
        expect(screen.getByText("legacy compliance fallback")).toBeTruthy();
        expect(screen.getByText("Heuristic 规则 4")).toBeTruthy();
        expect(screen.getByText("LLM 辅助 1")).toBeTruthy();
        expect(screen.getByText("观测完成 4")).toBeTruthy();
        expect(screen.getByText("观测失败 1")).toBeTruthy();
        expect(screen.getByRole("heading", { name: "历史趋势" })).toBeTruthy();
        expect(screen.getByText("2 个日期桶")).toBeTruthy();
        expect(screen.getByText("通过率 75%")).toBeTruthy();
        expect(screen.getByText("84.5")).toBeTruthy();
        expect(screen.getByRole("heading", { name: "模块通过率与状态分布" })).toBeTruthy();
        expect(screen.getAllByText("PPT 讲解录音").length).toBeGreaterThan(0);
        expect(screen.getByRole("heading", { name: "弱项热图" })).toBeTruthy();
        expect(screen.getAllByText("风险人数").length).toBeGreaterThan(0);
        expect(screen.getByText("3/8")).toBeTruthy();
        expect(screen.getAllByText("37.5%").length).toBeGreaterThan(0);
        expect(screen.getByText("L1 新人")).toBeTruthy();
        expect(screen.getByText("source: training_projection")).toBeTruthy();
        expect(screen.getByText("角色等级分布")).toBeTruthy();
        expect(screen.getAllByText("张三").length).toBeGreaterThan(0);
        expect(screen.getByText("ai_coach_failed")).toBeTruthy();
        const recordLinks = screen.getAllByRole("link", { name: /查看训练记录/ });
        expect(recordLinks[0].getAttribute("href")).toBe(
            "/admin/sales-trainer/training-records?user_id=user-1&module_key=ppt_explanation",
        );
        expect(recordLinks[1].getAttribute("href")).toBe(
            "/admin/sales-trainer/training-records?user_id=user-2",
        );
    });

    it("shows empty state when the current filter has no visible learners", async () => {
        getJourneyAnalyticsMock.mockResolvedValueOnce(
            makeAnalytics({
                summary: {
                    learner_count: 0,
                    loaded_learner_count: 0,
                    passed_learner_count: 0,
                    risk_learner_count: 0,
                    pass_rate: null,
                },
                funnel: [],
                module_summaries: [],
                weakness_heatmap: [],
                learner_level_summaries: [],
                role_level_summaries: [],
                risk_learners: [],
                filters: {
                    department: "销售二部",
                    limit: 500,
                },
            }),
        );

        renderPage();

        await waitFor(() => {
            expect(screen.getByText(/当前筛选下暂无 Journey 数据/)).toBeTruthy();
        });
        expect(screen.getByText(/部门「销售二部」当前没有可见学员 Journey/)).toBeTruthy();
    });

    it("keeps the observation aggregate block compatible when additive DTO is absent", async () => {
        getJourneyAnalyticsMock.mockResolvedValueOnce(
            makeAnalytics({
                roleplay_observation_aggregate: undefined,
            }),
        );

        renderPage();

        expect(await screen.findByRole("heading", { name: "角色一致性观测聚合" })).toBeTruthy();
        expect(screen.getByText(/后端 observation 聚合 DTO 尚未返回/)).toBeTruthy();
        expect(screen.getByRole("heading", { name: "Journey 漏斗" })).toBeTruthy();
    });

    it("surfaces API errors and retries instead of swallowing them into empty data", async () => {
        getJourneyAnalyticsMock
            .mockRejectedValueOnce(
                new ApiRequestError({
                    status: 403,
                    errorCode: "[ROLE_REQUIRED]",
                    message: "权限不足",
                    traceId: "trace-journey-403",
                    details: null,
                }),
            )
            .mockResolvedValueOnce(makeAnalytics());

        renderPage();

        await waitFor(() => {
            expect(screen.getByText(/Journey Analytics 加载失败/)).toBeTruthy();
        });
        expect(screen.getAllByText(/权限不足/).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/trace-journey-403/).length).toBeGreaterThan(0);

        fireEvent.click(screen.getByRole("button", { name: /重试加载/ }));

        await waitFor(() => {
            expect(screen.getAllByText("62.5%").length).toBeGreaterThan(0);
        });
        expect(getJourneyAnalyticsMock).toHaveBeenCalledTimes(2);
    });

    it("applies department filter and refreshes with the current filter", async () => {
        getJourneyAnalyticsMock
            .mockResolvedValueOnce(makeAnalytics({ filters: { department: "销售一部", limit: 500 } }))
            .mockResolvedValueOnce(makeAnalytics({ filters: { department: "销售二部", limit: 500 } }))
            .mockResolvedValueOnce(makeAnalytics({ filters: { department: "销售二部", limit: 500 } }));

        renderPage();

        await waitFor(() => {
            expect(getJourneyAnalyticsMock).toHaveBeenNthCalledWith(1, {
                department: undefined,
                training_stage: undefined,
                module_key: undefined,
                learner_level: undefined,
                role_level: undefined,
                limit: 500,
            });
        });

        fireEvent.change(screen.getByLabelText("部门筛选"), {
            target: { value: "销售二部" },
        });
        fireEvent.change(screen.getByLabelText("训练阶段筛选"), {
            target: { value: "needs_remediation" },
        });
        fireEvent.change(screen.getByLabelText("模块筛选"), {
            target: { value: "ppt_explanation" },
        });
        fireEvent.change(screen.getByLabelText("学员等级筛选"), {
            target: { value: "l1" },
        });
        fireEvent.change(screen.getByLabelText("角色等级筛选"), {
            target: { value: "field_sales" },
        });
        fireEvent.click(screen.getByRole("button", { name: "应用筛选" }));

        await waitFor(() => {
            expect(getJourneyAnalyticsMock).toHaveBeenNthCalledWith(2, {
                department: "销售二部",
                training_stage: "needs_remediation",
                module_key: "ppt_explanation",
                learner_level: "l1",
                role_level: "field_sales",
                limit: 500,
            });
        });

        fireEvent.click(screen.getByRole("button", { name: "刷新数据" }));

        await waitFor(() => {
            expect(getJourneyAnalyticsMock).toHaveBeenNthCalledWith(3, {
                department: "销售二部",
                training_stage: "needs_remediation",
                module_key: "ppt_explanation",
                learner_level: "l1",
                role_level: "field_sales",
                limit: 500,
            });
        });
    });

    it("fails closed before loading analytics when capabilities are unavailable", async () => {
        getCapabilitiesMock.mockRejectedValueOnce(new Error("capability unavailable"));

        renderPage();

        expect(await screen.findByText("页面访问受限")).toBeTruthy();
        expect(screen.getByText("capability unavailable")).toBeTruthy();
        expect(getJourneyAnalyticsMock).not.toHaveBeenCalled();
        expect(screen.queryByText("当前筛选下暂无 Journey 数据")).toBeNull();
    });
});
