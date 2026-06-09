import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerOperationLogsPage from "./page";

const {
    listOperationLogsMock,
} = vi.hoisted(() => ({
    listOperationLogsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/operation-logs",
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    listOperationLogs: listOperationLogsMock,
                },
            },
        },
    };
});

describe("SalesTrainerOperationLogsPage", () => {
    beforeEach(() => {
        listOperationLogsMock.mockReset();
        listOperationLogsMock.mockResolvedValue({
            items: [
                {
                    log_id: "log-1",
                    actor_id: "admin-1",
                    actor_role: "admin",
                    action: "exam_paper_updated",
                    target_type: "sales_trainer_exam_paper",
                    target_id: "paper-1",
                    request_id: null,
                    ip_address: null,
                    user_agent: null,
                    metadata: {
                        previous: {
                            title: "商务技巧考卷 (副本)",
                            status: "draft",
                            unit_id: "unit-1",
                            module_key: "business_skills",
                            paper_key: "newcomer_business_skills_paper_v1",
                        },
                        next: {
                            title: "商务技巧考卷（草稿验证）",
                            status: "draft",
                            unit_id: "unit-1",
                            module_key: "business_skills",
                            paper_key: "newcomer_business_skills_paper_v1",
                        },
                        changed_fields: ["title", "module_key", "unit_id"],
                    },
                    created_at: "2026-06-03T09:00:00Z",
                },
            ],
            total: 1,
        });
    });

    it("shows business audit summaries before raw diagnostic payloads", async () => {
        render(<SalesTrainerOperationLogsPage />);

        await waitFor(() => {
            expect(listOperationLogsMock).toHaveBeenCalledWith({ limit: 100 });
        });

        expect(screen.getByText("考卷已更新")).toBeTruthy();
        expect(screen.getByText("管理员 · admin-1")).toBeTruthy();
        expect(screen.getByText("考卷")).toBeTruthy();
        expect(screen.queryByText(/MVP/)).toBeNull();
        expect(screen.getByText("标题：商务技巧考卷 (副本) → 商务技巧考卷（草稿验证）")).toBeTruthy();
        expect(screen.getByText("变更字段：标题、所属训练关卡、模块单元")).toBeTruthy();
        expect(screen.queryByText(/sales_trainer_exam_paper/)).toBeNull();
        expect(screen.queryByText(/module_key/)).toBeNull();
        expect(screen.queryByText(/unit_id/)).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "查看原始数据" }));

        expect(screen.getByText(/sales_trainer_exam_paper/)).toBeTruthy();
        expect(screen.getByText(/module_key/)).toBeTruthy();
    });
});
