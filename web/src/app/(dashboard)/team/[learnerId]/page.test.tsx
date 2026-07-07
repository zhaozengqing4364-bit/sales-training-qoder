import { QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import TeamLearnerDetailPage from "./page";
import { createAppQueryClient } from "@/lib/query/client";

const {
    getAdminJourneyMock,
    useCurrentUserMock,
} = vi.hoisted(() => ({
    getAdminJourneyMock: vi.fn(),
    useCurrentUserMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ learnerId: "learner-1" }),
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
                    getAdminJourney: getAdminJourneyMock,
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

function buildJourneyPayload(overrides?: {
    learner_name?: string;
    department?: string;
    training_stage?: string;
    modules?: unknown[];
    overall_progress?: Record<string, number>;
}) {
    return {
        journey_id: "journey-1",
        learner_id: "learner-1",
        learner_name: overrides?.learner_name ?? "张三",
        department: overrides?.department ?? "销售部",
        path_key: "newcomer_training_path_v1",
        path_revision_id: "rev-1",
        path_revision_no: 1,
        source: "active_revision",
        legacy_snapshot_only: false,
        role_capabilities: [],
        learner_level: { level_key: "level-1", label: "初级", source: "user_profile", rank: 1 },
        role_level: { level_key: "role-1", label: "销售", source: "user_profile", rank: 1 },
        training_stage: overrides?.training_stage ?? "in_progress",
        modules: overrides?.modules ?? [
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
                score: 90,
                max_score: 100,
                completion_rule: "passed",
                unmet_reasons: [],
                outcome_history: [],
                next_action: { action_key: "review", label: "查看详情", disabled: false },
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
                score: 40,
                max_score: 100,
                completion_rule: "passed",
                unmet_reasons: [],
                outcome_history: [],
                next_action: { action_key: "retry", label: "重新提交", disabled: false },
            },
        ],
        overall_progress: overrides?.overall_progress ?? {
            total_modules: 5,
            completed_modules: 2,
            passed_modules: 1,
            failed_modules: 1,
            needs_remediation_modules: 0,
        },
        retraining_requests: [],
        diagnostics: [],
        generated_at: "2026-07-07T00:00:00Z",
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

describe("TeamLearnerDetailPage", () => {
    beforeEach(() => {
        getAdminJourneyMock.mockReset();
        useCurrentUserMock.mockReset();
    });

    it("shows loading skeleton while data is being fetched", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockReturnValue(new Promise(() => undefined));

        renderPage(<TeamLearnerDetailPage />);

        expect(screen.getByText("返回团队")).toBeTruthy();
        await waitFor(() => {
            expect(screen.getAllByTestId("skeleton").length).toBeGreaterThan(0);
        });
    });

    it("renders learner basic info and module list for a training_manager", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("张三")).toBeTruthy();
        });

        expect(screen.getByText(/销售部/)).toBeTruthy();
        expect(screen.getAllByText(/训练中/).length).toBeGreaterThan(0);
        expect(screen.getByText("商务技巧")).toBeTruthy();
        expect(screen.getByText("电梯演讲")).toBeTruthy();
        expect(screen.getByText("整体进度")).toBeTruthy();
        expect(screen.getByText("模块进度")).toBeTruthy();
        expect(screen.getAllByText("已通过").length).toBeGreaterThan(0);
        expect(screen.getAllByText("未通过").length).toBeGreaterThan(0);
    });

    it("renders score for each module", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("90 / 100")).toBeTruthy();
        });
        expect(screen.getByText("40 / 100")).toBeTruthy();
    });

    it("shows risk badge and risk reason banner for modules with risk", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("电梯演讲")).toBeTruthy();
        });

        expect(screen.getAllByText("需关注").length).toBeGreaterThan(0);
        expect(screen.getByText("待辅导标记")).toBeTruthy();
        expect(screen.getByText(/电梯演讲未通过/)).toBeTruthy();
    });

    it("renders back-to-team link pointing to /team", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("张三")).toBeTruthy();
        });

        const backLink = screen.getByRole("link", { name: /返回团队/ });
        expect(backLink.getAttribute("href")).toBe("/team");
    });

    it("shows not found state when backend returns TRAINING_RECORD_NOT_FOUND", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockRejectedValue(new Error("[TRAINING_RECORD_NOT_FOUND] 学员训练记录不存在。"));

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("学员记录不存在或无权查看")).toBeTruthy();
        });

        expect(screen.queryByText("张三")).toBeNull();
        expect(screen.queryByText("模块进度")).toBeNull();
    });

    it("shows error state with retry for generic network errors", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockRejectedValue(new Error("网络连接超时"));

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("学员数据加载失败")).toBeTruthy();
        });

        expect(screen.getByText(/网络连接超时/)).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
    });

    it("refetches data when retry button is clicked after error", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockRejectedValueOnce(new Error("first fail"));

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("学员数据加载失败")).toBeTruthy();
        });

        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        fireEvent.click(screen.getByRole("button", { name: "重试" }));

        await waitFor(() => {
            expect(screen.getByText("张三")).toBeTruthy();
        });
    });

    it("shows permission denied state when a learner visits the page", async () => {
        useCurrentUserMock.mockReturnValue({ data: learnerUser });
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("该页面仅向销售组长/培训经理开放")).toBeTruthy();
        });

        expect(screen.queryByText("张三")).toBeNull();
        expect(screen.queryByText("模块进度")).toBeNull();
    });

    it("shows empty module list state when journey has no modules", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload({ modules: [] }));

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("暂无模块记录")).toBeTruthy();
        });
    });

    it("does not expose engineering fields like journey_id or module_key", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("张三")).toBeTruthy();
        });

        expect(screen.queryByText("journey-1")).toBeNull();
        expect(screen.queryByText("business_skills")).toBeNull();
        expect(screen.queryByText("elevator_pitch")).toBeNull();
        expect(screen.queryByText("rev-1")).toBeNull();
        expect(screen.queryByText("newcomer_training_path_v1")).toBeNull();
        expect(screen.queryByText("active_revision")).toBeNull();
    });

    it("maps risk reasons to Chinese learner-facing labels, not engineering keys", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockResolvedValue(buildJourneyPayload());

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("待辅导标记")).toBeTruthy();
        });

        expect(screen.getByText(/电梯演讲未通过/)).toBeTruthy();
        expect(screen.queryByText("elevator_pitch:not_passed")).toBeNull();
        expect(screen.queryByText("business_skills:not_passed")).toBeNull();
    });

    it("does not show risk banner when learner has no risk modules", async () => {
        useCurrentUserMock.mockReturnValue({ data: trainingManagerUser });
        getAdminJourneyMock.mockResolvedValue(
            buildJourneyPayload({
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
                        score: 95,
                        max_score: 100,
                        completion_rule: "passed",
                        unmet_reasons: [],
                        outcome_history: [],
                        next_action: { action_key: "done", label: "已完成", disabled: false },
                    },
                ],
                overall_progress: {
                    total_modules: 5,
                    completed_modules: 1,
                    passed_modules: 1,
                    failed_modules: 0,
                    needs_remediation_modules: 0,
                },
            }),
        );

        renderPage(<TeamLearnerDetailPage />);

        await waitFor(() => {
            expect(screen.getByText("商务技巧")).toBeTruthy();
        });

        expect(screen.queryByText("待辅导标记")).toBeNull();
        expect(screen.queryByText("需关注")).toBeNull();
    });
});
