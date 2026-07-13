import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AdminShell } from "./admin-shell";
import type { CurrentUser } from "@/lib/auth/current-user";

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

vi.mock("@/lib/query/sales-trainer-admin", () => ({
    salesTrainerAdminCapabilitiesQueryOptions: () => ({
        queryKey: ["test", "sales-trainer-capabilities"],
        queryFn: async () => ({ capabilities: { admin_full_access: true } }),
        staleTime: 300_000,
    }),
}));

const currentUser: CurrentUser = {
    id: "admin-1",
    user_id: "admin-1",
    name: "管理员",
    display_name: "管理员",
    email: "admin@example.com",
    role: "admin",
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
};

function renderShell(children: ReactNode, user = currentUser) {
    const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false } },
    });
    return render(
        <QueryClientProvider client={queryClient}>
            <AdminShell currentUser={user}>{children}</AdminShell>
        </QueryClientProvider>,
    );
}

describe("AdminShell auth and role routing", () => {
    afterEach(() => {
        cleanup();
    });

    beforeEach(async () => {
        cleanup();
        await act(async () => {
            await Promise.resolve();
            await Promise.resolve();
        });
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

        renderShell(<div>admin content</div>);

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

        renderShell(<div>admin content</div>);

        await waitFor(() => {
            expect(replaceMock).toHaveBeenCalledWith("/");
        });
    });

    it("allows support users to stay inside the sales trainer admin area", async () => {
        usePathnameMock.mockReturnValue("/admin/sales-trainer/units");
        useCurrentUserMock.mockReturnValue({
            data: {
                ...currentUser,
                role: "support",
            },
            error: null,
        });

        renderShell(<div>sales trainer content</div>, { ...currentUser, role: "support" });

        await waitFor(() => {
            expect(screen.getByText("sales trainer content")).toBeTruthy();
        });
        expect(replaceMock).not.toHaveBeenCalled();
    });

    it("redirects support users away from non sales trainer admin pages", async () => {
        usePathnameMock.mockReturnValue("/admin/users");
        useCurrentUserMock.mockReturnValue({
            data: {
                ...currentUser,
                role: "support",
            },
            error: null,
        });

        renderShell(<div>admin content</div>, { ...currentUser, role: "support" });

        await waitFor(() => {
            expect(replaceMock).toHaveBeenCalledWith("/admin/newcomer-training/path");
        });
    });

    it("exposes the AI examiner management entry in the admin sidebar", () => {
        useCurrentUserMock.mockReturnValue({ data: currentUser, error: null });
        usePathnameMock.mockReturnValue("/admin/curriculum-practice/examiner-agents");

        renderShell(<div>admin content</div>);

        const examinerLinks = screen.getAllByRole("link", { name: /AI 考官管理/ });
        expect(examinerLinks.some((link) => link.getAttribute("href") === "/admin/curriculum-practice/examiner-agents"))
            .toBe(true);
    });
});
