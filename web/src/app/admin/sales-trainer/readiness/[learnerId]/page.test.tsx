import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerReadinessDossierPage from "./page";
import type {
    ReadinessDossier,
    ReadinessDossierRetrainingTask,
    ReadinessDossierReviewAction,
} from "@/lib/api/types/training-journey";

const { createReadinessReviewActionMock, getReadinessDossierMock } = vi.hoisted(() => ({
    createReadinessReviewActionMock: vi.fn(),
    getReadinessDossierMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ learnerId: "learner-1" }),
    usePathname: () => "/admin/sales-trainer/readiness/learner-1",
}));

vi.mock("@/lib/sales-trainer/use-admin-route-access", () => ({
    useSalesTrainerAdminRouteAccess: () => ({
        canAccess: true,
        capabilities: {
            view_records: true,
            view_global_records: true,
        },
        denialMessage: null,
        isLoading: false,
        reloadCapabilities: vi.fn(),
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
                    createReadinessReviewAction: createReadinessReviewActionMock,
                    getReadinessDossier: getReadinessDossierMock,
                },
            },
        },
    };
});

function dossierFixture(): ReadinessDossier {
    return {
        contract_version: "readiness_dossier_v1",
        learner: {
            learner_id: "learner-1",
            name: "张三",
            department: "销售一部",
        },
        path: {
            path_key: "newcomer_training_path_v1",
            path_revision_id: "revision-1",
            path_revision_no: 1,
            source: "active_revision",
        },
        status: "pending_review",
        status_label: "待复核",
        status_reason: "关键训练证据已齐，等待培训负责人复核。",
        summary: {
            total_modules: 3,
            completed_modules: 3,
            passed_modules: 3,
            failed_modules: 0,
            needs_remediation_modules: 0,
            evidence_count: 1,
            review_action_count: 0,
            weak_capability_count: 0,
            retraining_task_count: 0,
            completed_retraining_task_count: 0,
            review_state_source: "operation_log",
        },
        modules: [],
        competencies: [
            {
                capability_key: "expression_clarity",
                display_name: "表达清晰度",
                description: "表达是否清楚、可理解。",
                status: "ai_passed",
                score: 88,
                max_score: 100,
                weak: false,
                evidence_ids: ["audio_submission:submission-1"],
                latest_evidence_id: "audio_submission:submission-1",
                review_decision: null,
                reason: "AI/规则初评已达标，等待人工复核。",
            },
        ],
        evidence: [
            {
                evidence_id: "audio_submission:submission-1",
                evidence_type: "audio_submission",
                source_record_id: "submission-1",
                record_type: "audio_submission",
                module_key: "ppt_explanation",
                module_title: "PPT 讲解录音",
                module_type: "audio_scoring",
                capability_keys: ["expression_clarity"],
                status: "passed",
                score: 88,
                max_score: 100,
                passed: true,
                submitted_at: "2026-07-06T09:10:00Z",
                completed_at: null,
                material_snapshot: {
                    material_id: "material-1",
                    title: "PPT 标准材料",
                },
                scoring_snapshot: {
                    scoring_prompt_id: "prompt-1",
                    pass_threshold: 70,
                    max_score: 100,
                },
                task_brief_snapshot: {
                    title: "PPT 讲解任务",
                    purpose: "讲清客户价值。",
                },
                snapshot_ref: null,
                result_summary: "状态 passed，得分 88/100。",
                target_path: "/admin/sales-trainer/training-records/audio_submission/submission-1",
            },
        ],
        review_actions: [],
        latest_review_action: null,
        retraining_tasks: [],
        realtime_gate: {
            module_key: "realtime_roleplay",
            status: "disabled",
            locked: true,
            reason: "provider readiness 未通过。",
            training_gate_status: "pending_review",
            provider_readiness: null,
        },
        diagnostics: [
            {
                code: "[NEWCOMER_REALTIME_BINDING_INVALID]",
                message: "active path revision 中该模块缺少受治理的 runtime binding。",
                severity: "error",
                terminal: true,
            },
        ],
        next_actions: [],
        generated_at: "2026-07-06T09:20:00Z",
    };
}

describe("SalesTrainerReadinessDossierPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getReadinessDossierMock.mockResolvedValue(dossierFixture());
        createReadinessReviewActionMock.mockResolvedValue({
            action_id: "review-action-1",
            audit_log_id: "review-action-1",
            decision: "require_retraining",
            decision_label: "要求重练",
            reason: "表达结构仍需重练。",
            capability_keys: ["expression_clarity"],
            source_evidence_ids: ["audio_submission:submission-1"],
            reviewer_id: "admin-1",
            reviewer_role: "admin",
            created_at: "2026-07-06T09:30:00Z",
            retraining_task: {
                task_id: "retraining:learner-1:1",
                status: "pending",
                capability_keys: ["expression_clarity"],
                source_evidence_ids: ["audio_submission:submission-1"],
                completed_evidence_ids: [],
            },
            state_storage: "operation_log",
        });
    });

    it("renders dossier evidence in user language without raw API keys", async () => {
        render(<SalesTrainerReadinessDossierPage />);

        await waitFor(() => {
            expect(getReadinessDossierMock).toHaveBeenCalledWith("learner-1");
        });

        expect(screen.getByText("AI 初评达标")).toBeTruthy();
        expect(screen.getByText(/录音提交/)).toBeTruthy();
        expect(screen.getByText(/PPT 标准材料/)).toBeTruthy();
        expect(screen.getByText(/通过线 70/)).toBeTruthy();
        expect(screen.getByText("真实语音服务检查未通过，下一阶段暂不开放。")).toBeTruthy();
        expect(
            screen.getByText("真实语音对练后台接入配置缺失，请先处理训练路径配置。"),
        ).toBeTruthy();
        expect(screen.queryByText("ai_passed")).toBeNull();
        expect(screen.queryByText("audio_submission")).toBeNull();
        expect(screen.queryByText(/scoring_prompt_id/)).toBeNull();
        expect(screen.queryByText(/material_id/)).toBeNull();
        expect(screen.queryByText(/provider readiness/)).toBeNull();
        expect(screen.queryByText(/runtime binding/)).toBeNull();
        expect(screen.queryByText(/active path revision/)).toBeNull();
    });

    it("renders duplicate diagnostics without React key collisions", async () => {
        const dossier = dossierFixture();
        dossier.diagnostics = [
            ...dossier.diagnostics,
            { ...dossier.diagnostics[0] },
        ];
        getReadinessDossierMock.mockResolvedValue(dossier);
        const consoleErrorSpy = vi.spyOn(console, "error").mockImplementation(() => undefined);

        try {
            render(<SalesTrainerReadinessDossierPage />);

            await waitFor(() => {
                expect(getReadinessDossierMock).toHaveBeenCalledWith("learner-1");
            });
            expect(
                screen.getAllByText("真实语音对练后台接入配置缺失，请先处理训练路径配置。"),
            ).toHaveLength(2);
            const duplicateKeyWarnings = consoleErrorSpy.mock.calls.filter((call) =>
                call.some((part) =>
                    String(part).includes("Encountered two children with the same key"),
                ),
            );
            expect(duplicateKeyWarnings).toHaveLength(0);
        } finally {
            consoleErrorSpy.mockRestore();
        }
    });

    it("submits review action with selected evidence and refreshes the dossier", async () => {
        render(<SalesTrainerReadinessDossierPage />);

        await waitFor(() => {
            expect(getReadinessDossierMock).toHaveBeenCalledWith("learner-1");
        });

        fireEvent.change(screen.getByLabelText("结论"), {
            target: { value: "require_retraining" },
        });
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "表达结构仍需重练。" },
        });
        fireEvent.click(screen.getByRole("button", { name: /提交复核动作/ }));

        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledWith("learner-1", {
                decision: "require_retraining",
                reason: "表达结构仍需重练。",
                capability_keys: ["expression_clarity"],
                source_evidence_ids: ["audio_submission:submission-1"],
            });
        });
        expect(await screen.findByText("要求重练已记录。")).toBeTruthy();
        expect(getReadinessDossierMock).toHaveBeenCalledTimes(2);
    });

    it("renders completed retraining progress without exposing audit internals", async () => {
        const dossier = dossierFixture();
        dossier.summary.review_action_count = 1;
        dossier.summary.retraining_task_count = 1;
        dossier.summary.completed_retraining_task_count = 1;
        const retrainingTask: ReadinessDossierRetrainingTask = {
            task_id: "retraining:learner-1:1",
            status: "completed",
            source: "operation_log",
            capability_keys: ["expression_clarity"],
            source_evidence_ids: ["audio_submission:submission-1"],
            target_learner_id: "learner-1",
            completed_at: "2026-07-07T10:00:00Z",
            completed_evidence_ids: ["quiz_attempt:attempt-2"],
            comparison: {
                before_evidence_ids: ["audio_submission:submission-1"],
                after_evidence_ids: ["quiz_attempt:attempt-2"],
                after_status: "scored",
                after_passed: true,
                after_score: 96,
                after_max_score: 100,
            },
        };
        const reviewAction: ReadinessDossierReviewAction = {
            action_id: "review-action-1",
            audit_log_id: "review-action-1",
            decision: "require_retraining",
            decision_label: "要求重练",
            reason: "表达结构仍需重练。",
            capability_keys: ["expression_clarity"],
            source_evidence_ids: ["audio_submission:submission-1"],
            reviewer_id: "admin-1",
            reviewer_role: "admin",
            created_at: "2026-07-06T09:30:00Z",
            retraining_task: retrainingTask,
            state_storage: "operation_log",
        };
        dossier.review_actions = [reviewAction];
        dossier.latest_review_action = reviewAction;
        dossier.retraining_tasks = [retrainingTask];
        getReadinessDossierMock.mockResolvedValue(dossier);

        render(<SalesTrainerReadinessDossierPage />);

        expect(await screen.findByText("新人已完成重练，等待复核")).toBeTruthy();
        expect(screen.getByText("关联能力：表达清晰度")).toBeTruthy();
        expect(screen.getByText("原证据 1 条 · 重练证据 1 条")).toBeTruthy();
        expect(screen.getByText("重练后结果：已通过，得分 96 / 100。")).toBeTruthy();
        expect(screen.queryByText("retraining:learner-1:1")).toBeNull();
        expect(screen.queryByText("operation_log")).toBeNull();
        expect(screen.queryByText("audio_submission:submission-1")).toBeNull();
        expect(screen.queryByText("quiz_attempt:attempt-2")).toBeNull();
    });
});
