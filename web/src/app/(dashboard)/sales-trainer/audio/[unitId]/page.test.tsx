import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerAudioUploadPage from "./page";

const {
    pushMock,
    getUnitMock,
    listPathsMock,
    uploadAudioSubmissionDirectMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    getUnitMock: vi.fn(),
    listPathsMock: vi.fn(),
    uploadAudioSubmissionDirectMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ unitId: "audio-unit" }),
    useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                getUnit: getUnitMock,
                listPaths: listPathsMock,
                uploadAudioSubmissionDirect: uploadAudioSubmissionDirectMock,
            },
        },
    };
});

describe("SalesTrainerAudioUploadPage", () => {
    beforeEach(() => {
        getUnitMock.mockResolvedValue({
            unit_id: "audio-unit",
            name: "录音单元",
            description: "录音训练",
            unit_type: "audio_scoring",
            config: { audio: { purpose: "ppt_pitch", pass_threshold: 80 } },
            status: "published",
            created_by: "admin-1",
            updated_by: "admin-1",
            created_at: "2026-05-28T00:00:00Z",
            updated_at: "2026-05-28T00:00:00Z",
            questions: [],
        });
        listPathsMock.mockResolvedValue({
            items: [
                {
                    path_key: "new_seller",
                    title: "新人销售闯关",
                    goal_title: "掌握首次客户沟通",
                    total_levels: 1,
                    completed_levels: 0,
                    current_level_id: "audio-unit",
                    next_level_id: "audio-unit",
                    goal_context: {
                        goal_title: "掌握首次客户沟通",
                        score_basis: "sales_trainer_path_projection_v1",
                        evidence_items: [],
                        weak_points: [],
                        next_recommendation: null,
                    },
                    levels: [
                        {
                            unit_id: "audio-unit",
                            name: "录音单元",
                            description: "录音训练",
                            unit_type: "audio_scoring",
                            order_index: 1,
                            level_title: "第二关：录音表达",
                            level_description: "上传讲解语音作业。",
                            locked: false,
                            lock_reason: null,
                            status: "available",
                            completion_rule: "passed",
                            primary_action_label: "上传语音作业",
                            retry_action_label: "重练本关",
                            review_action_label: "查看结果",
                            target_path: "/sales-trainer/audio/audio-unit",
                            latest_result: null,
                        },
                    ],
                },
            ],
            total: 1,
        });
        uploadAudioSubmissionDirectMock.mockResolvedValue({ submission_id: "submission-1" });
    });

    it("shows level context, pass threshold, and uploads the selected audio file", async () => {
        render(<SalesTrainerAudioUploadPage />);

        expect(await screen.findByText("第二关：录音表达")).toBeTruthy();
        expect(screen.getByText("上传讲解语音作业。")).toBeTruthy();
        expect(screen.getByText(/本关需达到 80 分通过，可多次上传，以最新一次为准/)).toBeTruthy();
        expect(screen.getByText(/建议先用手机录音 App 录好语音/)).toBeTruthy();

        const file = new File(["audio"], "pitch.wav", { type: "audio/wav" });
        fireEvent.change(screen.getByLabelText("选择音频文件"), {
            target: { files: [file] },
        });

        expect(await screen.findByText(/已选择：pitch.wav/)).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: /上传并开始评分/ }));

        await waitFor(() => {
            expect(uploadAudioSubmissionDirectMock).toHaveBeenCalledWith({
                file,
                unit_id: "audio-unit",
                purpose: "ppt_pitch",
                source_page: "sales_trainer_audio_upload",
            });
        });
        expect(screen.queryByText(/50 秒|最大时长/)).toBeNull();
        expect(pushMock).toHaveBeenCalledWith("/sales-trainer/audio/result/submission-1");
    });
});
