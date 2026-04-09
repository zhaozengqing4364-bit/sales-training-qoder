import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ForgotPasswordPage from "./page";

const { pushMock, forgotPasswordMock } = vi.hoisted(() => ({
    pushMock: vi.fn(),
    forgotPasswordMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
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
                forgotPassword: forgotPasswordMock,
            },
        },
    };
});

describe("ForgotPasswordPage login recovery", () => {
    beforeEach(() => {
        pushMock.mockReset();
        forgotPasswordMock.mockReset();
    });

    it("trims the email before requesting a reset link and lets the user return to login", async () => {
        forgotPasswordMock.mockResolvedValue({ message: "ok" });

        render(<ForgotPasswordPage />);

        fireEvent.change(screen.getByLabelText("邮箱地址"), {
            target: { value: "  admin@test.com  " },
        });
        fireEvent.click(screen.getByRole("button", { name: "发送重置链接" }));

        await waitFor(() => {
            expect(forgotPasswordMock).toHaveBeenCalledWith("admin@test.com");
        });

        expect(await screen.findByText("邮件已发送")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "返回登录" }));

        expect(pushMock).toHaveBeenCalledWith("/login");
    });
});
