import { render, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { durableErrorMock, fetchMock } = vi.hoisted(() => ({
    durableErrorMock: vi.fn(),
    fetchMock: vi.fn(),
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

function ThrowOnRender(): never {
    throw new Error("boundary exploded");
}

describe("frontend route error reporting seam", () => {
    const originalApiUrl = process.env.NEXT_PUBLIC_API_URL;

    beforeEach(() => {
        process.env.NEXT_PUBLIC_API_URL = "http://localhost:3444/api/v1";
        durableErrorMock.mockReset();
        fetchMock.mockReset();
        fetchMock.mockResolvedValue({ ok: true, status: 202, json: async () => ({ accepted: true }) });
        vi.stubGlobal("fetch", fetchMock);
        vi.spyOn(console, "error").mockImplementation(() => {});
    });

    afterEach(() => {
        process.env.NEXT_PUBLIC_API_URL = originalApiUrl;
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

    it("posts ErrorBoundary crashes to the release-truth analytics route with cookie-safe keepalive semantics", async () => {
        render(
            <ErrorBoundary>
                <ThrowOnRender />
            </ErrorBoundary>,
        );

        await waitFor(() => {
            expect(fetchMock).toHaveBeenCalledWith(
                "http://localhost:3444/api/v1/analytics/error",
                expect.objectContaining({
                    method: "POST",
                    keepalive: true,
                    headers: expect.objectContaining({
                        "Content-Type": "application/json",
                    }),
                }),
            );
        });

        const request = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
        const body = JSON.parse(String(request?.body ?? "{}"));

        expect(body).toMatchObject({
            error: "boundary exploded",
            source: "react.error-boundary",
            boundary: "ErrorBoundary",
            componentStack: expect.any(String),
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
