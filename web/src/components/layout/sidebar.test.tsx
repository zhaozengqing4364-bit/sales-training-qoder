import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LearnerHelpEntry } from "./learner-help-entry";
import { SidebarContent } from "./sidebar";

const {
    usePathnameMock,
    useParamsMock,
    logoutMock,
} = vi.hoisted(() => ({
    usePathnameMock: vi.fn(),
    useParamsMock: vi.fn(),
    logoutMock: vi.fn(),
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

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            auth: {
                ...actual.api.auth,
                logout: logoutMock,
            },
        },
    };
});

vi.mock("@/lib/auth-handler", () => ({
    authHandler: {
        logout: vi.fn(),
    },
}));

const learnerUser = {
    id: "user-1",
    name: "王小明",
    display_name: "王小明",
    email: "learner@example.com",
    role: "user",
    department: "销售部",
};

describe("SidebarContent learner seams", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        logoutMock.mockResolvedValue(undefined);
        usePathnameMock.mockReturnValue("/history");
        useParamsMock.mockReturnValue({});
    });

    it("keeps the shared history entry available even when currentUser is missing", () => {
        render(<SidebarContent currentUser={null} />);

        const historyLink = screen.getByRole("menuitem", { name: "历史记录" }) as HTMLAnchorElement;
        expect(historyLink.getAttribute("href")).toBe("/history");
    });

    it("renders the compact learner help entry in collapsed sidebar mode with bounded route context", () => {
        usePathnameMock.mockReturnValue("/practice/session-123");
        useParamsMock.mockReturnValue({ sessionId: "session-123" });

        render(
            <SidebarContent
                currentUser={learnerUser}
                isCollapsed={true}
                footerSlot={<LearnerHelpEntry compact />}
            />,
        );

        expect(screen.getByRole("button", { name: "打开帮助与反馈" })).toBeTruthy();
        expect(screen.getByText("/practice/session-123")).toBeTruthy();
        expect(screen.getByText("session-123")).toBeTruthy();
    });
});
