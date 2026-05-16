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

function mockProvidersResponse(overrides?: {
    wecom?: Partial<{ enabled: boolean; configured: boolean; login_url: string; message: string }>;
    devFallback?: Partial<{ enabled: boolean; login_url: string; message: string }>;
}) {
    const payload = {
        success: true,
        data: {
            environment: "development",
            wecom: {
                enabled: false,
                configured: false,
                login_url: "http://localhost:3444/api/v1/auth/wecom/start?return_to=%2F",
                message: "当前环境未配置企业微信 SSO。",
                ...overrides?.wecom,
            },
            dev_fallback: {
                enabled: true,
                login_url: "http://localhost:3444/api/v1/auth/dev-login",
                message: "仅 development 环境可用的开发者登录。",
                ...overrides?.devFallback,
            },
        },
    };

    return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
    });
}

describe("LoginPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        loginMock.mockReset();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();

        const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
            const url = String(input);
            if (url.includes("/auth/providers")) {
                return mockProvidersResponse();
            }
            if (url.includes("/auth/dev-login")) {
                return new Response(
                    JSON.stringify({
                        success: true,
                        data: {
                            access_token: "dev-token",
                            token_type: "bearer",
                            user: {
                                user_id: "dev-user-1",
                                email: "dev@example.com",
                                name: "Developer",
                            },
                        },
                    }),
                    {
                        status: 200,
                        headers: { "Content-Type": "application/json" },
                    },
                );
            }
            throw new Error(`Unexpected fetch: ${url} ${init?.method ?? "GET"}`);
        });

        vi.stubGlobal("fetch", fetchMock);
    });

    it("renders WeCom as unavailable when the provider is not configured and shows the explicit dev fallback", async () => {
        render(<LoginPage />);

        const wecomButton = (await screen.findByRole("button", { name: /企业微信登录/i })) as HTMLButtonElement;

        expect(wecomButton.disabled).toBe(true);
        expect(await screen.findByText("当前环境未配置企业微信 SSO。"))
            .toBeTruthy();
        expect(await screen.findByRole("button", { name: /开发者快速登录/i }))
            .toBeTruthy();
        expect(screen.getByText(/仅 development 环境可用的开发者登录。/i)).toBeTruthy();
    });

    it("provides explicit accessible labels for the login fields", async () => {
        render(<LoginPage />);
        await screen.findByRole("button", { name: /开发者快速登录/i });

        expect(screen.getByLabelText("邮箱地址")).toBeTruthy();
        expect(screen.getByLabelText("密码")).toBeTruthy();
        expect(screen.getByLabelText(/记住邮箱/)).toBeTruthy();
    });

    it("lets learners reveal and hide the password without changing the value", async () => {
        render(<LoginPage />);
        await screen.findByRole("button", { name: /开发者快速登录/i });

        const passwordInput = screen.getByLabelText("密码") as HTMLInputElement;
        fireEvent.change(passwordInput, {
            target: { value: "secret-password" },
        });

        expect(passwordInput.type).toBe("password");

        fireEvent.click(screen.getByRole("button", { name: "显示密码" }));
        expect(passwordInput.type).toBe("text");
        expect(passwordInput.value).toBe("secret-password");

        fireEvent.click(screen.getByRole("button", { name: "隐藏密码" }));
        expect(passwordInput.type).toBe("password");
    });

    it("preserves a typed email when handing off to forgot-password", async () => {
        render(<LoginPage />);
        await screen.findByRole("button", { name: /开发者快速登录/i });

        fireEvent.change(screen.getByLabelText("邮箱地址"), {
            target: { value: "  admin@test.com  " },
        });

        expect(screen.getByRole("link", { name: "忘记密码？" }).getAttribute("href")).toBe("/forgot-password?email=admin%40test.com");
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

        fireEvent.change(screen.getByLabelText("邮箱地址"), {
            target: { value: "admin@test.com" },
        });
        fireEvent.change(screen.getByLabelText("密码"), {
            target: { value: "password" },
        });
        fireEvent.click(screen.getByRole("button", { name: /^登录/ }));

        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith("/");
        });

        expect(setItemSpy).not.toHaveBeenCalledWith("token", expect.any(String));
        expect(setItemSpy).not.toHaveBeenCalledWith("user", expect.any(String));
    });

    it("uses the explicit dev-login fallback and redirects home", async () => {
        const fetchMock = global.fetch as ReturnType<typeof vi.fn>;

        render(<LoginPage />);

        fireEvent.click(await screen.findByRole("button", { name: /开发者快速登录/i }));

        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith("/");
        });

        expect(fetchMock).toHaveBeenCalledWith(
            "http://localhost:3444/api/v1/auth/dev-login",
            expect.objectContaining({
                method: "POST",
                credentials: "include",
            }),
        );
    });

    // Regression: ISSUE-002 — native login fallback leaked credentials into the URL
    // Found by /qa on 2026-05-16
    // Report: .gstack/qa-reports/qa-report-127-0-0-1-3017-2026-05-16.md
    it("prevents native form fallback from placing credentials in the URL", async () => {
        const { container } = render(<LoginPage />);
        await screen.findByRole("button", { name: /开发者快速登录/i });

        const form = container.querySelector("form");
        expect(form).not.toBeNull();
        expect(form!.getAttribute("method")).toBe("post");

        const passwordInput = screen.getByLabelText("密码");
        expect(passwordInput.getAttribute("name")).toBeNull();
    });
});
