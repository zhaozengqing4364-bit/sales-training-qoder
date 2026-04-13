import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminLogsPage from "./page";

const {
    errorToastMock,
    getSystemLogsMock,
} = vi.hoisted(() => ({
    errorToastMock: vi.fn(),
    getSystemLogsMock: vi.fn(),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) =>
        asChild ? <>{children}</> : <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
}));

vi.mock("@/components/ui/input", () => ({
    Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        error: errorToastMock,
        success: vi.fn(),
        showToast: vi.fn(),
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            adminTools: {
                ...actual.api.adminTools,
                getSystemLogs: getSystemLogsMock,
            },
        },
    };
});

describe("AdminLogsPage", () => {
    beforeEach(() => {
        errorToastMock.mockReset();
        getSystemLogsMock.mockReset();
        getSystemLogsMock.mockResolvedValue({
            items: [
                {
                    id: "log-1",
                    action: "admin.user.updated",
                    user_identifier: "se***@example.com",
                    ip_address: "203.0.*.*",
                    status: "failed",
                    created_at: "2026-04-13T12:00:00Z",
                    details: null,
                    trace_id: null,
                    error_code: null,
                    phase: null,
                    session_id: null,
                    diagnostics: [
                        { key: "trace_id", value: "trace-123" },
                        { key: "error_code", value: "USER_UPDATE_FAILED" },
                        { key: "phase", value: "persist" },
                        { key: "session_id", value: "session-123" },
                        { key: "target_user_id", value: "user-456" },
                    ],
                },
            ],
            total: 1,
            page: 1,
            page_size: 10,
            has_more: false,
            policy: {
                version: "admin_support_redaction_v1",
                visible_fields: ["id", "action", "status", "created_at", "user_identifier", "ip_address", "details"],
                internal_only_fields: ["details.raw", "token", "password"],
                redaction_summary: "admin/support 仅暴露安全诊断字段",
                diagnostic_fields: ["trace_id", "error_code", "phase", "session_id", "target_user_id"],
            },
        });
    });

    it("renders safe diagnostics while keeping masked identity fields on the admin logs page", async () => {
        render(<AdminLogsPage />);

        await waitFor(() => {
            expect(getSystemLogsMock).toHaveBeenCalled();
        });

        expect(screen.getByText("se***@example.com")).toBeTruthy();
        expect(screen.getByText("203.0.*.*")).toBeTruthy();
        expect(screen.getByText("trace-123")).toBeTruthy();
        expect(screen.getByText("USER_UPDATE_FAILED")).toBeTruthy();
        expect(screen.getByText("persist")).toBeTruthy();
        expect(screen.getByText("session-123")).toBeTruthy();
        expect(screen.getByText("user-456")).toBeTruthy();
        expect(screen.getByText(/日志可见性策略：admin_support_redaction_v1/)).toBeTruthy();
        expect(screen.queryByText("error_code=USER_UPDATE_FAILED · phase=persist · session_id=session-123 · trace_id=trace-123")).toBeNull();
        expect(screen.queryByText("sensitive.user@example.com")).toBeNull();
        expect(screen.queryByText("203.0.113.42")).toBeNull();
    });
});
