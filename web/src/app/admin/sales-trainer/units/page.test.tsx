import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerUnitsPage from "./page";

const {
    pushMock,
    listUnitsMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    listUnitsMock: vi.fn(),
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
                    listUnits: listUnitsMock,
                    publishUnit: vi.fn(),
                    archiveUnit: vi.fn(),
                },
            },
        },
    };
});

describe("SalesTrainerUnitsPage", () => {
    beforeEach(() => {
        listUnitsMock.mockResolvedValue({
            items: [
                {
                    unit_id: "unit-1",
                    name: "做题训练",
                    description: "列表页项目",
                    unit_type: "quiz",
                    config: {},
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
});
