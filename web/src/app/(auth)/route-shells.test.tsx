import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>{children}</button>
    ),
}));

describe("auth route shells", () => {
    afterEach(() => {
        vi.unstubAllEnvs();
        vi.resetModules();
    });

    it("renders a shared auth loading status shell", async () => {
        const { default: AuthLoading } = await import("./loading");

        render(<AuthLoading />);

        expect(screen.getByRole("status")).toBeTruthy();
        expect(screen.getByText("正在加载登录与密码找回页面").className).toContain("sr-only");
        expect(screen.getByText("正在准备认证页面...")).toBeTruthy();
    });

    it("renders a recoverable auth error shell with login fallback", async () => {
        vi.stubEnv("NODE_ENV", "production");
        const resetMock = vi.fn();
        const { default: AuthError } = await import("./error");

        render(<AuthError error={new Error("auth crashed")} reset={resetMock} />);

        expect(screen.getByRole("heading", { name: "认证页面暂时不可用" })).toBeTruthy();
        expect(screen.getByText("请稍后重试；如果仍然失败，可先返回登录页重新开始。"))
            .toBeTruthy();
        expect(screen.getByRole("link", { name: "返回登录" }).getAttribute("href")).toBe("/login");
    });
});
