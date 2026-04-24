import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ReportPage from "./page";
import { ApiRequestError } from "@/lib/api/client";

const {
    pushMock,
    getReportMock,
    getReportTrendsMock,
    getNextRecommendationMock,
    getReplayMock,
    getKnowledgeCheckMock,
    getHighlightsMock,
    getHighlightReviewMock,
    saveHighlightReviewMock,
    createHighlightReviewShareMock,
    revokeHighlightReviewShareMock,
    createSessionMock,
    getComprehensiveReportMock,
    generateComprehensiveReportMock,
    getSegmentAudioBlobUrlMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    getReportMock: vi.fn(),
    getReportTrendsMock: vi.fn(),
    getNextRecommendationMock: vi.fn(),
    getReplayMock: vi.fn(),
    getKnowledgeCheckMock: vi.fn(),
    getHighlightsMock: vi.fn(),
    getHighlightReviewMock: vi.fn(),
    saveHighlightReviewMock: vi.fn(),
    createHighlightReviewShareMock: vi.fn(),
    revokeHighlightReviewShareMock: vi.fn(),
    createSessionMock: vi.fn(),
    getComprehensiveReportMock: vi.fn(),
    generateComprehensiveReportMock: vi.fn(),
    getSegmentAudioBlobUrlMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
    useParams: () => ({
        sessionId: "session-1",
    }),
}));

vi.mock("@/components/highlights", () => ({
    HighlightList: ({
        highlights,
        onJumpToMessage,
        reviewSelectedIds = [],
        onToggleReviewItem,
    }: {
        highlights: Array<{ id: string; turn_number: number; highlight_type?: string }>;
        onJumpToMessage?: (turnNumber: number) => void;
        reviewSelectedIds?: string[];
        onToggleReviewItem?: (highlight: { id: string; turn_number: number; highlight_type?: string }) => void;
    }) => (
        <div data-testid="highlight-list">
            <div>高光数:{highlights.length}</div>
            <div>复习清单已选:{reviewSelectedIds.join(",") || "无"}</div>
            {highlights[0] ? (
                <>
                    <button type="button" onClick={() => onJumpToMessage?.(highlights[0].turn_number)}>
                        跳到高光回放
                    </button>
                    {onToggleReviewItem && highlights[0].highlight_type === "bad" ? (
                        <button type="button" onClick={() => onToggleReviewItem(highlights[0])}>
                            加入复习清单
                        </button>
                    ) : null}
                </>
            ) : null}
        </div>
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            sessions: {
                ...actual.api.sessions,
                getReport: getReportMock,
                getReportTrends: getReportTrendsMock,
                getNextRecommendation: getNextRecommendationMock,
                getReplay: getReplayMock,
                getKnowledgeCheck: getKnowledgeCheckMock,
                getHighlights: getHighlightsMock,
                getHighlightReview: getHighlightReviewMock,
                saveHighlightReview: saveHighlightReviewMock,
                createHighlightReviewShare: createHighlightReviewShareMock,
                revokeHighlightReviewShare: revokeHighlightReviewShareMock,
                getSegmentAudioBlobUrl: getSegmentAudioBlobUrlMock,
            },
            practice: {
                ...actual.api.practice,
                createSession: createSessionMock,
            },
            admin: {
                ...actual.api.admin,
                getComprehensiveReport: getComprehensiveReportMock,
                generateComprehensiveReport: generateComprehensiveReportMock,
            },
        },
    };
});

const baseRetrievalFacts = {
    kb_bound: true,
    knowledge_base_ids: ["kb-product"],
    knowledge_base_count: 1,
    retrieval_enabled: true,
    status: "hit" as const,
    summary: "知识检索已触发并命中知识库",
    attempt_count: 2,
    hit_count: 1,
    hit_rate: 0.5,
    latest_attempt: {
        status: "hit",
        query: "这个方案的 ROI 怎么证明？",
        attempted_at: "2026-03-27T08:00:00Z",
        retrieval_mode: "hybrid",
        result_count: 2,
        knowledge_base_ids: ["kb-product"],
        result_summaries: [
            {
                knowledge_base_id: "kb-product",
                knowledge_base_name: "产品知识库",
                snippet: "某制造业客户上线后 3 个月回款周期缩短 18%，库存周转提升 12%。",
                retrieval_mode: "hybrid",
                score: 0.93,
            },
            {
                knowledge_base_id: "kb-product",
                knowledge_base_name: "产品知识库",
                snippet: "历史项目里，首年 ROI 通常在 1.6 到 2.1 之间。",
                retrieval_mode: "hybrid",
                score: 0.81,
            },
        ],
    },
    miss_explanation: null,
    failure_explanation: null,
};

const baseAudioAudit = {
    summary: {
        recording_status: "completed",
        total_segments: 2,
        uploaded_segments: 2,
        failed_segments: 0,
        total_bytes: 40960,
        latest_segment_sequence: 1,
        storage_prefix: "sessions/session-1/audio",
        last_uploaded_at: "2026-03-27T08:10:00Z",
        learner_status: "available" as const,
        degraded_reasons: [],
    },
    segments: [
        {
            segment_sequence: 0,
            created_at: "2026-03-27T08:00:00Z",
            duration_ms: 12000,
            size_bytes: 20480,
            upload_status: "uploaded",
            playback_path: "/api/v1/sessions/session-1/audio-segments/0",
            error_message: null,
        },
        {
            segment_sequence: 1,
            created_at: "2026-03-27T08:00:12Z",
            duration_ms: null,
            size_bytes: 20480,
            upload_status: "uploaded",
            playback_path: "/api/v1/sessions/session-1/audio-segments/1",
            error_message: null,
        },
    ],
};

const baseConclusionEvidence = {
    main_issue: {
        retrieval_source: { available: true, reason: null },
        transcript_source: { available: true, turn_count: 1 },
        audio_source: { available: true, reason: null },
    },
    next_goal: {
        retrieval_source: { available: true, reason: null },
        transcript_source: { available: true, turn_count: 1 },
        audio_source: { available: true, reason: null },
    },
    claim_truth: {
        retrieval_source: { available: true, reason: null },
        transcript_source: { available: true, turn_count: 1 },
        audio_source: { available: true, reason: null },
    },
};

const baseEvidenceDegradation = {
    retrieval: { status: "ok" as const, token: "retrieval_ok", explanation: null },
    transcript: { status: "ok" as const, token: "transcript_ok", explanation: null },
    audio: { status: "ok" as const, token: "audio_ok", explanation: null },
    enhanced_report: { status: "ok" as const, token: "enhanced_report_ok", explanation: null },
};

const baseReport = {
    session_id: "session-1",
    scenario_type: "sales" as const,
    logic_score: 68,
    accuracy_score: 74,
    completeness_score: 70,
    overall_score: 72,
    suggestions: ["先补足轮次后再复盘"],
    audio_url: null,
    transcript_url: null,
    voice_policy_snapshot_ref: null,
    audio_audit: baseAudioAudit,
    effectiveness_snapshot: {
        claim_truth: {
            status: "evidence_pending",
            label: "证据待补齐",
            source: "fallback_snapshot",
            reason: "insufficient_turn_data",
        },
    },
    pass_flags: null,
    main_capability_passed: false,
    overall_result: "fail" as const,
    main_issue: {
        issue_type: "insufficient_turns",
        issue_text: "有效回合不足，无法判断完整销售闭环。",
        recovery_rule: "至少完成 3 轮有效问答。",
    },
    next_goal: null,
    stage_summary: [
        {
            stage: "opening",
            duration_ms: 90000,
            score: 72,
        },
    ],
    evaluable: false,
    not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
    evidence_completeness: {
        complete: false,
        missing_fields: ["closing_stage"],
        message_count: 2,
    },
    retry_entry: {
        scenario_type: "sales" as const,
        agent_id: "agent-1",
        persona_id: "persona-1",
    },
    conclusion_evidence: baseConclusionEvidence,
    evidence_degradation: baseEvidenceDegradation,
};

const baseReplayData = {
    session_id: "session-1",
    agent_name: "销售教练",
    persona_name: "采购经理",
    voice_policy_snapshot_ref: null,
    total_duration_ms: 180000,
    overall_score: 72,
    effectiveness_snapshot: null,
    pass_flags: null,
    main_capability_passed: false,
    overall_result: "fail" as const,
    main_issue: null,
    next_goal: null,
    evaluable: true,
    not_evaluable_reason: null,
    evidence_completeness: {
        complete: true,
        missing_fields: [],
        message_count: 6,
    },
    messages: [],
    timeline_markers: [],
    stage_summary: [],
};

const basePresentationReview = {
    overall_score: 88,
    dimension_scores: [
        { name: "流畅连贯性", score: 90, weight: 0.22, description: "讲解节奏、重复情况与口头语控制。" },
        { name: "准确性", score: 86, weight: 0.2, description: "内容与资料一致性、错误信息控制。" },
        { name: "专业性", score: 84, weight: 0.18, description: "术语使用、结构组织与专业说服力。" },
        { name: "生动性", score: 82, weight: 0.14, description: "表达感染力、案例化与记忆点设计。" },
        { name: "互动问答", score: 80, weight: 0.14, description: "对提问的回应质量与现场互动承接。" },
        { name: "其他表现", score: 78, weight: 0.12, description: "时间控制、状态管理与其他综合表现。" },
    ],
    page_summaries: [
        {
            page_number: 1,
            stage_number: 1,
            start_turn: 1,
            end_turn: 2,
            average_score: 88,
            key_points: ["业务目标", "客户问题"],
            matched_required_points: ["业务目标", "客户问题"],
            missing_required_points: [],
            summary: "第一页完整讲清业务目标与客户问题。",
        },
        {
            page_number: 2,
            stage_number: 2,
            start_turn: 3,
            end_turn: 4,
            average_score: 84,
            key_points: ["ROI结果", "客户案例"],
            matched_required_points: ["ROI结果"],
            missing_required_points: ["客户案例"],
            summary: "第二页补充了 ROI 结果，但客户案例展开不够具体。",
        },
    ],
    required_talking_points: {
        status: "complete" as const,
        total: 3,
        covered: 2,
        missing: 1,
        coverage_ratio: 2 / 3,
    },
    issue_counts: {
        forbidden_word: 1,
        missing_point: 1,
        vague_response: 1,
    },
    strengths: ["表达流畅", "页间衔接自然"],
    improvements: ["补足客户案例细节"],
    recommendations: ["下一轮按页准备必须讲到的案例与 ROI 证据。"],
    detailed_feedback: "整体讲解稳定，但第二页的案例支撑仍不够扎实。",
    has_page_metadata: true,
    coverage_status: "complete" as const,
    diagnostics: {
        has_page_metadata: true,
        pages_with_messages: 2,
        total_pages: 2,
        page_coverage_ratio: 1,
        required_points_total: 3,
        required_points_covered: 2,
        required_points_missing: 1,
        required_coverage_ratio: 2 / 3,
        degraded_reasons: [],
    },
};

const basePresentationReport = {
    session_id: "session-1",
    scenario_type: "presentation" as const,
    logic_score: 90,
    accuracy_score: 86,
    completeness_score: 81,
    overall_score: 88,
    suggestions: ["下一轮继续补强第二页案例细节。"],
    audio_url: null,
    transcript_url: null,
    voice_policy_snapshot_ref: null,
    audio_audit: baseAudioAudit,
    effectiveness_snapshot: null,
    pass_flags: null,
    main_capability_passed: null,
    overall_result: null,
    main_issue: null,
    next_goal: null,
    stage_summary: [],
    evaluable: null,
    not_evaluable_reason: null,
    evidence_completeness: {
        complete: true,
        scenario_type: "presentation",
        presentation_review_available: true,
        page_metadata_complete: true,
        page_summary_count: 2,
        required_talking_points_status: "complete",
        required_points_total: 3,
        required_points_covered: 2,
        required_points_missing: 1,
        required_coverage_ratio: 2 / 3,
        degraded_reasons: [],
    },
    presentation_review: basePresentationReview,
    retry_entry: {
        scenario_type: "presentation" as const,
        presentation_id: "presentation-1",
        agent_id: null,
        persona_id: null,
    },
    conclusion_evidence: null,
    evidence_degradation: null,
};

describe("ReportPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        getReportMock.mockReset();
        getReportTrendsMock.mockReset();
        getNextRecommendationMock.mockReset();
        getReplayMock.mockReset();
        getKnowledgeCheckMock.mockReset();
        getHighlightsMock.mockReset();
        createSessionMock.mockReset();
        getComprehensiveReportMock.mockReset();
        generateComprehensiveReportMock.mockReset();
        getSegmentAudioBlobUrlMock.mockReset();
        localStorage.clear();

        getReplayMock.mockResolvedValue(baseReplayData);
        getReportTrendsMock.mockResolvedValue({
            session_id: "session-1",
            scenario_type: "sales",
            score_basis: "session_evidence_projection_evaluable_only",
            points: [
                {
                    session_id: "session-0",
                    date: "2026-03-20T00:00:00Z",
                    scenario_type: "sales",
                    logic_score: 60,
                    accuracy_score: 62,
                    completeness_score: 64,
                    overall_score: 62,
                    is_current: false,
                },
                {
                    session_id: "session-1",
                    date: "2026-03-21T00:00:00Z",
                    scenario_type: "sales",
                    logic_score: 68,
                    accuracy_score: 74,
                    completeness_score: 70,
                    overall_score: 72,
                    is_current: true,
                },
            ],
            delta_vs_previous: {
                logic_score: 8,
                accuracy_score: 12,
                completeness_score: 6,
                overall_score: 10,
            },
            explanation: null,
        });
        getNextRecommendationMock.mockResolvedValue({
            title: "补强产品知识与证据表达",
            reason: "上次可评估训练中「产品知识与证据」为 55 分，低于 60 分阈值。",
            action_label: "练产品知识专项",
            target_path: "/training/sales?focus=product_knowledge",
            recommendation_kind: "next_practice_ruleset",
            scenario_type: "sales",
            source_session_id: "session-1",
            rule_version: "growth_recommendation_rules_v1",
            explanation: "上次可评估训练中「产品知识与证据」为 55 分，低于 60 分阈值。",
            evidence_summary: {
                weak_dimension: "product_knowledge",
                score_field: "accuracy_score",
                score: 55,
                threshold: 60,
            },
        });
        getKnowledgeCheckMock.mockRejectedValue(new Error("knowledge check unavailable"));
        getHighlightsMock.mockResolvedValue({
            highlights: [],
            total_good: 0,
            total_bad: 0,
        });
        createSessionMock.mockResolvedValue({ session_id: "retry-1" });
        getSegmentAudioBlobUrlMock.mockResolvedValue("blob:audio-segment-1");
    });

    it("renders evaluable-only trend comparison and ruleset recommendation on report", async () => {
        getReportMock.mockResolvedValue(baseReport);
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced unavailable"));

        render(<ReportPage />);

        expect(await screen.findByText("同场景趋势对比")).toBeTruthy();
        expect(await screen.findByText("较上次 +10.0 分")).toBeTruthy();
        expect(await screen.findByText("推荐下次练什么")).toBeTruthy();
        expect(await screen.findByText("补强产品知识与证据表达")).toBeTruthy();
        expect(getReportTrendsMock).toHaveBeenCalledWith("session-1", 5);
        expect(getNextRecommendationMock).toHaveBeenCalledWith("session-1");
    });

    it("renders learner-facing degraded audio wording when partial audio is reported", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            audio_audit: {
                summary: {
                    ...baseAudioAudit.summary,
                    learner_status: "partial",
                    uploaded_segments: 1,
                    failed_segments: 1,
                    degraded_reasons: ["upload_failed"],
                },
                segments: [
                    baseAudioAudit.segments[0],
                    {
                        ...baseAudioAudit.segments[1],
                        upload_status: "failed",
                        playback_path: null,
                        error_message: "签名已过期，请重新上传",
                    },
                ],
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("部分音频片段上传失败")).toBeTruthy();
        expect(screen.getByText("签名已过期，请重新上传")).toBeTruthy();
    });

    it("renders sales rollup cards and sales-specific issue/goal copy from the unified report contract", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            logic_score: 84,
            accuracy_score: 73,
            completeness_score: 69,
            overall_score: 76,
            evaluable: true,
            not_evaluable_reason: null,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "weak_evidence",
                    label: "证据偏弱",
                    source: "score_snapshot",
                    reason: "low_evidence_score",
                    evidence_score: 63,
                },
            },
            main_issue: {
                issue_type: "evidence_gap",
                issue_text: "功能点说得多，但还没有把产品价值翻译成客户收益。",
                recovery_rule: "下一轮先用客户收益语言重述价值，再回应价格顾虑。",
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先补 ROI 证据，再推进一个明确的下一步动作。",
                rule: "至少给出一条证据并确认下一步。",
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 91,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("76");
        expect(screen.getByText("报告看不懂或证据不足时怎么办？")).toBeTruthy();
        expect(screen.getByText(/先看主问题、下一轮目标和高光复习清单/)).toBeTruthy();
        expect(screen.getByText("销售能力总览")).toBeTruthy();
        expect(screen.getByText("价值表达")).toBeTruthy();
        expect(screen.getByText("证据与收益")).toBeTruthy();
        expect(screen.getByText("异议推进")).toBeTruthy();
        expect(screen.getAllByText("主张证据状态").length).toBeGreaterThan(0);
        expect(screen.getByText("已经给出了证据，但力度还不够，仍需要更具体的案例、数据或 ROI 证明。")).toBeTruthy();
        expect(screen.getByText("证据强度：63 分。")).toBeTruthy();
        expect(screen.getByText("证据支撑")).toBeTruthy();
        expect(screen.getByText("证据补强")).toBeTruthy();
        expect(screen.getByText("下一轮训练卡")).toBeTruthy();
        expect(screen.getByText("汇总上次卡点、修正动作、判定条件、回放锚点和按目标再练入口。")).toBeTruthy();
        expect(screen.getByText("功能点说得多，但还没有把产品价值翻译成客户收益。")).toBeTruthy();
        expect(screen.getByText("修正动作：下一轮先用客户收益语言重述价值，再回应价格顾虑。")).toBeTruthy();
        expect(screen.getByText("先补 ROI 证据，再推进一个明确的下一步动作。")).toBeTruthy();
        expect(screen.getByText("判定条件：至少给出一条证据并确认下一步。")).toBeTruthy();
        expect(screen.getByText("综合评分反映价值翻译、证据支撑和异议推进的完成度。"))
            .toBeTruthy();
        expect(screen.getByTestId("audio-audit-card")).toBeTruthy();
        expect(screen.getByText("原始录音")).toBeTruthy();
        expect(screen.getByText("共 2 个片段 · 总时长 0:12")).toBeTruthy();
        expect(screen.getByText("片段 1")).toBeTruthy();
        expect(screen.getByText(/未知时长/)).toBeTruthy();
    });

    it("prefers canonical report rollups over stale legacy score fields", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            logic_score: 41,
            accuracy_score: 42,
            completeness_score: 43,
            overall_score: 44,
            evaluable: true,
            not_evaluable_reason: null,
            canonical_evaluation_kernel: {
                schema_version: "evaluation_kernel_v1",
                scenario_type: "sales",
                surface_id: "report",
                source_reader_id: "session_evidence_projection_v1",
                primary_reader_id: "session_evidence_projection_v1",
                mode: "canonical_consumer",
                rollups: {
                    logic: { label: "逻辑", score: 84 },
                    accuracy: { label: "准确", score: 73 },
                    completeness: { label: "完整", score: 69 },
                },
                overall_score: 76,
                dimensions: [],
                compatibility_reader_ids: ["practice_session_rollup_fields_v1"],
                downstream_surfaces: ["report", "replay", "history"],
            },
            compatibility_readers: {
                practice_session_rollup_fields_v1: {
                    logic_score: 84,
                    accuracy_score: 73,
                    completeness_score: 69,
                    overall_score: 76,
                },
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 76,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        const overallScore = await screen.findByTestId("report-overall-score");
        expect(overallScore.textContent).toContain("76");
        expect(overallScore.getAttribute("data-contract-source")).toBe("canonical_kernel");
    });

    it("marks compatibility-reader score fallback explicitly instead of treating it as canonical success", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            logic_score: 41,
            accuracy_score: 42,
            completeness_score: 43,
            overall_score: 44,
            evaluable: true,
            not_evaluable_reason: null,
            evidence_completeness: {
                ...baseReport.evidence_completeness,
                legacy_score_key_used: true,
            },
            compatibility_readers: {
                practice_session_rollup_fields_v1: {
                    logic_score: 84,
                    accuracy_score: 73,
                    completeness_score: 69,
                    overall_score: 76,
                },
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 76,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        const overallScore = await screen.findByTestId("report-overall-score");
        expect(overallScore.textContent).toContain("76");
        expect(overallScore.getAttribute("data-contract-source")).toBe("compatibility_reader");
        expect(screen.getByText("兼容了 legacy score key")).toBeTruthy();
    });

    it("deep-links the report issue and goal cards into replay using the stable replay anchors", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            main_issue: {
                issue_type: "evidence_gap",
                issue_text: "功能点说得多，但还没有把产品价值翻译成客户收益。",
                recovery_rule: "下一轮先用客户收益语言重述价值，再回应价格顾虑。",
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先补 ROI 证据，再推进一个明确的下一步动作。",
                rule: "至少给出一条证据并确认下一步。",
            },
        });
        getReplayMock.mockResolvedValue({
            ...baseReplayData,
            main_issue: {
                issue_type: "evidence_gap",
                issue_text: "功能点说得多，但还没有把产品价值翻译成客户收益。",
                recovery_rule: "下一轮先用客户收益语言重述价值，再回应价格顾虑。",
                replay_anchor: {
                    status: "resolved",
                    message_id: "msg-highlight",
                    turn_number: 4,
                    marker: {
                        type: "highlight",
                        timestamp_ms: 24000,
                        label: "客户已经明确要证据，但这轮还没给出任何案例或数字。",
                    },
                    degraded_reason: null,
                },
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先补 ROI 证据，再推进一个明确的下一步动作。",
                rule: "至少给出一条证据并确认下一步。",
                replay_anchor: {
                    status: "resolved",
                    message_id: "msg-highlight",
                    turn_number: 4,
                    marker: {
                        type: "highlight",
                        timestamp_ms: 24000,
                        label: "客户已经明确要证据，但这轮还没给出任何案例或数字。",
                    },
                    degraded_reason: null,
                },
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 88,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findAllByText("回放将定位到第 4 轮高光片段。"))
            .toHaveLength(2);

        fireEvent.click(screen.getByRole("button", { name: "定位问题片段" }));
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/session-1/replay?focus=main_issue&message_id=msg-highlight&turn=4&anchor_status=resolved&marker_type=highlight&marker_timestamp_ms=24000",
        );

        fireEvent.click(screen.getByRole("button", { name: "定位目标片段" }));
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/session-1/replay?focus=next_goal&message_id=msg-highlight&turn=4&anchor_status=resolved&marker_type=highlight&marker_timestamp_ms=24000",
        );
    });

    it("launches a focused sales retry from the goal card using retry_entry.focus_intent", async () => {
        const focusIntent = {
            version: "retry_focus_v1",
            source_session_id: "session-1",
            main_issue: {
                issue_type: "evidence_gap",
                issue_text: "价值主张缺少案例、数据或ROI支撑，客户很难相信收益承诺。",
                recovery_rule: "下一轮先给出案例、数据或benchmark，再回应价格/ROI追问。",
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先用案例、数据或ROI证据支撑主张，再推进下一步。",
                rule: "至少补上一条证据和一个明确的下一步动作。",
            },
        };
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            retry_entry: {
                scenario_type: "sales",
                agent_id: "agent-1",
                persona_id: "persona-1",
                presentation_id: null,
                focus_intent: focusIntent,
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先用案例、数据或ROI证据支撑主张，再推进下一步。",
                rule: "至少补上一条证据和一个明确的下一步动作。",
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 82,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("本分数来自当前会话的 canonical evidence；只有可评估训练才会纳入首页、个人中心和排行榜均分。")).toBeTruthy();
        fireEvent.click(await screen.findByRole("button", { name: "按目标再练一轮" }));

        await waitFor(() => {
            expect(createSessionMock).toHaveBeenCalledWith({
                scenario_type: "sales",
                agent_id: "agent-1",
                persona_id: "persona-1",
                presentation_id: undefined,
                focus_intent: focusIntent,
            });
        });
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/retry-1?scenario_type=sales&agent_id=agent-1&persona_id=persona-1",
        );
    });

    it("routes incomplete sales retry configuration to the sales training page from the next-round card", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            retry_entry: {
                scenario_type: "sales",
                agent_id: null,
                persona_id: null,
                presentation_id: null,
                focus_intent: {
                    version: "retry_focus_v1",
                    source_session_id: "session-1",
                    main_issue: baseReport.main_issue,
                    next_goal: {
                        goal_type: "evidence_backing",
                        goal_text: "先补 ROI 证据，再推进一个明确的下一步动作。",
                        rule: "至少给出一条证据并确认下一步。",
                    },
                },
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先补 ROI 证据，再推进一个明确的下一步动作。",
                rule: "至少给出一条证据并确认下一步。",
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 82,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("下一轮训练卡")).toBeTruthy();
        expect(screen.getByText("当前销售会话缺少角色配置，请在训练页重新选择智能体与角色。")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "去销售训练页重新选择" }));

        expect(createSessionMock).not.toHaveBeenCalled();
        expect(pushMock).toHaveBeenCalledWith("/training/sales");
    });

    it("keeps degraded replay fallback visible and lets evidence cards jump into replay by turn", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            main_issue: {
                issue_type: "objection_handling_gap",
                issue_text: "价格顾虑已经出现，但还没给出报价逻辑。",
                recovery_rule: "下一轮先承接价格顾虑，再解释报价依据。",
            },
            next_goal: {
                goal_type: "objection_reframe",
                goal_text: "下一轮先解释报价逻辑，再推进低风险下一步。",
                rule: "至少先承接价格顾虑，再说明报价或 ROI 逻辑。",
            },
        });
        getReplayMock.mockResolvedValue({
            ...baseReplayData,
            main_issue: {
                issue_type: "objection_handling_gap",
                issue_text: "价格顾虑已经出现，但还没给出报价逻辑。",
                recovery_rule: "下一轮先承接价格顾虑，再解释报价依据。",
                replay_anchor: {
                    status: "degraded",
                    message_id: "msg-objection",
                    turn_number: 2,
                    marker: {
                        type: "stage_change",
                        timestamp_ms: 1800,
                        label: "异议处理",
                    },
                    degraded_reason: "no_matching_highlight",
                },
            },
            next_goal: {
                goal_type: "objection_reframe",
                goal_text: "下一轮先解释报价逻辑，再推进低风险下一步。",
                rule: "至少先承接价格顾虑，再说明报价或 ROI 逻辑。",
                replay_anchor: {
                    status: "degraded",
                    message_id: "msg-objection",
                    turn_number: 2,
                    marker: {
                        type: "stage_change",
                        timestamp_ms: 1800,
                        label: "异议处理",
                    },
                    degraded_reason: "no_matching_highlight",
                },
            },
        });
        getHighlightsMock.mockResolvedValue({
            highlights: [
                {
                    id: "highlight-1",
                    turn_number: 6,
                    role: "user",
                    content: "我们还是担心 ROI。",
                    timestamp: "2026-03-25T00:00:00Z",
                    highlight_type: "bad",
                    highlight_reason: "客户已经明确追问 ROI。",
                    ai_feedback: null,
                    suggested_response: null,
                    sales_stage: "objection",
                    stage_name: "异议处理",
                    context: {},
                    audio_url: null,
                    score: 62,
                    learning_evidence: null,
                },
            ],
            total_good: 0,
            total_bad: 1,
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 82,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findAllByText("未找到精确高光，回放将定位到“异议处理”阶段。"))
            .toHaveLength(2);

        fireEvent.click(screen.getByRole("button", { name: "定位问题片段" }));
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/session-1/replay?focus=main_issue&message_id=msg-objection&turn=2&anchor_status=degraded&anchor_reason=no_matching_highlight&marker_type=stage_change&marker_timestamp_ms=1800",
        );

        pushMock.mockClear();
        fireEvent.click(screen.getByRole("button", { name: "跳到高光回放" }));
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/session-1/replay?focus=learning_evidence&turn=6",
        );
    });

    it("shows a local highlight review list and carries suggested responses into retry", async () => {
        const reviewHighlight = {
            id: "highlight-review-1",
            turn_number: 6,
            role: "user",
            content: "我们还是担心 ROI，但我先介绍功能。",
            timestamp: "2026-03-25T00:00:00Z",
            highlight_type: "bad",
            highlight_reason: "客户已经明确追问 ROI，回答仍停留在功能介绍。",
            ai_feedback: "需要用案例或数据补足证据。",
            suggested_response: "先补一条制造业客户 18% 回款周期缩短案例，再确认客户是否认可。",
            sales_stage: "objection",
            stage_name: "异议处理",
            context: {},
            audio_url: null,
            score: 62,
            learning_evidence: {
                reason: "这是最适合下一轮集中复练的 ROI 证据缺口。",
                issue_family: "evidence_gap",
                objection_family: "roi",
                stage: {
                    key: "objection",
                    name: "异议处理",
                },
                nearby_context: {},
                suggested_response: "先补一条制造业客户 18% 回款周期缩短案例，再确认客户是否认可。",
                linked_issue: null,
                linked_goal: null,
            },
        };
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            retry_entry: {
                scenario_type: "sales",
                agent_id: "agent-1",
                persona_id: "persona-1",
                presentation_id: null,
                focus_intent: {
                    version: "retry_focus_v1",
                    source_session_id: "session-1",
                    main_issue: baseReport.main_issue,
                    next_goal: {
                        goal_type: "evidence_backing",
                        goal_text: "先补 ROI 证据，再推进一个明确的下一步动作。",
                        rule: "至少给出一条证据并确认下一步。",
                    },
                },
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先补 ROI 证据，再推进一个明确的下一步动作。",
                rule: "至少给出一条证据并确认下一步。",
            },
        });
        getHighlightsMock.mockResolvedValue({
            highlights: [reviewHighlight],
            total_good: 0,
            total_bad: 1,
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 82,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("高光数:1")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "加入复习清单" }));

        expect(await screen.findByText("高光复习清单")).toBeTruthy();
        const persistedReview = JSON.parse(
            localStorage.getItem("qoder.highlightReviewList.v1:session-1") || "{}",
        );
        expect(persistedReview.schema_version).toBe("highlight_review_v1");
        expect(persistedReview.items).toHaveLength(1);
        expect(screen.getByText("我们还是担心 ROI，但我先介绍功能。")).toBeTruthy();
        expect(screen.getByText("先补一条制造业客户 18% 回款周期缩短案例，再确认客户是否认可。"))
            .toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "带清单再练" }));

        await waitFor(() => {
            expect(createSessionMock).toHaveBeenCalledWith({
                scenario_type: "sales",
                agent_id: "agent-1",
                persona_id: "persona-1",
                presentation_id: undefined,
                focus_intent: expect.objectContaining({
                    version: "retry_focus_v1",
                    source_session_id: "session-1",
                    highlight_review: {
                        version: "highlight_review_v1",
                        selected_count: 1,
                        items: [
                            expect.objectContaining({
                                id: "highlight-review-1",
                                source_session_id: "session-1",
                                turn_number: 6,
                                content: "我们还是担心 ROI，但我先介绍功能。",
                                issue_label: "证据支撑",
                                suggested_response: "先补一条制造业客户 18% 回款周期缩短案例，再确认客户是否认可。",
                            }),
                        ],
                    },
                }),
            });
        });
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/retry-1?scenario_type=sales&review_source=highlight_review&source_session_id=session-1&agent_id=agent-1&persona_id=persona-1",
        );
    });

    it("drops stale highlight review localStorage when the schema version does not match", async () => {
        localStorage.setItem(
            "qoder.highlightReviewList.v1:session-1",
            JSON.stringify({
                schema_version: "legacy_highlight_review",
                items: [
                    {
                        id: "legacy-highlight",
                        source_session_id: "session-1",
                        turn_number: 3,
                        content: "旧格式高光",
                    },
                ],
            }),
        );
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 82,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        await waitFor(() => {
            expect(getReportMock).toHaveBeenCalledWith("session-1");
        });
        expect(localStorage.getItem("qoder.highlightReviewList.v1:session-1")).toBeNull();
    });

    it("renders conclusion provenance and four-layer degradation from the canonical report payload", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            conclusion_evidence: {
                ...baseConclusionEvidence,
                next_goal: {
                    retrieval_source: { available: false, reason: "no_retrieval_facts" },
                    transcript_source: { available: true, turn_count: 2 },
                    audio_source: { available: false, reason: "no_audio_segments" },
                },
                claim_truth: {
                    retrieval_source: { available: false, reason: "report_generation_failed" },
                    transcript_source: { available: true, turn_count: 1 },
                    audio_source: { available: true, reason: null },
                },
            },
            evidence_degradation: {
                retrieval: {
                    status: "degraded",
                    token: "no_retrieval_facts",
                    explanation: "no_voice_policy_snapshot",
                },
                transcript: {
                    status: "ok",
                    token: "transcript_ok",
                    explanation: null,
                },
                audio: {
                    status: "degraded",
                    token: "no_audio_segments",
                    explanation: "no_audio_segments",
                },
                enhanced_report: {
                    status: "degraded",
                    token: "report_generation_failed",
                    explanation: "REPORT_GENERATION_FAILED",
                },
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 82,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("结论出处"))
            .toBeTruthy();
        expect(screen.getAllByText("本场销售主问题").length).toBeGreaterThan(0);
        expect(screen.getAllByText("下一轮销售目标").length).toBeGreaterThan(0);
        expect(screen.getAllByText("主张证据状态").length).toBeGreaterThan(0);
        expect(screen.getByText("知识库证据可用")).toBeTruthy();
        expect(screen.getAllByText("对话证据 1 轮").length).toBeGreaterThan(0);
        expect(screen.getAllByText("音频证据可用").length).toBeGreaterThan(0);
        expect(screen.getByText("知识库证据缺失：当前未产出检索事实。"))
            .toBeTruthy();
        expect(screen.getByText("对话证据 2 轮")).toBeTruthy();
        expect(screen.getByText("音频证据缺失：当前未录制可用音频片段。"))
            .toBeTruthy();
        expect(screen.getByText("知识库证据缺失：综合洞察生成失败，当前无法补充增强证据。"))
            .toBeTruthy();
        expect(screen.getByText("证据降级状态")).toBeTruthy();
        expect(screen.getByText("知识检索层"))
            .toBeTruthy();
        expect(screen.getByText("Retrieval 事实缺失，当前无法确认知识库命中情况。"))
            .toBeTruthy();
        expect(screen.getByText("转写证据层")).toBeTruthy();
        expect(screen.getByText("对话转写证据完整。"))
            .toBeTruthy();
        expect(screen.getByText("音频证据层")).toBeTruthy();
        expect(screen.getByText("原始音频缺失，本轮只能依赖文字证据。"))
            .toBeTruthy();
        expect(screen.getByText("增强洞察层")).toBeTruthy();
        expect(screen.getByText("综合洞察生成失败，但基础结论仍来自统一证据。"))
            .toBeTruthy();
    });

    it("omits malformed provenance rows while keeping valid report-driven copy visible when knowledge-check fails", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            conclusion_evidence: {
                main_issue: {
                    retrieval_source: { available: true, reason: null },
                    transcript_source: { available: true, turn_count: 1 },
                    audio_source: { available: true, reason: null },
                },
                next_goal: {
                    retrieval_source: { available: false },
                    transcript_source: { available: true },
                    audio_source: null,
                },
                claim_truth: null,
            },
            evidence_degradation: {
                retrieval: {
                    status: "degraded",
                    token: "no_retrieval_facts",
                    explanation: "no_voice_policy_snapshot",
                },
                transcript: {
                    status: "ok",
                    token: "transcript_ok",
                    explanation: null,
                },
                audio: {
                    status: "degraded",
                    token: 404,
                    explanation: "no_audio_segments",
                },
                enhanced_report: null,
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("结论出处")).toBeTruthy();
        expect(screen.getByText("知识库证据可用")).toBeTruthy();
        expect(screen.getByText("对话证据 1 轮")).toBeTruthy();
        expect(screen.getByText("音频证据可用")).toBeTruthy();
        expect(screen.queryByText("知识库证据缺失：当前未产出检索事实。")).toBeNull();
        expect(screen.queryByText("音频证据缺失：当前未录制可用音频片段。")).toBeNull();
        expect(screen.getByText("证据降级状态")).toBeTruthy();
        expect(screen.getByText("Retrieval 事实缺失，当前无法确认知识库命中情况。")).toBeTruthy();
        expect(screen.getByText("对话转写证据完整。")).toBeTruthy();
        expect(screen.queryByText("原始音频缺失，本轮只能依赖文字证据。")).toBeNull();
        expect(screen.queryByText("综合洞察生成失败，但基础结论仍来自统一证据。")).toBeNull();
    });

    it("renders unsupported claim truth from the unified evidence snapshot without falling back to diagnostics status copy", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "unsupported_claim",
                    label: "未被证据支撑",
                    source: "score_snapshot",
                    reason: "low_evidence_score",
                    evidence_score: 42,
                },
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findAllByText("主张证据状态")).not.toHaveLength(0);
        expect(screen.getByText("未被证据支撑")).toBeTruthy();
        expect(screen.getByText("当前这场对话里的收益或能力主张还没有被案例、数据或 ROI 证据支撑。")).toBeTruthy();
        expect(screen.getByText("证据强度：42 分。")).toBeTruthy();
    });

    it("renders canonical retrieval truth from the report payload even when the supplemental knowledge-check request fails", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "weak_evidence",
                    label: "证据偏弱",
                    source: "score_snapshot",
                    reason: "low_evidence_score",
                    evidence_score: 63,
                },
                retrieval_facts: baseRetrievalFacts,
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("知识库检索事实")).toBeTruthy();
        expect(screen.getAllByText("已命中").length).toBeGreaterThan(0);
        expect(screen.getByText("知识检索已触发并命中知识库")).toBeTruthy();
        expect(screen.getByText("证据偏弱")).toBeTruthy();
        expect(screen.getByText("知识库已命中相关内容，但当前证据力度仍不够——建议引用更具体的数据或案例。")).toBeTruthy();
        expect(screen.getByText(/最近检索问题：这个方案的 ROI 怎么证明/)).toBeTruthy();
        expect(screen.getByText("某制造业客户上线后 3 个月回款周期缩短 18%，库存周转提升 12%。")).toBeTruthy();
        expect(screen.queryByText("知识库命中检测")).toBeNull();
    });

    it("keeps canonical miss fallback visible when the supplemental knowledge-check request rejects", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "weak_evidence",
                    label: "证据偏弱",
                    source: "score_snapshot",
                    reason: "low_evidence_score",
                    evidence_score: 63,
                },
                retrieval_facts: {
                    ...baseRetrievalFacts,
                    status: "miss",
                    summary: "知识检索已触发，但未命中知识库内容",
                    hit_count: 0,
                    hit_rate: 0,
                    latest_attempt: {
                        ...baseRetrievalFacts.latest_attempt,
                        status: "miss",
                        result_count: 0,
                        result_summaries: [],
                    },
                },
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("知识库检索事实")).toBeTruthy();
        expect(screen.getAllByText("未命中").length).toBeGreaterThan(0);
        expect(screen.getByText("知识检索已触发，但未命中知识库内容")).toBeTruthy();
        expect(screen.getByText("检索「这个方案的 ROI 怎么证明？」未在知识库中找到相关内容，建议优化检索词或补充知识库文档。")).toBeTruthy();
        expect(screen.getByText("知识库检索未命中，可能缺少对应文档——建议补充相关产品或案例资料。")).toBeTruthy();
        expect(screen.queryByText("知识库命中检测")).toBeNull();
    });

    it("keeps canonical search-failed fallback visible when the supplemental knowledge-check request rejects", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "weak_evidence",
                    label: "证据偏弱",
                    source: "score_snapshot",
                    reason: "low_evidence_score",
                    evidence_score: 63,
                },
                retrieval_facts: {
                    ...baseRetrievalFacts,
                    status: "search_failed",
                    summary: "知识检索触发失败，当前无法获取知识库证据",
                    hit_count: 0,
                    hit_rate: 0,
                    latest_attempt: {
                        ...baseRetrievalFacts.latest_attempt,
                        status: "search_failed",
                        result_count: 0,
                        result_summaries: [],
                        error_summary: "向量检索服务超时",
                    },
                },
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("知识库检索事实")).toBeTruthy();
        expect(screen.getAllByText("检索失败").length).toBeGreaterThan(0);
        expect(screen.queryByText("已命中")).toBeNull();
        expect(screen.queryByText("未命中")).toBeNull();
        expect(screen.getByText("知识检索触发失败，当前无法获取知识库证据")).toBeTruthy();
        expect(screen.getByText("知识检索服务异常：向量检索服务超时")).toBeTruthy();
        expect(screen.getByText("知识库检索暂时异常，无法确认是否有相关内容支撑当前主张。")).toBeTruthy();
        expect(screen.queryByText("知识库命中检测")).toBeNull();
    });

    it("renders answer-level retrieval diagnostics from knowledge-check when available", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "weak_evidence",
                    label: "证据偏弱",
                    source: "score_snapshot",
                    reason: "low_evidence_score",
                    evidence_score: 63,
                },
                retrieval_facts: baseRetrievalFacts,
            },
        });
        getKnowledgeCheckMock.mockResolvedValue({
            session_id: "session-1",
            status: "hit",
            summary: "知识检索已触发并命中知识库",
            internal_retrieval_enabled: true,
            knowledge_base_ids: ["kb-product"],
            knowledge_base_count: 1,
            attempt_count: 2,
            hit_query_count: 1,
            total_results: 2,
            hit_rate: 0.5,
            last_query: "请介绍一下实习产品",
            last_result_count: 2,
            last_status: "hit",
            recent_queries: ["请介绍一下实习产品"],
            knowledge_answer_diagnostics: {
                mode: "grounded_strict",
                answerability: "sufficient",
                source_status: "hit",
                rewritten_queries: ["实习 产品介绍", "实习 核心能力"],
                citations: [
                    {
                        claim: "实习专家是一款企业内部智能演练平台。",
                        knowledge_base_name: "产品知识库",
                        document_title: "实习专家产品手册",
                        snippet: "实习专家是一款面向企业内部训练的智能演练平台。",
                        score: 0.92,
                    },
                ],
            },
        } as never);
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("回答约束：sufficient")).toBeTruthy();
        expect(screen.getByText("检索改写：实习 产品介绍 · 实习 核心能力")).toBeTruthy();
        expect(screen.getByText("实习专家是一款面向企业内部训练的智能演练平台。")).toBeTruthy();
    });

    it("omits the canonical retrieval section when retrieval_facts are absent from the report payload", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "weak_evidence",
                    label: "证据偏弱",
                    source: "score_snapshot",
                    reason: "low_evidence_score",
                },
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findAllByText("主张证据状态")).not.toHaveLength(0);
        expect(screen.queryByText("知识库检索事实")).toBeNull();
    });

    it("keeps canonical retrieval status visible when latest_attempt and result_summaries are malformed", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            evaluable: true,
            not_evaluable_reason: null,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "weak_evidence",
                    label: "证据偏弱",
                    source: "score_snapshot",
                    reason: "low_evidence_score",
                },
                retrieval_facts: {
                    ...baseRetrievalFacts,
                    latest_attempt: {
                        status: "hit",
                        query: 42,
                        result_count: "two",
                        result_summaries: [
                            { knowledge_base_id: "", snippet: "should-drop" },
                            { knowledge_base_id: "kb-product", snippet: "保留下来的唯一片段。" },
                            "bad-entry",
                        ],
                    },
                },
            },
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByText("知识库检索事实")).toBeTruthy();
        expect(screen.getByText("知识检索已触发并命中知识库")).toBeTruthy();
        expect(screen.getByText("保留下来的唯一片段。")).toBeTruthy();
        expect(screen.queryByText(/最近检索问题：/)).toBeNull();
        expect(screen.queryByText(/命中片段：/)).toBeNull();
        expect(screen.queryByText("should-drop")).toBeNull();
    });

    it("renders canonical presentation review, skips knowledge-check noise, and keeps retry linked to the same presentation", async () => {
        getReportMock.mockResolvedValue(basePresentationReport);
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced report unavailable"));

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("88");
        expect(screen.getByText("PPT 复盘报告")).toBeTruthy();
        expect(screen.queryByText("主张证据状态")).toBeNull();
        expect(screen.getByText("PPT 表达能力总览")).toBeTruthy();
        expect(screen.getByText("流畅连贯性")).toBeTruthy();
        expect(screen.getByText("互动问答")).toBeTruthy();
        expect(screen.getByText("逐页总结")).toBeTruthy();
        expect(screen.getByText("第一页完整讲清业务目标与客户问题。")).toBeTruthy();
        expect(screen.getByText("第二页补充了 ROI 结果，但客户案例展开不够具体。")).toBeTruthy();
        expect(screen.getByText("要点覆盖与表达诊断")).toBeTruthy();
        expect(screen.getByText("2 / 3 已覆盖")).toBeTruthy();
        expect(screen.getByText("禁用词提醒")).toBeTruthy();
        expect(screen.getByText("遗漏要点")).toBeTruthy();
        expect(await screen.findByText("综合洞察暂不可用，当前页面仍展示基于课件证据的 PPT 复盘。")).toBeTruthy();
        expect(screen.queryByText("销售推进结果")).toBeNull();
        expect(screen.queryByText("销售推进基线")).toBeNull();
        expect(screen.queryByText("知识库检索事实")).toBeNull();
        expect(screen.queryByText("知识库命中检测")).toBeNull();
        expect(getKnowledgeCheckMock).not.toHaveBeenCalled();

        fireEvent.click(screen.getByRole("button", { name: "按目标再练一轮" }));

        await waitFor(() => {
            expect(createSessionMock).toHaveBeenCalledWith({
                scenario_type: "presentation",
                agent_id: undefined,
                persona_id: undefined,
                presentation_id: "presentation-1",
            });
        });
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/retry-1?scenario_type=presentation&presentation_id=presentation-1",
        );
    });

    it("routes page retry without presentation configuration back to presentation training", async () => {
        getReportMock.mockResolvedValue({
            ...basePresentationReport,
            retry_entry: {
                scenario_type: "presentation" as const,
                presentation_id: null,
                agent_id: null,
                persona_id: null,
            },
        });
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced report unavailable"));

        render(<ReportPage />);

        expect(await screen.findByText("PPT 复盘报告")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "补练第 2 页" }));

        expect(createSessionMock).not.toHaveBeenCalled();
        expect(pushMock).toHaveBeenCalledWith("/training/presentation");
        expect(screen.getAllByText("当前演讲会话缺少课件配置，请返回训练页重新选择演示文稿。").length).toBeGreaterThan(0);
    });

    it("keeps PPT degraded guidance visible when highlights are unavailable", async () => {
        getReportMock.mockResolvedValue(basePresentationReport);
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced report unavailable"));
        getHighlightsMock.mockRejectedValue(new Error("ppt highlights unavailable"));

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("88");
        expect(screen.getByText("PPT 复盘报告")).toBeTruthy();
        expect(await screen.findByText("高光片段暂不可用，PPT 基础复盘不受影响。")).toBeTruthy();
        expect(screen.queryByText("主张证据状态")).toBeNull();
        expect(screen.queryByText("销售推进结果")).toBeNull();
        expect(screen.queryByText("知识库命中检测")).toBeNull();
        expect(getKnowledgeCheckMock).not.toHaveBeenCalled();
    });

    it("shows page-level PPT issue clusters with concrete evidence on the shared report route", async () => {
        getReportMock.mockResolvedValue({
            ...basePresentationReport,
            presentation_review: {
                ...basePresentationReview,
                page_summaries: [
                    {
                        ...basePresentationReview.page_summaries[0],
                        issue_clusters: [
                            {
                                issue_type: "off_page",
                                summary: "第 1 页讲解带到了其他页内容，优先回到当前页要点。",
                                evidence: ["第 2 页要点：实施计划"],
                                turn_numbers: [1],
                                linked_points: ["实施计划"],
                                linked_phrases: [],
                                related_page_numbers: [2],
                            },
                            {
                                issue_type: "forbidden_word",
                                summary: "第 1 页触发了禁忌表达，建议改成更稳妥、可验证的说法。",
                                evidence: ["触发短语：百分之百保证"],
                                turn_numbers: [1],
                                linked_points: [],
                                linked_phrases: ["百分之百保证"],
                                related_page_numbers: [],
                            },
                        ],
                    },
                    {
                        ...basePresentationReview.page_summaries[1],
                        issue_clusters: [
                            {
                                issue_type: "missing_point",
                                summary: "第 2 页仍缺少 1 个必讲点，需要补齐再进入下一页。",
                                evidence: ["未覆盖：客户案例"],
                                turn_numbers: [3, 4],
                                linked_points: ["客户案例"],
                                linked_phrases: [],
                                related_page_numbers: [],
                            },
                            {
                                issue_type: "overlong_explanation",
                                summary: "第 2 页展开偏长，但当前页 2 个要点只覆盖了 1 个。",
                                evidence: ["累计讲解约 128 个字，优先压缩到当前页必讲点。"],
                                turn_numbers: [3],
                                linked_points: ["ROI结果", "客户案例"],
                                linked_phrases: [],
                                related_page_numbers: [],
                            },
                            {
                                issue_type: "weak_qa_handling",
                                summary: "第 2 页的问答承接偏弱，需要把追问回答得更具体。",
                                evidence: ["如果客户追问负责人，我这边暂时只能说后面再确认。"],
                                turn_numbers: [4],
                                linked_points: [],
                                linked_phrases: [],
                                related_page_numbers: [],
                            },
                        ],
                    },
                ],
                diagnostics: {
                    ...basePresentationReview.diagnostics,
                    page_issue_cluster_count: 5,
                    page_issue_types: [
                        "forbidden_word",
                        "missing_point",
                        "off_page",
                        "overlong_explanation",
                        "weak_qa_handling",
                    ],
                },
            },
        });
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced report unavailable"));

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("88");
        expect(screen.getByText("页级问题簇总览")).toBeTruthy();
        expect(screen.getByText("共 5 个页级问题簇，优先按页修正这些表达偏差。"))
            .toBeTruthy();
        expect(screen.getByText("第 1 页问题簇")).toBeTruthy();
        expect(screen.getAllByText("串页偏题")[0]).toBeTruthy();
        expect(screen.getByText("第 1 页讲解带到了其他页内容，优先回到当前页要点。"))
            .toBeTruthy();
        expect(screen.getByText("关联页：第 2 页")).toBeTruthy();
        expect(screen.getByText("关联要点：实施计划")).toBeTruthy();
        expect(screen.getByText("触发短语：百分之百保证")).toBeTruthy();
        expect(screen.getByText("第 2 页问题簇")).toBeTruthy();
        expect(screen.getByText("展开过长")).toBeTruthy();
        expect(screen.getByText("第 2 页展开偏长，但当前页 2 个要点只覆盖了 1 个。"))
            .toBeTruthy();
        expect(screen.getByText("如果客户追问负责人，我这边暂时只能说后面再确认。"))
            .toBeTruthy();

        const pageReplayLinks = screen.getAllByRole("link", { name: "查看第 2 页回放" });
        expect(pageReplayLinks.some((link) => link.getAttribute("href") === "/practice/session-1/replay?focus=presentation_page&page=2&page_anchor_status=resolved")).toBe(true);

        fireEvent.click(screen.getByRole("button", { name: "补练第 2 页" }));

        await waitFor(() => {
            expect(createSessionMock).toHaveBeenCalledWith({
                scenario_type: "presentation",
                agent_id: undefined,
                persona_id: undefined,
                presentation_id: "presentation-1",
                focus_intent: {
                    version: "presentation_page_retry_v1",
                    source_session_id: "session-1",
                    presentation_page: {
                        page_number: 2,
                        reason: "missing_required_points",
                        summary: "第二页补充了 ROI 结果，但客户案例展开不够具体。",
                        missing_required_points: ["客户案例"],
                    },
                },
            });
        });
        expect(pushMock).toHaveBeenCalledWith(
            "/practice/retry-1?scenario_type=presentation&presentation_id=presentation-1&focus=presentation_page&page=2&source_session_id=session-1",
        );
    });

    it("shows presentation-specific degraded copy instead of falling back to sales UI when page metadata is missing", async () => {
        getReportMock.mockResolvedValue({
            ...basePresentationReport,
            overall_score: 79,
            evidence_completeness: {
                complete: false,
                scenario_type: "presentation",
                presentation_review_available: true,
                page_metadata_complete: false,
                page_summary_count: 0,
                required_talking_points_status: "degraded",
                required_points_total: 3,
                required_points_covered: 2,
                required_points_missing: 1,
                required_coverage_ratio: 2 / 3,
                degraded_reasons: ["missing_page_metadata"],
            },
            presentation_review: {
                ...basePresentationReview,
                page_summaries: [],
                required_talking_points: {
                    status: "degraded",
                    total: 3,
                    covered: 2,
                    missing: 1,
                    coverage_ratio: 2 / 3,
                },
                coverage_status: "degraded",
                has_page_metadata: false,
                diagnostics: {
                    ...basePresentationReview.diagnostics,
                    has_page_metadata: false,
                    pages_with_messages: 0,
                    page_coverage_ratio: 0,
                    degraded_reasons: ["missing_page_metadata"],
                },
            },
        });
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced report unavailable"));

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("79");
        expect(screen.getByText("当前会话缺少页码证据，逐页总结和要点覆盖仅展示已确认部分。")).toBeTruthy();
        expect(screen.getByText("逐页总结暂不可用")).toBeTruthy();
        expect(screen.getByRole("button", { name: "按目标再练一轮" })).toBeTruthy();
        expect(screen.queryByText("销售推进结果")).toBeNull();
        expect(screen.queryByText("销售推进基线")).toBeNull();
        expect(screen.queryByText("知识库命中检测")).toBeNull();
        expect(getKnowledgeCheckMock).not.toHaveBeenCalled();
    });

    it("trusts the unified evidence contract for overall score and evaluability even when comprehensive data conflicts", async () => {
        getReportMock.mockResolvedValue(baseReport);
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 95,
            dimension_scores: [
                { name: "逻辑性", score: 95, weight: 0.34, description: "冲突分数" },
            ],
            stage_summaries: [
                { stage_number: 1, start_turn: 1, end_turn: 2, average_score: 95, key_points: [], summary: "冲突阶段" },
            ],
            key_strengths: ["增强洞察"],
            key_improvements: ["增强建议"],
            detailed_feedback: "增强内容",
            recommendations: ["增强练习建议"],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        await waitFor(() => {
            expect(getReportMock).toHaveBeenCalledWith("session-1");
        });

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("72");
        expect(screen.queryByText("导出报告")).toBeNull();
        expect(screen.getAllByText("主张证据状态").length).toBeGreaterThan(0);
        expect(screen.getByText("证据待补齐")).toBeTruthy();
        expect(screen.getByText("当前仍在补证据或有效互动不足，暂时不能判定这条主张已经成立。")).toBeTruthy();
        expect(screen.getByText("开场破冰")).toBeTruthy();
        expect(screen.queryByText("95")).toBeNull();
    });

    it("renders the learner-facing missing raw-audio copy when audio_audit is absent", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            audio_audit: null,
        });
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 72,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect(await screen.findByTestId("audio-audit-card")).toBeTruthy();
        expect(screen.getByText("原始录音")).toBeTruthy();
        expect(screen.getByText("本次训练未录制原始音频")).toBeTruthy();
        expect(screen.queryByText(/共 2 个片段/)).toBeNull();
    });

    it("keeps the evidence view stable when enhanced report and highlights are unavailable", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            overall_score: 61,
            logic_score: 60,
            accuracy_score: 62,
            completeness_score: 61,
            evaluable: true,
            not_evaluable_reason: null,
            main_issue: {
                issue_type: "evidence_gap",
                issue_text: "价值主张已经提到了，但还没有拿出能让客户相信的证据。",
                recovery_rule: "先补一条 ROI 或客户案例，再继续推进。",
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先补 ROI 证据，再确认客户愿不愿意进入下一步。",
                rule: "至少补一条证据并确认下一步。",
            },
        });
        getComprehensiveReportMock.mockRejectedValue(new ApiRequestError({
            status: 404,
            errorCode: "[REPORT_NOT_FOUND]",
            message: "not found",
        }));
        generateComprehensiveReportMock.mockRejectedValue(new Error("enhanced report unavailable"));
        getHighlightsMock.mockRejectedValue(new Error("highlights unavailable"));

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("61");
        expect(screen.getByText("证据支撑")).toBeTruthy();
        expect(screen.getByText("价值主张已经提到了，但还没有拿出能让客户相信的证据。")).toBeTruthy();
        expect(screen.getByText("证据补强")).toBeTruthy();
        expect(screen.getByText("先补 ROI 证据，再确认客户愿不愿意进入下一步。")).toBeTruthy();
        expect(await screen.findByText("综合洞察暂不可用，当前页面仅展示统一训练证据。"))
            .toBeTruthy();
        expect(await screen.findByText("高光片段暂不可用，基础评估结果不受影响。"))
            .toBeTruthy();
    });

    it("keeps the canonical report conclusion visible when replay is still locked for the same session", async () => {
        getReportMock.mockResolvedValue({
            ...baseReport,
            overall_score: 79,
            logic_score: 83,
            accuracy_score: 74,
            completeness_score: 71,
            evaluable: true,
            not_evaluable_reason: null,
            effectiveness_snapshot: {
                claim_truth: {
                    status: "evidence_pending",
                    label: "证据待补齐",
                    source: "fallback_snapshot",
                    reason: "insufficient_turn_data",
                },
            },
            main_issue: {
                issue_type: "evidence_gap",
                issue_text: "客户已经追问 ROI，但这场对话还没补上足够证据。",
                recovery_rule: "下一轮先给案例或 ROI 数据，再继续推进。",
            },
            next_goal: {
                goal_type: "evidence_backing",
                goal_text: "先补 ROI 证据，再确认客户是否愿意进入下一步。",
                rule: "至少补一条证据并确认下一步。",
            },
        });
        getReplayMock.mockRejectedValue(new ApiRequestError({
            status: 400,
            errorCode: "[SESSION_NOT_COMPLETED]",
            message: "Session must be completed for replay",
        }));
        getComprehensiveReportMock.mockResolvedValue({
            session_id: "session-1",
            generated_at: "2026-03-23T00:00:00Z",
            overall_score: 79,
            dimension_scores: [],
            stage_summaries: [],
            key_strengths: [],
            key_improvements: [],
            detailed_feedback: "",
            recommendations: [],
            voice_policy_snapshot_ref: null,
        });

        render(<ReportPage />);

        expect((await screen.findByTestId("report-overall-score")).textContent).toContain("79");
        expect(screen.getAllByText("主张证据状态").length).toBeGreaterThan(0);
        expect(screen.getByText("证据待补齐")).toBeTruthy();
        expect(screen.getByText("客户已经追问 ROI，但这场对话还没补上足够证据。")).toBeTruthy();
        expect(screen.getByText("先补 ROI 证据，再确认客户是否愿意进入下一步。")).toBeTruthy();
        expect(await screen.findAllByText("当前暂无可定位的回放片段。")).toHaveLength(2);
        expect((screen.getByRole("button", { name: "定位问题片段" }) as HTMLButtonElement).disabled).toBe(true);
        expect((screen.getByRole("button", { name: "定位目标片段" }) as HTMLButtonElement).disabled).toBe(true);
    });
});
