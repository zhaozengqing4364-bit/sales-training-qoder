import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ForgotPasswordPage from "./page";

const { pushMock, forgotPasswordMock, searchParamsState } = vi.hoisted(() => ({
    pushMock: vi.fn(),
    forgotPasswordMock: vi.fn(),
    searchParamsState: { email: "" },
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
    useSearchParams: () => ({
        get: (key: string) => (key === "email" ? searchParamsState.email : null),
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
        searchParamsState.email = "";
    });

    it("hydrates the email field from the route handoff before requesting a reset link", async () => {
        searchParamsState.email = "  learner@example.com  ";
        forgotPasswordMock.mockResolvedValue({ message: "ok" });

        render(<ForgotPasswordPage />);

        expect((screen.getByLabelText("邮箱地址") as HTMLInputElement).value).toBe("learner@example.com");
        expect(screen.getByText("已从登录或个人中心带入邮箱，可直接发送重置邮件。")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "发送重置链接" }));

        await waitFor(() => {
            expect(forgotPasswordMock).toHaveBeenCalledWith("learner@example.com");
        });
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
