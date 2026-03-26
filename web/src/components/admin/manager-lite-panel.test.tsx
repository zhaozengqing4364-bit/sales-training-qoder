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

    it("keeps manager-lite copy on the same evidence line as admin analytics", async () => {
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
                    improving: [
                        {
                            user_id: "user-2",
                            user_name: "李四",
                            department: "销售二部",
                            pass_gain: 25,
                            baseline_pass_rate: 25,
                            current_pass_rate: 50,
                        },
                    ],
                }}
                onRemind={onRemindMock}
            />,
        );

        expect(screen.getByText("仅统计统一训练证据里已完成且可评估但未通过的训练。"))
            .toBeTruthy();
        expect(screen.getByText("通过率提升只按可评估的已完成训练计算。"))
            .toBeTruthy();
        expect(screen.getByText("先看统一报告，再决定是否提醒。"))
            .toBeTruthy();
        expect(screen.getByText("统一结果：未通过（已排除证据不足）")).toBeTruthy();

        const reportLink = screen.getByRole("link", { name: "查看统一报告" }) as HTMLAnchorElement;
        expect(reportLink.getAttribute("href")).toBe("/practice/session-1/report");

        fireEvent.click(screen.getByRole("button", { name: "一键提醒" }));

        await waitFor(() => {
            expect(onRemindMock).toHaveBeenCalledWith("user-1");
        });
    });
});
