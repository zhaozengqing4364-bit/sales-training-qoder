import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ManagerLitePanel } from "./manager-lite-panel";

const { onRemindMock } = vi.hoisted(() => ({
    onRemindMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

describe("ManagerLitePanel", () => {
    beforeEach(() => {
        onRemindMock.mockReset();
        onRemindMock.mockResolvedValue(undefined);
    });

    it("adds a direct report CTA for not-passed sessions while keeping remind action", async () => {
        render(
            <ManagerLitePanel
                data={{
                    not_passed: [
                        {
                            user_id: "user-1",
                            user_name: "张三",
                            department: "销售一部",
                            overall_result: "fail",
                            session_id: "session-1",
                            session_start_time: "2026-03-23T09:00:00Z",
                        },
                    ],
                    inactive_streak: [],
                    improving: [],
                }}
                onRemind={onRemindMock}
            />,
        );

        const reportLink = screen.getByRole("link", { name: "查看报告" }) as HTMLAnchorElement;
        expect(reportLink.getAttribute("href")).toBe("/practice/session-1/report");

        fireEvent.click(screen.getByRole("button", { name: "一键提醒" }));

        await waitFor(() => {
            expect(onRemindMock).toHaveBeenCalledWith("user-1");
        });
    });
});
