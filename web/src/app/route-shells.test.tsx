import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { durableErrorMock } = vi.hoisted(() => ({
    durableErrorMock: vi.fn(),
}));

vi.mock("@/lib/debug", () => ({
    debug: {
        durableError: durableErrorMock,
    },
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>{children}</button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

vi.mock("lucide-react", () => {
    const Icon = () => <svg aria-hidden="true" />;

    return {
        AlertCircle: Icon,
        RefreshCcw: Icon,
    };
});

describe("app and admin route shells", () => {
    afterEach(() => {
        durableErrorMock.mockReset();
    });

    it("renders the root loading shell with Chinese status copy", async () => {
        const { default: RootLoading } = await import("./loading");

        render(<RootLoading />);

        expect(screen.getByRole("status")).toBeTruthy();
        expect(screen.getByText("正在加载应用页面").className).toContain("sr-only");
        expect(screen.getByText("正在准备页面内容...")).toBeTruthy();
    });

    it("renders the admin loading shell without English loading copy", async () => {
        const { default: AdminLoading } = await import("./admin/loading");

        render(<AdminLoading />);

        expect(screen.getByRole("status")).toBeTruthy();
        expect(screen.getByText("正在加载管理后台").className).toContain("sr-only");
        expect(screen.getByText("正在加载系统资源...")).toBeTruthy();
        expect(screen.queryByText("Loading System Resources...")).toBeNull();
    });

    it("renders the admin error shell with Chinese title and actions", async () => {
        const resetMock = vi.fn();
        const adminError = Object.assign(new Error("admin crashed"), { digest: "digest-admin" });
        const { default: AdminError } = await import("./admin/error");

        render(<AdminError error={adminError} reset={resetMock} />);

        expect(screen.getByRole("heading", { name: "管理后台加载失败" })).toBeTruthy();
        expect(screen.getByText("加载管理后台时发生异常，我们已记录该问题。请稍后重试或返回首页。")).toBeTruthy();
        expect(screen.getByRole("button", { name: "返回首页" })).toBeTruthy();
        expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
        expect(screen.queryByText("Something went wrong!")).toBeNull();
        expect(screen.queryByText("Go Home")).toBeNull();
        expect(screen.queryByText("Retry")).toBeNull();
    });
});
