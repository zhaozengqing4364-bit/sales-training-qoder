import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PracticeLayout from "./layout";

const {
    usePathnameMock,
    useParamsMock,
} = vi.hoisted(() => ({
    usePathnameMock: vi.fn(),
    useParamsMock: vi.fn(),
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

describe("PracticeLayout learner help entry", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        usePathnameMock.mockReturnValue("/practice/session-42");
        useParamsMock.mockReturnValue({ sessionId: "session-42" });
    });

    it("renders the shared learner help entry with route and session context", () => {
        render(
            <PracticeLayout>
                <div>practice content</div>
            </PracticeLayout>,
        );

        expect(screen.getByRole("button", { name: "帮助与反馈" })).toBeTruthy();
        expect(screen.getByText("/practice/session-42")).toBeTruthy();
        expect(screen.getByText("session-42")).toBeTruthy();
    });

    it("falls back to generic help copy when route context is missing or malformed", () => {
        usePathnameMock.mockReturnValue("/practice/session-42?token=secret-token");
        useParamsMock.mockReturnValue({ sessionId: ["session-42", "extra"] });

        render(
            <PracticeLayout>
                <div>practice content</div>
            </PracticeLayout>,
        );

        expect(screen.getByText("/practice/session-42")).toBeTruthy();
        expect(screen.queryByText(/secret-token/)).toBeNull();
        expect(screen.queryByText(/extra/)).toBeNull();
    });
});
