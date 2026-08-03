import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Page from "./page";

const serverApiGet = vi.hoisted(() => vi.fn());

vi.mock("@/lib/server-api", () => ({ serverApiGet }));

describe("FoundationNotificationsPage", () => {
    beforeEach(() => {
        serverApiGet.mockReset();
        serverApiGet.mockImplementation((path: string) => {
            if (path.startsWith("/newcomer-training/notifications")) {
                return Promise.resolve({ items: [], total: 0, page: 2, page_size: 20, has_more: false });
            }
            if (path.startsWith("/newcomer-training/tasks")) {
                return Promise.resolve({ items: [], total: 0, page: 2, page_size: 20, has_more: false });
            }
            return Promise.reject(new Error("档案暂时不可用"));
        });
    });

    it("loads persistent sources in parallel and preserves partial results", async () => {
        render(await Page({ searchParams: Promise.resolve({ page: "2" }) }));

        expect(serverApiGet).toHaveBeenCalledTimes(3);
        expect(serverApiGet).toHaveBeenCalledWith("/newcomer-training/notifications?page=2&page_size=20");
        expect(serverApiGet).toHaveBeenCalledWith("/newcomer-training/tasks?page=2&page_size=20");
        expect(serverApiGet).toHaveBeenCalledWith("/newcomer-training/dossier");
        expect(screen.getByRole("status").textContent).toContain("复核结果暂时无法更新");
        expect(screen.getByRole("heading", { name: "当前没有新的训练通知" })).toBeTruthy();
    });
});
