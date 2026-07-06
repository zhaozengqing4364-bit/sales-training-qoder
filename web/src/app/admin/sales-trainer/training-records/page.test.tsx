import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerTrainingRecordsPage from "./page";

const {
    getCapabilitiesMock,
    pushMock,
    listTrainingRecordsMock,
    getJourneyAnalyticsMock,
    navigationState,
} = vi.hoisted(() => ({
    getCapabilitiesMock: vi.fn(),
    pushMock: vi.fn(),
    listTrainingRecordsMock: vi.fn(),
    getJourneyAnalyticsMock: vi.fn(),
    navigationState: {
        search: "",
    },
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/training-records",
    useRouter: () => ({ push: pushMock }),
    useSearchParams: () => new URLSearchParams(navigationState.search),
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
                    listTrainingRecords: listTrainingRecordsMock,
                    getJourneyAnalytics: getJourneyAnalyticsMock,
                },
            },
        },
    };
});

describe("SalesTrainerTrainingRecordsPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        pushMock.mockReset();
        listTrainingRecordsMock.mockReset();
        getJourneyAnalyticsMock.mockReset();
        navigationState.search = "";
        getCapabilitiesMock.mockResolvedValue({
            role: "ops",
            role_label: "运维人员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: true,
                view_global_records: true,
                retry_jobs: true,
                regrade_history: true,
                view_settings: true,
                view_logs: true,
            },
        });
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
                    training_stage: "needs_remediation",
                    learner_level: {
                        level_key: "unassigned",
                        label: "未分层",
                        source: "training_projection",
                        rank: 0,
                    },
                    role_level: {
                        level_key: "learner",
                        label: "普通学员",
                        source: "org_rule",
                        rank: 0,
                    },
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
                {
                    record_id: "rt-1",
                    record_type: "realtime_roleplay_session",
                    path_key: "newcomer_training_path_v1",
                    path_revision_id: "path-revision-1",
                    path_revision_no: 1,
                    module_key: "realtime_roleplay",
                    legacy_snapshot_only: false,
                    training_stage: "in_progress",
                    learner_level: {
                        level_key: "unassigned",
                        label: "未分层",
                        source: "training_projection",
                        rank: 0,
                    },
                    role_level: {
                        level_key: "learner",
                        label: "普通学员",
                        source: "org_rule",
                        rank: 0,
                    },
                    unit_id: "realtime-module",
                    unit_name: "新人实时对练",
                    unit_type: "realtime_roleplay",
                    user_id: "user-2",
                    user_name: "李四",
                    user_email: "lisi@example.com",
                    user_department: "销售二部",
                    status: "completed",
                    score: null,
                    max_score: null,
                    passed: null,
                    effective_score: {
                        score: null,
                        max_score: null,
                        passed: null,
                        source: "original_record",
                        original_score: null,
                        original_max_score: null,
                        score_delta: null,
                    },
                    latest_regrade: null,
                    score_explanation: null,
                    ability_profile: null,
                    remediation: null,
                    submitted_at: "2026-05-28T02:00:00Z",
                    material_snapshot: null,
                    score_scheme_snapshot: null,
                    task_brief_snapshot: null,
                    audio_submission: null,
                    quiz_attempt: null,
                    ai_coach_session: null,
                    realtime_roleplay_session: {
                        session_id: "rt-1",
                        snapshot: {
                            external_binding: {
                                binding_key: "newcomer_realtime_roleplay_v1",
                            },
                        },
                    },
                    operation_logs: [],
                },
            ],
            total: 2,
        });
        getJourneyAnalyticsMock.mockResolvedValue({
            generated_at: "2026-06-29T00:00:00Z",
            summary: {
                learner_count: 2,
                loaded_learner_count: 2,
                passed_learner_count: 1,
                risk_learner_count: 1,
                pass_rate: 0.5,
            },
            funnel: [],
            module_summaries: [
                {
                    module_key: "business_skills",
                    title: "商务技巧",
                    learner_count: 1,
                    passed_count: 0,
                    failed_count: 1,
                    status_counts: { needs_remediation: 1 },
                    pass_rate: 0,
                },
                {
                    module_key: "ai_coach",
                    title: "AI 教练",
                    learner_count: 1,
                    passed_count: 1,
                    failed_count: 0,
                    status_counts: { passed: 1 },
                    pass_rate: 1,
                },
                {
                    module_key: "realtime_roleplay",
                    title: "实时对练",
                    learner_count: 1,
                    passed_count: 0,
                    failed_count: 0,
                    status_counts: { in_progress: 1 },
                    pass_rate: null,
                },
            ],
            weakness_heatmap: [],
            trend_data: [],
            learner_level_summaries: [
                {
                    key: "unassigned",
                    label: "未分层",
                    learner_count: 2,
                    source: "training_projection",
                },
            ],
            role_level_summaries: [
                {
                    key: "learner",
                    label: "普通学员",
                    learner_count: 2,
                    source: "org_rule",
                },
            ],
            risk_learners: [],
            filters: {
                department: null,
                training_stage: null,
                module_key: null,
                learner_level: null,
                role_level: null,
                limit: 500,
            },
        });
    });

    it("shows original score, effective score, regrade delta, remediation, and unified detail link", async () => {
        render(<SalesTrainerTrainingRecordsPage />);

        await waitFor(() => {
            expect(listTrainingRecordsMock).toHaveBeenCalledWith({ limit: 100 });
        });

        expect(screen.getByText("商务技巧考卷")).toBeTruthy();
        expect(screen.getByLabelText("训练记录明细表格")).toBeTruthy();
        expect(screen.getByText("编号：unit-1")).toBeTruthy();
        expect(screen.getByText("18 / 20")).toBeTruthy();
        expect(screen.getByText("原始分 16 / 20")).toBeTruthy();
        expect(screen.getByText(/当前有效分 · 重评 \+2/)).toBeTruthy();
        expect(screen.getByText("安排弱项复习")).toBeTruthy();
        expect(screen.getAllByText("已评分").length).toBeGreaterThan(1);
        expect(screen.getAllByText("需补救").length).toBeGreaterThan(1);
        expect(screen.getAllByText("学员：未分层")[0]).toBeTruthy();
        expect(screen.getAllByText("角色：普通学员")[0]).toBeTruthy();
        expect(screen.getByText("新人实时对练")).toBeTruthy();
        expect(screen.getAllByText("实时对练").length).toBeGreaterThan(1);
        expect(screen.getAllByText("已完成").length).toBeGreaterThan(1);
        expect(screen.getByLabelText("学员编号")).toBeTruthy();
        expect(screen.getByLabelText("训练模块")).toBeTruthy();
        expect(screen.getByLabelText("训练阶段")).toBeTruthy();
        expect(screen.getByLabelText("记录状态")).toBeTruthy();
        expect(screen.getByLabelText("学员等级")).toBeTruthy();
        expect(screen.getByLabelText("角色等级")).toBeTruthy();
        expect(screen.getByRole("option", { name: "AI 教练" })).toBeTruthy();
        expect(screen.getByRole("option", { name: "未分层" })).toBeTruthy();
        expect(screen.getByRole("option", { name: "普通学员" })).toBeTruthy();
        expect(screen.queryByLabelText("用户 ID")).toBeNull();
        expect(screen.queryByText("scored")).toBeNull();

        fireEvent.click(screen.getAllByRole("button", { name: "查看详情" })[0]);
        expect(pushMock).toHaveBeenCalledWith(
            "/admin/sales-trainer/training-records/quiz_attempt/attempt-1",
        );
        fireEvent.click(screen.getAllByRole("button", { name: "查看详情" })[1]);
        expect(pushMock).toHaveBeenCalledWith(
            "/admin/sales-trainer/training-records/realtime_roleplay_session/rt-1",
        );
    });

    it("passes module, stage, level, and status filters to the records API", async () => {
        render(<SalesTrainerTrainingRecordsPage />);

        await waitFor(() => {
            expect(listTrainingRecordsMock).toHaveBeenCalledWith({ limit: 100 });
        });

        fireEvent.change(screen.getByLabelText("学员编号"), { target: { value: "user-1" } });
        fireEvent.change(screen.getByLabelText("训练任务编号"), { target: { value: "unit-1" } });
        fireEvent.change(screen.getByLabelText("材料版本编号"), { target: { value: "material-version-1" } });
        fireEvent.change(screen.getByLabelText("训练模块"), { target: { value: "business_skills" } });
        fireEvent.change(screen.getByLabelText("训练阶段"), { target: { value: "needs_remediation" } });
        fireEvent.change(screen.getByLabelText("记录状态"), { target: { value: "scored" } });
        fireEvent.change(screen.getByLabelText("学员等级"), { target: { value: "unassigned" } });
        fireEvent.change(screen.getByLabelText("角色等级"), { target: { value: "learner" } });
        fireEvent.click(screen.getByRole("button", { name: "查询" }));

        await waitFor(() => {
            expect(listTrainingRecordsMock).toHaveBeenLastCalledWith({
                user_id: "user-1",
                unit_id: "unit-1",
                material_version_id: "material-version-1",
                module_key: "business_skills",
                training_stage: "needs_remediation",
                status: "scored",
                learner_level: "unassigned",
                role_level: "learner",
                limit: 100,
            });
        });
        expect(pushMock).toHaveBeenCalledWith(
            "/admin/sales-trainer/training-records?user_id=user-1&unit_id=unit-1&material_version_id=material-version-1&module_key=business_skills&training_stage=needs_remediation&learner_level=unassigned&role_level=learner&status=scored",
        );
    });

    it("hydrates filters from analytics drilldown query and loads scoped records", async () => {
        navigationState.search = "?user_id=user-1&module_key=ai_coach";

        render(<SalesTrainerTrainingRecordsPage />);

        await waitFor(() => {
            expect(listTrainingRecordsMock).toHaveBeenCalledWith({
                user_id: "user-1",
                module_key: "ai_coach",
                limit: 100,
            });
        });
        expect((screen.getByLabelText("学员编号") as HTMLInputElement).value).toBe("user-1");
        expect((screen.getByLabelText("训练模块") as HTMLSelectElement).value).toBe("ai_coach");
    });

    it("does not request records before view_records capability is confirmed", async () => {
        getCapabilitiesMock.mockResolvedValue({
            role: "content_admin",
            role_label: "内容管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: true,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_settings: false,
                view_logs: false,
            },
        });

        render(<SalesTrainerTrainingRecordsPage />);

        expect(await screen.findByText("训练记录权限不足")).toBeTruthy();
        expect(screen.queryByText("暂无训练记录")).toBeNull();
        expect(listTrainingRecordsMock).not.toHaveBeenCalled();
    });

    it("shows a recoverable list load error instead of an empty record state", async () => {
        listTrainingRecordsMock
            .mockRejectedValueOnce(new Error("records service unavailable"))
            .mockResolvedValueOnce({
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
                        latest_regrade: null,
                        score_explanation: null,
                        ability_profile: null,
                        remediation: null,
                        submitted_at: "2026-05-28T00:00:00Z",
                        material_snapshot: null,
                        score_scheme_snapshot: null,
                        task_brief_snapshot: null,
                        audio_submission: null,
                        quiz_attempt: null,
                        ai_coach_session: null,
                        realtime_roleplay_session: null,
                        operation_logs: [],
                    },
                ],
                total: 1,
            });

        render(<SalesTrainerTrainingRecordsPage />);

        expect(await screen.findByText("训练记录加载失败")).toBeTruthy();
        expect(screen.getByText("records service unavailable")).toBeTruthy();
        expect(screen.queryByText("暂无训练记录")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: "重新加载训练记录" }));

        expect(await screen.findByText("商务技巧考卷")).toBeTruthy();
        await waitFor(() => {
            expect(listTrainingRecordsMock).toHaveBeenCalledTimes(2);
        });
    });
});
