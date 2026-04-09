import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

const { resetMock, consoleErrorMock } = vi.hoisted(() => ({
    resetMock: vi.fn(),
    consoleErrorMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
}));

describe("Practice route error boundary", () => {
    afterEach(() => {
        vi.unstubAllEnvs();
        vi.unstubAllGlobals();
        vi.resetModules();
        vi.clearAllMocks();
    });

    it("renders retry and safe navigation for the live practice route", async () => {
        vi.stubEnv("NODE_ENV", "development");
        vi.stubGlobal("console", { ...console, error: consoleErrorMock });

        const { default: PracticeRouteError } = await import("./error");

        render(
            <PracticeRouteError
                error={new Error("practice crashed")}
                reset={resetMock}
            />,
        );

        expect(screen.getByRole("heading", { name: "训练页面暂时不可用" })).toBeTruthy();
        expect(screen.getByText("你可以先重试当前页面；如果仍失败，请先返回训练大厅重新进入本场练习。"))
            .toBeTruthy();
        expect(screen.getByText("practice crashed")).toBeTruthy();
        expect(screen.getByRole("link", { name: "返回训练大厅" }).getAttribute("href")).toBe("/training");

        fireEvent.click(screen.getByRole("button", { name: "重试" }));
        expect(resetMock).toHaveBeenCalledTimes(1);
        expect(consoleErrorMock).toHaveBeenCalledWith("[LearnerRouteErrorState:practice-live]", expect.any(Error));
    });

    it("hides raw diagnostics in production while keeping recovery actions", async () => {
        vi.stubEnv("NODE_ENV", "production");
        vi.stubGlobal("console", { ...console, error: consoleErrorMock });

        const { default: PracticeRouteError } = await import("./error");

        render(
            <PracticeRouteError
                error={{ digest: "digest-only" } as Error & { digest?: string }}
                reset={resetMock}
            />,
        );

        expect(screen.getByRole("heading", { name: "训练页面暂时不可用" })).toBeTruthy();
        expect(screen.queryByText("digest-only")).toBeNull();
        expect(screen.getByRole("button", { name: "重试" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "返回训练大厅" }).getAttribute("href")).toBe("/training");
        expect(consoleErrorMock).toHaveBeenCalledWith(
            "[LearnerRouteErrorState:practice-live]",
            { digest: "digest-only" },
        );
    });
});
