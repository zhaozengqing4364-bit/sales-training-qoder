import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SessionReplayPage from "./page";
import { ApiRequestError } from "@/lib/api/client";

const {
  pushMock,
  backMock,
  getReplayMock,
  getHighlightsMock,
  getReportMock,
  getThumbnailBlobMock,
  createSessionMock,
  getSegmentAudioBlobUrlMock,
  searchParamsState,
  scrollIntoViewMock,
} = vi.hoisted(() => ({
  pushMock: vi.fn(),
  backMock: vi.fn(),
  getReplayMock: vi.fn(),
  getHighlightsMock: vi.fn(),
  getReportMock: vi.fn(),
  getThumbnailBlobMock: vi.fn(),
  createSessionMock: vi.fn(),
  getSegmentAudioBlobUrlMock: vi.fn(),
  searchParamsState: {
    current: new URLSearchParams(),
  },
  scrollIntoViewMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: pushMock,
    back: backMock,
  }),
  useParams: () => ({
    sessionId: "session-1",
  }),
  useSearchParams: () => searchParamsState.current,
}));

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: unknown }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("next/image", () => ({
  default: ({ src, alt }: { src: string; alt: string }) => <img src={src} alt={alt} />,
}));

vi.mock("@/components/highlights", () => ({
  HighlightList: ({ highlights }: { highlights: Array<any> }) => (
    <div data-testid="replay-highlight-list">
      <div>高光数:{highlights.length}</div>
      <div>高光学习证据:{highlights[0]?.learning_evidence?.reason ?? "none"}</div>
      <div>高光问题家族:{highlights[0]?.learning_evidence?.issue_family ?? "none"}</div>
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
        getReplay: getReplayMock,
        getHighlights: getHighlightsMock,
        getReport: getReportMock,
        getSegmentAudioBlobUrl: getSegmentAudioBlobUrlMock,
      },
      presentations: {
        ...actual.api.presentations,
        getThumbnailBlob: getThumbnailBlobMock,
      },
      practice: {
        ...actual.api.practice,
        createSession: createSessionMock,
      },
    },
  };
});

function buildReplayData(overrides: Record<string, unknown> = {}) {
  return {
    session_id: "session-1",
    agent_name: "销售教练",
    persona_name: "采购经理",
    voice_policy_snapshot_ref: null,
    total_duration_ms: 185000,
    overall_score: 78,
    audio_audit: {
      summary: {
        recording_status: "completed",
        total_segments: 2,
        uploaded_segments: 2,
        total_bytes: 40960,
        latest_segment_sequence: 1,
        storage_prefix: "sessions/session-1/audio",
        last_uploaded_at: "2026-03-27T08:10:00Z",
        learner_status: "available",
      },
      segments: [
        {
          segment_sequence: 0,
          created_at: "2026-03-27T08:00:00Z",
          duration_ms: 12000,
          size_bytes: 20480,
          upload_status: "uploaded",
          playback_path: "/api/v1/sessions/session-1/audio-segments/0",
        },
        {
          segment_sequence: 1,
          created_at: "2026-03-27T08:00:12Z",
          duration_ms: null,
          size_bytes: 20480,
          upload_status: "uploaded",
          playback_path: "/api/v1/sessions/session-1/audio-segments/1",
        },
      ],
    },
    effectiveness_snapshot: {
      claim_truth: {
        status: "evidence_verified",
        label: "证据已验证",
        source: "objection_ledger",
        reason: "evidence_provided",
        evidence_score: 82,
        closure_state: "evidence_provided",
      },
    },
    pass_flags: null,
    main_capability_passed: false,
    overall_result: "fail",
    main_issue: {
      issue_type: "evidence_gap",
      issue_text: "客户收益提到了，但还没有补上可信证据。",
      recovery_rule: "下一轮至少补一条 ROI 或客户案例证据。",
    },
    next_goal: {
      goal_type: "evidence_backing",
      goal_text: "先补 ROI 证据，再继续推进下一步。",
      rule: "至少给出一条证据并确认客户是否认可。",
    },
    evaluable: false,
    not_evaluable_reason: "INSUFFICIENT_TURN_DATA",
    evidence_completeness: {
      complete: false,
      missing_fields: ["closing_stage"],
      message_count: 3,
    },
    messages: [
      {
        id: "turn-1",
        session_id: "session-1",
        turn_number: 1,
        role: "assistant",
        content: "客户刚问这个方案凭什么可信。",
        timestamp: "2026-03-23T00:00:00Z",
        audio_url: null,
        duration_ms: 1200,
        score_snapshot: {
          overall_score: 78,
        },
        ai_feedback: null,
        is_highlight: false,
        highlight_type: null,
        highlight_reason: null,
      },
      {
        id: "turn-2",
        session_id: "session-1",
        turn_number: 2,
        role: "user",
        content: "我们这个方案能帮你省不少钱。",
        timestamp: "2026-03-23T00:00:15Z",
        audio_url: null,
        duration_ms: 1500,
        sales_stage: "objection",
        stage_name: "异议处理",
        score_snapshot: {
          overall_score: 62,
        },
        ai_feedback: "需要补 ROI 或客户案例。",
        is_highlight: true,
        highlight_type: "bad",
        highlight_reason: "只提了结果，没有给出证据。",
        learning_evidence: {
          reason: "客户已经追问可信度，这一轮决定能否继续推进。",
          issue_family: "evidence_gap",
          stage: {
            key: "objection",
            name: "异议处理",
          },
          nearby_context: {
            prev_message: {
              id: "turn-1",
              role: "assistant",
              content: "客户刚问这个方案凭什么可信。",
              timestamp: "2026-03-23T00:00:00Z",
            },
            next_message: null,
          },
          suggested_response: "先补一条 ROI 证据，再确认客户是否认可。",
          linked_issue: {
            issue_type: "evidence_gap",
            issue_text: "客户收益提到了，但还没有补上可信证据。",
            recovery_rule: "下一轮至少补一条 ROI 或客户案例证据。",
          },
          linked_goal: {
            goal_type: "evidence_backing",
            goal_text: "先补 ROI 证据，再继续推进下一步。",
            rule: "至少给出一条证据并确认客户是否认可。",
          },
        },
      },
      {
        id: "turn-4",
        session_id: "session-1",
        turn_number: 4,
        role: "assistant",
        content: "如果按你们当前客户流失率测算，三个月能回本。",
        timestamp: "2026-03-23T00:00:24Z",
        audio_url: null,
        duration_ms: 1800,
        sales_stage: "objection",
        stage_name: "异议处理",
        score_snapshot: {
          overall_score: 84,
        },
        ai_feedback: "这轮给出了 ROI 证据。",
        is_highlight: true,
        highlight_type: "good",
        highlight_reason: "补上了 ROI 证据。",
        learning_evidence: {
          reason: "用 ROI 证据正面回应了客户的可信度顾虑。",
          issue_family: "evidence_gap",
          stage: {
            key: "objection",
            name: "异议处理",
          },
          nearby_context: {
            prev_message: {
              id: "turn-2",
              role: "user",
              content: "我们这个方案能帮你省不少钱。",
              timestamp: "2026-03-23T00:00:15Z",
            },
            next_message: null,
          },
          suggested_response: "继续确认这条 ROI 证据是否足以支持下一步。",
          linked_issue: {
            issue_type: "evidence_gap",
            issue_text: "客户收益提到了，但还没有补上可信证据。",
            recovery_rule: "下一轮至少补一条 ROI 或客户案例证据。",
          },
          linked_goal: {
            goal_type: "evidence_backing",
            goal_text: "先补 ROI 证据，再继续推进下一步。",
            rule: "至少给出一条证据并确认客户是否认可。",
          },
        },
      },
    ],
    timeline_markers: [
      {
        timestamp_ms: 1800,
        type: "stage_change",
        label: "异议处理",
        message_id: "turn-2",
      },
      {
        timestamp_ms: 24000,
        type: "highlight",
        label: "ROI 证据回应",
        message_id: "turn-4",
        highlight_type: "good",
      },
    ],
    stage_summary: [
      {
        stage: "opening",
        duration_ms: 60000,
        score: 78,
      },
    ],
    ...overrides,
  };
}

function buildHighlightsResponse(overrides: Record<string, unknown> = {}) {
  return {
    highlights: [
      {
        id: "turn-2",
        turn_number: 2,
        role: "user",
        content: "我们这个方案能帮你省不少钱。",
        timestamp: "2026-03-23T00:00:15Z",
        highlight_type: "bad",
        highlight_reason: "只提了结果，没有给出证据。",
        ai_feedback: "需要补 ROI 或客户案例。",
        suggested_response: "先补一条 ROI 证据，再确认客户是否认可。",
        sales_stage: "objection",
        stage_name: "异议处理",
        context: {},
        audio_url: null,
        score: 62,
        learning_evidence: {
          reason: "客户已经追问可信度，这一轮决定能否继续推进。",
          issue_family: "evidence_gap",
        },
      },
    ],
    total_good: 0,
    total_bad: 1,
    ...overrides,
  };
}

function buildRetryReport(overrides: Record<string, unknown> = {}) {
  return {
    session_id: "session-1",
    scenario_type: "sales",
    logic_score: 78,
    accuracy_score: 70,
    completeness_score: 68,
    overall_score: 72,
    suggestions: ["先补 ROI 证据，再继续推进下一步。"],
    audio_url: null,
    transcript_url: null,
    voice_policy_snapshot_ref: null,
    effectiveness_snapshot: null,
    pass_flags: null,
    main_capability_passed: false,
    overall_result: "fail",
    main_issue: {
      issue_type: "evidence_gap",
      issue_text: "客户收益提到了，但还没有补上可信证据。",
      recovery_rule: "下一轮至少补一条 ROI 或客户案例证据。",
    },
    next_goal: {
      goal_type: "evidence_backing",
      goal_text: "先补 ROI 证据，再继续推进下一步。",
      rule: "至少给出一条证据并确认客户是否认可。",
    },
    stage_summary: [],
    evaluable: true,
    not_evaluable_reason: null,
    evidence_completeness: {
      complete: true,
      missing_fields: [],
      message_count: 4,
    },
    retry_entry: {
      scenario_type: "sales",
      agent_id: "agent-1",
      persona_id: "persona-1",
      presentation_id: null,
      focus_intent: {
        version: "retry_focus_v1",
        source_session_id: "session-1",
        main_issue: {
          issue_type: "evidence_gap",
          issue_text: "客户收益提到了，但还没有补上可信证据。",
          recovery_rule: "下一轮至少补一条 ROI 或客户案例证据。",
        },
        next_goal: {
          goal_type: "evidence_backing",
          goal_text: "先补 ROI 证据，再继续推进下一步。",
          rule: "至少给出一条证据并确认客户是否认可。",
        },
      },
    },
    ...overrides,
  };
}

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
      ],
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
    off_page: 1,
    weak_qa_handling: 1,
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
    page_issue_cluster_count: 3,
    page_issue_types: ["off_page", "missing_point", "weak_qa_handling"],
  },
};

function buildPresentationReplayData(overrides: Record<string, unknown> = {}) {
  return {
    ...buildReplayData({
      scenario_type: "presentation",
      presentation_id: "presentation-1",
      agent_name: null,
      persona_name: null,
      overall_score: 88,
      effectiveness_snapshot: null,
      pass_flags: null,
      main_capability_passed: null,
      overall_result: null,
      main_issue: null,
      next_goal: null,
      evaluable: null,
      not_evaluable_reason: null,
      stage_summary: [],
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
      messages: [
        {
          id: "ppt-turn-1",
          session_id: "session-1",
          turn_number: 1,
          role: "user",
          content: "第一页先讲业务目标，但不小心提前带到了实施计划。",
          timestamp: "2026-03-23T00:00:00Z",
          audio_url: null,
          duration_ms: 1200,
          score_snapshot: {
            overall_score: 88,
          },
          ai_feedback: null,
          is_highlight: false,
          highlight_type: null,
          highlight_reason: null,
          transcript_metadata: {
            page_number: 1,
          },
        },
        {
          id: "ppt-turn-2",
          session_id: "session-1",
          turn_number: 2,
          role: "assistant",
          content: "客户更关心当前页的问题背景。",
          timestamp: "2026-03-23T00:00:08Z",
          audio_url: null,
          duration_ms: 1500,
          score_snapshot: {
            overall_score: 86,
          },
          ai_feedback: null,
          is_highlight: false,
          highlight_type: null,
          highlight_reason: null,
          transcript_metadata: {
            page_number: 1,
          },
        },
        {
          id: "ppt-turn-3",
          session_id: "session-1",
          turn_number: 3,
          role: "user",
          content: "第二页我只讲了 ROI 结果，还没补客户案例。",
          timestamp: "2026-03-23T00:00:16Z",
          audio_url: null,
          duration_ms: 1700,
          score_snapshot: {
            overall_score: 82,
          },
          ai_feedback: null,
          is_highlight: false,
          highlight_type: null,
          highlight_reason: null,
          transcript_metadata: {
            page_number: 2,
          },
        },
        {
          id: "ppt-turn-4",
          session_id: "session-1",
          turn_number: 4,
          role: "assistant",
          content: "如果客户追问负责人，我这边暂时只能说后面再确认。",
          timestamp: "2026-03-23T00:00:24Z",
          audio_url: null,
          duration_ms: 1600,
          score_snapshot: {
            overall_score: 80,
          },
          ai_feedback: null,
          is_highlight: false,
          highlight_type: null,
          highlight_reason: null,
          transcript_metadata: {
            page_number: 2,
          },
        },
      ],
      timeline_markers: [],
    }),
    ...overrides,
  };
}

function buildPresentationReport(overrides: Record<string, unknown> = {}) {
  return {
    ...buildRetryReport({
      scenario_type: "presentation",
      logic_score: 90,
      accuracy_score: 86,
      completeness_score: 81,
      overall_score: 88,
      suggestions: ["下一轮继续补强第二页案例细节。"],
      main_capability_passed: null,
      overall_result: null,
      main_issue: null,
      next_goal: null,
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
        scenario_type: "presentation",
        presentation_id: "presentation-1",
        agent_id: null,
        persona_id: null,
        focus_intent: null,
      },
    }),
    ...overrides,
  };
}

function renderReplayPage(options: {
  search?: string;
  replayOverrides?: Record<string, unknown>;
  highlightsOverrides?: Record<string, unknown>;
  reportOverrides?: Record<string, unknown>;
} = {}) {
  searchParamsState.current = new URLSearchParams(options.search ?? "");
  getReplayMock.mockResolvedValue(buildReplayData(options.replayOverrides));
  getHighlightsMock.mockResolvedValue(buildHighlightsResponse(options.highlightsOverrides));
  getReportMock.mockResolvedValue(buildRetryReport(options.reportOverrides));
  render(<SessionReplayPage />);
}

describe("SessionReplayPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    backMock.mockReset();
    getReplayMock.mockReset();
    getHighlightsMock.mockReset();
    getReportMock.mockReset();
    getThumbnailBlobMock.mockReset();
    createSessionMock.mockReset();
    scrollIntoViewMock.mockReset();
    searchParamsState.current = new URLSearchParams();
    createSessionMock.mockResolvedValue({ session_id: "retry-1" });
    getThumbnailBlobMock.mockRejectedValue(new Error("thumbnail unavailable"));
    getSegmentAudioBlobUrlMock.mockReset();
    getSegmentAudioBlobUrlMock.mockResolvedValue("blob:audio-segment-1");

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoViewMock,
    });
  });

  it("shows an explicit blocked message when replay is still completion-gated", async () => {
    getReplayMock.mockRejectedValue(new ApiRequestError({
      status: 400,
      errorCode: "[SESSION_NOT_COMPLETED]",
      message: "Session must be completed for replay",
    }));
    getReportMock.mockResolvedValue(buildRetryReport());
    getHighlightsMock.mockResolvedValue(buildHighlightsResponse());

    render(<SessionReplayPage />);

    expect(await screen.findByText("统一训练证据不可用")).toBeTruthy();
    expect(screen.getByText("统一训练证据加载失败：当前会话还在评分中，回放会在持久化完成后解锁。"))
      .toBeTruthy();
  });

  it("renders the unified replay evidence without stitching conflicting messages", async () => {
    renderReplayPage();

    await waitFor(() => {
      expect(getReplayMock).toHaveBeenCalledWith("session-1");
    });

    const overallScore = await screen.findByTestId("replay-overall-score");
    expect(overallScore.textContent).toContain("78");
    expect(screen.getByText("当前会话暂不可评估")).toBeTruthy();
    expect(screen.getByText("主张证据状态")).toBeTruthy();
    expect(screen.getByText("证据已验证")).toBeTruthy();
    expect(screen.getByText("当前主张已有足够证据支撑，可以继续沿着这条事实线推进下一步。")).toBeTruthy();
    expect(screen.getByText("证据强度：82 分。本轮补充的证据已达到可验证水平。")).toBeTruthy();
    expect(screen.getByText("本场教练结论")).toBeTruthy();
    expect(screen.getAllByText("证据支撑").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("客户收益提到了，但还没有补上可信证据。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("先补 ROI 证据，再继续推进下一步。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("证据补强").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("客户刚问这个方案凭什么可信。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("我们这个方案能帮你省不少钱。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("为什么这轮关键").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("客户已经追问可信度，这一轮决定能否继续推进。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("更优回应").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("先补一条 ROI 证据，再确认客户是否认可。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("高光学习证据:客户已经追问可信度，这一轮决定能否继续推进。")).toBeTruthy();
    expect(screen.getByText("高光问题家族:evidence_gap")).toBeTruthy();
    expect(screen.getByTestId("audio-audit-card")).toBeTruthy();
    expect(screen.getByText("原始录音")).toBeTruthy();
    expect(screen.getByText("共 2 个片段 · 总时长 0:12")).toBeTruthy();
    expect(screen.getByText(/未知时长/)).toBeTruthy();
  });

  it("launches a focused retry from replay using the report retry_entry focus intent", async () => {
    renderReplayPage();

    fireEvent.click(await screen.findByRole("button", { name: "按目标再练一轮" }));

    await waitFor(() => {
      expect(createSessionMock).toHaveBeenCalledWith({
        scenario_type: "sales",
        agent_id: "agent-1",
        persona_id: "persona-1",
        presentation_id: undefined,
        focus_intent: {
          version: "retry_focus_v1",
          source_session_id: "session-1",
          main_issue: {
            issue_type: "evidence_gap",
            issue_text: "客户收益提到了，但还没有补上可信证据。",
            recovery_rule: "下一轮至少补一条 ROI 或客户案例证据。",
          },
          next_goal: {
            goal_type: "evidence_backing",
            goal_text: "先补 ROI 证据，再继续推进下一步。",
            rule: "至少给出一条证据并确认客户是否认可。",
          },
        },
      });
    });
    expect(pushMock).toHaveBeenCalledWith(
      "/practice/retry-1?scenario_type=sales&agent_id=agent-1&persona_id=persona-1",
    );
  });

  it("lands on the resolved report anchor and keeps the target turn highlighted", async () => {
    renderReplayPage({
      search: "focus=main_issue&message_id=turn-4&turn=4&anchor_status=resolved&marker_type=highlight&marker_timestamp_ms=24000",
    });

    const banner = await screen.findByTestId("replay-anchor-banner");
    expect(banner.textContent).toContain("已定位到主问题片段");
    expect(banner.textContent).toContain("已跳转到第 4 轮对应的高光片段。");

    await waitFor(() => {
      expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
    });

    const anchoredTurn = document.querySelector('[data-turn-number="4"]');
    expect(anchoredTurn?.className).toContain("border-blue-300");
    expect(screen.getByText("如果按你们当前客户流失率测算，三个月能回本。")).toBeTruthy();
  });

  it("surfaces degraded stage fallback when the report asked for a missing highlight", async () => {
    renderReplayPage({
      search: "focus=next_goal&message_id=turn-2&turn=2&anchor_status=degraded&anchor_reason=no_matching_highlight&marker_type=stage_change&marker_timestamp_ms=1800",
    });

    const banner = await screen.findByTestId("replay-anchor-banner");
    expect(banner.textContent).toContain("已定位到目标片段");
    expect(banner.textContent).toContain("未找到精确高光，已定位到“异议处理”阶段附近的第 2 轮。");

    await waitFor(() => {
      expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
    });

    const anchoredTurn = document.querySelector('[data-turn-number="2"]');
    expect(anchoredTurn?.className).toContain("border-blue-300");
  });

  it("keeps the degraded fallback visible when the requested turn and marker no longer exist", async () => {
    renderReplayPage({
      search: "focus=main_issue&message_id=missing-turn&turn=9&anchor_status=degraded&anchor_reason=missing_marker&marker_type=stage_change&marker_timestamp_ms=999999",
    });

    const banner = await screen.findByTestId("replay-anchor-banner");
    expect(banner.textContent).toContain("未找到主问题片段");
    expect(banner.textContent).toContain("报告引用的定位标记当前不存在，页面保留完整对话供手动查找。");
    expect(scrollIntoViewMock).not.toHaveBeenCalled();
    expect(screen.getAllByText("客户刚问这个方案凭什么可信。").length).toBeGreaterThanOrEqual(1);
  });

  it("renders presentation page evidence on replay and lets the learner jump from a page issue to the matching turn", async () => {
    searchParamsState.current = new URLSearchParams("page=2&page_anchor_status=resolved");
    getReplayMock.mockResolvedValue(buildPresentationReplayData());
    getHighlightsMock.mockResolvedValue(buildHighlightsResponse({ highlights: [] }));
    getReportMock.mockResolvedValue(buildPresentationReport());

    render(<SessionReplayPage />);

    expect((await screen.findByTestId("replay-overall-score")).textContent).toContain("88");
    expect(screen.getByText("PPT 回放")).toBeTruthy();
    expect(screen.getByText("PPT 页级问题定位")).toBeTruthy();
    const banner = await screen.findByTestId("presentation-page-banner");
    expect(banner.textContent).toContain("已定位到第 2 页");
    expect(banner.textContent).toContain("已打开报告引用的课件页，并同步展示该页问题簇与相关回合。");
    expect(screen.queryByText("主张证据状态")).toBeNull();
    expect(screen.getAllByText("第二页补充了 ROI 结果，但客户案例展开不够具体。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("第 2 页仍缺少 1 个必讲点，需要补齐再进入下一页。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("如果客户追问负责人，我这边暂时只能说后面再确认。").length).toBeGreaterThanOrEqual(1);

    fireEvent.click(screen.getAllByRole("button", { name: "定位到第 4 轮" })[0]);

    await waitFor(() => {
      expect(scrollIntoViewMock).toHaveBeenCalledWith({ behavior: "smooth", block: "center" });
    });

    expect(getThumbnailBlobMock).toHaveBeenCalledWith("presentation-1", 2);
    const anchoredTurn = document.querySelector('[data-turn-number="4"]');
    expect(anchoredTurn?.className).toContain("border-blue-300");
  });

  it("relaunches PPT retry from replay on the shared practice route family", async () => {
    getReplayMock.mockResolvedValue(buildPresentationReplayData());
    getHighlightsMock.mockResolvedValue(buildHighlightsResponse({ highlights: [] }));
    getReportMock.mockResolvedValue(buildPresentationReport());

    render(<SessionReplayPage />);

    fireEvent.click(await screen.findByRole("button", { name: "按目标再练一轮" }));

    await waitFor(() => {
      expect(createSessionMock).toHaveBeenCalledTimes(1);
    });

    const [payload] = createSessionMock.mock.calls.at(-1) ?? [];
    expect(payload).toMatchObject({
      scenario_type: "presentation",
      presentation_id: "presentation-1",
    });
    expect(payload.agent_id).toBeUndefined();
    expect(payload.persona_id).toBeUndefined();
    expect(payload.focus_intent).toBeUndefined();
    expect(pushMock).toHaveBeenCalledWith(
      "/practice/retry-1?scenario_type=presentation&presentation_id=presentation-1",
    );
  });

  it("keeps a degraded page banner visible when the requested PPT page anchor is missing", async () => {
    searchParamsState.current = new URLSearchParams("page=9&page_anchor_status=missing&page_anchor_reason=page_not_found");
    getReplayMock.mockResolvedValue(buildPresentationReplayData());
    getHighlightsMock.mockResolvedValue(buildHighlightsResponse({ highlights: [] }));
    getReportMock.mockResolvedValue(buildPresentationReport());

    render(<SessionReplayPage />);

    const banner = await screen.findByTestId("presentation-page-banner");
    expect(banner.textContent).toContain("未找到第 9 页");
    expect(banner.textContent).toContain("报告引用的页码当前不存在，已回退到第 1 页继续查看。");
    expect(screen.getAllByText("第一页完整讲清业务目标与客户问题。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("第 1 页讲解带到了其他页内容，优先回到当前页要点。")).toBeTruthy();
  });

  it("renders replay from the canonical projection even when the report snapshot carries conflicting family copy", async () => {
    renderReplayPage({
      reportOverrides: {
        overall_score: 55,
        main_issue: {
          issue_type: "objection_handling_gap",
          issue_text: "这是报告快照里的过期主问题，不应覆盖 replay contract。",
          recovery_rule: "报告快照里的过期修正动作。",
        },
        next_goal: {
          goal_type: "objection_reframe",
          goal_text: "这是报告快照里的过期目标，不应覆盖 replay contract。",
          rule: "报告快照里的过期目标规则。",
        },
        effectiveness_snapshot: {
          claim_truth: {
            status: "unsupported_claim",
            label: "未被证据支撑",
            source: "fallback_snapshot",
            reason: "stale_report_snapshot",
          },
        },
      },
    });

    expect((await screen.findByTestId("replay-overall-score")).textContent).toContain("78");
    expect(screen.getByText("证据已验证")).toBeTruthy();
    expect(screen.getAllByText("客户收益提到了，但还没有补上可信证据。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("先补 ROI 证据，再继续推进下一步。").length).toBeGreaterThanOrEqual(1);
    expect(screen.queryByText("这是报告快照里的过期主问题，不应覆盖 replay contract。")).toBeNull();
    expect(screen.queryByText("这是报告快照里的过期目标，不应覆盖 replay contract。")).toBeNull();
    expect(screen.queryByText("未被证据支撑")).toBeNull();
  });
});
