import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SessionReplayPage from "./page";

const {
  pushMock,
  backMock,
  getReplayMock,
  getHighlightsMock,
  searchParamsState,
  scrollIntoViewMock,
} = vi.hoisted(() => ({
  pushMock: vi.fn(),
  backMock: vi.fn(),
  getReplayMock: vi.fn(),
  getHighlightsMock: vi.fn(),
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

function renderReplayPage(options: {
  search?: string;
  replayOverrides?: Record<string, unknown>;
  highlightsOverrides?: Record<string, unknown>;
} = {}) {
  searchParamsState.current = new URLSearchParams(options.search ?? "");
  getReplayMock.mockResolvedValue(buildReplayData(options.replayOverrides));
  getHighlightsMock.mockResolvedValue(buildHighlightsResponse(options.highlightsOverrides));
  render(<SessionReplayPage />);
}

describe("SessionReplayPage", () => {
  beforeEach(() => {
    pushMock.mockReset();
    backMock.mockReset();
    getReplayMock.mockReset();
    getHighlightsMock.mockReset();
    scrollIntoViewMock.mockReset();
    searchParamsState.current = new URLSearchParams();

    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoViewMock,
    });
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
});
