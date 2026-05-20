"use client";

import * as React from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle,
  Clock,
  FileText,
  RefreshCw,
  Send,
  WifiOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/ui/glass-card";
import { GlassSheet } from "@/components/ui/glass-sheet";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api/client";
import { resolveExamReportHref } from "@/lib/exam-report-routing";
import {
  ensureExamReturnToStudy,
  getExamReturnHref,
  getExamReturnLabel,
  saveExamProgressSnapshot,
} from "@/lib/exam-session-storage";
import { ExamQuestionNavGrouped } from "@/components/exam/ExamQuestionNavGrouped";
import {
  useExaminerWebSocket,
  type ExamQuestionOutlineItem,
  type GradedQuestion,
} from "@/hooks/use-examiner-websocket";
import { examQuestionTypeLabel } from "@/lib/exam-question-type";

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m.toString().padStart(2, "0")}:${s.toString().padStart(2, "0")}`;
}

function EmptyQuestionBank() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-slate-500">
      <FileText className="w-16 h-16 mb-4 text-slate-300" />
      <p className="text-lg font-semibold">题库为空</p>
      <p className="mt-2 text-sm">当前考核没有可用题目，请联系管理员配置题库。</p>
    </div>
  );
}

function ComingSoon() {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-slate-500">
      <Clock className="w-16 h-16 mb-4 text-slate-300" />
      <p className="text-lg font-semibold">即将上线</p>
      <p className="mt-2 text-sm">AI 考核功能正在筹备中，敬请期待。</p>
    </div>
  );
}

function completionReasonLabel(reason: string | null): string {
  switch (reason) {
    case "all_questions_answered":
      return "全部题目已答完";
    case "timed_out":
      return "考核时间已到";
    case "empty_question_bank":
      return "题库为空";
    case "reconnected":
      return "重连后考核已结束";
    default:
      return reason ?? "考核已完成";
  }
}

function ScorePanel({
  questionOutline,
  answeredQuestionIndices,
  currentIndex,
  totalQuestions,
  disabled,
  onSelectQuestion,
  gradedQuestions,
}: {
  questionOutline: ExamQuestionOutlineItem[];
  answeredQuestionIndices: number[];
  currentIndex: number;
  totalQuestions: number;
  disabled: boolean;
  onSelectQuestion: (questionIndex: number) => void;
  gradedQuestions: GradedQuestion[];
}) {
  const answeredCount = answeredQuestionIndices.length;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-slate-800">答题进度</h2>

      <div className="flex items-center gap-3">
        <div className="flex-1 h-2 rounded-full bg-slate-200 overflow-hidden">
          <div
            className="h-full rounded-full bg-indigo-600 transition-all duration-500"
            style={{
              width: `${totalQuestions > 0 ? Math.round((answeredCount / totalQuestions) * 100) : 0}%`,
            }}
          />
        </div>
        <span className="text-sm font-semibold text-slate-600 tabular-nums">
          {answeredCount}/{totalQuestions}
        </span>
      </div>

      {questionOutline.length > 0 && (
        <ExamQuestionNavGrouped
          items={questionOutline}
          answeredIndices={answeredQuestionIndices}
          currentIndex={currentIndex}
          disabled={disabled}
          onSelect={onSelectQuestion}
        />
      )}

      {gradedQuestions.length > 0 && (
        <div className="space-y-2">
          {gradedQuestions.map((q) => (
            <div
              key={q.index}
              className="flex items-center justify-between rounded-xl border border-slate-100 bg-white/60 p-3 text-sm"
            >
              <span className="font-medium text-slate-700">第 {q.index + 1} 题</span>
              <div className="flex items-center gap-2">
                <span className="font-semibold tabular-nums text-slate-700">
                  {q.score} 分
                </span>
                <CheckCircle className="w-4 h-4 text-emerald-500" />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function ExamPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();

  const sessionId = params.sessionId as string;
  const [isPanelOpen, setIsPanelOpen] = React.useState(false);
  const [answerText, setAnswerText] = React.useState("");
  const [sending, setSending] = React.useState(false);
  const [hasPendingSubmit, setHasPendingSubmit] = React.useState(false);
  const [showSubmitConfirm, setShowSubmitConfirm] = React.useState(false);
  const pendingAnswerRef = React.useRef("");
  const confirmSubmitInFlightRef = React.useRef(false);
  const inputRef = React.useRef<HTMLTextAreaElement>(null);

  const {
    connectionState,
    examPhase,
    featureFlag,
    error,
    currentQuestion,
    questionIndex,
    totalQuestions,
    lastFeedback,
    gradedQuestions,
    questionOutline,
    answeredQuestionIndices,
    remainingTimeSeconds,
    answeredCount,
    completionStatus,
    completionReason,
    reportPath,
    voiceFailed,
    isTimeoutWarning,
    isDisconnected,
    progress,
    sendAnswer,
    sendNavigate,
    retry,
    setFeatureFlag,
    setVoiceFailed,
    setErrorState,
  } = useExaminerWebSocket(sessionId);

  // Versioned, question-scoped localStorage key for answer persistence
  const storageKey = currentQuestion
    ? `exam-answer-v1-${sessionId}-${currentQuestion.question_id}`
    : null;

  const contentIdFromQuery = searchParams.get("contentId")?.trim() ?? "";
  if (contentIdFromQuery) {
    ensureExamReturnToStudy(sessionId, contentIdFromQuery);
  }
  const examReturnLabel = getExamReturnLabel(sessionId);

  // Restore answer text from localStorage on mount or question change
  React.useEffect(() => {
    if (!storageKey || examPhase !== "answering" || !currentQuestion) return;
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) {
        setAnswerText(saved);
      } else {
        setAnswerText("");
      }
    } catch {
      setAnswerText("");
    }
    pendingAnswerRef.current = "";
    setSending(false);
    setHasPendingSubmit(false);
    setShowSubmitConfirm(false);
    requestAnimationFrame(() => {
      inputRef.current?.focus();
    });
  }, [storageKey, examPhase, currentQuestion]);

  // Persist answer text to localStorage on changes
  React.useEffect(() => {
    if (!storageKey || examPhase !== "answering" || !currentQuestion) return;
    if (answerText) {
      try {
        localStorage.setItem(storageKey, answerText);
      } catch {
        // localStorage not available
      }
    } else {
      try {
        localStorage.removeItem(storageKey);
      } catch {
        // localStorage not available
      }
    }
  }, [answerText, storageKey, examPhase, currentQuestion]);

  React.useEffect(() => {
    let cancelled = false;
    api.featureFlags
      .get()
      .then((flags) => {
        if (cancelled) return;
        setFeatureFlag(flags.curriculum.examiner ? "enabled" : "disabled");
      })
      .catch(() => {
        if (cancelled) return;
        setFeatureFlag("disabled");
      });
    return () => {
      cancelled = true;
    };
  }, [setFeatureFlag]);

  const focusAnswerInput = React.useCallback(() => {
    if (examPhase !== "answering" || !currentQuestion || showSubmitConfirm) {
      return;
    }
    const el = inputRef.current;
    if (!el || el.disabled) return;
    el.focus();
  }, [currentQuestion, examPhase, showSubmitConfirm]);

  const handleSubmit = React.useCallback(() => {
    const trimmed = answerText.trim();
    if (!trimmed || sending) return;
    pendingAnswerRef.current = trimmed;
    setShowSubmitConfirm(true);
  }, [answerText, sending]);

  const handleConfirmSubmit = React.useCallback(() => {
    if (confirmSubmitInFlightRef.current) return;
    setShowSubmitConfirm(false);
    const trimmed = pendingAnswerRef.current;
    if (!trimmed) return;
    if (connectionState !== "connected") return;
    if (examPhase !== "answering") return;
    if (!currentQuestion) return;

    const isLastQuestion =
      totalQuestions > 0 &&
      currentQuestion.question_index === totalQuestions - 1;

    confirmSubmitInFlightRef.current = true;
    sendAnswer(trimmed);
    setSending(false);
    setHasPendingSubmit(false);
    pendingAnswerRef.current = "";

    if (isLastQuestion) {
      return;
    }

    setAnswerText("");
    if (storageKey) {
      try {
        localStorage.removeItem(storageKey);
      } catch {
        // localStorage not available
      }
    }
    requestAnimationFrame(() => {
      focusAnswerInput();
    });
  }, [
    connectionState,
    currentQuestion,
    examPhase,
    focusAnswerInput,
    sendAnswer,
    storageKey,
    totalQuestions,
  ]);

  const persistExamSnapshot = React.useCallback(() => {
    if (storageKey && answerText.trim()) {
      try {
        localStorage.setItem(storageKey, answerText.trim());
      } catch {
        // localStorage not available
      }
    }
    saveExamProgressSnapshot(sessionId, {
      questionIndex,
      answeredCount: answeredQuestionIndices.length,
      totalQuestions,
      examPhase,
    });
  }, [
    answerText,
    examPhase,
    answeredQuestionIndices.length,
    questionIndex,
    sessionId,
    storageKey,
    totalQuestions,
  ]);

  const handleBack = React.useCallback(() => {
    if (examPhase === "completed") {
      router.push(getExamReturnHref(sessionId));
      return;
    }
    persistExamSnapshot();
    router.push(getExamReturnHref(sessionId));
  }, [examPhase, persistExamSnapshot, router, sessionId]);

  React.useEffect(() => {
    confirmSubmitInFlightRef.current = false;
  }, [questionIndex]);

  React.useEffect(() => {
    if (examPhase === "finalizing" || examPhase === "completed") {
      setShowSubmitConfirm(false);
    }
    if (examPhase === "completed") {
      setSending(false);
      setHasPendingSubmit(false);
      setAnswerText("");
      pendingAnswerRef.current = "";
    }
  }, [examPhase]);

  React.useEffect(() => {
    if (!showSubmitConfirm) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        setShowSubmitConfirm(false);
        pendingAnswerRef.current = "";
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleConfirmSubmit();
      }
    };
    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
  }, [handleConfirmSubmit, showSubmitConfirm]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (examPhase === "finalizing") {
      e.preventDefault();
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (showSubmitConfirm) {
        handleConfirmSubmit();
      } else {
        handleSubmit();
      }
    }
  };

  // 提交后或点击别处失去焦点时，再次键盘输入自动回到答案框
  React.useEffect(() => {
    if (examPhase !== "answering" || !currentQuestion || showSubmitConfirm) {
      return;
    }

    const onWindowKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.isComposing) return;
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      const active = document.activeElement;
      if (active === inputRef.current) return;
      if (
        active instanceof HTMLElement &&
        (active.tagName === "TEXTAREA" ||
          active.tagName === "INPUT" ||
          active.isContentEditable)
      ) {
        return;
      }

      const el = inputRef.current;
      if (!el || el.disabled) return;

      if (e.key === "Process") {
        el.focus();
        return;
      }

      const isPrintable =
        e.key.length === 1 && e.key !== "Enter" && e.key !== "Tab";
      if (isPrintable) {
        e.preventDefault();
        el.focus();
        setAnswerText((prev) => prev + e.key);
        return;
      }

      if (e.key === "Enter" && !e.shiftKey) {
        el.focus();
      }
    };

    window.addEventListener("keydown", onWindowKeyDown, true);
    return () => window.removeEventListener("keydown", onWindowKeyDown, true);
  }, [currentQuestion, examPhase, showSubmitConfirm]);

  const handleViewReport = () => {
    router.push(resolveExamReportHref(sessionId, reportPath));
  };

  const handleSelectQuestion = React.useCallback(
    (targetIndex: number) => {
      if (examPhase !== "answering" || targetIndex === questionIndex) return;
      setShowSubmitConfirm(false);
      pendingAnswerRef.current = "";
      if (storageKey && answerText.trim()) {
        try {
          localStorage.setItem(storageKey, answerText.trim());
        } catch {
          // localStorage not available
        }
      }
      sendNavigate(targetIndex);
    },
    [answerText, examPhase, questionIndex, sendNavigate, storageKey],
  );

  const navigationDisabled =
    connectionState !== "connected" || examPhase !== "answering";

  if (featureFlag === "loading") {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-3 text-slate-500">
        <p>正在加载...</p>
        <p className="text-xs text-slate-400">
          如长时间未响应，请刷新页面后重试。
        </p>
      </div>
    );
  }

  if (featureFlag === "disabled") {
    return (
      <div className="flex items-center justify-center h-full">
        <GlassCard className="max-w-md mx-4 p-8 text-center">
          <ComingSoon />
        </GlassCard>
      </div>
    );
  }

  if (error === "题库为空") {
    return (
      <div className="flex items-center justify-center h-full">
        <GlassCard className="max-w-md mx-4 p-8 text-center">
          <EmptyQuestionBank />
        </GlassCard>
      </div>
    );
  }

  return (
    <>
    <div className="flex h-full w-full">
      {/* Left column: exam content */}
      <div className="flex-1 flex flex-col h-full relative">
        {/* Header */}
        <header className="shrink-0 px-4 py-3 md:px-6 md:py-4 border-b border-white/40 bg-white/20 backdrop-blur-md">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 min-w-0">
              <Button
                variant="ghost"
                size="sm"
                className="shrink-0 rounded-full pl-2 pr-3 text-slate-600 hover:text-slate-900"
                onClick={handleBack}
                aria-label={examReturnLabel}
              >
                <ArrowLeft className="w-4 h-4" />
                <span className="hidden sm:inline text-sm">
                  {examReturnLabel}
                </span>
              </Button>
              <div className="min-w-0">
              <h1 className="text-lg font-bold text-slate-900">AI 考核</h1>
              <p className="text-xs text-slate-500 truncate">
                {connectionState === "connecting"
                  ? "连接中..."
                  : connectionState === "reconnecting"
                  ? "重连中..."
                  : connectionState === "failed"
                  ? "连接失败"
                  : examPhase === "completed"
                  ? "考核完成"
                  : `第 ${questionIndex + 1}/${totalQuestions} 题`}
              </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {remainingTimeSeconds !== null && examPhase !== "completed" && (
                <div
                  className={cn(
                    "flex items-center gap-1 rounded-full px-3 py-1 text-sm font-semibold tabular-nums",
                    isTimeoutWarning
                      ? "bg-red-100 text-red-700 animate-pulse"
                      : "bg-slate-100 text-slate-700",
                  )}
                >
                  <Clock className="w-4 h-4" />
                  {formatTime(remainingTimeSeconds)}
                </div>
              )}

              {totalQuestions > 0 && examPhase !== "completed" && (
                <div className="hidden sm:flex items-center gap-2 text-sm text-slate-600">
                  <div className="w-20 h-2 rounded-full bg-slate-200 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-indigo-600 transition-all"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                  <span className="tabular-nums">{progress}%</span>
                </div>
              )}

              <Button
                variant="ghost"
                size="icon"
                aria-label="查看答题进度"
                className="md:hidden"
                onClick={() => setIsPanelOpen(true)}
              >
                <FileText className="w-5 h-5 text-slate-500" />
              </Button>
            </div>
          </div>

        </header>

        {/* Disconnection / reconnect banner */}
        {isDisconnected && examPhase !== "completed" && (
          <div className="mx-4 mt-4 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800">
            <div className="flex items-start gap-3">
              <WifiOff className="w-5 h-5 mt-0.5 shrink-0 text-amber-600" />
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-sm">
                  {connectionState === "reconnecting"
                    ? "连接中断，正在重连..."
                    : "连接失败"}
                </p>
                <p className="mt-1 text-xs text-amber-700">
                  {connectionState === "reconnecting"
                    ? "网络波动，系统正在自动恢复连接。已答题目进度不会丢失。"
                    : "无法连接到考核服务器，请检查网络后重试。"}
                </p>
                {connectionState === "failed" && (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={retry}
                    className="mt-3 rounded-full border-amber-300 text-amber-800 hover:bg-amber-100"
                  >
                    <RefreshCw className="w-3 h-3 mr-1" />
                    重新连接
                  </Button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Voice failure fallback banner */}
        {voiceFailed && (
          <div className="mx-4 mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-3 text-sm text-blue-700 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            语音失败，已降级为文字输入
          </div>
        )}

        {/* Timeout warning */}
        {isTimeoutWarning && examPhase !== "completed" && (
          <div className="mx-4 mt-4 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 flex items-center gap-2 animate-pulse">
            <AlertCircle className="w-4 h-4 shrink-0" />
            剩余时间不足 {formatTime(remainingTimeSeconds ?? 0)}，请尽快完成答题
          </div>
        )}

        {/* Main content area */}
        <div className="flex-1 overflow-y-auto p-4 md:p-6">
          <div className="max-w-3xl mx-auto space-y-6">
            {/* Connecting state */}
            {connectionState === "connecting" && examPhase === "idle" && (
              <GlassCard className="p-8 text-center">
                <div className="animate-spin rounded-full h-10 w-10 border-2 border-indigo-600 border-t-transparent mx-auto mb-4" />
                <p className="text-slate-600">正在连接考核服务器...</p>
              </GlassCard>
            )}

            {/* Completed state */}
            {examPhase === "completed" && (
              <GlassCard className="p-8 text-center">
                <CheckCircle className="w-16 h-16 mx-auto mb-4 text-emerald-500" />
                <h2 className="text-2xl font-bold text-slate-900">考核完成</h2>
                {answeredCount !== null && (
                  <p className="mt-2 text-4xl font-black text-indigo-900 tabular-nums">
                    {answeredCount}/{totalQuestions}
                  </p>
                )}
                <p className="mt-2 text-sm text-slate-600">
                  {completionReasonLabel(completionReason)}
                </p>
                <Button
                  size="lg"
                  onClick={handleViewReport}
                  className="mt-6 rounded-full"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  查看考核报告
                </Button>
              </GlassCard>
            )}

            {/* Question display */}
            {examPhase === "finalizing" && currentQuestion && (
              <GlassCard className="p-6">
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <Badge variant="gray">
                    第 {currentQuestion.question_index + 1} / {totalQuestions} 题
                  </Badge>
                  <Badge variant="blue">已提交</Badge>
                </div>
                {currentQuestion.title && (
                  <h3 className="text-base font-bold text-slate-800 mb-2">
                    {currentQuestion.title}
                  </h3>
                )}
                <p className="text-lg text-slate-700 whitespace-pre-wrap">
                  {currentQuestion.stem}
                </p>
                {answerText.trim() && (
                  <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50/80 p-4">
                    <p className="text-xs font-semibold text-slate-500 mb-2">
                      你的答案
                    </p>
                    <p className="text-sm text-slate-700 whitespace-pre-wrap">
                      {answerText.trim()}
                    </p>
                  </div>
                )}
              </GlassCard>
            )}

            {examPhase === "answering" && currentQuestion && (
              <GlassCard className="p-6">
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  <Badge variant="gray">
                    第 {currentQuestion.question_index + 1} /{" "}
                    {totalQuestions} 题
                  </Badge>
                  <Badge variant="blue">
                    {examQuestionTypeLabel(currentQuestion.question_type)}
                  </Badge>
                </div>
                {currentQuestion.title && (
                  <h3 className="text-base font-bold text-slate-800 mb-2">
                    {currentQuestion.title}
                  </h3>
                )}
                <p className="text-lg text-slate-700 whitespace-pre-wrap">
                  {currentQuestion.stem}
                </p>
              </GlassCard>
            )}

            {/* Feedback display */}
            {examPhase === "feedback" && lastFeedback && (
              <GlassCard className="p-6">
                <div className="flex items-center gap-2 mb-4">
                  <Badge variant="gray">
                    第 {lastFeedback.question_index + 1} 题
                  </Badge>
                  <Badge variant="green">
                    {lastFeedback.score} 分
                  </Badge>
                </div>
                <p className="text-sm text-slate-700 whitespace-pre-wrap">
                  {lastFeedback.feedback}
                </p>
                {lastFeedback.reason && (
                  <div className="mt-3 rounded-xl border border-blue-100 bg-blue-50/80 p-3 text-sm text-blue-800">
                    <span className="font-semibold">评分理由：</span>
                    {lastFeedback.reason}
                  </div>
                )}
                <p className="mt-4 text-xs text-slate-400">
                  下一题将自动出现，请等待...
                </p>
              </GlassCard>
            )}

            {/* Error display (non-connection errors) */}
            {error && connectionState === "connected" && examPhase !== "completed" && (
              <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 mt-0.5 shrink-0" />
                <p>{error}</p>
              </div>
            )}
          </div>
        </div>

        {/* Answer input area */}
        {examPhase === "answering" && currentQuestion && (
          <div className="shrink-0 border-t border-white/40 bg-white/40 backdrop-blur-md p-4 md:p-6">
            {showSubmitConfirm && (
              <div className="max-w-3xl mx-auto mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-indigo-200 bg-indigo-50/90 px-4 py-2.5 text-sm text-indigo-900">
                <span>确认提交本题答案？再按 Enter 确认，Esc 取消</span>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="rounded-full"
                    onClick={() => {
                      setShowSubmitConfirm(false);
                      pendingAnswerRef.current = "";
                    }}
                  >
                    取消
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    className="rounded-full"
                    onClick={handleConfirmSubmit}
                  >
                    确认提交
                  </Button>
                </div>
              </div>
            )}
            <div className="max-w-3xl mx-auto flex gap-3">
              <textarea
                ref={inputRef}
                value={answerText}
                onChange={(e) => setAnswerText(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="请输入你的答案..."
                disabled={sending}
                rows={3}
                className="flex-1 resize-none rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 disabled:opacity-50"
              />
              <Button
                onClick={handleSubmit}
                disabled={!answerText.trim() || sending}
                size="lg"
                className="self-end rounded-full"
                aria-label="提交答案"
              >
                {sending ? (
                  <span className="flex items-center gap-1">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    提交中
                  </span>
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </div>
            <p className="mt-2 text-center text-xs text-slate-400">
              {showSubmitConfirm
                ? "Enter 确认提交 · Esc 取消 · Shift+Enter 换行"
                : "Enter 打开确认 · 再按 Enter 提交 · Shift+Enter 换行"}
            </p>
          </div>
        )}

        {/* Waiting state between questions */}
        {examPhase === "feedback" && (
          <div className="shrink-0 border-t border-white/40 bg-white/40 backdrop-blur-md p-4 md:p-6">
            <div className="max-w-3xl mx-auto flex items-center justify-center gap-3 text-slate-500">
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-indigo-600 border-t-transparent" />
              <span className="text-sm">等待下一题...</span>
            </div>
          </div>
        )}

        {examPhase === "finalizing" && (
          <div className="shrink-0 border-t border-white/40 bg-white/40 backdrop-blur-md p-4 md:p-6">
            <div className="max-w-3xl mx-auto flex flex-col items-center justify-center gap-2 text-slate-600 py-2">
              <div className="flex items-center gap-3">
                <div className="animate-spin rounded-full h-5 w-5 border-2 border-indigo-600 border-t-transparent" />
                <span className="text-sm font-medium">
                  正在生成考核结果，请稍候…
                </span>
              </div>
              <p className="text-xs text-slate-400">
                全部题目已提交，请勿重复按 Enter
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Right panel (desktop) */}
      <div className="hidden md:block w-80 lg:w-96 border-l border-white/40 bg-white/20 backdrop-blur-xl p-6 overflow-y-auto">
        <ScorePanel
          questionOutline={questionOutline}
          answeredQuestionIndices={answeredQuestionIndices}
          currentIndex={questionIndex}
          totalQuestions={totalQuestions}
          disabled={navigationDisabled}
          onSelectQuestion={handleSelectQuestion}
          gradedQuestions={gradedQuestions}
        />
      </div>

      {/* Mobile bottom panel */}
      <GlassSheet
        isOpen={isPanelOpen}
        onClose={() => setIsPanelOpen(false)}
        side="bottom"
        className="h-[70vh]"
      >
        <div className="h-full overflow-y-auto pb-8 pt-2">
          <ScorePanel
            questionOutline={questionOutline}
            answeredQuestionIndices={answeredQuestionIndices}
            currentIndex={questionIndex}
            totalQuestions={totalQuestions}
            disabled={navigationDisabled}
            onSelectQuestion={handleSelectQuestion}
            gradedQuestions={gradedQuestions}
          />
        </div>
      </GlassSheet>
    </div>
    </>
  );
}
