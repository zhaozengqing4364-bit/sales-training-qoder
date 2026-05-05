import { act, fireEvent, render, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "./page";
import packageJson from "../../../package.json";

const {
    getStatsMock,
    getRecommendationMock,
    getGrowthMock,
    getHistoryMock,
    getOpenInterventionMock,
    getMyHistoryMock,
    useCurrentUserMock,
} = vi.hoisted(() => ({
    getStatsMock: vi.fn(),
    getRecommendationMock: vi.fn(),
    getGrowthMock: vi.fn(),
    getHistoryMock: vi.fn(),
    getOpenInterventionMock: vi.fn(),
    getMyHistoryMock: vi.fn(),
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
    usePathname: () => "/",
    useParams: () => ({}),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) => {
        if (asChild) {
            return <>{children}</>;
        }
        return <button {...props}>{children}</button>;
    },
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
                getGrowth: getGrowthMock,
                getHistory: getHistoryMock,
            },
            user: {
                ...actual.api.user,
                getOpenIntervention: getOpenInterventionMock,
                getMyHistory: getMyHistoryMock,
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
        getGrowthMock.mockReset();
        getHistoryMock.mockReset();
        getOpenInterventionMock.mockReset();
        getMyHistoryMock.mockReset();
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
        getGrowthMock.mockResolvedValue({
            achievements: { unlocked: [] },
            notifications: { items: [], unread_count: 0 },
            goal: null,
        });
        getOpenInterventionMock.mockResolvedValue(null);
        getMyHistoryMock.mockResolvedValue({ sessions: [], total: 0, page: 1, page_size: 50, total_pages: 0 });
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
            recommendation_kind: "sales_retry",
            due_reason: "上次训练已生成可复练主问题",
            focus: "价值主张缺少案例",
            suggested_duration_minutes: 12,
            is_due_today: true,
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("今日复练任务")).toBeTruthy();
        expect(screen.getAllByText("按上次主问题再练一轮").length).toBeGreaterThan(0);
        expect(screen.getByText("• 到期原因：上次训练已生成可复练主问题")).toBeTruthy();
        expect(screen.getByText("• 本次焦点：价值主张缺少案例")).toBeTruthy();
        expect(screen.getByText("• 建议时长：12 分钟")).toBeTruthy();
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

    it("downgrades unsafe dashboard recommendation targets to the training route", async () => {
        getRecommendationMock.mockResolvedValue({
            title: "继续训练",
            reason: "后端推荐返回了不安全目标时，首页仍只能打开站内训练入口。",
            action_label: "打开推荐",
            target_path: "https://evil.example/phish",
        });

        render(<HomePage />);
        await flushDashboardData();

        const recommendationLinks = screen.getAllByRole("link", { name: "打开推荐" });
        expect(recommendationLinks.some((link) => link.getAttribute("href") === "/training")).toBe(true);
    });

    it("omits dashboard guidance, help, and growth operation cards", async () => {
        getGrowthMock.mockResolvedValue({
            achievements: {
                unlocked: [
                    {
                        achievement_id: "achievement-1",
                        code: "first_evaluable_session",
                        name: "首次有效训练",
                        description: "完成第一场可评估训练。",
                        icon_key: "trophy",
                        unlocked_at: "2026-04-21T06:00:00Z",
                    },
                ],
            },
            notifications: {
                unread_count: 1,
                items: [
                    {
                        notification_id: "notification-1",
                        type: "ai_coach",
                        title: "AI 教练建议：先练产品知识与证据",
                        content: "最近一次可评估训练中，产品知识与证据为 52 分。",
                        action_label: "按建议训练",
                        action_path: "/practice/session-1/report",
                        is_read: false,
                    },
                ],
            },
            goal: {
                goal_id: "goal-1",
                goal_type: "weekly_sessions",
                period: "weekly",
                target_count: 3,
                current_progress: 2,
                progress_ratio: 2 / 3,
                start_date: "2026-04-20",
                end_date: "2026-04-26",
                is_active: true,
            },
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.queryByText("最小上手指引")).toBeNull();
        expect(screen.queryByText("第一次来，先这样开始")).toBeNull();
        expect(screen.queryByText("继续按这 3 步推进训练")).toBeNull();
        expect(screen.queryByText("需要帮助或反馈？")).toBeNull();
        expect(screen.queryByText("徽章墙")).toBeNull();
        expect(screen.queryByText("首次有效训练")).toBeNull();
        expect(screen.queryByText("练习目标")).toBeNull();
        expect(screen.queryByText("自适应难度 dry-run")).toBeNull();
        expect(screen.queryByText("通知与 AI 教练")).toBeNull();
        expect(screen.queryByText("AI 教练建议：先练产品知识与证据")).toBeNull();
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

    it("keeps the main recommendation CTA without showing first-screen onboarding cards", async () => {
        getRecommendationMock.mockResolvedValue({
            title: "从异议处理开始",
            reason: "先完成一轮真实训练，再去历史页和统一报告复盘。",
            action_label: "开始异议处理训练",
            target_path: "/training/sales",
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.queryByText("第一次来，先这样开始")).toBeNull();
        expect(screen.queryByText("最小上手指引")).toBeNull();
        expect(screen.getAllByText("先完成一轮真实训练，再去历史页和统一报告复盘。").length).toBeGreaterThan(0);
        const trainingLinks = screen.getAllByRole("link", { name: "开始异议处理训练" });
        expect(trainingLinks.some((link) => link.getAttribute("href") === "/training/sales")).toBe(true);
        expect(screen.queryByRole("link", { name: "去历史页" })).toBeNull();
        expect(screen.queryByRole("link", { name: "报告入口" })).toBeNull();
    });

    it("keeps latest report shortcuts in recent records without restoring onboarding", async () => {
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

        expect(screen.queryByText("继续按这 3 步推进训练")).toBeNull();
        const trainingLinks = screen.getAllByRole("link", { name: "继续训练" });
        expect(trainingLinks.some((link) => link.getAttribute("href") === "/training/sales")).toBe(true);
        expect(screen.getAllByRole("link", { name: "历史页" }).every((link) => link.getAttribute("href") === "/history")).toBe(true);
        expect(screen.getAllByRole("link", { name: "查看报告" }).some((link) => (
            link.getAttribute("href") === "/practice/latest-session/report"
        ))).toBe(true);
        expect(screen.queryByText("最近一次可用报告：最新销售复盘")).toBeNull();
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
                report_status: "processing",
            },
            {
                id: "late-report-session",
                session_id: "late-report-session",
                title: "已生成报告记录",
                scenario_type: "sales",
                overall_score: 66,
                duration_seconds: 120,
                start_time: "2026-04-09T02:00:00Z",
                status: "in_progress",
                report_status: "completed",
                report_generated_at: "2026-04-09T02:05:00Z",
            },
        ]);

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("缺少会话编号，请到历史页核对这条记录。")).toBeTruthy();
        expect(screen.getByText("会话完成并生成统一训练证据后即可查看报告。")).toBeTruthy();
        expect((screen.getByRole("button", { name: "报告暂不可用" }) as HTMLButtonElement).disabled).toBe(true);
        expect((screen.getByRole("button", { name: "报告生成中" }) as HTMLButtonElement).disabled).toBe(true);
        expect(screen.queryByRole("link", { name: "报告暂不可用" })).toBeNull();
        expect(screen.getByRole("link", { name: "查看报告" }).getAttribute("href")).toBe("/practice/late-report-session/report");
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

    it("shows a stats module failure instead of fake zero metrics when dashboard stats fail", async () => {
        getStatsMock.mockRejectedValueOnce(new Error("stats unavailable"));

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("训练统计暂不可用，页面已保留可用入口；请稍后重试或前往对应页面查看。")).toBeTruthy();
        expect(screen.getByText("统计暂不可用")).toBeTruthy();
        expect(screen.getByText("训练统计模块失败时不展示 0 小时、0 场或 0% 复练率，避免把接口失败误读成真实空数据。")).toBeTruthy();
        expect(screen.getByText("训练统计接口失败时不展示默认 0 分，避免误导为真实成绩。")).toBeTruthy();
        expect(screen.queryByText("均分仅统计 0 次可评估训练，0 次证据不足训练不会计入均分。")).toBeNull();
        expect(screen.queryByText("0.0%")).toBeNull();
    });

    it("shows recommendation failure as an unavailable module instead of a fake start-training recommendation", async () => {
        getRecommendationMock.mockRejectedValueOnce(new Error("recommendation unavailable"));

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getAllByText("今日复练任务暂不可用").length).toBeGreaterThan(0);
        expect(screen.getAllByText("推荐接口暂时无法读取，不代表今天没有复练任务；可先进入训练大厅或稍后重试。").length).toBeGreaterThan(0);
        expect(screen.getByText("推荐状态：接口读取失败，未用默认训练入口伪装成真实推荐。")).toBeTruthy();
        expect(screen.queryByText("欢迎使用训练系统，开始一次练习来提升您的技能吧！")).toBeNull();
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

    it("removes the dashboard inline help card while keeping mobile quick actions", async () => {
        render(<HomePage />);
        await flushDashboardData();

        expect(screen.queryByText("需要帮助或反馈？")).toBeNull();
        expect(screen.queryByText(/统一入口在侧边栏底部的“帮助与反馈”里；手机端先打开左上角菜单。/)).toBeNull();
        expect(screen.queryByText(/页面异常、入口缺失或结果不对时/)).toBeNull();
        const mobileQuickActions = screen.getByRole("navigation", { name: "移动快捷入口" });
        expect(mobileQuickActions).toBeTruthy();
        expect(within(mobileQuickActions).getByRole("link", { name: /继续训练/ }).getAttribute("href")).toBe("/training");
        expect(within(mobileQuickActions).getByRole("link", { name: /历史/ }).getAttribute("href")).toBe("/history");
        expect(screen.queryByText(/7 x 24/)).toBeNull();
    });

    it("shows the learner's open manager intervention without exposing admin-only fields", async () => {
        getOpenInterventionMock.mockResolvedValue({
            intervention_id: "intervention-1",
            issue_family: "evidence_gap",
            note: "本周先补一条客户案例，再推进下一步。",
            due_state: "due",
            reminder_status: "sent",
            reminder_sent_at: "2026-04-19T08:00:00Z",
            created_at: "2026-04-19T08:00:00Z",
            updated_at: "2026-04-19T08:00:00Z",
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("主管给你的本周重点")).toBeTruthy();
        expect(screen.getByText("evidence / gap")).toBeTruthy();
        expect(screen.getByText("本周先补一条客户案例，再推进下一步。")).toBeTruthy();
        expect(screen.getByText(/创建于/)).toBeTruthy();
        expect(screen.getByRole("link", { name: "去训练" }).getAttribute("href")).toBe("/training");
        expect(screen.queryByText("manager_user_id")).toBeNull();
    });

    it("hides manager intervention card when none is open or when the reminder endpoint fails", async () => {
        getOpenInterventionMock.mockResolvedValueOnce(null);

        const { unmount } = render(<HomePage />);
        await flushDashboardData();

        expect(screen.queryByText("主管给你的本周重点")).toBeNull();
        unmount();

        getOpenInterventionMock.mockRejectedValueOnce(new Error("manager reminder unavailable"));
        render(<HomePage />);
        await flushDashboardData();

        expect(screen.queryByText("主管给你的本周重点")).toBeNull();
        expect(screen.queryByText("第一次来，先这样开始")).toBeNull();
        expect(screen.getAllByText("继续训练").length).toBeGreaterThan(0);
    });

    it("shows streak and weekly goal using only completed evaluable practice", async () => {
        vi.useFakeTimers();
        vi.setSystemTime(new Date("2026-04-20T10:00:00+08:00"));
        getMyHistoryMock.mockResolvedValueOnce({
            sessions: [
                {
                    session_id: "eligible-today",
                    scenario_name: "销售对练",
                    scenario_type: "sales",
                    persona_name: null,
                    agent_name: "销售教练",
                    start_time: "2026-04-20T01:00:00.000Z",
                    duration_seconds: 300,
                    overall_score: 88,
                    report_status: "completed",
                    report_generated_at: "2026-04-20T01:10:00.000Z",
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    stage_summary: [],
                },
                {
                    session_id: "eligible-today-second",
                    scenario_name: "演讲训练",
                    scenario_type: "presentation",
                    persona_name: null,
                    agent_name: "演讲教练",
                    start_time: "2026-04-20T03:00:00.000Z",
                    duration_seconds: 420,
                    overall_score: 86,
                    report_status: "completed",
                    report_generated_at: "2026-04-20T03:10:00.000Z",
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    stage_summary: [],
                },
                {
                    session_id: "eligible-yesterday",
                    scenario_name: "销售对练",
                    scenario_type: "sales",
                    persona_name: null,
                    agent_name: "销售教练",
                    start_time: "2026-04-19T01:00:00.000Z",
                    duration_seconds: 300,
                    overall_score: 82,
                    report_status: "completed",
                    report_generated_at: "2026-04-19T01:10:00.000Z",
                    status: "completed",
                    evaluable: true,
                    not_evaluable_reason: null,
                    stage_summary: [],
                },
                {
                    session_id: "not-evaluable",
                    scenario_name: "销售对练",
                    scenario_type: "sales",
                    persona_name: null,
                    agent_name: "销售教练",
                    start_time: "2026-04-18T01:00:00.000Z",
                    duration_seconds: 300,
                    overall_score: 0,
                    report_status: "completed",
                    report_generated_at: "2026-04-18T01:10:00.000Z",
                    status: "completed",
                    evaluable: false,
                    not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
                    stage_summary: [],
                },
                {
                    session_id: "unfinished",
                    scenario_name: "销售对练",
                    scenario_type: "sales",
                    persona_name: null,
                    agent_name: "销售教练",
                    start_time: "2026-04-17T01:00:00.000Z",
                    duration_seconds: 300,
                    overall_score: 90,
                    report_status: "completed",
                    report_generated_at: "2026-04-17T01:10:00.000Z",
                    status: "in_progress",
                    evaluable: true,
                    not_evaluable_reason: null,
                    stage_summary: [],
                },
            ],
            total: 5,
            page: 1,
            page_size: 50,
            total_pages: 1,
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.getByText("连续练习")).toBeTruthy();
        expect(screen.getByText("2 天")).toBeTruthy();
        expect(screen.getByText("本周目标")).toBeTruthy();
        expect(screen.getByText("2/3")).toBeTruthy();
        expect(screen.getByText("完成 3 次可评估训练点亮本周轻成就")).toBeTruthy();
        expect(screen.getByText("本周目标进度只纳入 completed/evaluable 训练，避免把未完成或证据不足记录包装成成就。")).toBeTruthy();
    });


    it("renders the main training CTA while stats and history are still loading", async () => {
        getStatsMock.mockReturnValueOnce(new Promise(() => undefined));
        getHistoryMock.mockReturnValueOnce(new Promise(() => undefined));
        getMyHistoryMock.mockReturnValueOnce(new Promise(() => undefined));
        getRecommendationMock.mockResolvedValueOnce({
            title: "继续价值表达训练",
            reason: "先把主训练入口展示出来，统计和历史稍后更新。",
            action_label: "继续训练",
            target_path: "/training/sales",
        });

        render(<HomePage />);
        await flushDashboardData();

        expect(screen.queryByText("loading dashboard")).toBeNull();
        expect(screen.getAllByText("继续价值表达训练").length).toBeGreaterThan(0);
        expect(screen.getAllByRole("link", { name: /继续训练/ }).some((link) => link.getAttribute("href") === "/training/sales")).toBe(true);
        expect(screen.getByText("统计加载中")).toBeTruthy();
        expect(screen.getByText("最近记录加载中")).toBeTruthy();
        expect(screen.getByText("最近记录仍在加载；你可以先使用训练入口继续练习。")).toBeTruthy();
    });

});
