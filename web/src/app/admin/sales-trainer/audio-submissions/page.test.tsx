import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerAudioSubmissionsPage from "./page";

const {
    listAudioSubmissionsMock,
    pushMock,
} = vi.hoisted(() => ({
    listAudioSubmissionsMock: vi.fn(),
    pushMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/audio-submissions",
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
                    listAudioSubmissions: listAudioSubmissionsMock,
                },
            },
        },
    };
});

describe("SalesTrainerAudioSubmissionsPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        listAudioSubmissionsMock.mockReset();
        listAudioSubmissionsMock.mockResolvedValue({
            items: [
                {
                    submission_id: "sub-1",
                    unit_id: "unit-1",
                    user_id: "user-1",
                    user_name: "张三",
                    user_email: null,
                    user_department: "销售一部",
                    purpose: "ppt_explanation",
                    original_filename: "ppt.wav",
                    content_type: "audio/wav",
                    size_bytes: 1024,
                    storage_key: "sales-trainer/sub-1.wav",
                    file_hash: null,
                    duration_seconds: 90,
                    source_page: "/sales-trainer/audio/unit-1",
                    confirmed_material_version_id: null,
                    confirmed_material_at: null,
                    material_snapshot: null,
                    score_scheme_snapshot: null,
                    task_brief_snapshot: null,
                    status: "transcription_failed",
                    error_code: "[ASR_TIMEOUT]",
                    error_message: "ASR 服务超时",
                    created_at: "2026-06-03T08:00:00Z",
                    updated_at: "2026-06-03T08:01:00Z",
                    transcript: null,
                    score_result: null,
                },
            ],
            total: 1,
        });
    });

    it("shows Chinese submission status for ops diagnosis", async () => {
        render(<SalesTrainerAudioSubmissionsPage />);

        await waitFor(() => {
            expect(listAudioSubmissionsMock).toHaveBeenCalledWith({ limit: 100 });
        });

        expect(screen.getByText("ppt.wav")).toBeTruthy();
        expect(screen.getByText("转写失败")).toBeTruthy();
        expect(screen.getByText("audio/wav · 学员录音上传页")).toBeTruthy();
        expect(screen.queryByText("/sales-trainer/audio/unit-1")).toBeNull();
        expect(screen.queryByText("transcription_failed")).toBeNull();
    });
});
