import { render, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { durableErrorMock } = vi.hoisted(() => ({
    durableErrorMock: vi.fn(),
}));

vi.mock("@/lib/debug", async (importOriginal) => {
    const actual = await importOriginal<typeof import("@/lib/debug")>();

    return {
        ...actual,
        debug: {
            ...actual.debug,
            durableError: durableErrorMock,
        },
    };
});

vi.mock("next/link", () => ({
    default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
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
        AlertTriangle: Icon,
        RefreshCw: Icon,
        Home: Icon,
        AlertCircle: Icon,
        RefreshCcw: Icon,
        ArrowLeft: Icon,
    };
});

import DashboardError from "@/app/(dashboard)/error";
import AdminError from "@/app/admin/error";
import { LearnerRouteErrorState } from "@/components/learner/learner-route-error-state";
import { AsyncErrorBoundary, ErrorBoundary } from "./ErrorBoundary";

function ThrowOnRender() {
    throw new Error("boundary exploded");
}

describe("frontend route error reporting seam", () => {
    beforeEach(() => {
        durableErrorMock.mockReset();
        vi.spyOn(console, "error").mockImplementation(() => {});
    });

    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("routes app error surfaces through debug.durableError", async () => {
        const dashboardError = Object.assign(new Error("dashboard failed"), { digest: "digest-dashboard" });
        const adminError = Object.assign(new Error("admin failed"), { digest: "digest-admin" });
        const learnerError = Object.assign(new Error("learner failed"), { digest: "digest-learner" });

        render(
            <>
                <DashboardError error={dashboardError} reset={vi.fn()} />
                <AdminError error={adminError} reset={vi.fn()} />
                <LearnerRouteErrorState error={learnerError} reset={vi.fn()} errorTag="practice-live" />
            </>,
        );

        await waitFor(() => {
            expect(durableErrorMock).toHaveBeenCalledWith(
                "route-error.dashboard",
                dashboardError,
                expect.objectContaining({ digest: "digest-dashboard" }),
            );
            expect(durableErrorMock).toHaveBeenCalledWith(
                "route-error.admin",
                adminError,
                expect.objectContaining({ digest: "digest-admin" }),
            );
            expect(durableErrorMock).toHaveBeenCalledWith(
                "route-error.learner",
                learnerError,
                expect.objectContaining({
                    digest: "digest-learner",
                    errorTag: "practice-live",
                }),
            );
        });
    });

    it("routes boundary crashes through debug.durableError with component context", async () => {
        render(
            <ErrorBoundary>
                <ThrowOnRender />
            </ErrorBoundary>,
        );

        await waitFor(() => {
            expect(durableErrorMock).toHaveBeenCalledWith(
                "react.error-boundary",
                expect.any(Error),
                expect.objectContaining({
                    componentStack: expect.any(String),
                }),
            );
        });
    });

    it("routes async boundary crashes through debug.durableError with component context", async () => {
        render(
            <AsyncErrorBoundary>
                <ThrowOnRender />
            </AsyncErrorBoundary>,
        );

        await waitFor(() => {
            expect(durableErrorMock).toHaveBeenCalledWith(
                "react.async-error-boundary",
                expect.any(Error),
                expect.objectContaining({
                    componentStack: expect.any(String),
                }),
            );
        });
    });
});
