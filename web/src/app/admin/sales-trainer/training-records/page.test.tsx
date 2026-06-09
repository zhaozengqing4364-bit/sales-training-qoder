import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerTrainingRecordsPage from "./page";

const {
    pushMock,
    listTrainingRecordsMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    listTrainingRecordsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/training-records",
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
                    listTrainingRecords: listTrainingRecordsMock,
                },
            },
        },
    };
});

describe("SalesTrainerTrainingRecordsPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        listTrainingRecordsMock.mockReset();
        listTrainingRecordsMock.mockResolvedValue({
            items: [
                {
                    record_id: "attempt-1",
                    record_type: "quiz_attempt",
                    path_key: "newcomer_training_path_v1",
                    path_revision_id: "path-revision-1",
                    path_revision_no: 1,
                    module_key: "business_skills",
                    legacy_snapshot_only: false,
                    unit_id: "unit-1",
                    unit_name: "商务技巧考卷",
                    unit_type: "quiz",
                    user_id: "user-1",
                    user_name: "张三",
                    user_email: "zhangsan@example.com",
                    user_department: "销售一部",
                    status: "scored",
                    score: 18,
                    max_score: 20,
                    passed: true,
                    submitted_at: "2026-05-28T00:00:00Z",
                    material_snapshot: null,
                    score_scheme_snapshot: null,
                    task_brief_snapshot: null,
                    audio_submission: null,
                    quiz_attempt: null,
                    operation_logs: [],
                },
            ],
            total: 1,
        });
    });

    it("shows business task names and Chinese statuses instead of raw backend ids", async () => {
        render(<SalesTrainerTrainingRecordsPage />);

        await waitFor(() => {
            expect(listTrainingRecordsMock).toHaveBeenCalledWith({ limit: 100 });
        });

        expect(screen.getByText("商务技巧考卷")).toBeTruthy();
        expect(screen.getByText("编号：unit-1")).toBeTruthy();
        expect(screen.getByText("已评分")).toBeTruthy();
        expect(screen.getByLabelText("学员编号")).toBeTruthy();
        expect(screen.queryByLabelText("用户 ID")).toBeNull();
        expect(screen.queryByText("scored")).toBeNull();
    });
});
