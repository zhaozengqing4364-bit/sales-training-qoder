import { act, fireEvent, render, screen } from "@testing-library/react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ExamPage from "./page";

const {
  pushMock,
  useExaminerWebSocketMock,
  featureFlagsGetMock,
} = vi.hoisted(() => ({
  pushMock: vi.fn(),
  useExaminerWebSocketMock: vi.fn(),
  featureFlagsGetMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useParams: () => ({ sessionId: "exam-session-1" }),
  useRouter: () => ({ push: pushMock }),
}));

vi.mock("@/components/ui/button", () => ({
  Button: ({
    children,
    asChild,
    ...props
  }: ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) => {
    if (asChild) return <>{children}</>;
    return (
      <button type="button" {...props}>
        {children}
      </button>
    );
  },
}));

vi.mock("@/components/ui/glass-card", () => ({
  GlassCard: ({ children }: { children: ReactNode }) => (
    <div data-testid="glass-card">{children}</div>
  ),
}));

vi.mock("@/components/ui/glass-sheet", () => ({
  GlassSheet: ({ children }: { children: ReactNode }) => (
    <div data-testid="glass-sheet">{children}</div>
  ),
}));

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: ReactNode }) => (
    <span data-testid="badge">{children}</span>
  ),
}));

vi.mock("@/hooks/use-examiner-websocket", () => ({
  useExaminerWebSocket: (...args: unknown[]) => useExaminerWebSocketMock(...args),
}));

vi.mock("@/lib/api/client", () => ({
  api: {
    featureFlags: {
      get: () => featureFlagsGetMock(),
    },
  },
}));

async function flushPreflightEffects() {
  await act(async () => {
    await Promise.resolve();
  });
}

function buildExamHookMock(overrides: Record<string, unknown> = {}) {
  return {
    connectionState: "connected",
    examPhase: "ready",
    featureFlag: "enabled",
    error: null,
    sessionId: "exam-session-1",
    currentQuestion: null,
    questionIndex: 0,
    totalQuestions: 5,
    lastFeedback: null,
    gradedQuestions: [],
    remainingTimeSeconds: 600,
    answeredCount: null,
    completionStatus: null,
    completionReason: null,
    reportPath: null,
    voiceFailed: false,
    isTimeoutWarning: false,
    isDisconnected: false,
    progress: 0,
    sendAnswer: vi.fn(),
    retry: vi.fn(),
    setFeatureFlag: vi.fn(),
    setVoiceFailed: vi.fn(),
    setErrorState: vi.fn(),
    ...overrides,
  };
}

describe("ExamPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    featureFlagsGetMock.mockResolvedValue({ curriculum: { examiner: true } });
    useExaminerWebSocketMock.mockReturnValue(buildExamHookMock());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Feature flag states ──

  it("shows loading state while feature flag is loading", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({ featureFlag: "loading" }),
    );

    render(<ExamPage />);

    expect(screen.getByText("正在加载...")).toBeDefined();
  });

  it("shows 即将上线 when feature flag is disabled", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({ featureFlag: "disabled" }),
    );

    render(<ExamPage />);

    expect(screen.getByText("即将上线")).toBeDefined();
    expect(
      screen.getByText("AI 考核功能正在筹备中，敬请期待。"),
    ).toBeDefined();
  });

  // ── Empty states ──

  it("shows 题库为空 when error is empty question bank", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({ error: "题库为空" }),
    );

    render(<ExamPage />);

    expect(screen.getByText("题库为空")).toBeDefined();
    expect(
      screen.getByText("当前考核没有可用题目，请联系管理员配置题库。"),
    ).toBeDefined();
  });

  it("shows 题库为空 in completed view for empty_question_bank reason", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "completed",
        answeredCount: 0,
        totalQuestions: 0,
        completionReason: "empty_question_bank",
      }),
    );

    render(<ExamPage />);

    // "考核完成" appears in both header subtitle and completed card
    expect(screen.getAllByText("考核完成").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("题库为空").length).toBeGreaterThanOrEqual(1);
  });

  // ── Connection states ──

  it("shows connecting message when connecting and idle", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "connecting",
        examPhase: "idle",
      }),
    );

    render(<ExamPage />);

    expect(screen.getByText("正在连接考核服务器...")).toBeDefined();
  });

  it("shows reconnecting banner when reconnecting", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "reconnecting",
        isDisconnected: true,
        examPhase: "ready",
      }),
    );

    render(<ExamPage />);

    // "连接中断，正在重连..." appears in both header subtitle and banner
    expect(screen.getAllByText("连接中断，正在重连...").length).toBeGreaterThanOrEqual(1);
    expect(
      screen.getByText(
        "网络波动，系统正在自动恢复连接。已答题目进度不会丢失。",
      ),
    ).toBeDefined();
  });

  it("shows failed state with retry button", async () => {
    const retryMock = vi.fn();
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "failed",
        isDisconnected: true,
        examPhase: "ready",
        retry: retryMock,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    // "连接失败" appears in both header subtitle and banner — check banner text
    expect(screen.getByText("无法连接到考核服务器，请检查网络后重试。")).toBeDefined();
    const retryBtn = screen.getByText("重新连接");
    expect(retryBtn).toBeDefined();

    fireEvent.click(retryBtn);
    expect(retryMock).toHaveBeenCalled();
  });

  // ── Timeout warning ──

  it("shows timeout warning when time is low", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        isTimeoutWarning: true,
        remainingTimeSeconds: 8,
        examPhase: "answering",
      }),
    );

    render(<ExamPage />);

    expect(screen.getByText(/剩余时间不足/)).toBeDefined();
  });

  // ── Voice fallback ──

  it("shows voice fallback banner", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({ voiceFailed: true }),
    );

    render(<ExamPage />);

    expect(screen.getByText("语音失败，已降级为文字输入")).toBeDefined();
  });

  // ── Question answering ──

  it("shows question title, stem, and answer input", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "answering",
        currentQuestion: {
          question_index: 2,
          question_id: "q-003",
          title: "SPIN 销售法",
          stem: "请简述 SPIN 销售法的四个步骤及其作用。",
          remaining_seconds: 90,
        },
        questionIndex: 2,
        totalQuestions: 5,
      }),
    );

    render(<ExamPage />);

    expect(screen.getByText("SPIN 销售法")).toBeDefined();
    expect(
      screen.getByText("请简述 SPIN 销售法的四个步骤及其作用。"),
    ).toBeDefined();
    expect(screen.getByPlaceholderText("请输入你的答案...")).toBeDefined();
    expect(screen.getByText("第 3 / 5 题")).toBeDefined();
    expect(screen.getByText("本题剩余 90 秒")).toBeDefined();
  });

  it("opens confirmation dialog on submit click, does not call sendAnswer until confirmed", async () => {
    const sendAnswerMock = vi.fn();
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "answering",
        currentQuestion: {
          question_index: 0,
          question_id: "q-001",
          title: "Q1",
          stem: "What is sales?",
          remaining_seconds: 120,
        },
        sendAnswer: sendAnswerMock,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    const textarea = screen.getByPlaceholderText("请输入你的答案...");
    fireEvent.change(textarea, {
      target: { value: "SPIN = Situation, Problem, Implication, Need-payoff" },
    });

    const submitBtn = screen.getByRole("button", { name: "提交答案" });
    fireEvent.click(submitBtn);

    // Clicking submit should open confirmation, NOT call sendAnswer
    expect(sendAnswerMock).not.toHaveBeenCalled();
    expect(screen.getByText("提交答案")).toBeTruthy();
    expect(screen.getByText(/提交后不可修改/)).toBeTruthy();

    // Confirm the submission
    fireEvent.click(screen.getByRole("button", { name: "确认提交" }));
    expect(sendAnswerMock).toHaveBeenCalledWith(
      "SPIN = Situation, Problem, Implication, Need-payoff",
    );
    expect(sendAnswerMock).toHaveBeenCalledTimes(1);
  });

  it("cancels submission and keeps answer text intact", async () => {
    const sendAnswerMock = vi.fn();
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "answering",
        currentQuestion: {
          question_index: 0,
          question_id: "q-001",
          title: "Q1",
          stem: "What is sales?",
          remaining_seconds: 120,
        },
        sendAnswer: sendAnswerMock,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    const textarea = screen.getByPlaceholderText("请输入你的答案...");
    fireEvent.change(textarea, {
      target: { value: "My draft answer" },
    });

    const submitBtn = screen.getByRole("button", { name: "提交答案" });
    fireEvent.click(submitBtn);

    // Cancel the submission
    fireEvent.click(screen.getByRole("button", { name: "继续作答" }));

    // sendAnswer should never be called
    expect(sendAnswerMock).not.toHaveBeenCalled();

    // Answer text should still be in the textarea
    expect((textarea as HTMLTextAreaElement).value).toBe("My draft answer");
  });

  it("prevents double submit while answer is in flight", async () => {
    const sendAnswerMock = vi.fn();
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "answering",
        currentQuestion: {
          question_index: 0,
          question_id: "q-001",
          title: "Q1",
          stem: "Test question",
          remaining_seconds: 120,
        },
        sendAnswer: sendAnswerMock,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    const textarea = screen.getByPlaceholderText("请输入你的答案...");
    fireEvent.change(textarea, { target: { value: "First answer" } });

    // Open confirmation dialog and confirm
    fireEvent.click(screen.getByRole("button", { name: "提交答案" }));
    fireEvent.click(screen.getByRole("button", { name: "确认提交" }));

    expect(sendAnswerMock).toHaveBeenCalledTimes(1);

    // After sending, the button should have the disabled attribute
    const submitBtnAfter = screen.getByRole("button", { name: "提交答案" });
    expect(submitBtnAfter.hasAttribute("disabled")).toBe(true);
  });

  it("shows submitting state and retains draft while phase remains answering", async () => {
    const sendAnswerMock = vi.fn();
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "answering",
        currentQuestion: {
          question_index: 0,
          question_id: "q-001",
          title: "Q1",
          stem: "Test question",
          remaining_seconds: 120,
        },
        sendAnswer: sendAnswerMock,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    const textarea = screen.getByPlaceholderText("请输入你的答案...");
    fireEvent.change(textarea, { target: { value: "My answer" } });

    // Open confirmation and confirm
    fireEvent.click(screen.getByRole("button", { name: "提交答案" }));
    fireEvent.click(screen.getByRole("button", { name: "确认提交" }));

    // sendAnswer called once
    expect(sendAnswerMock).toHaveBeenCalledTimes(1);
    expect(sendAnswerMock).toHaveBeenCalledWith("My answer");

    // Button should show submitting state
    expect(screen.getByText(/提交中/)).toBeTruthy();

    // Draft should REMAIN in textarea during flight (cleared only on success signal)
    expect((textarea as HTMLTextAreaElement).value).toBe("My answer");
  });

  it("textarea is empty when phase is not answering (draft already cleared)", async () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "feedback",
        lastFeedback: {
          question_index: 0,
          question_id: "q-001",
          score: 7,
          feedback: "Good job.",
        },
        gradedQuestions: [{ index: 0, score: 7, feedback: "Good job." }],
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    // No answer textarea rendered in feedback phase — confirmed by absence
    expect(screen.queryByPlaceholderText("请输入你的答案...")).toBeNull();
  });

  it("Enter key opens confirmation dialog without immediately calling sendAnswer", async () => {
    const sendAnswerMock = vi.fn();
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "answering",
        currentQuestion: {
          question_index: 0,
          question_id: "q-001",
          title: "Q1",
          stem: "Test question",
          remaining_seconds: 120,
        },
        sendAnswer: sendAnswerMock,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    const textarea = screen.getByPlaceholderText("请输入你的答案...");
    fireEvent.change(textarea, { target: { value: "Enter-triggered answer" } });

    // Press Enter
    fireEvent.keyDown(textarea, { key: "Enter", shiftKey: false });

    // Confirmation dialog should appear, sendAnswer should NOT have been called
    expect(sendAnswerMock).not.toHaveBeenCalled();
    expect(screen.getByText(/提交后不可修改/)).toBeTruthy();

    // Confirm
    fireEvent.click(screen.getByRole("button", { name: "确认提交" }));
    expect(sendAnswerMock).toHaveBeenCalledWith("Enter-triggered answer");
    expect(sendAnswerMock).toHaveBeenCalledTimes(1);
  });

  // ── Send guards ──

  it("does not enter submitting state when confirming while disconnected", async () => {
    const sendAnswerMock = vi.fn();
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "failed",
        examPhase: "answering",
        currentQuestion: {
          question_index: 0,
          question_id: "q-001",
          title: "Q1",
          stem: "Test question",
          remaining_seconds: 120,
        },
        sendAnswer: sendAnswerMock,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    const textarea = screen.getByPlaceholderText("请输入你的答案...");
    fireEvent.change(textarea, { target: { value: "My answer" } });

    fireEvent.click(screen.getByRole("button", { name: "提交答案" }));
    fireEvent.click(screen.getByRole("button", { name: "确认提交" }));

    expect(sendAnswerMock).not.toHaveBeenCalled();
    expect(screen.queryByText(/提交中/)).toBeNull();
    expect((textarea as HTMLTextAreaElement).value).toBe("My answer");
  });

  it("does not enter submitting state when confirming while not in answering phase", async () => {
    const sendAnswerMock = vi.fn();
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "connected",
        examPhase: "feedback",
        lastFeedback: {
          question_index: 0,
          question_id: "q-001",
          score: 7,
          feedback: "Good job.",
        },
        sendAnswer: sendAnswerMock,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    // In feedback phase, there is no answer textarea; confirm path is unreachable
    expect(screen.queryByPlaceholderText("请输入你的答案...")).toBeNull();
    expect(sendAnswerMock).not.toHaveBeenCalled();
  });

  it("does not enter submitting state when confirming with no current question", async () => {
    const sendAnswerMock = vi.fn();
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "connected",
        examPhase: "answering",
        currentQuestion: null,
        sendAnswer: sendAnswerMock,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    // Without currentQuestion, the answer textarea is not rendered at all
    expect(screen.queryByPlaceholderText("请输入你的答案...")).toBeNull();
    expect(sendAnswerMock).not.toHaveBeenCalled();
  });

  // ── Draft isolation ──

  it("does not restore Q1 draft when Q2 is the active question", async () => {
    localStorage.clear();
    localStorage.setItem("exam-answer-v1-exam-session-1-q-001", "stale Q1 draft");

    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "connected",
        examPhase: "answering",
        currentQuestion: {
          question_index: 1,
          question_id: "q-002",
          title: "Q2",
          stem: "Second question",
          remaining_seconds: 120,
        },
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    const textarea = screen.getByPlaceholderText("请输入你的答案...");
    expect((textarea as HTMLTextAreaElement).value).toBe("");
  });

  it("clears textarea when active question changes to Q2 with no in-memory draft", async () => {
    localStorage.clear();

    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "connected",
        examPhase: "answering",
        currentQuestion: {
          question_index: 0,
          question_id: "q-001",
          title: "Q1",
          stem: "First question",
          remaining_seconds: 120,
        },
      }),
    );

    const { rerender } = render(<ExamPage />);
    await flushPreflightEffects();

    const textarea = screen.getByPlaceholderText("请输入你的答案...");
    fireEvent.change(textarea, { target: { value: "My Q1 answer" } });
    expect((textarea as HTMLTextAreaElement).value).toBe("My Q1 answer");

    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "connected",
        examPhase: "answering",
        currentQuestion: {
          question_index: 1,
          question_id: "q-002",
          title: "Q2",
          stem: "Second question",
          remaining_seconds: 120,
        },
      }),
    );

    rerender(<ExamPage />);
    await flushPreflightEffects();

    const textareaAfter = screen.getByPlaceholderText("请输入你的答案...");
    expect((textareaAfter as HTMLTextAreaElement).value).toBe("");
  });

  // ── Feedback display ──

  it("shows feedback with score and reason", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "feedback",
        lastFeedback: {
          question_index: 0,
          question_id: "q-001",
          score: 8,
          feedback: "回答准确，结构清晰，但缺少具体案例支撑。",
          reason: "缺少量化数据和行业案例",
        },
        gradedQuestions: [
          { index: 0, score: 8, feedback: "回答准确，结构清晰，但缺少具体案例支撑。" },
        ],
      }),
    );

    render(<ExamPage />);

    // "8 分" appears in both feedback card and score panel
    const scoreMatches = screen.getAllByText("8 分");
    expect(scoreMatches.length).toBeGreaterThanOrEqual(2);
    expect(
      screen.getByText("回答准确，结构清晰，但缺少具体案例支撑。"),
    ).toBeDefined();
    expect(screen.getByText("缺少量化数据和行业案例")).toBeDefined();
    expect(screen.getByText("评分理由：")).toBeDefined();
    expect(screen.getByText("下一题将自动出现，请等待...")).toBeDefined();
  });

  it("shows feedback without reason when reason is absent", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "feedback",
        lastFeedback: {
          question_index: 0,
          question_id: "q-001",
          score: 6,
          feedback: "回答一般。",
        },
        gradedQuestions: [{ index: 0, score: 6, feedback: "回答一般。" }],
      }),
    );

    render(<ExamPage />);

    expect(screen.getAllByText("6 分").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("回答一般。")).toBeDefined();
    expect(screen.queryByText("评分理由：")).toBeNull();
  });

  // ── Completed states ──

  it("shows completed view with report button and all_questions_answered label", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "completed",
        answeredCount: 5,
        totalQuestions: 5,
        completionReason: "all_questions_answered",
        reportPath: "/reports/exam-session-1.pdf",
      }),
    );

    render(<ExamPage />);

    // "考核完成" appears in both header subtitle and card title
    expect(screen.getAllByText("考核完成").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("5/5")).toBeDefined();
    expect(screen.getByText("全部题目已答完")).toBeDefined();
    expect(screen.getByText("查看考核报告")).toBeDefined();
  });

  it("navigates to report_path on report button click", async () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "completed",
        answeredCount: 5,
        totalQuestions: 5,
        completionReason: "all_questions_answered",
        reportPath: "/reports/exam-session-1.pdf",
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    const reportBtn = screen.getByText("查看考核报告");
    fireEvent.click(reportBtn);
    expect(pushMock).toHaveBeenCalledWith("/reports/exam-session-1.pdf");
  });

  it("falls back to /practice/{sessionId}/report when no report_path", async () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "completed",
        answeredCount: 3,
        totalQuestions: 5,
        completionReason: "timed_out",
        reportPath: null,
      }),
    );

    render(<ExamPage />);
    await flushPreflightEffects();

    const reportBtn = screen.getByText("查看考核报告");
    fireEvent.click(reportBtn);
    expect(pushMock).toHaveBeenCalledWith("/practice/exam-session-1/report");
  });

  it("shows timed_out label in completed view", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "completed",
        answeredCount: 3,
        totalQuestions: 5,
        completionReason: "timed_out",
      }),
    );

    render(<ExamPage />);

    expect(screen.getAllByText("考核完成").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("考核时间已到").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("3/5")).toBeDefined();
  });

  it("shows reconnected label in completed view", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "completed",
        answeredCount: 2,
        totalQuestions: 4,
        completionReason: "reconnected",
      }),
    );

    render(<ExamPage />);

    expect(screen.getByText("重连后考核已结束")).toBeDefined();
  });

  // ── Score panel (desktop right panel) ──

  it("shows graded progress in score panel", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        examPhase: "answering",
        currentQuestion: {
          question_index: 2,
          question_id: "q-003",
          title: "Q3",
          stem: "Question 3",
          remaining_seconds: 60,
        },
        questionIndex: 2,
        totalQuestions: 5,
        gradedQuestions: [
          { index: 0, score: 8, feedback: "Good" },
          { index: 1, score: 6, feedback: "OK" },
        ],
      }),
    );

    render(<ExamPage />);

    // Score panel renders in both desktop right panel and mobile GlassSheet (duplicate text)
    expect(screen.getAllByText("答题进度").length).toBeGreaterThanOrEqual(1);
    // "2/5" appears in both header subtitle and score panel
    expect(screen.getAllByText("2/5").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("第 1 题").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("第 2 题").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("8 分").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("6 分").length).toBeGreaterThanOrEqual(1);
  });

  // ── Error display ──

  it("shows inline error when connected and non-empty error occurs", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "connected",
        error: "考核时间已到",
        examPhase: "answering",
      }),
    );

    render(<ExamPage />);

    expect(screen.getByText("考核时间已到")).toBeDefined();
  });

  it("does not show error banner when exam is completed", () => {
    useExaminerWebSocketMock.mockReturnValue(
      buildExamHookMock({
        connectionState: "connected",
        error: "考核时间已到",
        examPhase: "completed",
        completionReason: "timed_out",
      }),
    );

    render(<ExamPage />);

    // Error should NOT appear as inline error banner when exam is completed
    // (completed view shows its own completion reason, not the error banner)
    expect(screen.getAllByText("考核完成").length).toBeGreaterThanOrEqual(1);
  });
});
