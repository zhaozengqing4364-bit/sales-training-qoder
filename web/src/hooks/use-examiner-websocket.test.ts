import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useExaminerWebSocket } from "./use-examiner-websocket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  readyState: number = 0;
  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;

  static OPEN = 1;
  static CONNECTING = 0;
  static CLOSED = 3;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(_data: string) {
    // Captured by test spies
  }

  close(code?: number, reason?: string) {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(
      new CloseEvent("close", { code: code ?? 1000, reason, wasClean: true }),
    );
  }

  static reset() {
    MockWebSocket.instances = [];
  }
}

function emitMessage(ws: MockWebSocket, type: string, data: unknown) {
  ws.onmessage?.(new MessageEvent("message", { data: JSON.stringify({ type, data }) }));
}

function openConnection(ws: MockWebSocket) {
  ws.readyState = MockWebSocket.OPEN;
  ws.onopen?.();
}

vi.stubGlobal("WebSocket", MockWebSocket);

describe("useExaminerWebSocket", () => {
  beforeEach(() => {
    MockWebSocket.reset();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("starts in connecting state", () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    expect(result.current.connectionState).toBe("connecting");
    expect(result.current.examPhase).toBe("idle");
    expect(result.current.featureFlag).toBe("loading");
  });

  it("transitions to connected on session.init", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "session-1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 5,
        remaining_seconds: 600,
        status: "in_progress",
      });
    });

    expect(result.current.connectionState).toBe("connected");
    expect(result.current.examPhase).toBe("ready");
    expect(result.current.totalQuestions).toBe(5);
    expect(result.current.remainingTimeSeconds).toBe(600);
  });

  it("transitions to answering on exam.question", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "s1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 3,
        remaining_seconds: 600,
        status: "in_progress",
      });
      emitMessage(ws, "exam.question", {
        question_index: 0,
        question_id: "q-001",
        title: "SPIN 销售法",
        stem: "请简述 SPIN 销售法的四个步骤。",
        remaining_seconds: 120,
      });
    });

    expect(result.current.examPhase).toBe("answering");
    expect(result.current.currentQuestion?.stem).toBe("请简述 SPIN 销售法的四个步骤。");
    expect(result.current.currentQuestion?.title).toBe("SPIN 销售法");
    expect(result.current.currentQuestion?.question_id).toBe("q-001");
    expect(result.current.questionIndex).toBe(0);
  });

  it("transitions to feedback on exam.feedback", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "s1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 3,
        remaining_seconds: 600,
        status: "in_progress",
      });
      emitMessage(ws, "exam.question", {
        question_index: 0,
        question_id: "q-001",
        title: "Q1",
        stem: "What is sales?",
        remaining_seconds: 120,
      });
      emitMessage(ws, "exam.feedback", {
        question_index: 0,
        question_id: "q-001",
        score: 8,
        feedback: "回答不错，但缺少案例支撑。",
        reason: "缺少具体案例和量化数据",
      });
    });

    expect(result.current.examPhase).toBe("feedback");
    expect(result.current.lastFeedback?.score).toBe(8);
    expect(result.current.lastFeedback?.feedback).toBe("回答不错，但缺少案例支撑。");
    expect(result.current.lastFeedback?.reason).toBe("缺少具体案例和量化数据");
    expect(result.current.gradedQuestions).toHaveLength(1);
    expect(result.current.gradedQuestions[0].score).toBe(8);
    expect(result.current.gradedQuestions[0].feedback).toBe("回答不错，但缺少案例支撑。");
  });

  it("transitions to completed on exam.completed", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "s1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 5,
        remaining_seconds: 600,
        status: "in_progress",
      });
      emitMessage(ws, "exam.completed", {
        session_id: "s1",
        status: "completed",
        answered_count: 5,
        total_questions: 5,
        reason: "all_questions_answered",
        report_path: "/reports/s1.pdf",
      });
    });

    expect(result.current.examPhase).toBe("completed");
    expect(result.current.answeredCount).toBe(5);
    expect(result.current.completionStatus).toBe("completed");
    expect(result.current.completionReason).toBe("all_questions_answered");
    expect(result.current.reportPath).toBe("/reports/s1.pdf");
  });

  it("handles exam.completed without optional report_path", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "s1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 2,
        remaining_seconds: 60,
        status: "in_progress",
      });
      emitMessage(ws, "exam.completed", {
        session_id: "s1",
        status: "completed",
        answered_count: 1,
        total_questions: 2,
        reason: "timed_out",
      });
    });

    expect(result.current.examPhase).toBe("completed");
    expect(result.current.completionReason).toBe("timed_out");
    expect(result.current.reportPath).toBeNull();
  });

  it("sends exam.answer message", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    const sendSpy = vi.spyOn(ws, "send");

    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "s1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 3,
        remaining_seconds: 600,
        status: "in_progress",
      });
      emitMessage(ws, "exam.question", {
        question_index: 0,
        question_id: "q-001",
        title: "Q1",
        stem: "Describe SPIN.",
        remaining_seconds: 120,
      });
    });

    await act(async () => {
      result.current.sendAnswer("SPIN = Situation, Problem, Implication, Need-payoff");
    });

    expect(sendSpy).toHaveBeenCalledTimes(1);
    const sent = JSON.parse(sendSpy.mock.calls[0][0] as string);
    expect(sent.type).toBe("exam.answer");
    expect(sent.data.question_index).toBe(0);
    expect(sent.data.answer_text).toBe("SPIN = Situation, Problem, Implication, Need-payoff");
  });

  it("handles reconnection state on close", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "s1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 3,
        remaining_seconds: 600,
        status: "in_progress",
      });
      ws.close(1006, "Abnormal closure");
    });

    expect(result.current.connectionState).toBe("reconnecting");
    expect(result.current.isDisconnected).toBe(true);
  });

  it("shows failed state after max reconnects", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    for (let i = 0; i < 6; i++) {
      const ws = MockWebSocket.instances[MockWebSocket.instances.length - 1];
      await act(async () => {
        if (i === 0) {
          openConnection(ws);
          emitMessage(ws, "session.init", {
            session_id: "s1",
            examiner_agent_id: "ea-1",
            current_question_index: 0,
            total_questions: 3,
            remaining_seconds: 600,
            status: "in_progress",
          });
        }
        ws.close(1006, "Abnormal");
      });
      if (i < 5) {
        await act(async () => {
          vi.advanceTimersByTime(32000);
        });
      }
    }

    expect(result.current.connectionState).toBe("failed");
  });

  it("counts down remaining time from session.init", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "s1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 3,
        remaining_seconds: 60,
        status: "in_progress",
      });
    });

    expect(result.current.remainingTimeSeconds).toBe(60);

    await act(async () => {
      vi.advanceTimersByTime(5000);
    });

    expect(result.current.remainingTimeSeconds).toBeLessThanOrEqual(55);
  });

  it("shows timeout warning when time is low", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "s1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 3,
        remaining_seconds: 15,
        status: "in_progress",
      });
    });

    await act(async () => {
      vi.advanceTimersByTime(6000);
    });

    expect(result.current.isTimeoutWarning).toBe(true);
  });

  it("sets disabled feature flag", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    await act(async () => {
      result.current.setFeatureFlag("disabled");
    });

    expect(result.current.featureFlag).toBe("disabled");
  });

  it("sets voice failed state", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    await act(async () => {
      result.current.setVoiceFailed();
    });

    expect(result.current.voiceFailed).toBe(true);
  });

  it("sets custom error state", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    await act(async () => {
      result.current.setErrorState("题库为空");
    });

    expect(result.current.error).toBe("题库为空");
  });

  it("tracks graded questions across multiple questions", async () => {
    const { result } = renderHook(() => useExaminerWebSocket("session-1"));

    const ws = MockWebSocket.instances[0];
    await act(async () => {
      openConnection(ws);
      emitMessage(ws, "session.init", {
        session_id: "s1",
        examiner_agent_id: "ea-1",
        current_question_index: 0,
        total_questions: 3,
        remaining_seconds: 600,
        status: "in_progress",
      });
      emitMessage(ws, "exam.question", {
        question_index: 0, question_id: "q-1", title: "Q1", stem: "Question 1", remaining_seconds: 120,
      });
      emitMessage(ws, "exam.feedback", {
        question_index: 0, question_id: "q-1", score: 7, feedback: "OK",
      });
      emitMessage(ws, "exam.question", {
        question_index: 1, question_id: "q-2", title: "Q2", stem: "Question 2", remaining_seconds: 120,
      });
      emitMessage(ws, "exam.feedback", {
        question_index: 1, question_id: "q-2", score: 9, feedback: "Good", reason: "Excellent detail",
      });
    });

    expect(result.current.gradedQuestions).toHaveLength(2);
    expect(result.current.gradedQuestions[0].score).toBe(7);
    expect(result.current.gradedQuestions[0].feedback).toBe("OK");
    expect(result.current.gradedQuestions[1].score).toBe(9);
    expect(result.current.gradedQuestions[1].feedback).toBe("Good");
  });
});
