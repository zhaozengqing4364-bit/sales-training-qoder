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
        expect(screen.getByText("我的排名")).toBeTruthy();
        expect(screen.getByText(/均分 80/)).toBeTruthy();
        expect(screen.queryByText(/weighted-score/i)).toBeNull();
    });

    it("keeps the evaluable-session explanation and empty state when leaderboard data is empty or malformed", async () => {
        getPublicLeaderboardMock.mockResolvedValueOnce({
            time_period: "weekly",
            total_users: 0,
        });
        getMyRankMock.mockResolvedValueOnce(null);

        render(<LeaderboardPage />);

        expect(
            await screen.findByText("暂无排行榜数据，完成可评估练习后会自动上榜。"),
        ).toBeTruthy();
        expect(
            screen.getByText("均分与排名只纳入可评估的已完成训练，证据不足会话会单独记账，不会混入榜单。"),
        ).toBeTruthy();
        expect(
            screen.getByText("若某次训练因证据不足暂不可评估，它会保留在训练记录里，但不会拉高或拉低排行榜均分。"),
        ).toBeTruthy();
        expect(getMyRankMock).toHaveBeenCalledWith({
            scenario_type: undefined,
            time_period: "weekly",
        });
        expect(screen.queryByText("我的排名")).toBeNull();
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
        expect(screen.queryByText("暂无排行榜数据，完成可评估练习后会自动上榜。")).toBeNull();
        expect(screen.queryByText("我的排名")).toBeNull();
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
            });
        });
        expect(await screen.findByText("我的排名")).toBeTruthy();
        expect(screen.getByText(/均分 78/)).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "总榜" }));

        await waitFor(() => {
            expect(getPublicLeaderboardMock).toHaveBeenLastCalledWith({
                scenario_type: undefined,
                time_period: "all_time",
                include_me: true,
                limit: 20,
            });
        });

        fireEvent.click(screen.getByRole("button", { name: "PPT 演练" }));

        await waitFor(() => {
            expect(getPublicLeaderboardMock).toHaveBeenLastCalledWith({
                scenario_type: "presentation",
                time_period: "all_time",
                include_me: true,
                limit: 20,
            });
        });

        expect(
            screen.getByText("均分与排名只纳入可评估的已完成训练，证据不足会话会单独记账，不会混入榜单。"),
        ).toBeTruthy();
    });
});
