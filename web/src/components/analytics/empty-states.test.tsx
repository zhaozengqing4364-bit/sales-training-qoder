import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AgentRankingChart } from "./AgentRankingChart";
import { LeaderboardTable } from "./LeaderboardTable";
import { ScoreDistributionChart } from "./ScoreDistributionChart";
import { TrendsChart } from "./TrendsChart";

const { responsiveContainerProps } = vi.hoisted(() => ({
    responsiveContainerProps: [] as Array<{
        initialDimension?: { width: number; height: number };
        width?: string | number;
        height?: string | number;
    }>,
}));

vi.mock("next/link", () => ({
    default: ({ href, children, className }: { href: string; children: ReactNode; className?: string }) => (
        <a href={href} className={className}>{children}</a>
    ),
}));

vi.mock("recharts", () => {
    const ChartWrapper = ({ children }: { children?: ReactNode }) => <div>{children}</div>;

    return {
        ResponsiveContainer: ({
            children,
            initialDimension,
            width,
            height,
        }: {
            children?: ReactNode;
            initialDimension?: { width: number; height: number };
            width?: string | number;
            height?: string | number;
        }) => {
            responsiveContainerProps.push({ initialDimension, width, height });
            return <div data-testid="responsive-container">{children}</div>;
        },
        LineChart: ChartWrapper,
        Line: () => null,
        XAxis: () => null,
        YAxis: () => null,
        CartesianGrid: () => null,
        Tooltip: () => null,
        Legend: () => null,
        PieChart: ChartWrapper,
        Pie: ChartWrapper,
        Cell: () => null,
        BarChart: ChartWrapper,
        Bar: ChartWrapper,
    };
});

describe("analytics empty states", () => {
    beforeEach(() => {
        responsiveContainerProps.length = 0;
    });

    it("explains the trends trigger and links learners to training", () => {
        render(<TrendsChart data={[]} />);

        expect(screen.getByText("暂无趋势数据")).toBeTruthy();
        expect(screen.getByText(/当前时间范围还没有可评估训练快照/)).toBeTruthy();
        expect(screen.getByRole("link", { name: /去训练大厅/ }).getAttribute("href")).toBe("/training");
    });

    it("explains why score buckets are empty and provides a training CTA", () => {
        render(<ScoreDistributionChart data={{ excellent: 0, good: 0, fair: 0, poor: 0 }} />);

        expect(screen.getByText("暂无分数数据")).toBeTruthy();
        expect(screen.getByText(/证据不足或未完成训练不会被计入分布/)).toBeTruthy();
        expect(screen.getByRole("link", { name: /去训练大厅/ }).getAttribute("href")).toBe("/training");
    });

    it("explains leaderboard eligibility and links to training", () => {
        render(<LeaderboardTable data={[]} />);

        expect(screen.getByText("暂无排行榜数据")).toBeTruthy();
        expect(screen.getByText(/当前范围还没有用户完成可评估训练/)).toBeTruthy();
        expect(screen.getByRole("link", { name: /去训练大厅/ }).getAttribute("href")).toBe("/training");
    });

    it("explains missing agent usage evidence and links admins to records", () => {
        render(
            <AgentRankingChart
                data={{
                    agent_stats: [],
                    persona_stats: [],
                    scenario_distribution: {},
                }}
            />,
        );

        expect(screen.getByText("暂无 Agent 使用数据")).toBeTruthy();
        expect(screen.getByText(/还没有已完成且可评估的训练使用到智能体或客户角色/)).toBeTruthy();
        expect(screen.getByRole("link", { name: /查看训练记录/ }).getAttribute("href")).toBe("/admin/records");
    });

    it("passes initial dimensions to Recharts containers before ResizeObserver measures", () => {
        render(
            <>
                <TrendsChart
                    data={[
                        {
                            date: "2026-05-15T00:00:00Z",
                            sessions_count: 2,
                            average_score: 78,
                            active_users: 1,
                        },
                    ]}
                />
                <ScoreDistributionChart data={{ excellent: 1, good: 1, fair: 0, poor: 0 }} />
                <AgentRankingChart
                    data={{
                        agent_stats: [
                            {
                                agent_id: "agent-1",
                                agent_name: "销售教练",
                                category: "sales",
                                usage_count: 3,
                                average_score: 82,
                                completion_rate: 100,
                            },
                        ],
                        persona_stats: [],
                        scenario_distribution: { sales: 3 },
                    }}
                />
            </>,
        );

        expect(responsiveContainerProps).toHaveLength(3);
        expect(responsiveContainerProps).toEqual(
            expect.arrayContaining([
                expect.objectContaining({
                    width: "100%",
                    height: "100%",
                    initialDimension: { width: 320, height: 288 },
                }),
                expect.objectContaining({
                    width: "100%",
                    height: "100%",
                    initialDimension: { width: 320, height: 288 },
                }),
                expect.objectContaining({
                    width: "100%",
                    height: "100%",
                    initialDimension: { width: 320, height: 288 },
                }),
            ]),
        );
    });
});
