import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerOperationLogsPage from "./page";

const {
    getCapabilitiesMock,
    listOperationLogsMock,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
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
                    getCapabilities: getCapabilitiesMock,
                    listOperationLogs: listOperationLogsMock,
                },
            },
        },
    };
});

function capabilities(overrides: Record<string, boolean> = {}) {
    const values = {
        admin_full_access: false,
        manage_content: false,
        manage_questions: false,
        manage_modules: false,
        manage_prompts: false,
        view_records: false,
        view_global_records: false,
        retry_jobs: false,
        regrade_history: false,
        view_logs: true,
        view_settings: false,
        ...overrides,
    };
    return {
        role: "support",
        role_label: "运营支持",
        capabilities: values,
        capability_keys: Object.entries(values)
            .filter(([, enabled]) => enabled)
            .map(([key]) => key),
    };
}

describe("SalesTrainerOperationLogsPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        listOperationLogsMock.mockReset();
        getCapabilitiesMock.mockResolvedValue(capabilities());
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

    it("fails closed before loading logs without view logs permission", async () => {
        getCapabilitiesMock.mockResolvedValue(capabilities({ view_logs: false }));

        render(<SalesTrainerOperationLogsPage />);

        expect(await screen.findByText("操作日志权限不足")).toBeTruthy();
        expect(listOperationLogsMock).not.toHaveBeenCalled();
        expect(screen.queryByText("暂无操作日志")).toBeNull();
        expect(screen.queryByText("正在加载操作日志...")).toBeNull();
    });

    it("keeps log load failures visible instead of rendering an empty audit table", async () => {
        listOperationLogsMock.mockRejectedValue(new Error("logs unavailable"));

        render(<SalesTrainerOperationLogsPage />);

        expect(await screen.findByText("操作日志加载失败")).toBeTruthy();
        expect(screen.getByText("logs unavailable")).toBeTruthy();
        expect(screen.queryByText("暂无操作日志")).toBeNull();
        expect(screen.queryByText("考卷已更新")).toBeNull();
    });
});
