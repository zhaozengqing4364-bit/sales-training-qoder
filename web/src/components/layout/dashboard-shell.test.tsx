import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardShell } from "./dashboard-shell";

const {
    sessionExpiredMock,
    useCurrentUserMock,
    usePathnameMock,
    useParamsMock,
    useSidebarStoreMock,
} = vi.hoisted(() => ({
    sessionExpiredMock: vi.fn(),
    useCurrentUserMock: vi.fn(),
    usePathnameMock: vi.fn(),
    useParamsMock: vi.fn(),
    useSidebarStoreMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => usePathnameMock(),
    useParams: () => useParamsMock(),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) =>
        asChild ? <>{children}</> : <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-modal", () => ({
    Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTrigger: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/glass-tooltip", () => ({
    TooltipProvider: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    Tooltip: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    TooltipTrigger: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    TooltipContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/glass-sheet", () => ({
    GlassSheet: ({ isOpen, children }: { isOpen: boolean; children: ReactNode }) => (
        isOpen ? <div data-testid="mobile-sheet">{children}</div> : null
    ),
}));

vi.mock("@/hooks/use-current-user", () => ({
    useCurrentUser: (...args: unknown[]) => useCurrentUserMock(...args),
}));

vi.mock("@/hooks/use-sidebar", () => ({
    useSidebarStore: () => useSidebarStoreMock(),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
    };
});

vi.mock("@/lib/auth-handler", () => ({
    authHandler: {
        sessionExpired: sessionExpiredMock,
    },
}));

const currentUser = {
    id: "user-1",
    user_id: "user-1",
    name: "王小明",
    display_name: "王小明",
    email: "learner@example.com",
    role: "user" as const,
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
};

describe("DashboardShell learner help entry", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useCurrentUserMock.mockReturnValue({ data: null, error: null });
        usePathnameMock.mockReturnValue("/history");
        useParamsMock.mockReturnValue({});
        useSidebarStoreMock.mockReturnValue({
            isCollapsed: false,
            toggleSidebar: vi.fn(),
            setSidebarState: vi.fn(),
        });
    });

    it("renders the learner help entry in the desktop shell and the mobile drawer", () => {
        render(
            <DashboardShell currentUser={currentUser}>
                <div>dashboard content</div>
            </DashboardShell>,
        );

        expect(screen.getByRole("button", { name: "帮助与反馈" })).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: /menu/i }));

        expect(screen.getByTestId("mobile-sheet")).toBeTruthy();
        expect(screen.getAllByRole("button", { name: "帮助与反馈" })).toHaveLength(2);
    });

    it("keeps the help entry render path local even when auth redirect is triggered", () => {
        useCurrentUserMock.mockReturnValue({ data: null, error: { status: 401 } });

        render(
            <DashboardShell currentUser={currentUser}>
                <div>dashboard content</div>
            </DashboardShell>,
        );

        expect(screen.getByRole("button", { name: "帮助与反馈" })).toBeTruthy();
        expect(sessionExpiredMock).toHaveBeenCalledTimes(1);
    });
});
