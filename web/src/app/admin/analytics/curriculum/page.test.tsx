import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CurriculumAnalyticsPage from "./page";
import { api } from "@/lib/api/client";
import type { CurriculumAnalyticsResponse } from "@/lib/api/types";

vi.mock("@/lib/api/client", () => ({
    api: {
        analytics: {
            getCurriculumAnalytics: vi.fn(),
        },
    },
    getApiErrorMessage: vi.fn((error: unknown) => {
        if (error instanceof Error) return error.message;
        return "未知错误";
    }),
}));

vi.mock("@/components/analytics/curriculum-score-trend", () => ({
    CurriculumScoreTrend: ({ data }: { data: unknown[] }) => <div>ScoreTrend:{data.length}</div>,
}));

vi.mock("@/components/analytics/curriculum-heatmap", () => ({
    CurriculumHeatmap: ({ data }: { data: unknown[] }) => <div>Heatmap:{data.length}</div>,
}));

function makeDashboard(overrides: Partial<CurriculumAnalyticsResponse> = {}): CurriculumAnalyticsResponse {
    return {
        summary: {
            assigned_count: 12,
            completed_count: 9,
            completion_rate: 0.75,
            top_weak_dimension: "异议处理",
            average_score_delta: 8.5,
        },
        heatmap: [
            {
                template_id: "tpl-1",
                template_name: "新人异议处理训练",
                dimension: "异议处理",
                average_score: 62,
                sample_count: 5,
            },
        ],
        score_trend: [
            { date: "2026-05-10", average_score: 70, sample_count: 2 },
            { date: "2026-05-11", average_score: 78.5, sample_count: 3 },
        ],
        review_outcomes: {
            approved: 4,
            rejected: 1,
            calibrated: 2,
            retraining_required: 3,
        },
        retraining_conversion: {
            created: 3,
            started: 2,
            completed: 1,
        },
        cache: { enabled: false, hit: false, ttl_seconds: null },
        ...overrides,
    };
}

describe("CurriculumAnalyticsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it("should show loading state initially", async () => {
        let resolvePromise: (value: CurriculumAnalyticsResponse) => void = () => {};
        vi.mocked(api.analytics.getCurriculumAnalytics).mockReturnValue(
            new Promise<CurriculumAnalyticsResponse>((resolve) => { resolvePromise = resolve; }),
        );

        render(<CurriculumAnalyticsPage />);

        expect(screen.getByText(/正在加载课程分析数据/)).toBeDefined();
        resolvePromise(makeDashboard());
    });

    it("should render summary, charts, review outcomes and retraining conversion", async () => {
        vi.mocked(api.analytics.getCurriculumAnalytics).mockResolvedValue(makeDashboard());

        render(<CurriculumAnalyticsPage />);

        await waitFor(() => { expect(screen.getByText(/课程分析仪表盘/)).toBeDefined(); });
        expect(screen.getByText("9")).toBeDefined();
        expect(screen.getByText("75%" )).toBeDefined();
        expect(screen.getByText("异议处理")).toBeDefined();
        expect(screen.getByText("+8.5")).toBeDefined();
        expect(screen.getByText("Heatmap:1")).toBeDefined();
        expect(screen.getByText("ScoreTrend:2")).toBeDefined();
        expect(screen.getByRole("heading", { name: "主管复核结果" })).toBeDefined();
        expect(screen.getByText(/需复训 3/)).toBeDefined();
        expect(screen.getByRole("heading", { name: "复训闭环" })).toBeDefined();
        expect(screen.getByText(/已完成 1/)).toBeDefined();
    });

    it("should show empty state when dashboard has no curriculum samples", async () => {
        vi.mocked(api.analytics.getCurriculumAnalytics).mockResolvedValue(
            makeDashboard({
                summary: {
                    assigned_count: 0,
                    completed_count: 0,
                    completion_rate: 0,
                    top_weak_dimension: null,
                    average_score_delta: 0,
                },
                heatmap: [],
                score_trend: [],
            }),
        );

        render(<CurriculumAnalyticsPage />);

        await waitFor(() => { expect(screen.getByText(/暂无课程分析数据/)).toBeDefined(); });
        expect(screen.getByText(/完成课程训练并生成冻结报告后/)).toBeDefined();
    });

    it("should retry after API failure", async () => {
        vi.mocked(api.analytics.getCurriculumAnalytics)
            .mockRejectedValueOnce(new Error("网络错误"))
            .mockResolvedValueOnce(makeDashboard());

        render(<CurriculumAnalyticsPage />);

        await waitFor(() => { expect(screen.getByText(/网络错误/)).toBeDefined(); });
        fireEvent.click(screen.getByText(/重试加载/));
        await waitFor(() => { expect(screen.getByText("75%" )).toBeDefined(); });
        expect(api.analytics.getCurriculumAnalytics).toHaveBeenCalledTimes(2);
    });

    it("should reload dashboard when time range changes", async () => {
        vi.mocked(api.analytics.getCurriculumAnalytics)
            .mockResolvedValueOnce(makeDashboard())
            .mockResolvedValueOnce(makeDashboard({
                summary: {
                    assigned_count: 20,
                    completed_count: 15,
                    completion_rate: 0.75,
                    top_weak_dimension: "价值表达",
                    average_score_delta: 4.2,
                },
            }));

        render(<CurriculumAnalyticsPage />);

        await waitFor(() => {
            expect(api.analytics.getCurriculumAnalytics).toHaveBeenCalledWith({ time_range: "30d" });
        });
        fireEvent.click(screen.getByRole("button", { name: "近 90 天" }));

        await waitFor(() => {
            expect(api.analytics.getCurriculumAnalytics).toHaveBeenCalledWith({ time_range: "90d" });
        });
        expect(api.analytics.getCurriculumAnalytics).toHaveBeenCalledTimes(2);
        expect(screen.getByText("15")).toBeDefined();
    });
});
