import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RecordsPage from "./page";

const {
    errorToastMock,
    successToastMock,
    deleteTrainingRecordMock,
    getTrainingRecordsMock,
} = vi.hoisted(() => ({
    errorToastMock: vi.fn(),
    successToastMock: vi.fn(),
    deleteTrainingRecordMock: vi.fn(),
    getTrainingRecordsMock: vi.fn(),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) =>
        asChild ? <>{children}</> : <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
}));

vi.mock("@/components/ui/glass-modal", () => ({
    Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/components/ui/glass-tooltip", () => ({
    TooltipProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
    Tooltip: ({ children }: { children: ReactNode }) => <>{children}</>,
    TooltipTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
    TooltipContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/mobile-table-card", () => ({
    MobileTableCard: ({ children, title, actions }: { children?: ReactNode; title?: ReactNode; actions?: ReactNode }) => (
        <div>
            <div>{title}</div>
            <div>{actions}</div>
            {children}
        </div>
    ),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: successToastMock,
        error: errorToastMock,
        showToast: vi.fn(),
    }),
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
    ConfirmDialog: ({ open, title, description, confirmText, onConfirm }: {
        open: boolean;
        title: string;
        description: string;
        confirmText?: string;
        onConfirm: () => void;
    }) => (
        open ? (
            <div>
                <div>{title}</div>
                <div>{description}</div>
                <button type="button" onClick={onConfirm}>{confirmText ?? "确认"}</button>
            </div>
        ) : null
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getTrainingRecords: getTrainingRecordsMock,
                deleteTrainingRecord: deleteTrainingRecordMock,
            },
        },
    };
});

describe("RecordsPage", () => {
    beforeEach(() => {
        errorToastMock.mockReset();
        successToastMock.mockReset();
        deleteTrainingRecordMock.mockReset();
        getTrainingRecordsMock.mockReset();

        getTrainingRecordsMock.mockResolvedValue([
            {
                id: "session-1",
                title: "首通销售演练",
                scenario_type: "sales",
                overall_score: 88,
                duration_seconds: 120,
                start_time: "2026-04-11T12:00:00Z",
                feedback_summary: "表现稳定",
            },
        ]);
    });

    it("routes record deletion through the shared confirm dialog before mutating state", async () => {
        deleteTrainingRecordMock.mockResolvedValue(undefined);
        const nativeConfirmSpy = vi.spyOn(window, "confirm").mockImplementation(() => true);

        render(<RecordsPage />);

        await waitFor(() => {
            expect(getTrainingRecordsMock).toHaveBeenCalled();
        });

        fireEvent.click(screen.getAllByRole("button", { name: "删除记录 首通销售演练" })[0]);

        expect(screen.getByText("删除训练记录")).toBeTruthy();
        expect(screen.getByText("确定要删除「首通销售演练」吗？")).toBeTruthy();
        expect(deleteTrainingRecordMock).not.toHaveBeenCalled();
        expect(nativeConfirmSpy).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "删除" }));

        await waitFor(() => {
            expect(deleteTrainingRecordMock).toHaveBeenCalledWith("session-1");
        });
        expect(successToastMock).toHaveBeenCalledWith("删除成功");
    });

    it("keeps deletion failures in toast feedback instead of falling back to alert dialogs", async () => {
        deleteTrainingRecordMock.mockRejectedValueOnce(new Error("删除失败"));
        const nativeAlertSpy = vi.spyOn(window, "alert").mockImplementation(() => undefined);

        render(<RecordsPage />);

        await waitFor(() => {
            expect(getTrainingRecordsMock).toHaveBeenCalled();
        });

        fireEvent.click(screen.getAllByRole("button", { name: "删除记录 首通销售演练" })[0]);
        fireEvent.click(screen.getByRole("button", { name: "删除" }));

        await waitFor(() => {
            expect(deleteTrainingRecordMock).toHaveBeenCalledWith("session-1");
        });

        expect(errorToastMock).toHaveBeenCalledWith("删除失败");
        expect(nativeAlertSpy).not.toHaveBeenCalled();
    });

    it("shows load failures instead of silently rendering an empty table", async () => {
        getTrainingRecordsMock.mockRejectedValueOnce(new Error("records offline"));

        render(<RecordsPage />);

        expect(await screen.findByText("训练记录加载失败")).toBeTruthy();
        expect(screen.getByText("records offline")).toBeTruthy();
        expect(errorToastMock).toHaveBeenCalledWith("records offline");
    });

    it("disables next page when fewer than one page of records is returned", async () => {
        render(<RecordsPage />);

        await waitFor(() => {
            expect(getTrainingRecordsMock).toHaveBeenCalled();
        });

        expect((screen.getByRole("button", { name: "下一页" }) as HTMLButtonElement).disabled).toBe(true);
    });
});
