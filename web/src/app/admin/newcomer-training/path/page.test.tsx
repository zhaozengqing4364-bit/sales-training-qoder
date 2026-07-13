import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { ActivityConfig, TrainingPathConfigResponse } from "@/lib/api/types/newcomer-training";
import { NewcomerTrainingPathPageClient as Page } from "./path-page-client";

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/newcomer-training/path",
}));

const { getPath, listLearningContents, listExamPapers, listScoringRubrics, listMaterials, listPracticeTemplates, listVoiceRuntimeProfiles, listCoachProfiles, publishCandidate } = vi.hoisted(() => ({
    getPath: vi.fn(),
    listLearningContents: vi.fn(),
    listExamPapers: vi.fn(),
    listScoringRubrics: vi.fn(),
    listMaterials: vi.fn(),
    listPracticeTemplates: vi.fn(),
    listVoiceRuntimeProfiles: vi.fn(),
    listCoachProfiles: vi.fn(),
    publishCandidate: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
    api: {
        learningContents: { list: listLearningContents },
        admin: {
            newcomerTraining: {
                getPath,
                publishCandidate,
                listCoachProfiles,
                listScoringRubrics,
            },
            salesTrainer: {
                listExamPapers,
                listMaterials,
            },
            listPracticeTemplates,
            getVoiceRuntimeProfiles: listVoiceRuntimeProfiles,
        },
    },
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({ success: vi.fn(), error: vi.fn(), showToast: vi.fn() }),
}));

vi.mock("@/lib/sales-trainer/use-admin-route-access", () => ({
    useSalesTrainerAdminRouteAccess: () => ({
        capabilities: { capabilities: { admin_full_access: true } },
        canAccess: true,
        denialMessage: null,
        error: null,
        isLoading: false,
        reloadCapabilities: vi.fn(),
    }),
}));

function modelWithActivity(activity: ActivityConfig): TrainingPathConfigResponse {
    return {
        active_revision_id: "revision-1",
        active_revision_no: 1,
        working_revision_id: "revision-1",
        payload: {
            schema_version: "newcomer_training_orchestration_v1",
            title: "新人训练路径",
            description: null,
            phases: [{
                phase_id: "phase-1", title: "产品学习", description: null, outcome: null,
                order_index: 1, required: true,
                modules: [{
                    module_id: "module-1", title: "产品基础", description: null, outcome: null,
                    order_index: 1, required: true, estimated_minutes: 30,
                    audience_rule: { learner_levels: [], roles: [], departments: [] },
                    prerequisites: [],
                    completion_policy: { mode: "all_required", activity_ids: [activity.activity_id], count: null },
                    activities: [activity],
                }],
            }],
        },
        validation: null,
    };
}

function quizActivity(): ActivityConfig {
    return {
        activity_id: "activity-quiz", type: "quiz", title: "产品测验", description: null,
        objective: null, why_it_matters: null, steps: [], success_criteria: [],
        primary_action_label: null, order_index: 1, required: true, estimated_minutes: 10,
        prerequisites: [], config: { exam_paper_id: "paper-1", pass_score: 80, max_attempts: null },
    };
}

describe("newcomer path page", () => {
    beforeEach(() => {
        getPath.mockReset();
        publishCandidate.mockReset();
        listLearningContents.mockReset().mockResolvedValue({ items: [], total: 0 });
        listExamPapers.mockReset().mockResolvedValue({ items: [], total: 0 });
        listScoringRubrics.mockReset().mockResolvedValue([]);
        listMaterials.mockReset().mockResolvedValue({ items: [], total: 0 });
        listPracticeTemplates.mockReset().mockResolvedValue({ items: [], total: 0 });
        listVoiceRuntimeProfiles.mockReset().mockResolvedValue({ items: [], total: 0 });
        listCoachProfiles.mockReset().mockResolvedValue([]);
    });

    it("does not download resource catalogs until an activity needs them", async () => {
        const user = userEvent.setup();
        listLearningContents.mockResolvedValue({
            items: [{ learning_content_id: "content-1", title: "产品知识手册", status: "published" }],
            total: 1,
        });
        render(<Page initialModel={{
            active_revision_id: "revision-1",
            active_revision_no: 1,
            working_revision_id: "revision-1",
            payload: {
                schema_version: "newcomer_training_orchestration_v1",
                title: "新人训练路径",
                description: null,
                phases: [{
                    phase_id: "phase-1", title: "产品学习", description: null, outcome: null,
                    order_index: 1, required: true,
                    modules: [{
                        module_id: "module-1", title: "产品基础", description: null, outcome: null,
                        order_index: 1, required: true, estimated_minutes: 30,
                        audience_rule: { learner_levels: [], roles: [], departments: [] },
                        prerequisites: [],
                        completion_policy: { mode: "all_required", activity_ids: ["activity-1"], count: null },
                        activities: [{
                            activity_id: "activity-1", type: "lesson", title: "学习产品资料",
                            description: null, objective: null, why_it_matters: null, steps: [],
                            success_criteria: [], primary_action_label: null, order_index: 1,
                            required: true, estimated_minutes: 20, prerequisites: [],
                            config: { learning_content_id: "content-1", completion_mode: "all_chapters" },
                        }],
                    }],
                }],
            },
            validation: null,
        }} />);

        await Promise.resolve();
        expect(listLearningContents).not.toHaveBeenCalled();
        expect(listExamPapers).not.toHaveBeenCalled();
        expect(listVoiceRuntimeProfiles).not.toHaveBeenCalled();

        await user.click(screen.getByRole("button", { name: "编辑活动 学习产品资料" }));

        await waitFor(() => expect(listLearningContents).toHaveBeenCalledTimes(1));
        expect(await screen.findByRole("option", { name: "产品知识手册" })).toBeTruthy();
        expect(listExamPapers).not.toHaveBeenCalled();
        expect(listVoiceRuntimeProfiles).not.toHaveBeenCalled();

        await user.click(screen.getByRole("button", { name: "训练路径大纲" }));
        await user.click(screen.getByRole("button", { name: "编辑活动 学习产品资料" }));
        expect(listLearningContents).toHaveBeenCalledTimes(1);
    });

    it("keeps the editor usable when one resource catalog fails", async () => {
        const user = userEvent.setup();
        getPath.mockResolvedValue(modelWithActivity(quizActivity()));
        listExamPapers.mockRejectedValue(new Error("paper catalog unavailable"));

        render(<Page />);

        await waitFor(() => expect(screen.getByRole("tree", { name: "训练路径大纲" })).toBeTruthy());
        await user.click(screen.getByRole("button", { name: "编辑活动 产品测验" }));
        await waitFor(() => expect(listExamPapers).toHaveBeenCalledTimes(1));
        expect(screen.getByRole("alert").textContent).toContain("试卷目录暂不可用");
        expect(screen.getByRole("button", { name: "重新加载试卷目录" })).toBeTruthy();

        listExamPapers.mockResolvedValue({ items: [], total: 0 });
        await user.click(screen.getByRole("button", { name: "重新加载试卷目录" }));
        await waitFor(() => expect(screen.queryByText("试卷目录暂不可用")).toBeNull());
        expect(getPath).toHaveBeenCalledTimes(1);
        expect(listExamPapers).toHaveBeenCalledTimes(2);
    });

    it("loads the focused editor from the canonical API", async () => {
        getPath.mockResolvedValue({
            active_revision_id: null,
            active_revision_no: null,
            working_revision_id: null,
            payload: {
                schema_version: "newcomer_training_orchestration_v1",
                title: "新人训练路径",
                description: null,
                phases: [],
            },
            validation: null,
        });

        render(<Page />);
        expect(screen.getByText("正在加载训练路径…")).toBeTruthy();
        await waitFor(() => expect(screen.getByRole("tree", { name: "训练路径大纲" })).toBeTruthy());
        expect(getPath).toHaveBeenCalledTimes(1);
    });

    it("shows the path editor without waiting for slow resource catalogs", async () => {
        const user = userEvent.setup();
        getPath.mockResolvedValue(modelWithActivity(quizActivity()));
        listExamPapers.mockImplementation(() => new Promise(() => undefined));

        render(<Page />);

        expect(await screen.findByRole("tree", { name: "训练路径大纲" })).toBeTruthy();
        expect(screen.queryByText("正在加载当前活动需要的可选资源…")).toBeNull();

        await user.click(screen.getByRole("button", { name: "编辑活动 产品测验" }));

        expect(screen.getByText("正在加载当前活动需要的可选资源…")).toBeTruthy();
        expect(screen.getByRole("form", { name: "活动设置" })).toBeTruthy();
    });

    it("renders server-provided path data without showing a blank loading screen", async () => {
        getPath.mockImplementation(() => new Promise(() => undefined));

        render(<Page initialModel={{
            active_revision_id: null,
            active_revision_no: null,
            working_revision_id: null,
            payload: {
                schema_version: "newcomer_training_orchestration_v1",
                title: "新人训练路径",
                description: null,
                phases: [],
            },
            validation: null,
        }} />);

        expect(screen.queryByText("正在加载训练路径…")).toBeNull();
        expect(await screen.findByRole("tree", { name: "训练路径大纲" })).toBeTruthy();
    });

    it("closes the publish confirmation without waiting for resource catalogs to refresh", async () => {
        const user = userEvent.setup();
        const initialModel = {
            active_revision_id: "revision-1",
            active_revision_no: 1,
            working_revision_id: "revision-1",
            payload: {
                schema_version: "newcomer_training_orchestration_v1" as const,
                title: "新人训练路径",
                description: null,
                phases: [],
            },
            validation: null,
        };
        publishCandidate.mockResolvedValue({ revision_id: "revision-2" });
        getPath.mockResolvedValue({ ...initialModel, active_revision_id: "revision-2" });
        listExamPapers.mockImplementation(() => new Promise(() => undefined));

        render(<Page initialModel={initialModel} />);
        await user.type(screen.getByLabelText("发布说明"), "更新新人训练路径");
        await user.click(screen.getByRole("button", { name: "发布" }));
        await user.click(screen.getByRole("button", { name: "确认发布" }));

        await waitFor(() => expect(screen.queryByText("确认发布训练路径")).toBeNull());
        expect(publishCandidate).toHaveBeenCalledTimes(1);
    });

    it("shows a retryable inline error", async () => {
        getPath.mockRejectedValue(new Error("network"));
        render(<Page />);
        expect((await screen.findByRole("alert")).textContent).toContain("训练路径加载失败");
        expect(screen.getByRole("button", { name: "重新加载" })).toBeTruthy();
    });
});
