import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminShell } from "./admin-shell";

const {
    replaceMock,
    sessionExpiredMock,
    useCurrentUserMock,
    usePathnameMock,
    useSidebarStoreMock,
} = vi.hoisted(() => ({
    replaceMock: vi.fn(),
    sessionExpiredMock: vi.fn(),
    useCurrentUserMock: vi.fn(),
    usePathnameMock: vi.fn(),
    useSidebarStoreMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>{children}</a>
    ),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        replace: replaceMock,
    }),
    usePathname: () => usePathnameMock(),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) =>
        asChild ? <>{children}</> : <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-sheet", () => ({
    GlassSheet: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/hooks/use-current-user", () => ({
    useCurrentUser: (...args: unknown[]) => useCurrentUserMock(...args),
}));

vi.mock("@/hooks/use-sidebar", () => ({
    useSidebarStore: () => useSidebarStoreMock(),
}));

vi.mock("@/lib/auth-handler", () => ({
    authHandler: {
        sessionExpired: sessionExpiredMock,
    },
}));

const currentUser = {
    id: "admin-1",
    user_id: "admin-1",
    name: "管理员",
    display_name: "管理员",
    email: "admin@example.com",
    role: "admin" as const,
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
};

describe("AdminShell auth and role routing", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useCurrentUserMock.mockReturnValue({ data: null, error: null });
        usePathnameMock.mockReturnValue("/admin");
        useSidebarStoreMock.mockReturnValue({
            isCollapsed: false,
            toggleSidebar: vi.fn(),
            setSidebarState: vi.fn(),
        });
    });

    it("delegates auth expiry to authHandler instead of forcing a browser location jump", async () => {
        useCurrentUserMock.mockReturnValue({ data: null, error: { status: 401 } });

        render(
            <AdminShell currentUser={currentUser}>
                <div>admin content</div>
            </AdminShell>,
        );

        await waitFor(() => {
            expect(sessionExpiredMock).toHaveBeenCalledTimes(1);
        });
        expect(replaceMock).not.toHaveBeenCalled();
    });

    it("uses router replace for non-admin role fallback", async () => {
        useCurrentUserMock.mockReturnValue({
            data: {
                ...currentUser,
                role: "user",
            },
            error: null,
        });

        render(
            <AdminShell currentUser={currentUser}>
                <div>admin content</div>
            </AdminShell>,
        );

        await waitFor(() => {
            expect(replaceMock).toHaveBeenCalledWith("/");
        });
        expect(sessionExpiredMock).not.toHaveBeenCalled();
    });

    it("exposes the AI examiner management entry in the admin sidebar", () => {
        useCurrentUserMock.mockReturnValue({ data: currentUser, error: null });
        usePathnameMock.mockReturnValue("/admin/curriculum-practice/examiner-agents");

        render(
            <AdminShell currentUser={currentUser}>
                <div>admin content</div>
            </AdminShell>,
        );

        const examinerLinks = screen.getAllByRole("link", { name: /AI 考官管理/ });
        expect(examinerLinks.some((link) => link.getAttribute("href") === "/admin/curriculum-practice/examiner-agents"))
            .toBe(true);
    });
});
