import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerPathsPage from "./page";

const { listUnitsMock, pushMock } = vi.hoisted(() => ({
    listUnitsMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/paths",
    useRouter: () => ({ push: pushMock }),
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
                    listUnits: listUnitsMock,
                },
            },
        },
    };
});

describe("SalesTrainerPathsPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        listUnitsMock.mockResolvedValue({
            items: [
                {
                    unit_id: "unit-1",
                    name: "产品定位训练",
                    description: null,
                    unit_type: "quiz",
                    config: {
                        path: {
                            enabled: true,
                            path_key: "new_seller",
                            path_title: "新人销售闯关",
                            goal_title: "掌握首次客户沟通",
                            level_title: "第一关：产品定位",
                            order_index: 1,
                            completion_rule: "passed",
                            unlock_after_unit_ids: [],
                        },
                    },
                    status: "published",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-05-28T00:00:00Z",
                    updated_at: "2026-05-28T00:00:00Z",
                    questions: [],
                },
                {
                    unit_id: "unit-2",
                    name: "录音表达训练",
                    description: null,
                    unit_type: "audio_scoring",
                    config: {
                        path: {
                            enabled: true,
                            path_key: "new_seller",
                            path_title: "新人销售闯关",
                            goal_title: "掌握首次客户沟通",
                            level_title: "第二关：录音表达",
                            order_index: 2,
                            completion_rule: "scored",
                            unlock_after_unit_ids: ["unit-1"],
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
            total: 2,
        });
    });

    it("groups unit path config into an admin path overview", async () => {
        render(<SalesTrainerPathsPage />);

        await waitFor(() => {
            expect(listUnitsMock).toHaveBeenCalledWith({
                include_archived: true,
                limit: 200,
            });
        });

        expect(screen.getByText("新人销售闯关")).toBeTruthy();
        expect(screen.getByText("掌握首次客户沟通")).toBeTruthy();
        expect(screen.getByText("第一关：产品定位")).toBeTruthy();
        expect(screen.getByText("第二关：录音表达")).toBeTruthy();
        expect(screen.getByText("1/2")).toBeTruthy();
        expect(screen.getByText("unit-1")).toBeTruthy();

        const editButtons = screen.getAllByRole("button", { name: "编辑关卡" });
        expect(editButtons).toHaveLength(2);
        fireEvent.click(editButtons[1]);
        expect(pushMock).toHaveBeenCalledWith("/admin/sales-trainer/units/unit-2/edit");
    });
});
