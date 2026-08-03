import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

const { pushMock, loginMock, changeTemporaryPasswordMock, getProvidersMock, devLoginMock, toastErrorMock } = vi.hoisted(() => ({
    pushMock: vi.fn(),
    loginMock: vi.fn(),
    changeTemporaryPasswordMock: vi.fn(),
    getProvidersMock: vi.fn(),
    devLoginMock: vi.fn(),
    toastErrorMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        error: toastErrorMock,
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
            auth: {
                ...actual.api.auth,
                login: loginMock,
                changeTemporaryPassword: changeTemporaryPasswordMock,
                getProviders: getProvidersMock,
                devLogin: devLoginMock,
            },
        },
    };
});

function mockProvidersPayload(overrides?: {
    wecom?: Partial<{ enabled: boolean; configured: boolean; login_url: string; message: string }>;
    devFallback?: Partial<{ enabled: boolean; login_url: string; message: string }>;
}) {
    return {
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
    };
}

describe("LoginPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        loginMock.mockReset();
        changeTemporaryPasswordMock.mockReset();
        getProvidersMock.mockReset();
        devLoginMock.mockReset();
        toastErrorMock.mockReset();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();

        getProvidersMock.mockResolvedValue(mockProvidersPayload());
        devLoginMock.mockResolvedValue({
            access_token: "dev-token",
            token_type: "bearer",
            user: {
                user_id: "dev-user-1",
                email: "dev@example.com",
                name: "Developer",
            },
        });
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
        expect(screen.getByText("登录新人销售训练平台，继续当前训练任务")).toBeTruthy();
        expect(screen.queryByText("AI")).toBeNull();
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

    it("shows inline error, toast, and restores button after password login timeout", async () => {
        loginMock.mockRejectedValue(new Error("登录超时，请重试。"));

        render(<LoginPage />);

        fireEvent.change(screen.getByLabelText("邮箱地址"), {
            target: { value: "admin@test.com" },
        });
        fireEvent.change(screen.getByLabelText("密码"), {
            target: { value: "password" },
        });
        fireEvent.click(screen.getByRole("button", { name: /^登录/ }));

        expect((await screen.findByRole("alert")).textContent).toContain("登录超时，请重试。");
        expect(toastErrorMock).toHaveBeenCalledWith("登录超时，请重试");

        await waitFor(() => {
            expect((screen.getByRole("button", { name: /^登录/ }) as HTMLButtonElement).disabled).toBe(false);
        });
    });

    it("uses the explicit dev-login fallback and redirects home", async () => {
        render(<LoginPage />);

        fireEvent.click(await screen.findByRole("button", { name: /开发者快速登录/i }));

        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith("/");
        });

        expect(devLoginMock).toHaveBeenCalledTimes(1);
    });

    it("coalesces rapid repeated developer-login clicks into one request", async () => {
        let resolveLogin: (() => void) | undefined;
        devLoginMock.mockImplementation(() => new Promise((resolve) => {
            resolveLogin = () => resolve({
                access_token: "dev-token",
                token_type: "bearer",
                user: {
                    user_id: "dev-1",
                    email: "dev@example.com",
                    name: "Developer",
                    role: "admin",
                },
            });
        }));
        render(<LoginPage />);

        const button = await screen.findByRole("button", { name: /开发者快速登录/i });
        fireEvent.click(button);
        fireEvent.click(button);

        expect(devLoginMock).toHaveBeenCalledTimes(1);
        resolveLogin?.();
        await waitFor(() => expect(pushMock).toHaveBeenCalledWith("/"));
    });

    it("redirects training_manager to /team after password login", async () => {
        loginMock.mockResolvedValue({
            token: "mgr-token",
            user: {
                id: "mgr-1",
                name: "王经理",
                email: "manager@test.com",
                role: "training_manager",
            },
        });

        render(<LoginPage />);

        fireEvent.change(screen.getByLabelText("邮箱地址"), {
            target: { value: "manager@test.com" },
        });
        fireEvent.change(screen.getByLabelText("密码"), {
            target: { value: "password" },
        });
        fireEvent.click(screen.getByRole("button", { name: /^登录/ }));

        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith("/team");
        });
    });

    it("reconciles an unconfirmed password change by logging in with the new password", async () => {
        loginMock
            .mockResolvedValueOnce({
                token: "temporary-token",
                requires_password_change: true,
                user: {
                    id: "mgr-1",
                    name: "王经理",
                    email: "manager@test.com",
                    role: "training_manager",
                },
            })
            .mockResolvedValueOnce({
                token: "business-token",
                requires_password_change: false,
                user: {
                    id: "mgr-1",
                    name: "王经理",
                    email: "manager@test.com",
                    role: "training_manager",
                },
            });
        changeTemporaryPasswordMock.mockRejectedValue(new Error("密码修改超时，请重试。"));

        render(<LoginPage />);

        fireEvent.change(screen.getByLabelText("邮箱地址"), {
            target: { value: "manager@test.com" },
        });
        fireEvent.change(screen.getByLabelText("密码"), {
            target: { value: "temporary-password" },
        });
        fireEvent.click(screen.getByRole("button", { name: /^登录/ }));

        await screen.findByPlaceholderText("设置新密码");
        fireEvent.change(screen.getByPlaceholderText("设置新密码"), {
            target: { value: "NewPassword2026" },
        });
        fireEvent.change(screen.getByPlaceholderText("再次输入新密码"), {
            target: { value: "NewPassword2026" },
        });
        fireEvent.click(screen.getByRole("button", { name: /保存新密码并进入/ }));

        await waitFor(() => {
            expect(loginMock).toHaveBeenLastCalledWith({
                email: "manager@test.com",
                password: "NewPassword2026",
            });
            expect(pushMock).toHaveBeenCalledWith("/team");
        });
        expect(screen.queryByText("密码修改超时，请重试。")).toBeNull();
    });

    it("redirects training_manager to /team after dev login", async () => {
        devLoginMock.mockResolvedValue({
            access_token: "dev-mgr-token",
            token_type: "bearer",
            user: {
                user_id: "mgr-dev",
                email: "dev-mgr@example.com",
                name: "开发经理",
                role: "training_manager",
            },
        });

        render(<LoginPage />);

        fireEvent.click(await screen.findByRole("button", { name: /开发者快速登录/i }));

        await waitFor(() => {
            expect(pushMock).toHaveBeenCalledWith("/team");
        });
    });

    it("loads provider state through the shared auth API client", async () => {
        render(<LoginPage />);

        await screen.findByRole("button", { name: /开发者快速登录/i });

        expect(getProvidersMock).toHaveBeenCalledTimes(1);
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
