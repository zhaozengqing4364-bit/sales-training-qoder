import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TeamDashboardPage from "./page";
import { createAppQueryClient } from "@/lib/query/client";

const {
    listAdminJourneysMock,
    getJourneyAnalyticsMock,
    useCurrentUserMock,
} = vi.hoisted(() => ({
    listAdminJourneysMock: vi.fn(),
    getJourneyAnalyticsMock: vi.fn(),
    useCurrentUserMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: React.ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) => {
        if (asChild) {
            return <>{children}</>;
        }
        return <button type="button" {...props}>{children}</button>;
    },
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children, className }: { children: React.ReactNode; className?: string }) => (
        <span className={className}>{children}</span>
    ),
}));

vi.mock("@/components/ui/skeleton", () => ({
    Skeleton: ({ className }: { className?: string }) => (
        <div className={className} data-testid="skeleton" />
    ),
}));

vi.mock("@/components/ui/empty-state", () => ({
    EmptyState: ({ title, description, actionLabel, onAction }: { title: string; description: string; actionLabel?: string; onAction?: () => void }) => (
        <div>
            <div>{title}</div>
            <div>{description}</div>
            {actionLabel && onAction ? <button type="button" onClick={onAction}>{actionLabel}</button> : null}
        </div>
    ),
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
                    listAdminJourneys: listAdminJourneysMock,
                    getJourneyAnalytics: getJourneyAnalyticsMock,
                },
            },
        },
        getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : String(error),
    };
});

vi.mock("@/hooks/use-current-user", () => ({
    useCurrentUser: useCurrentUserMock,
}));

const trainingManagerUser = {
    id: "mgr-1",
    user_id: "mgr-1",
    name: "王经理",
    display_name: "王经理",
    email: "manager@example.com",
    role: "training_manager",
    department: "销售部",
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
};

const learnerUser = {
    id: "user-1",
    user_id: "user-1",
    name: "学员小李",
    display_name: "学员小李",
    email: "learner@example.com",
    role: "user",
    department: "销售部",
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
};

function buildAnalyticsPayload(overrides?: {
    learner_count?: number;
    passed_learner_count?: number;
    risk_learner_count?: number;
    in_progress_count?: number;
}) {
    return {
        generated_at: "2026-07-07T00:00:00Z",
        summary: {
            learner_count: overrides?.learner_count ?? 3,
            loaded_learner_count: overrides?.learner_count ?? 3,
            passed_learner_count: overrides?.passed_learner_count ?? 1,
            risk_learner_count: overrides?.risk_learner_count ?? 1,
            pass_rate: 0.33,
        },
        funnel: [
            { stage: "not_started", learner_count: 1, rate: 0.33 },
            { stage: "in_progress", learner_count: overrides?.in_progress_count ?? 1, rate: 0.33 },
            { stage: "passed", learner_count: overrides?.passed_learner_count ?? 1, rate: 0.33 },
        ],
        module_summaries: [],
        weakness_heatmap: [],
        trend_data: [],
        learner_level_summaries: [],
        role_level_summaries: [],
        risk_learners: [
            {
                learner_id: "learner-2",
                learner_name: "卡关学员",
                department: "销售部",
                training_stage: "needs_remediation",
                risk_reasons: [
                    "business_skills:not_passed",
                    "elevator_pitch:status:failed",
                ],
                risk_module_count: 2,
                risk_module_keys: ["business_skills", "elevator_pitch"],
            },
        ],
        filters: { limit: 500 },
    };
}

function buildJourneysPayload(overrides?: { items?: unknown[] }) {
    const defaultItems = [
        {
            journey_id: "journey-1",
            learner_id: "learner-1",
            learner_name: "张三",
            department: "销售部",
            path_key: "newcomer_training_path_v1",
            path_revision_id: "rev-1",
            path_revision_no: 1,
            source: "active_revision",
            legacy_snapshot_only: false,
            role_capabilities: [],
            learner_level: { level_key: "level-1", label: "初级", source: "user_profile", rank: 1 },
            role_level: { level_key: "role-1", label: "销售", source: "user_profile", rank: 1 },
            training_stage: "in_progress",
            modules: [
                {
                    module_key: "business_skills",
                    title: "商务技巧",
                    display_name: "商务技巧",
                    module_type: "article_exam",
                    kind: "quiz_attempt",
                    order_index: 1,
                    enabled: true,
                    status: "passed",
                    stage: "passed",
                    passed: true,
                    completion_rule: "passed",
                    unmet_reasons: [],
                    outcome_history: [],
                },
                {
                    module_key: "elevator_pitch",
                    title: "电梯演讲",
                    display_name: "电梯演讲",
                    module_type: "audio_scoring_group",
                    kind: "audio_submission",
                    order_index: 2,
                    enabled: true,
                    status: "in_progress",
                    stage: "in_progress",
                    passed: null,
                    completion_rule: "passed",
                    unmet_reasons: [],
                    outcome_history: [],
                },
            ],
            overall_progress: {
                total_modules: 5,
                completed_modules: 2,
                passed_modules: 1,
                failed_modules: 1,
                needs_remediation_modules: 0,
            },
            retraining_requests: [],
            diagnostics: [],
            generated_at: "2026-07-07T00:00:00Z",
        },
        {
            journey_id: "journey-2",
            learner_id: "learner-2",
            learner_name: "卡关学员",
            department: "销售部",
            path_key: "newcomer_training_path_v1",
            path_revision_id: "rev-1",
            path_revision_no: 1,
            source: "active_revision",
            legacy_snapshot_only: false,
            role_capabilities: [],
            learner_level: { level_key: "level-1", label: "初级", source: "user_profile", rank: 1 },
            role_level: { level_key: "role-1", label: "销售", source: "user_profile", rank: 1 },
            training_stage: "needs_remediation",
            modules: [
                {
                    module_key: "business_skills",
                    title: "商务技巧",
                    display_name: "商务技巧",
                    module_type: "article_exam",
                    kind: "quiz_attempt",
                    order_index: 1,
                    enabled: true,
                    status: "failed",
                    stage: "failed",
                    passed: false,
                    completion_rule: "passed",
                    unmet_reasons: [],
                    outcome_history: [],
                },
                {
                    module_key: "elevator_pitch",
                    title: "电梯演讲",
                    display_name: "电梯演讲",
                    module_type: "audio_scoring_group",
                    kind: "audio_submission",
                    order_index: 2,
                    enabled: true,
                    status: "failed",
                    stage: "failed",
                    passed: false,
                    completion_rule: "passed",
                    unmet_reasons: [],
                    outcome_history: [],
                },
            ],
            overall_progress: {
                total_modules: 5,
                completed_modules: 1,
                passed_modules: 0,
                failed_modules: 2,
                needs_remediation_modules: 1,
            },
            retraining_requests: [],
            diagnostics: [],
            generated_at: "2026-07-07T00:00:00Z",
        },
    ];
    return {
        items: overrides?.items ?? defaultItems,
        total: (overrides?.items ?? defaultItems).length,
        limit: 50,
        offset: 0,
    };
}

function renderPage(ui: ReactElement) {
    const queryClient = createAppQueryClient();
    return render(
        <QueryClientProvider client={queryClient}>
            {ui}
        </QueryClientProvider>,
    );
}

describe("TeamDashboardPage", () => {
    beforeEach(() => {
        listAdminJourneysMock.mockReset();
        getJourneyAnalyticsMock.mockReset();
        useCurrentUserMock.mockReset();
    });

    it("shows loading skeleton while data is being fetched", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        listAdminJourneysMock.mockReturnValue(new Promise(() => undefined));
        getJourneyAnalyticsMock.mockReturnValue(new Promise(() => undefined));

        renderPage(<TeamDashboardPage />);

        expect(screen.getByText("我的团队")).toBeTruthy();
        await waitFor(() => {
            expect(screen.getAllByTestId("skeleton").length).toBeGreaterThan(0);
        });
    });

    it("renders team summary cards and learner list for a training_manager", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText("总人数")).toBeTruthy();
        });

        expect(screen.getByText("3")).toBeTruthy();
        expect(screen.getByText("共 2 名学员")).toBeTruthy();
        expect(screen.getByText("张三")).toBeTruthy();
        expect(screen.getByText("卡关学员")).toBeTruthy();
        expect(screen.getAllByText("待辅导").length).toBeGreaterThan(0);
    });

    it("renders learner rows as links to detail pages", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText("张三")).toBeTruthy();
        });

        const detailLinks = screen.getAllByRole("link");
        const learnerDetailLinks = detailLinks.filter((link) => link.getAttribute("href")?.startsWith("/team/"));
        expect(learnerDetailLinks.length).toBe(2);
        expect(learnerDetailLinks.some((link) => link.getAttribute("href") === "/team/learner-1")).toBe(true);
        expect(learnerDetailLinks.some((link) => link.getAttribute("href") === "/team/learner-2")).toBe(true);
    });

    it("shows error state when both queries fail", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        listAdminJourneysMock.mockRejectedValue(new Error("journeys unavailable"));
        getJourneyAnalyticsMock.mockRejectedValue(new Error("analytics unavailable"));

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText("团队数据加载失败")).toBeTruthy();
        });

        expect(screen.getByText(/journeys unavailable|analytics unavailable/)).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
    });

    it("shows partial error banner when only journeys fails but analytics succeeds", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        listAdminJourneysMock.mockRejectedValue(new Error("journeys unavailable"));
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText(/部分数据加载失败/)).toBeTruthy();
        });
    });

    it("shows permission denied state when a learner visits the page", async () => {
        useCurrentUserMock.mockReturnValue({ data: learnerUser });
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText("该页面仅向销售组长/培训经理开放")).toBeTruthy();
        });

        expect(screen.queryByText("总人数")).toBeNull();
        expect(screen.queryByText("学员列表")).toBeNull();
    });

    it("shows empty department state when training_manager has no department", async () => {
        useCurrentUserMock.mockReturnValue({
            data: { ...trainingManagerUser, department: undefined },
        });
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText("您尚未分配部门")).toBeTruthy();
        });
    });

    it("shows no learners state when department has zero journeys", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload({ items: [] }));
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload({ learner_count: 0 }));

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText("本部门暂无学员")).toBeTruthy();
        });
    });

    it("refetches data when retry button is clicked after error", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        listAdminJourneysMock.mockRejectedValueOnce(new Error("first fail"));
        getJourneyAnalyticsMock.mockRejectedValueOnce(new Error("first fail"));

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText("团队数据加载失败")).toBeTruthy();
        });

        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        fireEvent.click(screen.getByRole("button", { name: "重试" }));

        await waitFor(() => {
            expect(screen.getByText("张三")).toBeTruthy();
        });
    });

    it("does not expose engineering fields like journey_id or module_key", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText("张三")).toBeTruthy();
        });

        expect(screen.queryByText("journey-1")).toBeNull();
        expect(screen.queryByText("journey-2")).toBeNull();
        expect(screen.queryByText("business_skills")).toBeNull();
        expect(screen.queryByText("elevator_pitch")).toBeNull();
        expect(screen.queryByText("rev-1")).toBeNull();
    });

    it("maps risk_reason engineering keys to Chinese learner-facing labels", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        listAdminJourneysMock.mockResolvedValue(buildJourneysPayload());
        getJourneyAnalyticsMock.mockResolvedValue(buildAnalyticsPayload());

        renderPage(<TeamDashboardPage />);

        await waitFor(() => {
            expect(screen.getByText("卡关学员")).toBeTruthy();
        });

        // 后端 risk_reason 工程字符串必须被映射成中文可读文案，
        // 而不是直接展示 business_skills:not_passed / elevator_pitch:status:failed。
        expect(screen.getByText(/商务技巧未通过/)).toBeTruthy();
        expect(screen.getByText(/电梯演讲状态异常/)).toBeTruthy();

        expect(screen.queryByText("business_skills:not_passed")).toBeNull();
        expect(screen.queryByText("elevator_pitch:status:failed")).toBeNull();
    });
});
