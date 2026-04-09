import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProfilePage from "./page";

const {
    getMeMock,
    getHistoryStatisticsMock,
    getSessionStatsMock,
    logoutMock,
    updateProfileMock,
} = vi.hoisted(() => ({
    getMeMock: vi.fn(),
    getHistoryStatisticsMock: vi.fn(),
    getSessionStatsMock: vi.fn(),
    logoutMock: vi.fn(),
    updateProfileMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) =>
        asChild ? <>{children}</> : <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

vi.mock("@/components/ui/input", () => ({
    Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            auth: {
                ...actual.api.auth,
                logout: logoutMock,
            },
            user: {
                ...actual.api.user,
                getMe: getMeMock,
                updateProfile: updateProfileMock,
            },
            dashboard: {
                ...actual.api.dashboard,
                getHistoryStatistics: getHistoryStatisticsMock,
            },
            sessions: {
                ...actual.api.sessions,
                getStats: getSessionStatsMock,
            },
        },
    };
});

vi.mock("@/lib/auth-handler", () => ({
    authHandler: {
        logout: vi.fn(),
    },
}));

function renderProfilePage() {
    const queryClient = new QueryClient({
        defaultOptions: {
            queries: {
                retry: false,
            },
        },
    });

    return render(
        <QueryClientProvider client={queryClient}>
            <ProfilePage />
        </QueryClientProvider>,
    );
}

describe("ProfilePage password route handoff", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        localStorage.clear();

        getMeMock.mockResolvedValue({
            id: "user-1",
            name: "王小明",
            display_name: "王小明",
            email: "learner@example.com",
            department: "销售部",
        });
        getHistoryStatisticsMock.mockResolvedValue({
            total_sessions: 4,
            average_score: 86,
            best_score: 92,
            total_practice_time_seconds: 1200,
            total_practice_time_minutes: 20,
        });
        getSessionStatsMock.mockResolvedValue({
            total_sessions: 4,
            weekly_sessions: 2,
            average_score: 86,
            completed_sessions: 4,
            total_practice_minutes: 20,
        });
        updateProfileMock.mockResolvedValue(undefined);
        logoutMock.mockResolvedValue(undefined);
    });

    it("renders the password CTA as a controlled forgot-password link with truthful copy", async () => {
        renderProfilePage();

        await waitFor(() => {
            expect(getMeMock).toHaveBeenCalled();
        });

        expect(screen.getByText("通过邮箱重置密码，沿用现有邮箱找回流程")).toBeTruthy();
        expect(screen.queryByText(/通知/)).toBeNull();
        const resetLink = screen.getByRole("link", { name: "通过邮箱重置密码" }) as HTMLAnchorElement;
        expect(resetLink.getAttribute("href")).toBe("/forgot-password");
    });

    it("hydrates the voice speed select from the shared preference seam and never PATCHes fake persistence", async () => {
        localStorage.setItem("voice_speed_preference", "1.25");

        renderProfilePage();

        await waitFor(() => {
            expect(getMeMock).toHaveBeenCalled();
        });

        const voiceSpeedSelect = screen.getByRole("combobox", { name: "语音播放速度" }) as HTMLSelectElement;
        expect(voiceSpeedSelect.value).toBe("1.25");

        fireEvent.change(voiceSpeedSelect, { target: { value: "1.5" } });

        expect(localStorage.getItem("voice_speed_preference")).toBe("1.5");
        expect(updateProfileMock).not.toHaveBeenCalled();
    });

    it("normalizes malformed localStorage values back to the default option", async () => {
        localStorage.setItem("voice_speed_preference", "fast");

        renderProfilePage();

        const voiceSpeedSelect = await screen.findByRole("combobox", { name: "语音播放速度" }) as HTMLSelectElement;
        expect(voiceSpeedSelect.value).toBe("1.0");
        expect(localStorage.getItem("voice_speed_preference")).toBe("1.0");
    });

    it("renders all supported voice speed options from the shared seam", async () => {
        renderProfilePage();

        const voiceSpeedSelect = await screen.findByRole("combobox", { name: "语音播放速度" });
        const optionValues = Array.from(voiceSpeedSelect.querySelectorAll("option")).map((option) => option.getAttribute("value"));

        expect(optionValues).toEqual(["0.75", "1.0", "1.25", "1.5"]);
    });

    it("keeps the page fallback visible when profile loading fails without breaking the password route", async () => {
        getMeMock.mockRejectedValueOnce(new Error("profile failed"));
        getHistoryStatisticsMock.mockRejectedValueOnce(new Error("history failed"));
        getSessionStatsMock.mockRejectedValueOnce(new Error("session failed"));

        renderProfilePage();

        expect(await screen.findByText("加载个人信息失败，请刷新重试。")).toBeTruthy();
        const resetLink = screen.getByRole("link", { name: "通过邮箱重置密码" }) as HTMLAnchorElement;
        expect(resetLink.getAttribute("href")).toBe("/forgot-password");
    });
});
