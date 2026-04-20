import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LeaderboardPage from "./page";

const { getPublicLeaderboardMock, getMyRankMock } = vi.hoisted(() => ({
    getPublicLeaderboardMock: vi.fn(),
    getMyRankMock: vi.fn(),
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children, className }: { children: ReactNode; className?: string }) => (
        <span className={className}>{children}</span>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

vi.mock("next/link", () => ({
    default: ({ href, children, className }: { href: string; children: ReactNode; className?: string }) => (
        <a href={href} className={className}>{children}</a>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            dashboard: {
                ...actual.api.dashboard,
                getPublicLeaderboard: getPublicLeaderboardMock,
                getMyRank: getMyRankMock,
            },
        },
    };
});

function createLeaderboardEntry(overrides: Partial<{
    rank: number;
    user_id: string;
    username: string;
    total_sessions: number;
    average_score: number;
    best_score: number;
    improvement_score: number;
    first_score: number;
    latest_score: number;
    sample_size: number;
    issue_type: string | null;
}> = {}) {
    return {
        rank: 1,
        user_id: "user-1",
        username: "张三",
        total_sessions: 6,
        average_score: 88.2,
        best_score: 93,
        ...overrides,
    };
}

describe("LeaderboardPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getPublicLeaderboardMock.mockReset();
        getMyRankMock.mockReset();
        getPublicLeaderboardMock.mockResolvedValue({
            time_period: "weekly",
            score_basis: "session_evidence_projection_evaluable_only",
            evaluable_sessions: 14,
            not_evaluable_sessions: 3,
            total_users: 4,
            entries: [
                createLeaderboardEntry(),
                createLeaderboardEntry({
                    rank: 2,
                    user_id: "user-2",
                    username: "李四",
                    total_sessions: 5,
                    average_score: 84.4,
                    best_score: 90,
                }),
                createLeaderboardEntry({
                    rank: 3,
                    user_id: "user-3",
                    username: "王五",
                    total_sessions: 4,
                    average_score: 82.1,
                    best_score: 87,
                }),
                createLeaderboardEntry({
                    rank: 4,
                    user_id: "user-4",
                    username: "赵六",
                    total_sessions: 3,
                    average_score: 80.6,
                    best_score: 85,
                }),
            ],
            my_rank: {
                user_id: "me",
                rank: 5,
                total_sessions: 2,
                average_score: 79.5,
                score_basis: "session_evidence_projection_evaluable_only",
                evaluable_sessions: 2,
                not_evaluable_sessions: 0,
            },
        });
        getMyRankMock.mockResolvedValue({
            user_id: "me",
            rank: 9,
            total_sessions: 1,
            average_score: 75.4,
        });
    });

    it("renders learner-safe evaluable-session copy for a populated leaderboard", async () => {
        render(<LeaderboardPage />);

        await waitFor(() => {
            expect(getPublicLeaderboardMock).toHaveBeenCalledWith({
                scenario_type: undefined,
                time_period: "weekly",
                leaderboard_mode: "score",
                issue_type: undefined,
                include_me: true,
                limit: 20,
            });
        });

        expect(await screen.findByText("张三")).toBeTruthy();
        expect(
            screen.getByText("均分与排名只纳入可评估的已完成训练，证据不足会话会单独记账，不会混入榜单。"),
        ).toBeTruthy();
        expect(
            screen.getByText("若某次训练因证据不足暂不可评估，它会保留在训练记录里，但不会拉高或拉低排行榜均分。"),
        ).toBeTruthy();
        expect(screen.getByText("当前榜单纳入 14 次可评估训练，3 次证据不足训练未计入排名。")).toBeTruthy();
        expect(screen.getByText("我的排名 · 综合分榜")).toBeTruthy();
        expect(screen.getByText(/均分 80/)).toBeTruthy();
        expect(screen.getByText("我的附近排名 · 综合分榜")).toBeTruthy();
        expect(screen.getByText("同分邻近用户")).toBeTruthy();
        expect(screen.getByText("基于当前综合分榜中与你名次相邻或均分接近的用户生成；只使用已完成且可评估训练。")).toBeTruthy();
        expect(screen.getAllByText("赵六").length).toBeGreaterThan(0);
        expect(screen.getByText(/与你均分差 1\.1 分/)).toBeTruthy();
        expect(screen.queryByText(/weighted-score/i)).toBeNull();
    });

    it("keeps the evaluable-session explanation and empty state when leaderboard data is empty or malformed", async () => {
        getPublicLeaderboardMock.mockResolvedValueOnce({
            time_period: "weekly",
            total_users: 0,
        });
        getMyRankMock.mockResolvedValueOnce(null);

        render(<LeaderboardPage />);

        expect(await screen.findByText("暂无排行榜数据")).toBeTruthy();
        expect(
            screen.getByText(/当前筛选范围还没有可评估训练进入榜单/),
        ).toBeTruthy();
        expect(screen.getAllByRole("link", { name: /去训练大厅/ }).some((link) => link.getAttribute("href") === "/training")).toBe(true);
        expect(
            screen.getByText("均分与排名只纳入可评估的已完成训练，证据不足会话会单独记账，不会混入榜单。"),
        ).toBeTruthy();
        expect(
            screen.getByText("若某次训练因证据不足暂不可评估，它会保留在训练记录里，但不会拉高或拉低排行榜均分。"),
        ).toBeTruthy();
        expect(getMyRankMock).toHaveBeenCalledWith({
            scenario_type: undefined,
            time_period: "weekly",
            leaderboard_mode: "score",
            issue_type: undefined,
        });
        expect(screen.queryByText(/我的排名/)).toBeNull();
    });

    it("distinguishes leaderboard request failures from a genuinely empty leaderboard", async () => {
        getPublicLeaderboardMock
            .mockRejectedValueOnce(new Error("leaderboard failed"))
            .mockResolvedValueOnce({
                time_period: "weekly",
                total_users: 1,
                entries: [createLeaderboardEntry({ username: "恢复后的张三" })],
            });

        render(<LeaderboardPage />);

        expect(
            await screen.findByText("排行榜暂时无法加载：leaderboard failed"),
        ).toBeTruthy();
        expect(screen.queryByText("暂无排行榜数据")).toBeNull();
        expect(screen.queryByText(/我的排名/)).toBeNull();
        expect(getMyRankMock).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "重试排行榜" }));

        expect(await screen.findByText("恢复后的张三")).toBeTruthy();
        expect(screen.queryByText(/排行榜暂时无法加载/)).toBeNull();
    });

    it("preserves filter interactions and fallback my-rank loading while keeping evaluable-session copy", async () => {
        getPublicLeaderboardMock
            .mockResolvedValueOnce({
                time_period: "weekly",
                total_users: 1,
                entries: [createLeaderboardEntry()],
            })
            .mockResolvedValueOnce({
                time_period: "all_time",
                total_users: 1,
                entries: [createLeaderboardEntry({ rank: 1, username: "总榜张三" })],
            })
            .mockResolvedValueOnce({
                time_period: "all_time",
                scenario_type: "presentation",
                total_users: 1,
                entries: [createLeaderboardEntry({ rank: 1, username: "PPT 张三" })],
            });
        getMyRankMock
            .mockResolvedValueOnce({
                user_id: "me",
                rank: 7,
                total_sessions: 3,
                average_score: 78.1,
            })
            .mockResolvedValue({
                user_id: "me",
                rank: 7,
                total_sessions: 3,
                average_score: 78.1,
            });

        render(<LeaderboardPage />);

        await waitFor(() => {
            expect(getMyRankMock).toHaveBeenCalledWith({
                scenario_type: undefined,
                time_period: "weekly",
                leaderboard_mode: "score",
                issue_type: undefined,
            });
        });
        expect(await screen.findByText("我的排名 · 综合分榜")).toBeTruthy();
        expect(screen.getAllByText(/均分 78/).length).toBeGreaterThan(0);

        fireEvent.click(screen.getByRole("button", { name: "总榜" }));

        await waitFor(() => {
            expect(getPublicLeaderboardMock).toHaveBeenLastCalledWith({
                scenario_type: undefined,
                time_period: "all_time",
                leaderboard_mode: "score",
                issue_type: undefined,
                include_me: true,
                limit: 20,
            });
        });

        fireEvent.click(screen.getByRole("button", { name: "PPT 演练" }));

        await waitFor(() => {
            expect(getPublicLeaderboardMock).toHaveBeenLastCalledWith({
                scenario_type: "presentation",
                time_period: "all_time",
                leaderboard_mode: "score",
                issue_type: undefined,
                include_me: true,
                limit: 20,
            });
        });

        expect(
            screen.getByText("均分与排名只纳入可评估的已完成训练，证据不足会话会单独记账，不会混入榜单。"),
        ).toBeTruthy();
    });

    it("explains when my rank is outside the current leaderboard page", async () => {
        getPublicLeaderboardMock.mockResolvedValueOnce({
            time_period: "weekly",
            score_basis: "session_evidence_projection_evaluable_only",
            evaluable_sessions: 20,
            not_evaluable_sessions: 1,
            total_users: 30,
            entries: [
                createLeaderboardEntry({ rank: 1, user_id: "top-1", username: "榜首", average_score: 96, best_score: 98 }),
                createLeaderboardEntry({ rank: 2, user_id: "top-2", username: "第二名", average_score: 94, best_score: 96 }),
            ],
            my_rank: {
                user_id: "me",
                rank: 28,
                total_sessions: 1,
                average_score: 61.2,
                score_basis: "session_evidence_projection_evaluable_only",
                evaluable_sessions: 1,
                not_evaluable_sessions: 0,
            },
        });

        render(<LeaderboardPage />);

        expect(await screen.findByText("我的附近排名暂不在本页范围")).toBeTruthy();
        expect(screen.getByText(/你当前在综合分榜排名 #28，均分 61/)).toBeTruthy();
        expect(screen.getAllByRole("link", { name: /去训练大厅/ }).some((link) => link.getAttribute("href") === "/training")).toBe(true);
    });

    it("switches to improvement mode and keeps nearby rank based on current mode params", async () => {
        render(<LeaderboardPage />);

        await screen.findByText("张三");

        getPublicLeaderboardMock.mockResolvedValueOnce({
            time_period: "weekly",
            leaderboard_mode: "improvement",
            eligibility: {
                score_basis: "session_evidence_projection_evaluable_only",
                min_evaluable_sessions: 2,
                explanation: "进步榜至少需要 2 次可评估训练",
            },
            evaluable_sessions: 9,
            not_evaluable_sessions: 2,
            total_users: 3,
            entries: [
                createLeaderboardEntry({
                    rank: 1,
                    user_id: "user-boost-1",
                    username: "进步王",
                    average_score: 86,
                    best_score: 90,
                    improvement_score: 16,
                    first_score: 70,
                    latest_score: 86,
                    sample_size: 3,
                }),
                createLeaderboardEntry({
                    rank: 3,
                    user_id: "user-boost-3",
                    username: "稳步提升",
                    average_score: 83,
                    best_score: 88,
                    improvement_score: 13,
                    first_score: 70,
                    latest_score: 83,
                    sample_size: 2,
                }),
            ],
            my_rank: {
                user_id: "me",
                rank: 2,
                total_sessions: 3,
                average_score: 85,
                improvement_score: 14,
                first_score: 71,
                latest_score: 85,
                sample_size: 3,
            },
        });

        fireEvent.click(screen.getByRole("button", { name: "进步榜" }));

        await waitFor(() => {
            expect(getPublicLeaderboardMock).toHaveBeenLastCalledWith({
                scenario_type: undefined,
                time_period: "weekly",
                leaderboard_mode: "improvement",
                issue_type: undefined,
                include_me: true,
                limit: 20,
            });
        });

        expect((await screen.findAllByText("进步王")).length).toBeGreaterThan(0);
        expect(screen.getByText("我的排名 · 进步榜")).toBeTruthy();
        expect(screen.getByText(/进步 \+14/)).toBeTruthy();
        expect(screen.getAllByText(/\+16/).length).toBeGreaterThan(0);
        expect(screen.getAllByText(/当前 86 · 3 次样本/).length).toBeGreaterThan(0);
        expect(screen.getByText("同进步幅度邻近用户")).toBeTruthy();
        expect(screen.getByText("基于当前进步榜中与你名次相邻或进步接近的用户生成；只使用已完成且可评估训练。")).toBeTruthy();
        expect(screen.getByText(/与你进步差 1\.0 分/)).toBeTruthy();
    });

    it("shows a sample-insufficient explanation for empty improvement mode", async () => {
        render(<LeaderboardPage />);

        await screen.findByText("张三");

        getPublicLeaderboardMock.mockResolvedValueOnce({
            time_period: "weekly",
            leaderboard_mode: "improvement",
            eligibility: {
                score_basis: "session_evidence_projection_evaluable_only",
                min_evaluable_sessions: 2,
                explanation: "进步榜至少需要 2 次可评估训练",
            },
            evaluable_sessions: 1,
            not_evaluable_sessions: 4,
            total_users: 0,
            entries: [],
            my_rank: {
                user_id: "me",
                rank: null,
                total_sessions: 1,
                average_score: 72,
                improvement_score: 0,
                sample_size: 1,
                message: "sample insufficient",
            },
        });

        fireEvent.click(screen.getByRole("button", { name: "进步榜" }));

        expect(await screen.findByText("进步榜样本不足")).toBeTruthy();
        expect(screen.getByText("进步榜至少需要 2 次可评估训练")).toBeTruthy();
        expect(screen.getByText(/当前账号还没有至少 2 次可评估训练进入进步榜/)).toBeTruthy();
        expect(screen.queryByText("暂无排行榜数据")).toBeNull();
    });

    it("shows issue buckets first, then requests the selected issue-type leaderboard", async () => {
        render(<LeaderboardPage />);

        await screen.findByText("张三");

        getPublicLeaderboardMock.mockResolvedValueOnce({
            time_period: "weekly",
            leaderboard_mode: "issue_type",
            evaluable_sessions: 8,
            not_evaluable_sessions: 1,
            total_users: 0,
            entries: [],
            issue_type_buckets: [
                { issue_type: "evidence_gap", count: 4, evaluable_sessions: 8 },
                { issue_type: "objection_handling_gap", count: 2, evaluable_sessions: 3 },
            ],
            my_rank: null,
        });

        fireEvent.click(screen.getByRole("button", { name: "同目标榜" }));

        await waitFor(() => {
            expect(getPublicLeaderboardMock).toHaveBeenLastCalledWith({
                scenario_type: undefined,
                time_period: "weekly",
                leaderboard_mode: "issue_type",
                issue_type: undefined,
                include_me: true,
                limit: 20,
            });
        });
        expect(await screen.findByText("先选择一个训练目标")).toBeTruthy();
        expect(screen.getByRole("button", { name: /证据支撑/ })).toBeTruthy();
        expect(screen.getByRole("button", { name: /异议处理/ })).toBeTruthy();

        getPublicLeaderboardMock.mockResolvedValueOnce({
            time_period: "weekly",
            leaderboard_mode: "issue_type",
            issue_type: "evidence_gap",
            evaluable_sessions: 8,
            not_evaluable_sessions: 1,
            total_users: 2,
            entries: [
                createLeaderboardEntry({
                    rank: 1,
                    user_id: "issue-1",
                    username: "证据高手",
                    average_score: 88,
                    best_score: 92,
                    issue_type: "evidence_gap",
                }),
                createLeaderboardEntry({
                    rank: 3,
                    user_id: "issue-3",
                    username: "案例补强者",
                    average_score: 84,
                    best_score: 89,
                    issue_type: "evidence_gap",
                }),
            ],
            issue_type_buckets: [
                { issue_type: "evidence_gap", count: 4, evaluable_sessions: 8 },
                { issue_type: "objection_handling_gap", count: 2, evaluable_sessions: 3 },
            ],
            my_rank: {
                user_id: "me",
                rank: 2,
                total_sessions: 4,
                average_score: 86,
                issue_type: "evidence_gap",
            },
        });

        fireEvent.click(screen.getByRole("button", { name: /证据支撑/ }));

        await waitFor(() => {
            expect(getPublicLeaderboardMock).toHaveBeenLastCalledWith({
                scenario_type: undefined,
                time_period: "weekly",
                leaderboard_mode: "issue_type",
                issue_type: "evidence_gap",
                include_me: true,
                limit: 20,
            });
        });

        expect((await screen.findAllByText("证据高手")).length).toBeGreaterThan(0);
        expect(screen.getByText("我的排名 · 同目标榜")).toBeTruthy();
        expect(screen.getByText("我的附近排名 · 同目标榜")).toBeTruthy();
        expect(screen.getByText("基于当前同目标榜中与你名次相邻或均分接近的用户生成；只使用已完成且可评估训练。")).toBeTruthy();
    });

});
