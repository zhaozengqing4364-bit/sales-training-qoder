import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

const { pushMock, loginMock } = vi.hoisted(() => ({
    pushMock: vi.fn(),
    loginMock: vi.fn(),
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
                login: loginMock,
            },
        },
    };
});

describe("LoginPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        loginMock.mockReset();
    });

    it("renders a forgot-password link below the password field", () => {
        render(<LoginPage />);

        expect(screen.getByRole("link", { name: "忘记密码？" }).getAttribute("href")).toBe("/forgot-password");
    });

    it("redirects after a successful cookie-session login without storing auth in localStorage", async () => {
        loginMock.mockResolvedValue({
            token: "legacy-token",
            user: {
                id: "user-1",
                name: "管理员",
                email: "admin@test.com",
                role: "admin",
            },
        });

        const setItemSpy = vi.spyOn(Storage.prototype, "setItem");

        render(<LoginPage />);

        fireEvent.change(screen.getByPlaceholderText("name@company.com"), {
            target: { value: "admin@test.com" },
        });
        fireEvent.change(screen.getByPlaceholderText("••••••••"), {
            target: { value: "password" },
        });
        fireEvent.click(screen.getByRole("button", { name: /^登录/ }));

        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith("/");
        });

        expect(setItemSpy).not.toHaveBeenCalledWith("token", expect.any(String));
        expect(setItemSpy).not.toHaveBeenCalledWith("user", expect.any(String));
    });
});
