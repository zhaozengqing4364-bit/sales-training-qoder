import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { LeaderboardTable } from "./LeaderboardTable";
import { ScoreDistributionChart } from "./ScoreDistributionChart";
import { TrendsChart } from "./TrendsChart";

vi.mock("next/link", () => ({
    default: ({ href, children, className }: { href: string; children: ReactNode; className?: string }) => (
        <a href={href} className={className}>{children}</a>
    ),
}));

describe("analytics empty states", () => {
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
});
