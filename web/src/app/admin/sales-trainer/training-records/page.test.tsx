import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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
                    score: 16,
                    max_score: 20,
                    passed: false,
                    effective_score: {
                        score: 18,
                        max_score: 20,
                        passed: true,
                        source: "latest_regrade",
                        original_score: 16,
                        original_max_score: 20,
                        score_delta: 2,
                    },
                    latest_regrade: {
                        regrade_run_id: "run-1",
                        status: "completed",
                    },
                    score_explanation: {
                        summary: "错题已按新考卷版本重算。",
                    },
                    ability_profile: {
                        weak_dimensions: [],
                    },
                    remediation: {
                        needed: true,
                        action_label: "安排弱项复习",
                        reason: "重评后仍需补救。",
                        target_path: "/admin/sales-trainer/training-records/quiz_attempt/attempt-1",
                        priority: "medium",
                    },
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

    it("shows original score, effective score, regrade delta, remediation, and unified detail link", async () => {
        render(<SalesTrainerTrainingRecordsPage />);

        await waitFor(() => {
            expect(listTrainingRecordsMock).toHaveBeenCalledWith({ limit: 100 });
        });

        expect(screen.getByText("商务技巧考卷")).toBeTruthy();
        expect(screen.getByText("编号：unit-1")).toBeTruthy();
        expect(screen.getByText("18 / 20")).toBeTruthy();
        expect(screen.getByText("原始分 16 / 20")).toBeTruthy();
        expect(screen.getByText(/当前有效分 · 重评 \+2/)).toBeTruthy();
        expect(screen.getByText("安排弱项复习")).toBeTruthy();
        expect(screen.getByText("已评分")).toBeTruthy();
        expect(screen.getByLabelText("学员编号")).toBeTruthy();
        expect(screen.queryByLabelText("用户 ID")).toBeNull();
        expect(screen.queryByText("scored")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "查看详情" }));
        expect(pushMock).toHaveBeenCalledWith(
            "/admin/sales-trainer/training-records/quiz_attempt/attempt-1",
        );
    });
});
