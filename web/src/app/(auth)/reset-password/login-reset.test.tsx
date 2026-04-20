import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ResetPasswordPage from "./page";

const { pushMock, resetPasswordMock, tokenState } = vi.hoisted(() => ({
    pushMock: vi.fn(),
    resetPasswordMock: vi.fn(),
    tokenState: { value: "" },
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
    useSearchParams: () => ({
        get: (key: string) => (key === "token" ? tokenState.value : null),
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            auth: {
                ...actual.api.auth,
                resetPassword: resetPasswordMock,
            },
        },
    };
});

describe("ResetPasswordPage login recovery", () => {
    beforeEach(() => {
        pushMock.mockReset();
        resetPasswordMock.mockReset();
        tokenState.value = "";
    });

    it("accepts a manually entered reset token when the URL has no token", async () => {
        resetPasswordMock.mockResolvedValue({ message: "ok" });

        render(<ResetPasswordPage />);

        fireEvent.change(screen.getByLabelText("重置令牌"), {
            target: { value: "reset-token-from-email" },
        });
        fireEvent.change(screen.getByLabelText("新密码"), {
            target: { value: "new-password-123" },
        });
        fireEvent.change(screen.getByLabelText("确认新密码"), {
            target: { value: "new-password-123" },
        });
        fireEvent.click(screen.getByRole("button", { name: "重置密码" }));

        await waitFor(() => {
            expect(resetPasswordMock).toHaveBeenCalledWith("reset-token-from-email", "new-password-123");
        });

        expect(await screen.findByText("密码已重置")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "去登录" }));

        expect(pushMock).toHaveBeenCalledWith("/login");
    });

    it("shows a validation error when the new password is shorter than 8 characters", async () => {
        tokenState.value = "query-token";

        render(<ResetPasswordPage />);

        fireEvent.change(screen.getByLabelText("新密码"), {
            target: { value: "short7!" },
        });
        fireEvent.change(screen.getByLabelText("确认新密码"), {
            target: { value: "short7!" },
        });
        fireEvent.click(screen.getByRole("button", { name: "重置密码" }));

        expect(await screen.findByText("密码至少需要 8 个字符")).toBeTruthy();
        expect(resetPasswordMock).not.toHaveBeenCalled();
    });

    it("shows a validation error when the two passwords do not match", async () => {
        tokenState.value = "query-token";

        render(<ResetPasswordPage />);

        fireEvent.change(screen.getByLabelText("新密码"), {
            target: { value: "new-password-123" },
        });
        fireEvent.change(screen.getByLabelText("确认新密码"), {
            target: { value: "different-password" },
        });
        fireEvent.click(screen.getByRole("button", { name: "重置密码" }));

        expect(await screen.findByText("两次输入的密码不一致")).toBeTruthy();
        expect(resetPasswordMock).not.toHaveBeenCalled();
    });
});
