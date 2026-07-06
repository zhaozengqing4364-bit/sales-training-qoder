import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerAudioSubmissionsPage from "./page";

const {
    getCapabilitiesMock,
    listAudioSubmissionsMock,
    pushMock,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
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
                    getCapabilities: getCapabilitiesMock,
                    listAudioSubmissions: listAudioSubmissionsMock,
                },
            },
        },
    };
});

describe("SalesTrainerAudioSubmissionsPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        pushMock.mockReset();
        listAudioSubmissionsMock.mockReset();
        getCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_questions: false,
                manage_modules: false,
                manage_prompts: false,
                view_records: true,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_logs: false,
                view_settings: false,
            },
            capability_keys: ["view_records"],
        });
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

    it("keeps list load failures visible instead of rendering an empty recording list", async () => {
        listAudioSubmissionsMock.mockRejectedValueOnce(new Error("audio list unavailable"));

        render(<SalesTrainerAudioSubmissionsPage />);

        expect(await screen.findByText("录音记录加载失败")).toBeTruthy();
        expect(screen.getByText("audio list unavailable")).toBeTruthy();
        expect(screen.queryByText("暂无录音记录")).toBeNull();
        expect(screen.queryByText("ppt.wav")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "重新加载录音记录" }));

        await waitFor(() => {
            expect(listAudioSubmissionsMock).toHaveBeenCalledTimes(2);
        });
        expect(await screen.findByText("ppt.wav")).toBeTruthy();
        expect(screen.queryByText("录音记录加载失败")).toBeNull();
    });

    it("fails closed before loading audio submissions when capabilities are unavailable", async () => {
        getCapabilitiesMock.mockRejectedValueOnce(new Error("capability unavailable"));

        render(<SalesTrainerAudioSubmissionsPage />);

        expect(await screen.findByText("页面访问受限")).toBeTruthy();
        expect(screen.getByText("capability unavailable")).toBeTruthy();
        expect(listAudioSubmissionsMock).not.toHaveBeenCalled();
        expect(screen.queryByText("暂无录音记录")).toBeNull();
    });
});
