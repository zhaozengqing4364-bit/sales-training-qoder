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

const trainingManagerUser = {
    id: "mgr-1",
    name: "王经理",
    display_name: "王经理",
    email: "manager@example.com",
    role: "training_manager",
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

    it("exposes the learner newcomer training path entry from the shared sidebar nav", () => {
        render(<SidebarContent currentUser={learnerUser} />);

        const salesTrainerLink = screen.getByRole("menuitem", { name: "新人训练路径" }) as HTMLAnchorElement;
        expect(salesTrainerLink.getAttribute("href")).toBe("/sales-trainer");
    });

    it("keeps the profile affordance reachable on the expanded learner user menu", async () => {
        render(<SidebarContent currentUser={learnerUser} />);

        const profileLink = await screen.findByRole("link", { name: "编辑资料" }) as HTMLAnchorElement;
        expect(profileLink.getAttribute("href")).toBe("/profile");
    });

    it("keeps the profile affordance reachable in collapsed mode even when learner fields are missing", async () => {
        render(
            <SidebarContent
                currentUser={{
                    ...learnerUser,
                    display_name: "",
                    email: "",
                }}
                isCollapsed={true}
            />,
        );

        const profileLink = await screen.findByRole("link", { name: "编辑资料" }) as HTMLAnchorElement;
        expect(profileLink.getAttribute("href")).toBe("/profile");
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

describe("SidebarContent training_manager team entry", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        logoutMock.mockResolvedValue(undefined);
        usePathnameMock.mockReturnValue("/team");
        useParamsMock.mockReturnValue({});
    });

    it("shows the team entry only for training_manager role", () => {
        render(<SidebarContent currentUser={trainingManagerUser} />);

        const teamLink = screen.getByRole("menuitem", { name: "我的团队" }) as HTMLAnchorElement;
        expect(teamLink.getAttribute("href")).toBe("/team");
    });

    it("does not show the team entry for learner role", () => {
        render(<SidebarContent currentUser={learnerUser} />);

        expect(screen.queryByRole("menuitem", { name: "我的团队" })).toBeNull();
    });

    it("does not show the team entry when currentUser is missing", () => {
        render(<SidebarContent currentUser={null} />);

        expect(screen.queryByRole("menuitem", { name: "我的团队" })).toBeNull();
    });
});
