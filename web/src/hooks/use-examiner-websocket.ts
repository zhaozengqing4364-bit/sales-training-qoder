"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { WS_BASE_URL } from "@/hooks/websocket/types";
import {
  normalizeExamQuestionType,
  type ExamQuestionType,
} from "@/lib/exam-question-type";

// ── Exam message types (exact match with backend #75 examiner_runtime.py) ──

export interface ExamInitData {
  session_id: string;
  examiner_agent_id: string;
  current_question_index: number;
  total_questions: number;
  remaining_seconds: number;
  status: string;
  questions_outline?: ExamQuestionOutlineItem[];
  answered_question_indices?: number[];
}

export interface ExamQuestionOutlineItem {
  question_index: number;
  question_id: string;
  title: string;
  question_type: ExamQuestionType;
}

export interface ExamQuestionData {
  question_index: number;
  question_id: string;
  title: string;
  stem: string;
  question_type: ExamQuestionType;
  remaining_seconds: number;
}

export interface ExamProgressData {
  answered_question_indices: number[];
  current_question_index: number;
}

export interface ExamFeedbackData {
  question_index: number;
  question_id: string;
  score: number;
  feedback: string;
  reason?: string;
}

export interface ExamCompletedData {
  session_id: string;
  status: string;
  answered_count: number;
  total_questions: number;
  reason: string;
  report_path?: string;
}

export interface GradedQuestion {
  index: number;
  score: number;
  feedback: string;
}

export type ExamConnectionState = "connecting" | "connected" | "reconnecting" | "failed";
export type ExamPhase =
  | "idle"
  | "ready"
  | "answering"
  | "feedback"
  | "finalizing"
  | "completed";
export type FeatureFlagStatus = "loading" | "enabled" | "disabled";

export interface ExamState {
  connectionState: ExamConnectionState;
  examPhase: ExamPhase;
  featureFlag: FeatureFlagStatus;
  error: string | null;
  sessionId: string | null;
  currentQuestion: ExamQuestionData | null;
  questionIndex: number;
  totalQuestions: number;
  lastFeedback: ExamFeedbackData | null;
  gradedQuestions: GradedQuestion[];
  questionOutline: ExamQuestionOutlineItem[];
  answeredQuestionIndices: number[];
  remainingTimeSeconds: number | null;
  answeredCount: number | null;
  completionStatus: string | null;
  completionReason: string | null;
  reportPath: string | null;
  voiceFailed: boolean;
  disconnectedAt: number | null;
}

const INITIAL_STATE: ExamState = {
  connectionState: "connecting",
  examPhase: "idle",
  // Default to "disabled" so SSR never shows perpetual "正在加载...".
  // The page's useEffect fetches real feature flags and enables if allowed.
  featureFlag: "disabled" as FeatureFlagStatus,
  error: null,
  sessionId: null,
  currentQuestion: null,
  questionIndex: -1,
  totalQuestions: 0,
  lastFeedback: null,
  gradedQuestions: [],
  questionOutline: [],
  answeredQuestionIndices: [],
  remainingTimeSeconds: null,
  answeredCount: null,
  completionStatus: null,
  completionReason: null,
  reportPath: null,
  voiceFailed: false,
  disconnectedAt: null,
};

// ── Constants ──
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_MS = 1000;
const RECONNECT_MAX_MS = 30000;
const TIMEOUT_WARNING_THRESHOLD_S = 10;

function nextReconnectDelay(attempt: number): number {
  return Math.min(RECONNECT_BASE_MS * Math.pow(2, attempt), RECONNECT_MAX_MS);
}

function buildExaminerWsUrl(sessionId: string): string {
  return `${WS_BASE_URL}/ws/curriculum/examiner/${encodeURIComponent(sessionId)}`;
}

export function useExaminerWebSocket(sessionId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const manualDisconnectRef = useRef(false);
  const isConnectingRef = useRef(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const questionTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [state, setState] = useState<ExamState>(INITIAL_STATE);
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  });

  const clearTimer = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    if (questionTimeoutRef.current !== null) {
      clearTimeout(questionTimeoutRef.current);
      questionTimeoutRef.current = null;
    }
  }, []);

  const startGlobalTimer = useCallback((totalSeconds: number) => {
    clearTimer();
    setState((prev) => ({ ...prev, remainingTimeSeconds: totalSeconds }));
    timerRef.current = setInterval(() => {
      setState((prev) => {
        if (prev.remainingTimeSeconds === null || prev.remainingTimeSeconds <= 0) {
          return prev;
        }
        const next = prev.remainingTimeSeconds - 1;
        if (next <= 0 && prev.examPhase !== "completed") {
          return { ...prev, remainingTimeSeconds: 0, error: "考核时间已到" };
        }
        return { ...prev, remainingTimeSeconds: next };
      });
    }, 1000);
  }, [clearTimer]);

  const startQuestionTimer = useCallback((timeoutS: number) => {
    if (questionTimeoutRef.current !== null) {
      clearTimeout(questionTimeoutRef.current);
    }
    questionTimeoutRef.current = setTimeout(() => {
      setState((prev) => {
        if (prev.examPhase === "answering") {
          return { ...prev, error: "本题答题时间已到，请提交答案" };
        }
        return prev;
      });
    }, timeoutS * 1000);
  }, []);

  const handleMessage = useCallback(
    (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string);
        const msgType = msg.type as string;

        switch (msgType) {
          case "session.init": {
            const data = msg.data as ExamInitData;
            setState((prev) => ({
              ...prev,
              connectionState: "connected",
              examPhase: "ready",
              sessionId: data.session_id,
              questionIndex: data.current_question_index,
              totalQuestions: data.total_questions,
              questionOutline: (data.questions_outline ?? []).map((item) => ({
                question_index: item.question_index,
                question_id: item.question_id,
                title: item.title,
                question_type: normalizeExamQuestionType(item.question_type),
              })),
              answeredQuestionIndices: data.answered_question_indices ?? [],
              error: null,
            }));
            if (data.remaining_seconds > 0) {
              startGlobalTimer(data.remaining_seconds);
            }
            break;
          }

          case "exam.question": {
            const data = msg.data as ExamQuestionData;
            setState((prev) => ({
              ...prev,
              examPhase: prev.examPhase === "finalizing" ? "finalizing" : "answering",
              currentQuestion: {
                ...data,
                question_type: normalizeExamQuestionType(data.question_type),
              },
              questionIndex: data.question_index,
              lastFeedback: null,
              error: null,
            }));
            if (data.remaining_seconds > 0) {
              startQuestionTimer(data.remaining_seconds);
            }
            break;
          }

          case "exam.feedback": {
            const data = msg.data as ExamFeedbackData;
            setState((prev) => ({
              ...prev,
              examPhase: "feedback",
              lastFeedback: data,
              gradedQuestions: [
                ...prev.gradedQuestions,
                {
                  index: data.question_index,
                  score: data.score,
                  feedback: data.feedback,
                },
              ],
              error: null,
            }));
            if (questionTimeoutRef.current !== null) {
              clearTimeout(questionTimeoutRef.current);
              questionTimeoutRef.current = null;
            }
            break;
          }

          case "exam.progress": {
            const data = msg.data as ExamProgressData;
            setState((prev) => ({
              ...prev,
              answeredQuestionIndices: data.answered_question_indices ?? [],
              questionIndex: data.current_question_index ?? prev.questionIndex,
            }));
            break;
          }

          case "exam.finalizing": {
            setState((prev) => ({
              ...prev,
              examPhase: "finalizing",
              error: null,
            }));
            break;
          }

          case "exam.completed": {
            const data = msg.data as ExamCompletedData;
            clearTimer();
            setState((prev) => ({
              ...prev,
              examPhase: "completed",
              answeredCount: data.answered_count,
              completionStatus: data.status,
              completionReason: data.reason,
              reportPath: data.report_path ?? null,
              error: null,
            }));
            break;
          }

          default:
            break;
        }
      } catch {
        // Ignore non-JSON messages
      }
    },
    [clearTimer, startGlobalTimer, startQuestionTimer],
  );

  const handleMessageRef = useRef(handleMessage);
  useEffect(() => {
    handleMessageRef.current = handleMessage;
  });

  const sendAnswer = useCallback(
    (answerText: string) => {
      const current = stateRef.current;
      if (
        wsRef.current?.readyState !== WebSocket.OPEN ||
        current.examPhase !== "answering" ||
        current.currentQuestion === null
      ) {
        return;
      }

      const message = {
        type: "exam.answer",
        data: {
          question_index: current.currentQuestion.question_index,
          answer_text: answerText,
        },
      };
      wsRef.current.send(JSON.stringify(message));
      const answeredIndex = current.currentQuestion.question_index;
      const isLastQuestion =
        current.totalQuestions > 0 &&
        answeredIndex === current.totalQuestions - 1;
      setState((prev) => ({
        ...prev,
        examPhase: isLastQuestion ? ("finalizing" as const) : ("answering" as const),
        error: null,
        answeredQuestionIndices: prev.answeredQuestionIndices.includes(answeredIndex)
          ? prev.answeredQuestionIndices
          : [...prev.answeredQuestionIndices, answeredIndex].sort((a, b) => a - b),
      }));
    },
    [],
  );

  const sendNavigate = useCallback((questionIndex: number) => {
    const current = stateRef.current;
      if (
        wsRef.current?.readyState !== WebSocket.OPEN ||
        current.examPhase === "completed" ||
        current.examPhase === "finalizing" ||
        questionIndex < 0 ||
        questionIndex >= current.totalQuestions
      ) {
        return;
      }

    wsRef.current.send(
      JSON.stringify({
        type: "exam.navigate",
        data: { question_index: questionIndex },
      }),
    );
  }, []);

  const applyConnectionState = useCallback(
    (connectionState: ExamConnectionState, error: string | null) => {
      setState((prev) => {
        if (prev.connectionState === connectionState && prev.error === error) {
          return prev;
        }
        return {
          ...prev,
          connectionState,
          error,
          disconnectedAt: connectionState !== "connected" ? Date.now() : prev.disconnectedAt,
        };
      });
    },
    [],
  );

  const connectRef = useRef<(() => void) | null>(null);

  const connect = useCallback(() => {
    if (isConnectingRef.current) return;
    if (
      wsRef.current?.readyState === WebSocket.OPEN ||
      wsRef.current?.readyState === WebSocket.CONNECTING
    ) {
      return;
    }

    manualDisconnectRef.current = false;
    isConnectingRef.current = true;

    const connectingState: ExamConnectionState =
      reconnectAttempts.current > 0 ? "reconnecting" : "connecting";
    applyConnectionState(
      connectingState,
      connectingState === "reconnecting" ? "连接中断，正在重连..." : null,
    );

    const url = buildExaminerWsUrl(sessionId);
    const ws = new WebSocket(url);

    ws.onopen = () => {
      reconnectAttempts.current = 0;
      isConnectingRef.current = false;
      applyConnectionState("connected", null);
    };

    ws.onmessage = (event: MessageEvent) => {
      handleMessageRef.current?.(event);
    };

    ws.onerror = () => {
      isConnectingRef.current = false;
      if (ws.readyState === WebSocket.CLOSED) return;

      const shouldRetry = reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS;
      applyConnectionState(
        shouldRetry ? "reconnecting" : "failed",
        shouldRetry ? "连接中断，正在尝试恢复..." : "连接失败，请点击重试",
      );
    };

    ws.onclose = (event) => {
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      isConnectingRef.current = false;

      if (manualDisconnectRef.current) return;

      const shouldRetry =
        reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS &&
        event.code !== 1000 &&
        event.code !== 1001;

      if (shouldRetry) {
        reconnectAttempts.current++;
        const delay = nextReconnectDelay(reconnectAttempts.current);
        applyConnectionState("reconnecting", "连接中断，正在重连...");
        setTimeout(() => {
          if (!manualDisconnectRef.current) {
            connectRef.current?.();
          }
        }, delay);
        return;
      }

      applyConnectionState("failed", "连接失败，请点击重试");
    };

    wsRef.current = ws;
  }, [sessionId, applyConnectionState]);

  useEffect(() => {
    connectRef.current = connect;
  });

  const disconnect = useCallback(() => {
    manualDisconnectRef.current = true;
    isConnectingRef.current = false;
    reconnectAttempts.current = 0;
    clearTimer();
    if (wsRef.current) {
      wsRef.current.close(1000, "User disconnected");
      wsRef.current = null;
    }
  }, [clearTimer]);

  const retry = useCallback(() => {
    reconnectAttempts.current = 0;
    setState((prev) => ({
      ...prev,
      connectionState: "connecting",
      examPhase: "idle",
      error: null,
      currentQuestion: null,
      lastFeedback: null,
      gradedQuestions: [],
      questionOutline: [],
      answeredQuestionIndices: [],
    }));
    connect();
  }, [connect]);

  const setFeatureFlag = useCallback((status: FeatureFlagStatus) => {
    setState((prev) => ({ ...prev, featureFlag: status }));
  }, []);

  const setVoiceFailed = useCallback(() => {
    setState((prev) => ({ ...prev, voiceFailed: true }));
  }, []);

  const setErrorState = useCallback((error: string) => {
    setState((prev) => ({ ...prev, error }));
  }, []);

  useEffect(() => {
    // Do not start WebSocket when the examiner feature is disabled.
    // This avoids 403 errors and wasted connections when the page
    // renders the "即将上线" fallback.
    if (state.featureFlag === "disabled") {
      disconnect();
      return;
    }

    // eslint-disable-next-line react-hooks/set-state-in-effect
    connect();
    return () => {
      disconnect();
    };
  }, [state.featureFlag, connect, disconnect]);

  const isTimedOut =
    state.remainingTimeSeconds !== null && state.remainingTimeSeconds <= 0;
  const isTimeoutWarning =
    state.remainingTimeSeconds !== null &&
    state.remainingTimeSeconds > 0 &&
    state.remainingTimeSeconds <= TIMEOUT_WARNING_THRESHOLD_S;
  const isDisconnected =
    state.connectionState === "reconnecting" || state.connectionState === "failed";
  const progress =
    state.totalQuestions > 0
      ? Math.round(
          (state.answeredQuestionIndices.length / state.totalQuestions) * 100,
        )
      : 0;

  return {
    ...state,
    isTimedOut,
    isTimeoutWarning,
    isDisconnected,
    progress,
    sendAnswer,
    sendNavigate,
    retry,
    setFeatureFlag,
    setVoiceFailed,
    setErrorState,
  };
}
