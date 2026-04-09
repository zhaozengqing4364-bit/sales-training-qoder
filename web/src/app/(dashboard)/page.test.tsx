import { act, render, screen } from "@testing-library/react";
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

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children, className }: { children: ReactNode; className?: string }) => (
        <span className={className}>{children}</span>
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

        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(getStatsMock).toHaveBeenCalled();
        expect(screen.getByRole("heading", { name: /早安, 王小明/i })).toBeTruthy();
        expect(screen.getByRole("button", { name: `v${packageJson.version}` })).toBeTruthy();
        expect(screen.queryByText("2026年1月10日")).toBeNull();
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

        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });

        expect(getRecommendationMock).toHaveBeenCalled();
        expect(screen.getByRole("heading", { name: /晚安, fallback.user/i })).toBeTruthy();
    });
});
