import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerReadinessDossierPage, {
    readinessReviewSubmissionIsCurrent,
} from "./page";
import type {
    ReadinessDossier,
    ReadinessDossierRetrainingTask,
    ReadinessDossierReviewAction,
} from "@/lib/api/types";
import { ApiRequestError } from "@/lib/api/client";

const {
    createReadinessReviewActionMock,
    getReadinessDossierMock,
    routeAccessMock,
    useParamsMock,
} = vi.hoisted(() => ({
    createReadinessReviewActionMock: vi.fn(),
    getReadinessDossierMock: vi.fn(),
    routeAccessMock: vi.fn(),
    useParamsMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useParams: () => useParamsMock(),
    usePathname: () => "/admin/sales-trainer/readiness/learner-1",
}));

vi.mock("@/lib/sales-trainer/use-admin-route-access", () => ({
    useSalesTrainerAdminRouteAccess: () => routeAccessMock(),
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
            review_state_source: "readiness_review_action",
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

function deferred<T>() {
    let resolve!: (value: T) => void;
    let reject!: (reason?: unknown) => void;
    const promise = new Promise<T>((resolvePromise, rejectPromise) => {
        resolve = resolvePromise;
        reject = rejectPromise;
    });
    return { promise, reject, resolve };
}

describe("SalesTrainerReadinessDossierPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useParamsMock.mockReturnValue({ learnerId: "learner-1" });
        routeAccessMock.mockReturnValue({
            canAccess: true,
            capabilities: {
                role: "training_manager",
                role_label: "培训负责人",
                capabilities: {
                    admin_full_access: false,
                    manage_content: false,
                    manage_questions: false,
                    manage_modules: false,
                    manage_prompts: false,
                    review_readiness: true,
                    view_records: true,
                    view_global_records: false,
                    retry_jobs: false,
                    regrade_history: false,
                    view_logs: false,
                    view_settings: false,
                },
                capability_keys: ["view_records", "review_readiness"],
            },
            denialMessage: null,
            error: null,
            isLoading: false,
            reloadCapabilities: vi.fn(),
        });
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
            state_storage: "readiness_review_action",
        });
    });

    it("fails closed synchronously when any frozen submission context changes", () => {
        const currentContext = {
            submissionLearnerId: "learner-1",
            routeLearnerId: "learner-1",
            dossierLearnerId: "learner-1",
            submissionExpectedLatestReviewActionId: "review-action-1",
            currentLatestReviewActionId: "review-action-1",
        };

        expect(readinessReviewSubmissionIsCurrent(currentContext)).toBe(true);
        expect(readinessReviewSubmissionIsCurrent({
            ...currentContext,
            routeLearnerId: "learner-2",
        })).toBe(false);
        expect(readinessReviewSubmissionIsCurrent({
            ...currentContext,
            dossierLearnerId: "learner-2",
        })).toBe(false);
        expect(readinessReviewSubmissionIsCurrent({
            ...currentContext,
            currentLatestReviewActionId: "review-action-2",
        })).toBe(false);
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

    it("uses safe learner and evidence labels when display names are missing", async () => {
        const dossier = dossierFixture();
        dossier.learner.name = null;
        dossier.evidence[0].module_title = null;
        dossier.evidence[0].module_key = "ppt_explanation_internal";
        dossier.evidence[0].evidence_id = "audio_submission:raw-evidence-42";
        dossier.evidence[0].target_path = null;
        getReadinessDossierMock.mockResolvedValue(dossier);
        render(<SalesTrainerReadinessDossierPage />);

        expect(await screen.findByText("未命名新人的训练达标档案")).toBeTruthy();
        expect(screen.getAllByText("训练证据").length).toBeGreaterThan(0);
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "需要补充人工判断。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "提交复核动作" }));
        expect(within(screen.getByLabelText("复核动作确认")).getByText("未命名新人")).toBeTruthy();
        expect(document.body.textContent).not.toContain("learner-1");
        expect(document.body.textContent).not.toContain("ppt_explanation_internal");
        expect(document.body.textContent).not.toContain("raw-evidence-42");
    });

    it.each([
        ["raw JSON payload", new Error("raw JSON payload leaked from storage")],
        ["readiness_service", new Error("readiness_service database timeout")],
        ["trace-secret-load", new ApiRequestError({
            status: 500,
            errorCode: "[READINESS_UNKNOWN_FAILURE]",
            message: "unknown server message",
            traceId: "trace-secret-load",
        })],
    ])("fails closed for unknown load error %s", async (secret, loadError) => {
        getReadinessDossierMock.mockRejectedValue(loadError);
        render(<SalesTrainerReadinessDossierPage />);

        expect(await screen.findByText("档案暂时无法加载，请稍后重试。")).toBeTruthy();
        expect(document.body.textContent).not.toContain(secret);
        expect(document.body.textContent).not.toContain("trace_id");
    });

    it("fails closed when capability loading returns internal details with a trace", async () => {
        routeAccessMock.mockReturnValue({
            canAccess: false,
            capabilities: null,
            denialMessage: "readiness_service database timeout (trace_id: trace-capability)",
            error: "readiness_service database timeout (trace_id: trace-capability)",
            isLoading: false,
            reloadCapabilities: vi.fn(),
        });
        render(<SalesTrainerReadinessDossierPage />);

        expect(screen.getByText("权限信息加载失败")).toBeTruthy();
        expect(screen.getByText("权限信息暂时无法加载，请稍后重试。")).toBeTruthy();
        expect(document.body.textContent).not.toContain("readiness_service");
        expect(document.body.textContent).not.toContain("trace-capability");
        expect(document.body.textContent).not.toContain("trace_id");
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

    it("opens a decision-specific confirmation before sending the review action", async () => {
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

        expect(createReadinessReviewActionMock).not.toHaveBeenCalled();
        const confirmation = screen.getByLabelText("复核动作确认");
        expect(within(confirmation).getByText("张三")).toBeTruthy();
        expect(within(confirmation).getByText("要求重练")).toBeTruthy();
        expect(within(confirmation).getByText("表达结构仍需重练。")).toBeTruthy();
        expect(confirmation.textContent).toContain("能力项数量1 项");
        expect(confirmation.textContent).toContain("证据数量1 条");
        expect(screen.queryByRole("button", { name: "提交复核动作" })).toBeNull();
        expect(confirmation.getAttribute("tabindex")).toBe("-1");
        await waitFor(() => {
            expect(document.activeElement).toBe(confirmation);
        });

        fireEvent.click(screen.getByRole("button", { name: "确认下发重练" }));

        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledWith(
                "learner-1",
                expect.objectContaining({
                    decision: "require_retraining",
                    reason: "表达结构仍需重练。",
                    capability_keys: ["expression_clarity"],
                    source_evidence_ids: ["audio_submission:submission-1"],
                    idempotency_key: expect.any(String),
                    expected_latest_review_action_id: null,
                }),
            );
        });
        const success = await screen.findByRole("status");
        expect(success.textContent).toBe("要求重练已记录。");
        expect(success.getAttribute("aria-live")).toBe("polite");
        expect(getReadinessDossierMock).toHaveBeenCalledTimes(2);
    });

    it("confirms the effective defaults when the reviewer clears every selection", async () => {
        render(<SalesTrainerReadinessDossierPage />);

        await screen.findByLabelText("原因");
        for (const checkbox of screen.getAllByRole("checkbox")) {
            fireEvent.click(checkbox);
        }
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "按档案默认范围确认。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "提交复核动作" }));

        const confirmation = screen.getByLabelText("复核动作确认");
        expect(confirmation.textContent).toContain("能力项数量1 项");
        expect(confirmation.textContent).toContain("证据数量1 条");
        expect(
            screen.getAllByRole<HTMLInputElement>("checkbox").every(
                (checkbox) => checkbox.checked,
            ),
        ).toBe(true);

        fireEvent.click(
            screen.getByRole("button", { name: "确认新人达标并开放下一阶段" }),
        );
        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledWith(
                "learner-1",
                expect.objectContaining({
                    capability_keys: ["expression_clarity"],
                    source_evidence_ids: ["audio_submission:submission-1"],
                }),
            );
        });
    });

    it("confirms needs-retraining capabilities selected by the backend default rule", async () => {
        const dossier = dossierFixture();
        dossier.competencies[0].status = "needs_retraining";
        dossier.competencies[0].weak = true;
        getReadinessDossierMock.mockResolvedValue(dossier);
        render(<SalesTrainerReadinessDossierPage />);

        await screen.findByLabelText("原因");
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "继续针对弱项重练。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "提交复核动作" }));

        const confirmation = screen.getByLabelText("复核动作确认");
        expect(confirmation.textContent).toContain("能力项数量1 项");
        fireEvent.click(
            screen.getByRole("button", { name: "确认新人达标并开放下一阶段" }),
        );
        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledWith(
                "learner-1",
                expect.objectContaining({
                    capability_keys: ["expression_clarity"],
                }),
            );
        });
    });

    it("uses explicit approve copy and the current dossier review version", async () => {
        const dossier = dossierFixture();
        dossier.latest_review_action = {
            action_id: "review-action-current",
            audit_log_id: "audit-current",
            decision: "mark_manual_follow_up",
            decision_label: "标记需人工跟进",
            reason: "等待补充材料。",
            capability_keys: [],
            source_evidence_ids: [],
            reviewer_id: "manager-1",
            reviewer_role: "training_manager",
            created_at: "2026-07-06T09:00:00Z",
            retraining_task: null,
            state_storage: "readiness_review_action",
        };
        getReadinessDossierMock.mockResolvedValue(dossier);
        render(<SalesTrainerReadinessDossierPage />);

        await screen.findByLabelText("原因");
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "证据完整，可以进入下一阶段。" },
        });
        fireEvent.click(screen.getByRole("button", { name: /提交复核动作/ }));
        fireEvent.click(
            screen.getByRole("button", { name: "确认新人达标并开放下一阶段" }),
        );

        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledWith(
                "learner-1",
                expect.objectContaining({
                    expected_latest_review_action_id: "review-action-current",
                }),
            );
        });
    });

    it("keeps one idempotency token across a network retry", async () => {
        createReadinessReviewActionMock
            .mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce({
                decision_label: "要求重练",
            });
        render(<SalesTrainerReadinessDossierPage />);

        await screen.findByLabelText("原因");
        fireEvent.change(screen.getByLabelText("结论"), {
            target: { value: "require_retraining" },
        });
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "表达结构仍需重练。" },
        });
        fireEvent.click(screen.getByRole("button", { name: /提交复核动作/ }));
        fireEvent.click(screen.getByRole("button", { name: "确认下发重练" }));

        expect((await screen.findByRole("alert")).textContent).toContain("网络连接失败");
        const firstToken = createReadinessReviewActionMock.mock.calls[0][1].idempotency_key;
        fireEvent.click(screen.getByRole("button", { name: "确认下发重练" }));

        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledTimes(2);
        });
        expect(createReadinessReviewActionMock.mock.calls[1][1].idempotency_key).toBe(firstToken);
    });

    it("clears the pending token and confirmation when the reviewer edits the request", async () => {
        createReadinessReviewActionMock
            .mockRejectedValueOnce(new TypeError("NetworkError when attempting to fetch resource"))
            .mockResolvedValueOnce({ decision_label: "要求重练" });
        render(<SalesTrainerReadinessDossierPage />);

        await screen.findByLabelText("原因");
        fireEvent.change(screen.getByLabelText("结论"), {
            target: { value: "require_retraining" },
        });
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "第一次原因。" },
        });
        fireEvent.click(screen.getByRole("button", { name: /提交复核动作/ }));
        fireEvent.click(screen.getByRole("button", { name: "确认下发重练" }));
        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledTimes(1);
        });
        await screen.findByRole("alert");
        const firstToken = createReadinessReviewActionMock.mock.calls[0][1].idempotency_key;

        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "修改后的原因。" },
        });
        expect(screen.queryByRole("button", { name: "确认下发重练" })).toBeNull();
        fireEvent.click(screen.getByRole("button", { name: /提交复核动作/ }));
        fireEvent.click(screen.getByRole("button", { name: "确认下发重练" }));

        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledTimes(2);
        });
        expect(createReadinessReviewActionMock.mock.calls[1][1].idempotency_key).not.toBe(
            firstToken,
        );
    });

    it("refreshes a conflicting dossier and requires a fresh confirmation without replay", async () => {
        const refreshed = dossierFixture();
        refreshed.latest_review_action = {
            action_id: "review-action-other",
            audit_log_id: "audit-other",
            decision: "mark_manual_follow_up",
            decision_label: "标记需人工跟进",
            reason: "另一位负责人已提交。",
            capability_keys: [],
            source_evidence_ids: [],
            reviewer_id: "manager-2",
            reviewer_role: "training_manager",
            created_at: "2026-07-06T09:40:00Z",
            retraining_task: null,
            state_storage: "readiness_review_action",
        };
        getReadinessDossierMock
            .mockResolvedValueOnce(dossierFixture())
            .mockResolvedValueOnce(refreshed);
        createReadinessReviewActionMock.mockRejectedValue(
            new ApiRequestError({
                status: 409,
                errorCode: "[READINESS_REVIEW_VERSION_CONFLICT]",
                message: "档案已更新。",
            }),
        );
        render(<SalesTrainerReadinessDossierPage />);

        await screen.findByLabelText("原因");
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "证据完整。" },
        });
        fireEvent.click(screen.getByRole("button", { name: /提交复核动作/ }));
        fireEvent.click(
            screen.getByRole("button", { name: "确认新人达标并开放下一阶段" }),
        );

        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledTimes(1);
        });
        expect(await screen.findByText(/档案已更新/)).toBeTruthy();
        await waitFor(() => {
            expect(getReadinessDossierMock).toHaveBeenCalledTimes(2);
        });
        expect(createReadinessReviewActionMock).toHaveBeenCalledTimes(1);
        expect(
            screen.queryByRole("button", { name: "确认新人达标并开放下一阶段" }),
        ).toBeNull();
    });

    it("invalidates the frozen submission after manual refresh and uses the new version and token", async () => {
        const refreshed = dossierFixture();
        refreshed.latest_review_action = {
            action_id: "review-action-refreshed",
            audit_log_id: "audit-refreshed",
            decision: "mark_manual_follow_up",
            decision_label: "标记需人工跟进",
            reason: "另一位负责人已提交。",
            capability_keys: [],
            source_evidence_ids: [],
            reviewer_id: "manager-2",
            reviewer_role: "training_manager",
            created_at: "2026-07-06T09:40:00Z",
            retraining_task: null,
            state_storage: "readiness_review_action",
        };
        getReadinessDossierMock
            .mockResolvedValueOnce(dossierFixture())
            .mockResolvedValue(refreshed);
        createReadinessReviewActionMock
            .mockRejectedValueOnce(new TypeError("Failed to fetch"))
            .mockResolvedValueOnce({ decision_label: "确认达标" });
        render(<SalesTrainerReadinessDossierPage />);

        await screen.findByLabelText("原因");
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "证据完整，可以进入下一阶段。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "提交复核动作" }));
        fireEvent.click(
            screen.getByRole("button", { name: "确认新人达标并开放下一阶段" }),
        );
        await screen.findByRole("alert");
        const firstToken = createReadinessReviewActionMock.mock.calls[0][1].idempotency_key;

        fireEvent.click(screen.getByRole("button", { name: "刷新" }));
        await waitFor(() => {
            expect(getReadinessDossierMock).toHaveBeenCalledTimes(2);
        });
        expect(createReadinessReviewActionMock).toHaveBeenCalledTimes(1);
        expect(
            screen.queryByRole("button", { name: "确认新人达标并开放下一阶段" }),
        ).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "提交复核动作" }));
        fireEvent.click(
            screen.getByRole("button", { name: "确认新人达标并开放下一阶段" }),
        );
        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledTimes(2);
        });
        const refreshedPayload = createReadinessReviewActionMock.mock.calls[1][1];
        expect(refreshedPayload.expected_latest_review_action_id).toBe(
            "review-action-refreshed",
        );
        expect(refreshedPayload.idempotency_key).not.toBe(firstToken);
    });

    it("sanitizes action errors before rendering them", async () => {
        createReadinessReviewActionMock.mockRejectedValue(new ApiRequestError({
            status: 500,
            errorCode: "[READINESS_UNKNOWN_FAILURE]",
            message: "readiness_service database timeout with raw JSON",
            traceId: "trace-secret-action",
        }));
        render(<SalesTrainerReadinessDossierPage />);

        await screen.findByLabelText("原因");
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "证据完整。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "提交复核动作" }));
        fireEvent.click(
            screen.getByRole("button", { name: "确认新人达标并开放下一阶段" }),
        );

        expect(await screen.findByText("复核动作提交失败，请稍后重试。")).toBeTruthy();
        expect(document.body.textContent).not.toContain("trace_id");
        expect(document.body.textContent).not.toContain("trace-secret-action");
        expect(document.body.textContent).not.toContain("READINESS_UNKNOWN_FAILURE");
        expect(document.body.textContent).not.toContain("readiness_service");
        expect(document.body.textContent).not.toContain("raw JSON");
    });

    it("invalidates learner A confirmation when the same component switches to learner B", async () => {
        const learnerA = dossierFixture();
        learnerA.learner.learner_id = "learner-a";
        learnerA.learner.name = "张三";
        const learnerB = dossierFixture();
        learnerB.learner.learner_id = "learner-b";
        learnerB.learner.name = "李四";
        useParamsMock.mockReturnValue({ learnerId: "learner-a" });
        getReadinessDossierMock.mockImplementation((learnerId: string) => (
            Promise.resolve(learnerId === "learner-a" ? learnerA : learnerB)
        ));
        const randomUUIDSpy = vi.spyOn(globalThis.crypto, "randomUUID")
            .mockReturnValueOnce("00000000-0000-4000-8000-000000000001")
            .mockReturnValueOnce("00000000-0000-4000-8000-000000000002");

        try {
            const { rerender } = render(<SalesTrainerReadinessDossierPage />);
            await waitFor(() => {
                expect(getReadinessDossierMock).toHaveBeenCalledWith("learner-a");
            });
            fireEvent.change(screen.getByLabelText("原因"), {
                target: { value: "证据完整。" },
            });
            fireEvent.click(screen.getByRole("button", { name: "提交复核动作" }));
            expect(within(screen.getByLabelText("复核动作确认")).getByText("张三")).toBeTruthy();

            useParamsMock.mockReturnValue({ learnerId: "learner-b" });
            rerender(<SalesTrainerReadinessDossierPage />);
            await waitFor(() => {
                expect(getReadinessDossierMock).toHaveBeenCalledWith("learner-b");
            });
            expect(screen.queryByLabelText("复核动作确认")).toBeNull();
            expect(createReadinessReviewActionMock).not.toHaveBeenCalled();
            expect((screen.getByLabelText("原因") as HTMLTextAreaElement).value).toBe("");

            fireEvent.change(screen.getByLabelText("原因"), {
                target: { value: "学员 B 的确认原因。" },
            });
            fireEvent.click(screen.getByRole("button", { name: "提交复核动作" }));
            expect(within(screen.getByLabelText("复核动作确认")).getByText("李四")).toBeTruthy();
            fireEvent.click(
                screen.getByRole("button", { name: "确认新人达标并开放下一阶段" }),
            );
            await waitFor(() => {
                expect(createReadinessReviewActionMock).toHaveBeenCalledWith(
                    "learner-b",
                    expect.objectContaining({
                        idempotency_key: "00000000-0000-4000-8000-000000000002",
                        expected_latest_review_action_id: null,
                    }),
                );
            });
        } finally {
            randomUUIDSpy.mockRestore();
        }
    });

    it("ignores a stale learner A dossier response after switching to learner B", async () => {
        const learnerA = dossierFixture();
        learnerA.learner.learner_id = "learner-a";
        learnerA.learner.name = "张三";
        const learnerB = dossierFixture();
        learnerB.learner.learner_id = "learner-b";
        learnerB.learner.name = "李四";
        const learnerARequest = deferred<ReadinessDossier>();
        useParamsMock.mockReturnValue({ learnerId: "learner-a" });
        getReadinessDossierMock.mockImplementation((learnerId: string) => (
            learnerId === "learner-a"
                ? learnerARequest.promise
                : Promise.resolve(learnerB)
        ));

        const { rerender } = render(<SalesTrainerReadinessDossierPage />);
        await waitFor(() => {
            expect(getReadinessDossierMock).toHaveBeenCalledWith("learner-a");
        });

        useParamsMock.mockReturnValue({ learnerId: "learner-b" });
        rerender(<SalesTrainerReadinessDossierPage />);
        expect(await screen.findByText("李四的训练达标档案")).toBeTruthy();

        await act(async () => {
            learnerARequest.resolve(learnerA);
            await learnerARequest.promise;
        });
        await waitFor(() => {
            expect(screen.getByText("李四的训练达标档案")).toBeTruthy();
        });
        expect(screen.queryByText("张三的训练达标档案")).toBeNull();
    });

    it("does not apply learner A submission results after switching to learner B", async () => {
        const learnerA = dossierFixture();
        learnerA.learner.learner_id = "learner-a";
        learnerA.learner.name = "张三";
        const learnerB = dossierFixture();
        learnerB.learner.learner_id = "learner-b";
        learnerB.learner.name = "李四";
        const submission = deferred<{ decision_label: string }>();
        useParamsMock.mockReturnValue({ learnerId: "learner-a" });
        getReadinessDossierMock.mockImplementation((learnerId: string) => (
            Promise.resolve(learnerId === "learner-a" ? learnerA : learnerB)
        ));
        createReadinessReviewActionMock.mockReturnValue(submission.promise);

        const { rerender } = render(<SalesTrainerReadinessDossierPage />);
        await screen.findByText("张三的训练达标档案");
        fireEvent.change(screen.getByLabelText("原因"), {
            target: { value: "学员 A 的确认原因。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "提交复核动作" }));
        fireEvent.click(
            screen.getByRole("button", { name: "确认新人达标并开放下一阶段" }),
        );
        await waitFor(() => {
            expect(createReadinessReviewActionMock).toHaveBeenCalledWith(
                "learner-a",
                expect.any(Object),
            );
        });

        useParamsMock.mockReturnValue({ learnerId: "learner-b" });
        rerender(<SalesTrainerReadinessDossierPage />);
        expect(await screen.findByText("李四的训练达标档案")).toBeTruthy();

        await act(async () => {
            submission.resolve({ decision_label: "确认达标" });
            await submission.promise;
        });
        await waitFor(() => {
            expect(screen.getByText("李四的训练达标档案")).toBeTruthy();
        });
        expect(screen.queryByRole("status")).toBeNull();
        expect(getReadinessDossierMock.mock.calls.at(-1)?.[0]).toBe("learner-b");
    });

    it("keeps the dossier visible but hides write controls for ops read-only access", async () => {
        routeAccessMock.mockReturnValue({
            canAccess: true,
            capabilities: {
                role: "operations",
                role_label: "运维",
                capabilities: {
                    admin_full_access: false,
                    manage_content: false,
                    manage_questions: false,
                    manage_modules: false,
                    manage_prompts: false,
                    review_readiness: false,
                    view_records: true,
                    view_global_records: true,
                    retry_jobs: false,
                    regrade_history: false,
                    view_logs: false,
                    view_settings: false,
                },
                capability_keys: ["view_records", "view_global_records"],
            },
            denialMessage: null,
            error: null,
            isLoading: false,
            reloadCapabilities: vi.fn(),
        });
        render(<SalesTrainerReadinessDossierPage />);

        expect(await screen.findByText("PPT 讲解录音")).toBeTruthy();
        expect(screen.getByText(/当前账号仅可查看档案/)).toBeTruthy();
        expect(screen.queryByLabelText("结论")).toBeNull();
        expect(screen.queryByRole("button", { name: /提交复核动作/ })).toBeNull();
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
            state_storage: "readiness_review_action",
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
