import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import type { NotificationCenterViewModel } from "@/lib/newcomer-training/view-models";
import { NotificationCenter } from "./notification-center";

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>{children}</a>
    ),
}));

function model(overrides: Partial<NotificationCenterViewModel> = {}): NotificationCenterViewModel {
    return {
        items: [],
        total: 0,
        page: 1,
        pageSize: 20,
        hasMore: false,
        partialMessage: null,
        ...overrides,
    };
}

describe("NotificationCenter", () => {
    it("explains the durable empty state and recovery location", () => {
        render(<NotificationCenter model={model()} />);

        expect(screen.getByRole("heading", { name: "当前没有新的训练通知" })).toBeTruthy();
        expect(screen.getByText(/处理进度和结果入口会保存在这里/)).toBeTruthy();
        expect(screen.getByRole("link", { name: "返回当前训练" }).getAttribute("href")).toBe("/newcomer-training");
    });

    it("keeps partial data visible with result links and bounded pagination", () => {
        render(<NotificationCenter model={model({
            page: 2,
            hasMore: true,
            partialMessage: "复核结果暂时无法更新，已保留其余可用结果。",
            items: [{
                id: "task:task-1",
                kind: "task",
                kindLabel: "后台任务",
                title: "录音评估",
                description: "结果已经安全保存。",
                statusLabel: "已完成",
                createdAt: "2026-07-17T08:00:00Z",
                href: "/newcomer-training/activities/audio-1",
                actionLabel: "查看业务结果",
                unread: false,
                canCancel: false,
            }],
        })} />);

        expect(screen.getByRole("status").textContent).toContain("复核结果暂时无法更新");
        expect(screen.getByRole("link", { name: "查看业务结果" }).getAttribute("href")).toBe("/newcomer-training/activities/audio-1");
        expect(screen.getByRole("link", { name: "上一页" }).getAttribute("href")).toBe("/newcomer-training/notifications?page=1");
        expect(screen.getByRole("link", { name: "下一页" }).getAttribute("href")).toBe("/newcomer-training/notifications?page=3");
    });
});
