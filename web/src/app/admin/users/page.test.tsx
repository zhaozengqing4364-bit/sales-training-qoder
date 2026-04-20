import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UsersPage from "./page";

const {
    pushMock,
    successToastMock,
    errorToastMock,
    getUsersMock,
    getOperatingPackMock,
    createUserMock,
    updateUserMock,
    suspendUserMock,
    activateUserMock,
    deleteUserMock,
    exportUsersMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    successToastMock: vi.fn(),
    errorToastMock: vi.fn(),
    getUsersMock: vi.fn(),
    getOperatingPackMock: vi.fn(),
    createUserMock: vi.fn(),
    updateUserMock: vi.fn(),
    suspendUserMock: vi.fn(),
    activateUserMock: vi.fn(),
    deleteUserMock: vi.fn(),
    exportUsersMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: successToastMock,
        error: errorToastMock,
    }),
}));

vi.mock("@/components/ui/glass-modal", () => ({
    Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/glass-tooltip", () => ({
    TooltipProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
    Tooltip: ({ children }: { children: ReactNode }) => <>{children}</>,
    TooltipTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    TooltipContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/mobile-table-card", () => ({
    MobileTableCard: ({ children, title }: { children?: ReactNode; title?: ReactNode }) => (
        <div>
            <div>{title}</div>
            {children}
        </div>
    ),
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
    ConfirmDialog: () => null,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getUsers: getUsersMock,
                createUser: createUserMock,
                updateUser: updateUserMock,
                suspendUser: suspendUserMock,
                activateUser: activateUserMock,
                deleteUser: deleteUserMock,
                exportUsers: exportUsersMock,
            },
            analytics: {
                ...actual.api.analytics,
                getOperatingPack: getOperatingPackMock,
            },
        },
    };
});

describe("UsersPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        successToastMock.mockReset();
        errorToastMock.mockReset();
        getUsersMock.mockReset();
        getOperatingPackMock.mockReset();
        createUserMock.mockReset();
        updateUserMock.mockReset();
        suspendUserMock.mockReset();
        activateUserMock.mockReset();
        deleteUserMock.mockReset();
        exportUsersMock.mockReset();

        getUsersMock.mockResolvedValue({
            items: [],
            total: 0,
            page: 1,
            page_size: 10,
            has_more: false,
        });
    });

    it("falls back to the shared empty manager-lite lists when the operating-pack payload omits manager_lists", async () => {
        getOperatingPackMock.mockResolvedValue({
            score_basis: "session_evidence_projection_evaluable_only",
            weekly_summary: {
                window_days: 7,
                window_start: "2026-03-19T00:00:00Z",
                window_end: "2026-03-26T00:00:00Z",
                completed_sessions: 0,
                evaluable_sessions: 0,
                not_evaluable_sessions: 0,
                degraded_sessions: 0,
                active_departments: 0,
                at_risk_users: 0,
                improving_users: 0,
                top_issue_family: null,
                top_blocker_family: null,
                top_not_evaluable_reason: null,
                top_degraded_reason: null,
            },
            cohort_issue_buckets: [],
            department_issue_buckets: [],
            repeated_blocker_families: [],
            degradation_breakdown: {
                not_evaluable_reasons: [],
                degraded_reasons: [],
            },
        });

        render(<UsersPage />);

        await waitFor(() => {
            expect(getOperatingPackMock).toHaveBeenCalledWith({
                time_range: "7d",
                limit: 10,
                inactive_days: 7,
            });
        });

        expect(await screen.findByText("本周经营名单 drill-in")).toBeTruthy();
        expect(screen.getByText("当前没有风险成员。")).toBeTruthy();
        expect(screen.getByText("当前没有连续未练成员。")).toBeTruthy();
        expect(screen.getByText("当前没有显著回升成员。")).toBeTruthy();
    });
});
