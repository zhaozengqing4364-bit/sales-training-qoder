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
            evaluable_sessions: 3,
            not_evaluable_sessions: 1,
            average_score: 86,
            best_score: 92,
            score_basis: "session_evidence_projection_evaluable_only",
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

    it("renders the password CTA as a controlled forgot-password handoff with truthful copy", async () => {
        renderProfilePage();

        await waitFor(() => {
            expect(getMeMock).toHaveBeenCalled();
        });

        expect(screen.getByText("通过邮箱重置密码，会带入当前账号邮箱。", { exact: false })).toBeTruthy();
        expect(screen.getByText("仅统计 3 次可评估训练，1 次证据不足训练不计入均分。")).toBeTruthy();
        expect(screen.getByText("仅保存在当前浏览器，刷新后会保留。", { exact: false })).toBeTruthy();
        expect(screen.queryByText(/通知/)).toBeNull();
        const resetLink = screen.getByRole("link", { name: "通过邮箱重置密码" }) as HTMLAnchorElement;
        expect(resetLink.getAttribute("href")).toBe("/forgot-password?email=learner%40example.com");
    });

    it("does not fall back to legacy session average when no evaluable history score exists", async () => {
        getHistoryStatisticsMock.mockResolvedValueOnce({
            total_sessions: 2,
            evaluable_sessions: 0,
            not_evaluable_sessions: 2,
            average_score: 0,
            best_score: 0,
            score_basis: "session_evidence_projection_evaluable_only",
            total_practice_time_seconds: 600,
            total_practice_time_minutes: 10,
        });
        getSessionStatsMock.mockResolvedValueOnce({
            total_sessions: 2,
            weekly_sessions: 1,
            average_score: 99,
            completed_sessions: 2,
            total_practice_minutes: 10,
        });

        renderProfilePage();

        expect(await screen.findByText("仅统计 0 次可评估训练，2 次证据不足训练不计入均分。")).toBeTruthy();
        expect(screen.getByText("0", { exact: true })).toBeTruthy();
        expect(screen.queryByText("99")).toBeNull();
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

    it("keeps the shared learner help guidance visible on profile", async () => {
        renderProfilePage();

        await waitFor(() => {
            expect(getMeMock).toHaveBeenCalled();
        });

        expect(screen.getByText("需要帮助或反馈？")).toBeTruthy();
        expect(screen.getByText(/统一入口在侧边栏底部的“帮助与反馈”里；手机端先打开左上角菜单。/)).toBeTruthy();
        expect(screen.getByText(/页面异常、入口缺失或结果不对时，请通过这个统一入口反馈当前页面路径或会话编号。/)).toBeTruthy();
        expect(screen.getByText(/当前 learner 默认只看到训练、历史、个人中心；运行状态和管理后台只对管理员或支持角色开放。/)).toBeTruthy();
        expect(screen.queryByText(/7 x 24/)).toBeNull();
    });
});
