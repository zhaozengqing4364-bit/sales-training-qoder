import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

import SupervisorTrainingPage from "./page";
import { api } from "@/lib/api/client";
import type {
    CertificationReviewQueueItem,
    TeamInsightsResponse,
    TeamInsightsLearnerDetail,
} from "@/lib/api/types";

vi.mock("@/lib/api/client", () => ({
    api: {
        supervisor: {
            getTeamInsights: vi.fn(),
            getLearnerDetail: vi.fn(),
            listCertificationReviewQueue: vi.fn(),
            updateReviewDecision: vi.fn(),
            upsertScoreCalibration: vi.fn(),
        },
    },
    getApiErrorMessage: vi.fn((err: unknown) => {
        if (err instanceof Error) return err.message;
        return "未知错误";
    }),
}));

vi.mock("@/lib/debug", () => ({
    debug: { warn: vi.fn() },
}));

function makeEmptyResponse(): TeamInsightsResponse {
    return {
        completion: { total_tasks: 0, completed_tasks: 0, completion_rate: 0, by_status: {} },
        top_weaknesses: [],
        top3_common_issues: [],
        readiness: { by_status: {}, learners: [] },
        retraining_candidates: [],
        learners: [],
    };
}

function makeFullResponse(overrides: Partial<TeamInsightsResponse> = {}): TeamInsightsResponse {
    return {
        completion: { total_tasks: 10, completed_tasks: 7, completion_rate: 70.0, by_status: { completed: 7, assigned: 3 } },
        top_weaknesses: [
            { dimension: "异议处理", count: 5, average_score: 3.2, learner_ids: ["u1", "u2", "u3"] },
            { dimension: "需求挖掘", count: 4, average_score: 3.5, learner_ids: ["u1", "u4"] },
        ],
        top3_common_issues: [
            { issue: "开场白过长", dimension: "沟通效率", count: 6, learner_ids: ["u1", "u2", "u3", "u4"] },
            { issue: "未确认客户需求", dimension: "需求挖掘", count: 5, learner_ids: ["u1", "u3"] },
            { issue: "价值主张模糊", dimension: "方案呈现", count: 4, learner_ids: ["u2", "u4"] },
        ],
        readiness: {
            by_status: { approved: 3, ready_for_trial: 2, shadow_only: 1 },
            learners: [
                { learner_id: "u1", learner_name: "张三", readiness_status: "approved", latest_review_id: "r1", session_id: "s1" },
                { learner_id: "u2", learner_name: "李四", readiness_status: "ready_for_trial", latest_review_id: "r2", session_id: "s2" },
            ],
        },
        retraining_candidates: [
            {
                learner_id: "u3", learner_name: "王五", session_id: "s3", review_id: "r3",
                retraining_task_id: "rt1", training_task_id: null,
                skill_dimension: "异议处理", readiness_status: "not_ready", reason: "异议处理分数过低",
            },
        ],
        learners: [
            {
                learner_id: "u1", learner_name: "张三",
                completion: { total_tasks: 5, completed_tasks: 5, completion_rate: 100.0, by_status: { completed: 5 } },
                latest_score: 85.5, readiness_status: "approved", top_weaknesses: [], config_metadata: {},
            },
            {
                learner_id: "u2", learner_name: "李四",
                completion: { total_tasks: 3, completed_tasks: 2, completion_rate: 67.0, by_status: { completed: 2, assigned: 1 } },
                latest_score: null, readiness_status: null,
                top_weaknesses: [{ dimension: "需求挖掘", count: 1, average_score: null, learner_ids: ["u2"] }],
                config_metadata: {},
            },
        ],
        ...overrides,
    };
}

function makeLearnerDetail(overrides: Partial<TeamInsightsLearnerDetail> = {}): TeamInsightsLearnerDetail {
    return {
        learner_id: "u1", learner_name: "张三",
        learner_email: "zhangsan@example.com",
        completion: { total_tasks: 5, completed_tasks: 5, completion_rate: 100.0, by_status: { completed: 5 } },
        latest_score: 85.5, readiness_status: "approved",
        top_weaknesses: [], config_metadata: { version_label: "v1", bundle_key: "scoring.rulesets" },
        training_tasks: [{ task_id: "t1", title: "销售开场白训练", scenario_type: "sales", status: "completed", goal: "提升开场白" }],
        latest_review: null,
        common_issues: [{ issue: "开场白过长", dimension: "沟通效率", count: 2, learner_ids: ["u1"] }],
        retraining_candidates: [],
        ...overrides,
    };
}

function makeCertificationQueueItem(
    overrides: Partial<CertificationReviewQueueItem> = {},
): CertificationReviewQueueItem {
    return {
        review_id: "review-cert-1",
        session_id: "session-cert-1",
        report_id: "report-cert-1",
        learner: { user_id: "u-cert", name: "赵六", email: "zhaoliu@example.com" },
        curriculum: {
            practice_template: { template_id: "tpl-cert", name: "新人认证路径" },
            stage_keys: ["template_stage_onboarding_certification_review"],
            stage_snapshots: {
                template_stage_onboarding_certification_review: {
                    runtime_payload: { mode: "customer_roleplay" },
                },
            },
        },
        score: 72,
        evidence: {
            transcript_anchors: [{ evidence_id: "ev-1", evidence_type: "transcript", quote: "认证关键证据" }],
            stage_snapshots: {
                template_stage_onboarding_certification_review: {
                    runtime_payload: { mode: "customer_roleplay" },
                },
            },
            thinking_evidence: [
                {
                    turn_index: 2,
                    template_stage_key: "template_stage_onboarding_certification_review",
                    response_id: "resp-cert",
                    thinking_text: "Reviewer-only certification reasoning",
                    captured_at: "2026-05-13T10:00:00Z",
                },
            ],
        },
        submitted_at: "2026-05-13T10:00:00Z",
        outcome: "pending",
        ...overrides,
    };
}

describe("SupervisorTrainingPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        vi.mocked(api.supervisor.listCertificationReviewQueue).mockResolvedValue([]);
        vi.mocked(api.supervisor.updateReviewDecision).mockResolvedValue({
            review_id: "review-cert-1",
            session_id: "session-cert-1",
            trainee_user_id: "u-cert",
            supervisor_user_id: "admin-1",
            decision: "approved",
            readiness_status: "approved",
            required_retraining: false,
            retraining_tasks: [],
            calibrations: [],
        });
        vi.mocked(api.supervisor.upsertScoreCalibration).mockResolvedValue({
            review_id: "review-cert-1",
            session_id: "session-cert-1",
            dimension: "template_stage_onboarding_certification_review",
            ai_score: 72,
            supervisor_score: 72,
            calibration_label: "accurate",
            comment: "认证复核：校准",
        });
    });

    it("should show loading state initially", async () => {
        let resolvePromise: (value: TeamInsightsResponse) => void = () => {};
        vi.mocked(api.supervisor.getTeamInsights).mockReturnValue(
            new Promise<TeamInsightsResponse>((resolve) => { resolvePromise = resolve; }),
        );
        render(<SupervisorTrainingPage />);
        expect(screen.getByText(/正在加载主管训练数据/i)).toBeDefined();
        resolvePromise(makeEmptyResponse());
    });

    it("should show error state when API fails", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockRejectedValue(new Error("网络错误"));
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/重试加载/)).toBeDefined(); });
        expect(screen.getByText(/网络错误/)).toBeDefined();
    });

    it("should retry on clicking retry button", async () => {
        vi.mocked(api.supervisor.getTeamInsights)
            .mockRejectedValueOnce(new Error("网络错误"))
            .mockResolvedValueOnce(makeFullResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/重试加载/)).toBeDefined(); });
        fireEvent.click(screen.getByText(/重试加载/));
        await waitFor(() => { expect(screen.getByText(/团队训练完成率/)).toBeDefined(); });
        expect(api.supervisor.getTeamInsights).toHaveBeenCalledTimes(2);
    });

    it("should show empty state when no data", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeEmptyResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/暂无团队训练数据/)).toBeDefined(); });
        expect(screen.getByText("0%")).toBeDefined();
    });

    it("should render completion rate correctly with backend percent semantics", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/团队训练完成率/)).toBeDefined(); });
        expect(screen.getByText("70%")).toBeDefined();
        expect(screen.getByText("7")).toBeDefined();
        expect(screen.getByText("10")).toBeDefined();
    });

    it("should render top weaknesses", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/团队弱项维度/)).toBeDefined(); });
        expect(screen.getByText("异议处理")).toBeDefined();
        expect(screen.getAllByText(/需求挖掘/).length).toBeGreaterThanOrEqual(1);
    });

    it("should render Top3 common issues", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/Top3 共性问题/)).toBeDefined(); });
        expect(screen.getByText("开场白过长")).toBeDefined();
        expect(screen.getByText("未确认客户需求")).toBeDefined();
        expect(screen.getByText("价值主张模糊")).toBeDefined();
    });

    it("should render readiness pipeline", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/准备状态管道/)).toBeDefined(); });
        expect(screen.getAllByText(/已批准/).length).toBeGreaterThanOrEqual(1);
    });

    it("should render retraining candidates", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/待复训学员/)).toBeDefined(); });
        expect(screen.getByText("王五")).toBeDefined();
    });

    it("should show 暂无数据 for null average_score in weaknesses", async () => {
        const response = makeFullResponse({
            top_weaknesses: [{ dimension: "需求挖掘", count: 4, average_score: null, learner_ids: ["u1"] }],
        });
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(response);
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/团队训练完成率/)).toBeDefined(); });
        expect(screen.getAllByText("暂无数据").length).toBeGreaterThanOrEqual(1);
    });

    it("should show 证据不足 for learner with null readiness", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/团队训练完成率/)).toBeDefined(); });
        expect(screen.getByText(/证据不足/)).toBeDefined();
    });

    it("should send filter params when clicking 筛选", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeEmptyResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByPlaceholderText(/场景类型/)).toBeDefined(); });
        fireEvent.change(screen.getByPlaceholderText(/场景类型/), { target: { value: "sales" } });
        fireEvent.click(screen.getByText("筛选"));
        await waitFor(() => {
            expect(api.supervisor.getTeamInsights).toHaveBeenCalledWith(
                expect.objectContaining({ scenario_type: "sales" }),
            );
        });
    });

    it("should open learner detail panel on clicking learner name", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        const detail = makeLearnerDetail();
        vi.mocked(api.supervisor.getLearnerDetail).mockResolvedValue(detail);
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/团队训练完成率/)).toBeDefined(); });
        fireEvent.click(screen.getAllByText("张三")[0]!);
        await waitFor(() => {
            expect(api.supervisor.getLearnerDetail).toHaveBeenCalledWith("u1", undefined);
        });
        await waitFor(() => { expect(screen.getByText("zhangsan@example.com")).toBeDefined(); });
    });

    it("should show error in detail panel when learner detail API fails", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        vi.mocked(api.supervisor.getLearnerDetail).mockRejectedValue(new Error("详情加载失败"));
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/团队训练完成率/)).toBeDefined(); });
        fireEvent.click(screen.getAllByText("张三")[0]!);
        await waitFor(() => { expect(screen.getByText(/详情加载失败/)).toBeDefined(); });
    });

    it("should close learner detail panel", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        vi.mocked(api.supervisor.getLearnerDetail).mockResolvedValue(makeLearnerDetail());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/团队训练完成率/)).toBeDefined(); });
        fireEvent.click(screen.getAllByText("张三")[0]!);
        await waitFor(() => { expect(screen.getByText("zhangsan@example.com")).toBeDefined(); });
        fireEvent.click(screen.getByText(/关闭/));
        await waitFor(() => { expect(screen.queryByText("zhangsan@example.com")).toBeNull(); });
    });

    it("should refresh data when clicking refresh button", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        render(<SupervisorTrainingPage />);
        await waitFor(() => { expect(screen.getByText(/刷新/)).toBeDefined(); });
        fireEvent.click(screen.getByText(/刷新/));
        await waitFor(() => { expect(api.supervisor.getTeamInsights).toHaveBeenCalledTimes(2); });
    });

    it("should render certification review queue with curriculum evidence and thinking", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        vi.mocked(api.supervisor.listCertificationReviewQueue).mockResolvedValue([
            makeCertificationQueueItem(),
        ]);

        render(<SupervisorTrainingPage />);

        await waitFor(() => { expect(screen.getByText(/认证复核队列/)).toBeDefined(); });
        expect(screen.getByText("赵六")).toBeDefined();
        expect(screen.getByText("新人认证路径")).toBeDefined();
        expect(screen.getByText(/72/)).toBeDefined();
        expect(screen.getByText("认证关键证据")).toBeDefined();
        expect(screen.getByText("Reviewer-only certification reasoning")).toBeDefined();
    });

    it("should submit approve reject calibrate and retrain actions from certification queue", async () => {
        vi.mocked(api.supervisor.getTeamInsights).mockResolvedValue(makeFullResponse());
        vi.mocked(api.supervisor.listCertificationReviewQueue).mockResolvedValue([
            makeCertificationQueueItem(),
        ]);

        render(<SupervisorTrainingPage />);

        await waitFor(() => { expect(screen.getByText("赵六")).toBeDefined(); });
        fireEvent.click(screen.getByRole("button", { name: "批准" }));
        await waitFor(() => {
            expect(api.supervisor.updateReviewDecision).toHaveBeenCalledTimes(1);
        });
        fireEvent.click(screen.getByRole("button", { name: "驳回" }));
        await waitFor(() => {
            expect(api.supervisor.updateReviewDecision).toHaveBeenCalledTimes(2);
        });
        fireEvent.click(screen.getByRole("button", { name: "要求复训" }));

        await waitFor(() => {
            expect(api.supervisor.updateReviewDecision).toHaveBeenCalledTimes(3);
            expect(api.supervisor.updateReviewDecision).toHaveBeenCalledWith(
                "review-cert-1",
                expect.objectContaining({ decision: "approved", readiness_status: "approved" }),
            );
        });
        expect(api.supervisor.updateReviewDecision).toHaveBeenCalledWith(
            "review-cert-1",
            expect.objectContaining({ decision: "rejected", readiness_status: "not_ready" }),
        );
        expect(api.supervisor.updateReviewDecision).toHaveBeenCalledWith(
            "review-cert-1",
            expect.objectContaining({
                decision: "needs_retraining",
                readiness_status: "shadow_only",
                required_retraining: true,
            }),
        );

        fireEvent.click(screen.getByRole("button", { name: "校准" }));
        await waitFor(() => {
            expect(api.supervisor.upsertScoreCalibration).toHaveBeenCalledWith(
                "review-cert-1",
                expect.objectContaining({
                    session_id: "session-cert-1",
                    dimension: "template_stage_onboarding_certification_review",
                    ai_score: 72,
                    supervisor_score: 72,
                    calibration_label: "accurate",
                    comment: "认证复核：校准",
                }),
            );
        });
    });
});
