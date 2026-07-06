import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerAudioUploadPage from "./page";

const {
    pushMock,
    getUnitBriefMock,
    listPathsMock,
    uploadAudioSubmissionDirectMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    getUnitBriefMock: vi.fn(),
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
                getUnitBrief: getUnitBriefMock,
                listPaths: listPathsMock,
                getMaterialVersionFileUrl: (
                    versionId: string,
                    options?: { disposition?: "attachment" | "inline" },
                ) => `/api/materials/${versionId}/file${options?.disposition ? `?disposition=${options.disposition}` : ""}`,
                uploadAudioSubmissionDirect: uploadAudioSubmissionDirectMock,
            },
        },
    };
});

describe("SalesTrainerAudioUploadPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        getUnitBriefMock.mockReset();
        listPathsMock.mockReset();
        uploadAudioSubmissionDirectMock.mockReset();
        getUnitBriefMock.mockResolvedValue({
            unit: {
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
            },
            task_brief: {
                enabled: true,
                title: "第二关：录音表达",
                purpose: "上传讲解语音作业。",
                scenario: "按公司主胶片逻辑完成一次讲解录音。",
                instructions: ["下载最新版 PPT", "按主线录音"],
                success_criteria: ["结构完整"],
                common_mistakes: ["没有讲清价值"],
                upload_guidance: "先确认材料版本，再上传录音。",
            },
            materials: [
                {
                    material_id: "material-1",
                    material_key: "company_master_deck",
                    name: "公司主胶片",
                    material_type: "ppt_deck",
                    description: null,
                    purpose: "ppt_pitch",
                    required: true,
                    confirmation_required: true,
                    learner_note: "使用最新版公司主胶片。",
                    display_order: 1,
                    current_version: {
                        version_id: "version-1",
                        material_id: "material-1",
                        version_label: "v2026.06",
                        title: "公司主胶片 2026-06",
                        file_name: "deck.md",
                        content_type: "text/markdown",
                        file_size_bytes: 1024,
                        storage_key: "cos://deck.pptx",
                        file_hash: null,
                        release_notes: null,
                        status: "published",
                        published_at: "2026-06-01T00:00:00Z",
                        published_by: "admin-1",
                        created_by: "admin-1",
                        created_at: "2026-06-01T00:00:00Z",
                        updated_at: "2026-06-01T00:00:00Z",
                    },
                },
            ],
            score_scheme: {
                prompt_id: "prompt-1",
                name: "PPT 讲解评分",
                purpose: "ppt_pitch",
                version: 1,
                status: "published",
                pass_threshold: 80,
                learner_rubric: {
                    visible_to_learner: true,
                    criteria: [{ key: "structure", label: "结构", weight: 40 }],
                    common_mistakes: ["没有讲清价值"],
                },
            },
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

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("shows level context, pass threshold, and uploads the selected audio file", async () => {
        render(<SalesTrainerAudioUploadPage />);

        expect(await screen.findByText("第二关：录音表达")).toBeTruthy();
        expect(screen.getByText("上传讲解语音作业。")).toBeTruthy();
        expect(screen.getByText(/本关需达到 80 分通过，可多次上传，以最新一次为准/)).toBeTruthy();
        expect(screen.getByText(/下载最新版 PPT/)).toBeTruthy();
        expect(screen.getAllByText(/v2026.06/).length).toBeGreaterThan(0);

        const file = new File(["audio"], "pitch.wav", { type: "audio/wav" });
        fireEvent.change(screen.getByLabelText("选择音频文件"), {
            target: { files: [file] },
        });

        expect(await screen.findByText(/已选择：pitch.wav/)).toBeTruthy();
        fireEvent.click(screen.getByText(/我已下载并确认使用 v2026.06/));

        fireEvent.click(screen.getByRole("button", { name: /上传并开始评分/ }));

        await waitFor(() => {
            expect(uploadAudioSubmissionDirectMock).toHaveBeenCalledWith({
                file,
                unit_id: "audio-unit",
                purpose: "ppt_pitch",
                source_page: "sales_trainer_audio_upload",
                confirmed_material_version_id: "version-1",
            });
        });
        expect(screen.queryByText(/50 秒|最大时长/)).toBeNull();
        expect(listPathsMock).not.toHaveBeenCalled();
        expect(pushMock).toHaveBeenCalledWith("/sales-trainer/audio/result/submission-1");
    });

    it("uses unit brief as the only learner source and does not fail when legacy paths are unavailable", async () => {
        listPathsMock.mockRejectedValue(new Error("legacy paths unavailable"));

        render(<SalesTrainerAudioUploadPage />);

        expect(await screen.findByText("第二关：录音表达")).toBeTruthy();
        expect(screen.getByText("上传讲解语音作业。")).toBeTruthy();
        expect(screen.getByText(/本关需达到 80 分通过/)).toBeTruthy();
        expect(listPathsMock).not.toHaveBeenCalled();
    });

    it("fails closed when the audio pass threshold is missing", async () => {
        getUnitBriefMock.mockResolvedValueOnce({
            unit: {
                unit_id: "audio-unit",
                name: "录音单元",
                description: "录音训练",
                unit_type: "audio_scoring",
                config: { audio: { purpose: "ppt_pitch" } },
                status: "published",
                created_by: "admin-1",
                updated_by: "admin-1",
                created_at: "2026-05-28T00:00:00Z",
                updated_at: "2026-05-28T00:00:00Z",
                questions: [],
            },
            task_brief: {
                enabled: true,
                title: "第二关：录音表达",
                purpose: "上传讲解语音作业。",
                scenario: null,
                instructions: [],
                success_criteria: [],
                common_mistakes: [],
                upload_guidance: null,
            },
            materials: [],
            score_scheme: {
                prompt_id: "prompt-1",
                name: "PPT 讲解评分",
                purpose: "ppt_pitch",
                version: 1,
                status: "published",
                pass_threshold: null,
                learner_rubric: {
                    visible_to_learner: true,
                    criteria: [],
                    common_mistakes: [],
                },
            },
        });

        render(<SalesTrainerAudioUploadPage />);

        expect(await screen.findByText("评分标准配置缺失")).toBeTruthy();
        expect(screen.queryByText(/本关需达到 70 分通过/)).toBeNull();

        const file = new File(["audio"], "pitch.wav", { type: "audio/wav" });
        fireEvent.change(screen.getByLabelText("选择音频文件"), {
            target: { files: [file] },
        });

        const uploadButton = await screen.findByRole("button", { name: /上传并开始评分/ });
        expect(uploadButton).toHaveProperty("disabled", true);
        fireEvent.click(uploadButton);
        expect(uploadAudioSubmissionDirectMock).not.toHaveBeenCalled();
    });

    it("renders markdown training material preview without forcing a download", async () => {
        const fetchMock = vi.fn(async () => new Response(
            "## 好示范\n\n新人应先讲客户场景，再讲方案价值。",
            { status: 200 },
        ));
        vi.stubGlobal("fetch", fetchMock);

        render(<SalesTrainerAudioUploadPage />);

        fireEvent.click(await screen.findByRole("button", { name: "查看材料" }));

        expect(fetchMock).toHaveBeenCalledWith(
            "/api/materials/version-1/file?disposition=inline",
            { credentials: "include" },
        );
        expect(await screen.findByText("好示范")).toBeTruthy();
        expect(screen.getByText("新人应先讲客户场景，再讲方案价值。")).toBeTruthy();
        expect(screen.getByRole("link", { name: /下载材料/ }).getAttribute("href"))
            .toBe("/api/materials/version-1/file");
    });
});
