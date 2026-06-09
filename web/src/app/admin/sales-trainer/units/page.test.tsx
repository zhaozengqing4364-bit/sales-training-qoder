import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerUnitsPage from "./page";

const {
    pushMock,
    listUnitsMock,
    listUnitRevisionsMock,
    rollbackUnitMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    listUnitsMock: vi.fn(),
    listUnitRevisionsMock: vi.fn(),
    rollbackUnitMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/units",
    useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: vi.fn(),
        error: vi.fn(),
    }),
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
                    publishUnit: vi.fn(),
                    archiveUnit: vi.fn(),
                },
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    listUnits: listUnitsMock,
                    publishUnit: vi.fn(),
                    archiveUnit: vi.fn(),
                    listUnitRevisions: listUnitRevisionsMock,
                    rollbackUnit: rollbackUnitMock,
                },
            },
        },
    };
});

describe("SalesTrainerUnitsPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        listUnitsMock.mockResolvedValue({
            items: [
                {
                    unit_id: "unit-1",
                    name: "做题训练",
                    description: "列表页项目",
                    unit_type: "quiz",
                    config: {
                        path: {
                            path_key: "newcomer_training_path_v1",
                            module_key: "business_skills",
                        },
                    },
                    status: "draft",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-05-28T00:00:00Z",
                    updated_at: "2026-05-28T00:00:00Z",
                    questions: [],
                },
            ],
            total: 1,
        });
        listUnitRevisionsMock.mockResolvedValue({
            items: [],
            total: 0,
        });
        rollbackUnitMock.mockResolvedValue({});
    });

    it("keeps the units list as an index page and routes creation to /new", async () => {
        render(<SalesTrainerUnitsPage />);

        await waitFor(() => {
            expect(listUnitsMock).toHaveBeenCalled();
        });

        expect(screen.getByText("列表页项目")).toBeTruthy();
        expect(screen.queryByText("训练单元名称")).toBeNull();
        fireEvent.click(screen.getByRole("button", { name: "新建训练单元" }));
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/units/new");
    });

    it("does not show copy draft action for published units", async () => {
        listUnitsMock.mockResolvedValueOnce({
            items: [
                {
                    unit_id: "unit-published",
                    name: "商务技巧",
                    description: "已发布训练单元",
                    unit_type: "quiz",
                    config: {
                        path: {
                            path_key: "newcomer_training_path_v1",
                            module_key: "business_skills",
                        },
                    },
                    status: "published",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-05-28T00:00:00Z",
                    updated_at: "2026-05-29T00:00:00Z",
                    questions: [],
                },
            ],
            total: 1,
        });

        render(<SalesTrainerUnitsPage />);

        await waitFor(() => {
            expect(screen.getByText("商务技巧")).toBeTruthy();
        });

        expect(screen.getByText("已发布")).toBeTruthy();
        expect(screen.queryByRole("button", { name: /复制草稿/ })).toBeNull();
    });

    it("opens revision history and rolls back with an explicit reason", async () => {
        listUnitsMock.mockResolvedValue({
            items: [
                {
                    unit_id: "unit-history",
                    name: "商务技巧",
                    description: "已发布训练单元",
                    unit_type: "quiz",
                    config: {
                        path: {
                            path_key: "newcomer_training_path_v1",
                            module_key: "business_skills",
                        },
                    },
                    status: "published",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-05-28T00:00:00Z",
                    updated_at: "2026-05-29T00:00:00Z",
                    questions: [{ question_id: "q1" }],
                },
            ],
            total: 1,
        });
        listUnitRevisionsMock.mockResolvedValue({
            items: [
                {
                    revision_id: "rev-2",
                    revision_no: 2,
                    status: "published",
                    change_class: "scoring_high_risk",
                    title: "商务技巧新版",
                    question_count: 1,
                    is_active: true,
                    is_working: false,
                    source_revision_id: "rev-1",
                    payload_hash: "hash-2",
                    reason: "发布新版",
                    trace_id: "trace-2",
                    created_by: "admin-1",
                    published_by: "admin-1",
                    created_at: "2026-05-29T00:00:00Z",
                    published_at: "2026-05-29T00:00:00Z",
                },
                {
                    revision_id: "rev-1",
                    revision_no: 1,
                    status: "published",
                    change_class: "semantic",
                    title: "商务技巧旧版",
                    question_count: 1,
                    is_active: false,
                    is_working: false,
                    source_revision_id: null,
                    payload_hash: "hash-1",
                    reason: "初始发布",
                    trace_id: "trace-1",
                    created_by: "admin-1",
                    published_by: "admin-1",
                    created_at: "2026-05-28T00:00:00Z",
                    published_at: "2026-05-28T00:00:00Z",
                },
            ],
            total: 2,
        });

        render(<SalesTrainerUnitsPage />);

        await waitFor(() => {
            expect(screen.getByText("商务技巧")).toBeTruthy();
        });
        fireEvent.click(screen.getByRole("button", { name: /历史版本/ }));

        await waitFor(() => {
            expect(screen.getByText("历史版本：商务技巧")).toBeTruthy();
        });
        expect(screen.getByText("回滚只影响后续学员；已经开始的学习、考试和录音记录继续保留当时快照。")).toBeTruthy();
        fireEvent.change(screen.getByLabelText("回滚原因（第 1 版）"), {
            target: { value: "恢复试运行前版本" },
        });
        fireEvent.click(screen.getByRole("button", { name: "回滚到第 1 版" }));

        await waitFor(() => {
            expect(rollbackUnitMock).toHaveBeenCalledWith("unit-history", {
                target_revision_id: "rev-1",
                reason: "恢复试运行前版本",
            });
        });
    });
});
