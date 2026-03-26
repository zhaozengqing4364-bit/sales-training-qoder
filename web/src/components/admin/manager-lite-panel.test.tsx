import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ManagerLitePanel } from "./manager-lite-panel";

const { onRemindMock, getUserHrefMock } = vi.hoisted(() => ({
    onRemindMock: vi.fn(),
    getUserHrefMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

describe("ManagerLitePanel", () => {
    beforeEach(() => {
        onRemindMock.mockReset();
        getUserHrefMock.mockReset();
        onRemindMock.mockResolvedValue(undefined);
        getUserHrefMock.mockImplementation(({ kind, userId }: { kind: string; userId: string }) => {
            if (kind === "not_passed") {
                return `/admin/users/${userId}?focusIssueFamily=evidence_gap&focusNote=%E5%85%88%E5%AF%B9%E7%85%A7%E6%9C%80%E8%BF%91%E7%BB%9F%E4%B8%80%E6%8A%A5%E5%91%8A%E8%A1%A5%E8%AF%81%E6%8D%AE`;
            }
            return `/admin/users/${userId}`;
        });
    });

    it("keeps manager-lite copy on the same evidence line and links supervisors into current user detail surfaces", async () => {
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
                getUserHref={getUserHrefMock}
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

        const focusLink = screen.getByRole("link", { name: "查看并设重点" }) as HTMLAnchorElement;
        expect(focusLink.getAttribute("href")).toBe(
            "/admin/users/user-1?focusIssueFamily=evidence_gap&focusNote=%E5%85%88%E5%AF%B9%E7%85%A7%E6%9C%80%E8%BF%91%E7%BB%9F%E4%B8%80%E6%8A%A5%E5%91%8A%E8%A1%A5%E8%AF%81%E6%8D%AE",
        );

        const inspectLink = screen.getByRole("link", { name: "查看详情" }) as HTMLAnchorElement;
        expect(inspectLink.getAttribute("href")).toBe("/admin/users/user-2");

        fireEvent.click(screen.getByRole("button", { name: "一键提醒" }));

        await waitFor(() => {
            expect(onRemindMock).toHaveBeenCalledWith("user-1");
        });
    });
});
