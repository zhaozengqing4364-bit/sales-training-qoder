import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "./page";
import packageJson from "../../../package.json";

const {
    getStatsMock,
    getRecommendationMock,
    getHistoryMock,
    useCurrentUserMock,
} = vi.hoisted(() => ({
    getStatsMock: vi.fn(),
    getRecommendationMock: vi.fn(),
    getHistoryMock: vi.fn(),
    useCurrentUserMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: vi.fn(),
    }),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button {...props}>{children}</button>
    ),
}));

vi.mock("@/components/dashboard-skeleton", () => ({
    DashboardSkeleton: () => <div>loading dashboard</div>,
}));

vi.mock("@/components/ui/swipeable-item", () => ({
    SwipeableItem: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/empty-state", () => ({
    EmptyState: ({ title, description, actionLabel }: { title: string; description: string; actionLabel?: string }) => (
        <div>
            <div>{title}</div>
            <div>{description}</div>
            {actionLabel ? <button>{actionLabel}</button> : null}
        </div>
    ),
}));

vi.mock("@/components/ui/glass-modal", () => ({
    Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTrigger: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogClose: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            dashboard: {
                ...actual.api.dashboard,
                getStats: getStatsMock,
                getRecommendation: getRecommendationMock,
                getHistory: getHistoryMock,
            },
        },
    };
});

vi.mock("@/hooks/use-current-user", () => ({
    useCurrentUser: useCurrentUserMock,
}));

async function flushDashboardData() {
    await act(async () => {
        await Promise.resolve();
        await Promise.resolve();
    });
}

describe("HomePage dashboard header", () => {
    beforeEach(() => {
        vi.useRealTimers();
        getStatsMock.mockReset();
        getRecommendationMock.mockReset();
        getHistoryMock.mockReset();
        useCurrentUserMock.mockReset();

        getStatsMock.mockResolvedValue({
            weekly_activity: { total_duration_minutes: 0, session_count: 0, trend_direction: "flat", trend_percentage: 0 },
            last_session: { score: 0, percentile: 0, trend: "stable" },
            score_basis: "session_evidence_projection_evaluable_only",
            evaluable_sessions: 2,
            not_evaluable_sessions: 1,
            effectiveness: {
                pass_rate_3min_flow: 0,
                pass_rate_5turn_defense: 0,
                pass_rate_4step_structure: 0,
                next_day_retry_rate: 0,
            },
        });
        getRecommendationMock.mockResolvedValue({
            title: "继续训练",
            reason: "保持节奏",
            action_label: "开始训练",
            target_path: "/training",
        });
        getHistoryMock.mockResolvedValue([]);
        useCurrentUserMock.mockReturnValue({ data: null });
    });

    it("shows the current user's display name with a time-based greeting and the package version badge", async () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-04-09T09:00:00+08:00"));
        useCurrentUserMock.mockReturnValue({
            data: {
                id: "user-1",
                user_id: "user-1",
                display_name: "王小明",
                name: "王小明",
                email: "alex@example.com",
                role: "user",
                is_active: true,
                created_at: "2026-04-01T00:00:00Z",
            },
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(getStatsMock).toHaveBeenCalled();
        expect(screen.getByRole("heading", { name: /早安, 王小明/i })).toBeTruthy();
        expect(screen.getByRole("button", { name: `v${packageJson.version}` })).toBeTruthy();
        expect(screen.getByText("均分仅统计 2 次可评估训练，1 次证据不足训练不会计入均分。")).toBeTruthy();
        expect(screen.queryByText("2026年1月10日")).toBeNull();
    });

    it("surfaces next-goal dashboard recommendations as a direct focused retry CTA", async () => {
        getRecommendationMock.mockResolvedValue({
            title: "按上次主问题再练一轮",
            reason: "先用案例、数据或ROI证据支撑主张，再推进下一步。 上次主问题：价值主张缺少案例。",
            action_label: "按目标再练一轮",
            target_path: "/agents/agent-1?persona_id=persona-1&focus_intent=%7B%7D",
            score_basis: "session_evidence_projection_evaluable_only",
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getAllByText("按上次主问题再练一轮").length).toBeGreaterThan(0);
        expect(screen.getAllByText("推荐来源：上次可评估训练报告的主问题与下一轮目标。").length).toBeGreaterThan(0);
        const retryLinks = screen.getAllByRole("link", { name: "按目标再练一轮" });
        expect(retryLinks.some((link) => link.getAttribute("href") === "/agents/agent-1?persona_id=persona-1&focus_intent=%7B%7D")).toBe(true);
    });

    it("surfaces PPT page-level recommendations as a concrete review task", async () => {
        getRecommendationMock.mockResolvedValue({
            title: "补练 PPT 第 5 页",
            reason: "第 5 页有必讲点未覆盖：补充客户案例",
            action_label: "查看逐页复练任务",
            target_path: "/practice/session-ppt-1/report?focus=presentation_page&page=5",
            recommendation_kind: "presentation_page_retry",
            scenario_type: "presentation",
            source_session_id: "session-ppt-1",
            focus_page: 5,
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getAllByText("补练 PPT 第 5 页").length).toBeGreaterThan(0);
        expect(screen.getAllByText("第 5 页有必讲点未覆盖：补充客户案例").length).toBeGreaterThan(0);
        expect(screen.getAllByText("推荐来源：上次 PPT 报告的第 5 页缺口与必讲点覆盖。").length).toBeGreaterThan(0);
        const taskLinks = screen.getAllByRole("link", { name: "查看逐页复练任务" });
        expect(taskLinks.some((link) => link.getAttribute("href") === "/practice/session-ppt-1/report?focus=presentation_page&page=5")).toBe(true);
    });

    it("falls back to the email prefix and switches to an evening greeting when no name is present", async () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-04-09T20:00:00+08:00"));
        useCurrentUserMock.mockReturnValue({
            data: {
                id: "user-2",
                user_id: "user-2",
                display_name: "",
                name: "",
                email: "fallback.user@example.com",
                role: "user",
                is_active: true,
                created_at: "2026-04-01T00:00:00Z",
            },
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(getRecommendationMock).toHaveBeenCalled();
        expect(screen.getByRole("heading", { name: /晚安, fallback.user/i })).toBeTruthy();
    });

    it("shows a first-screen onboarding card that links learners into the real training and history flow", async () => {
        getRecommendationMock.mockResolvedValue({
            title: "从异议处理开始",
            reason: "先完成一轮真实训练，再去历史页和统一报告复盘。",
            action_label: "开始异议处理训练",
            target_path: "/training/sales",
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("第一次来，先这样开始")).toBeTruthy();
        expect(screen.getAllByText("先完成一轮真实训练，再去历史页和统一报告复盘。").length).toBeGreaterThan(0);
        const trainingLinks = screen.getAllByRole("link", { name: "开始异议处理训练" });
        expect(trainingLinks.some((link) => link.getAttribute("href") === "/training/sales")).toBe(true);
        expect(screen.getByRole("link", { name: "去历史页" }).getAttribute("href")).toBe("/history");
        expect(screen.getByRole("link", { name: "报告入口" }).getAttribute("href")).toBe("/history");
    });

    it("prefers the latest report shortcut in onboarding so returning learners stay on the real train-history-report loop", async () => {
        getRecommendationMock.mockResolvedValue({
            title: "继续产品介绍训练",
            reason: "先完成今天的重点训练，再复盘最近一次报告。",
            action_label: "继续训练",
            target_path: "/training/sales",
        });
        getHistoryMock.mockResolvedValue([
            {
                id: "older-session",
                session_id: "older-session",
                title: "较早的销售复盘",
                scenario_type: "sales",
                overall_score: 80,
                duration_seconds: 180,
                start_time: "2026-04-08T00:00:00Z",
                status: "completed",
                feedback_summary: "先补客户案例。",
            },
            {
                id: "latest-session",
                session_id: "latest-session",
                title: "最新销售复盘",
                scenario_type: "sales",
                overall_score: 91,
                duration_seconds: 240,
                start_time: "2026-04-09T00:00:00Z",
                status: "completed",
                feedback_summary: "继续保持节奏。",
            },
        ]);

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("继续按这 3 步推进训练")).toBeTruthy();
        const trainingLinks = screen.getAllByRole("link", { name: "继续训练" });
        expect(trainingLinks.some((link) => link.getAttribute("href") === "/training/sales")).toBe(true);
        expect(screen.getByRole("link", { name: "去历史页" }).getAttribute("href")).toBe("/history");
        expect(screen.getByRole("link", { name: "报告入口" }).getAttribute("href")).toBe("/practice/latest-session/report");
        expect(screen.getByText("最近一次可用报告：最新销售复盘")).toBeTruthy();
    });

    it("truthifies the version dialog into a live entry summary instead of static release-note claims", async () => {
        getRecommendationMock.mockResolvedValue({
            title: "继续产品介绍训练",
            reason: "今天优先补齐开场后的客户价值表达。",
            action_label: "继续训练",
            target_path: "/training",
        });
        getHistoryMock.mockResolvedValue([
            {
                id: "sales-session-1",
                session_id: "sales-session-1",
                title: "销售复盘",
                scenario_type: "sales",
                overall_score: 88,
                duration_seconds: 180,
                start_time: "2026-04-09T00:00:00Z",
                status: "completed",
                feedback_summary: "继续补强成交证据。",
            },
        ]);

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("当前版本可用入口")).toBeTruthy();
        expect(screen.getAllByText("继续产品介绍训练").length).toBeGreaterThan(0);
        expect(screen.getByText("首页当前已加载 1 条最近记录，可直接去历史页或统一报告继续复盘。")).toBeTruthy();
        expect(screen.queryByText("PPT 长时演讲稳定性优化")).toBeNull();
        expect(screen.queryByText("演讲策略配置简化")).toBeNull();
        expect(screen.queryByText("性能优化")).toBeNull();
    });

    it("keeps report export, goal setting, and share-analysis affordances absent from dashboard home", async () => {
        render(<HomePage />);
        await flushDashboardData();

        expect(screen.queryByRole("button", { name: "导出报告" })).toBeNull();
        expect(screen.queryByRole("link", { name: "导出报告" })).toBeNull();
        expect(screen.queryByRole("button", { name: "设定目标" })).toBeNull();
        expect(screen.queryByRole("link", { name: "设定目标" })).toBeNull();
        expect(screen.queryByRole("button", { name: "分享分析" })).toBeNull();
        expect(screen.queryByRole("link", { name: "分享分析" })).toBeNull();
    });

    it("replaces fake filter and detail affordances with real history/report links", async () => {
        getHistoryMock.mockResolvedValue([
            {
                id: "sales-session-1",
                session_id: "sales-session-1",
                title: "销售复盘",
                scenario_type: "sales",
                overall_score: 88,
                duration_seconds: 180,
                start_time: "2026-04-09T00:00:00Z",
                status: "completed",
                feedback_summary: "继续补强成交证据。",
            },
            {
                id: "ppt-session-2",
                session_id: "ppt-session-2",
                title: "PPT 演讲复盘",
                scenario_type: "presentation",
                overall_score: 92,
                duration_seconds: 360,
                start_time: "2026-04-08T00:00:00Z",
                status: "completed",
                feedback_summary: "封面后需要更快进入客户价值。",
            },
        ]);

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("高级筛选请在历史页进行")).toBeTruthy();
        expect(screen.getByRole("link", { name: "去历史页筛选" }).getAttribute("href")).toBe("/history");
        expect(screen.queryByText("应用筛选")).toBeNull();
        expect(screen.queryByRole("button", { name: "查看详情" })).toBeNull();

        const reportLinks = screen.getAllByRole("link", { name: "查看报告" });
        expect(reportLinks.map((link) => link.getAttribute("href"))).toEqual([
            "/practice/sales-session-1/report",
            "/practice/ppt-session-2/report",
        ]);
        expect(screen.getAllByRole("link", { name: "查看历史" }).every((link) => link.getAttribute("href") === "/history")).toBe(true);
        expect(screen.getAllByRole("link", { name: "历史页" }).every((link) => link.getAttribute("href") === "/history")).toBe(true);
    });

    it("keeps malformed or incomplete sessions on explicit disabled report states with learner-safe copy", async () => {
        getHistoryMock.mockResolvedValue([
            {
                id: "session-0",
                title: "坏数据记录",
                scenario_type: "sales",
                overall_score: 0,
                duration_seconds: 10,
                start_time: "2026-04-09T00:00:00Z",
                status: "completed",
            },
            {
                id: "in-progress-session",
                session_id: "in-progress-session",
                title: "进行中练习",
                scenario_type: "sales",
                overall_score: 42,
                duration_seconds: 75,
                start_time: "2026-04-09T01:00:00Z",
                status: "in_progress",
            },
        ]);

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("缺少会话编号，请到历史页核对这条记录。")).toBeTruthy();
        expect(screen.getByText("会话完成并生成统一训练证据后即可查看报告。")).toBeTruthy();
        expect((screen.getByRole("button", { name: "报告暂不可用" }) as HTMLButtonElement).disabled).toBe(true);
        expect((screen.getByRole("button", { name: "报告生成中" }) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.queryByRole("link", { name: "报告暂不可用" })).toBeNull();
    });

    it("falls back to history and training actions when dashboard history fails", async () => {
        getHistoryMock
            .mockRejectedValueOnce(new Error("history unavailable"))
            .mockResolvedValueOnce([
                {
                    id: "recovered-session",
                    session_id: "recovered-session",
                    title: "恢复后的销售复盘",
                    scenario_type: "sales",
                    overall_score: 86,
                    duration_seconds: 180,
                    start_time: "2026-04-09T00:00:00Z",
                    status: "completed",
                    feedback_summary: "继续补强成交证据。",
                },
            ]);

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("最近记录暂不可用")).toBeTruthy();
        expect(screen.getByText("最近记录暂不可用，页面已保留可用入口；请稍后重试或前往对应页面查看。")).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试首页数据" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "去历史页筛选" }).getAttribute("href")).toBe("/history");
        expect(screen.getAllByRole("button", { name: "去历史页重试" }).length).toBeGreaterThan(0);
        expect(screen.queryByRole("link", { name: "查看报告" })).toBeNull();
        expect(screen.queryByRole("button", { name: "查看详情" })).toBeNull();
        expect(screen.queryByText("应用筛选")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "重试首页数据" }));
        await flushDashboardData();

        expect(screen.getByText("恢复后的销售复盘")).toBeTruthy();
        expect(screen.queryByText("最近记录暂不可用")).toBeNull();
    });

    it("marks the dashboard as degraded instead of showing fake normal defaults when all home APIs fail", async () => {
        getStatsMock.mockRejectedValueOnce(new Error("stats unavailable"));
        getRecommendationMock.mockRejectedValueOnce(new Error("recommendation unavailable"));
        getHistoryMock.mockRejectedValueOnce(new Error("history unavailable"));

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("训练统计、推荐入口、最近记录暂不可用，页面已保留可用入口；请稍后重试或前往对应页面查看。")).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试首页数据" })).toBeTruthy();
        expect(screen.getByText("最近记录暂不可用")).toBeTruthy();
    });

    it("keeps the shared learner help guidance visible on dashboard home", async () => {
        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("需要帮助或反馈？")).toBeTruthy();
        expect(screen.getByText(/统一入口在侧边栏底部的“帮助与反馈”里；手机端先打开左上角菜单。/)).toBeTruthy();
        expect(screen.getByText(/页面异常、入口缺失或结果不对时，请通过这个统一入口反馈当前页面路径或会话编号。/)).toBeTruthy();
        expect(screen.getByText(/当前 learner 默认只看到训练、历史、个人中心；运行状态和管理后台只对管理员或支持角色开放。/)).toBeTruthy();
        expect(screen.queryByText(/7 x 24/)).toBeNull();
    });
});
