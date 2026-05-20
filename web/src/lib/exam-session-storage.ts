const RETURN_KEY_PREFIX = "exam-return-v1-";
const PROGRESS_KEY_PREFIX = "exam-progress-v1-";
const LEARNING_CONTENT_KEY_PREFIX = "exam-learning-content-v1-";

export const LEARNING_PATH_FROM_PARAM = "learning-path";

export type ExamReturnContext = {
  href: string;
  label: string;
  learningContentId?: string;
  savedAt: number;
};

export type ExamProgressSnapshot = {
  questionIndex: number;
  answeredCount: number;
  totalQuestions: number;
  examPhase: string;
  savedAt: number;
};

function safeGetItem(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSetItem(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // localStorage unavailable
  }
}

export function setExamReturnContext(
  sessionId: string,
  context: Omit<ExamReturnContext, "savedAt">,
): void {
  const payload: ExamReturnContext = { ...context, savedAt: Date.now() };
  safeSetItem(`${RETURN_KEY_PREFIX}${sessionId}`, JSON.stringify(payload));
}

export function getExamReturnContext(sessionId: string): ExamReturnContext | null {
  const raw = safeGetItem(`${RETURN_KEY_PREFIX}${sessionId}`);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as ExamReturnContext;
    if (typeof parsed.href !== "string" || !parsed.href.startsWith("/")) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function studyHrefForLearningContent(
  learningContentId: string,
  options?: { fromLearningPath?: boolean },
): string {
  const base = `/study/${encodeURIComponent(learningContentId)}`;
  if (options?.fromLearningPath) {
    return `${base}?from=${LEARNING_PATH_FROM_PARAM}`;
  }
  return base;
}

export function examHrefForSession(
  sessionId: string,
  learningContentId: string,
): string {
  return `/exam/${encodeURIComponent(sessionId)}?contentId=${encodeURIComponent(learningContentId)}`;
}

export function setExamLearningContentBinding(
  sessionId: string,
  learningContentId: string,
): void {
  safeSetItem(
    `${LEARNING_CONTENT_KEY_PREFIX}${sessionId}`,
    learningContentId,
  );
}

export function getExamLearningContentId(sessionId: string): string | null {
  const raw = safeGetItem(`${LEARNING_CONTENT_KEY_PREFIX}${sessionId}`);
  return raw && raw.trim().length > 0 ? raw : null;
}

/** 写入讲义返回地址；若已有完整 return context 则保留，仅补充 content 绑定。 */
export function ensureExamReturnToStudy(
  sessionId: string,
  learningContentId: string,
): void {
  setExamLearningContentBinding(sessionId, learningContentId);
  if (getExamReturnContext(sessionId)) {
    return;
  }
  setExamReturnContext(sessionId, {
    href: studyHrefForLearningContent(learningContentId),
    label: "返回讲义",
    learningContentId,
  });
}

export function getExamReturnHref(sessionId: string): string {
  const context = getExamReturnContext(sessionId);
  if (context) {
    return context.href;
  }
  const learningContentId = getExamLearningContentId(sessionId);
  if (learningContentId) {
    return studyHrefForLearningContent(learningContentId);
  }
  return "/learning-path";
}

export function getExamReturnLabel(sessionId: string): string {
  const context = getExamReturnContext(sessionId);
  if (context) {
    return context.label;
  }
  if (getExamLearningContentId(sessionId)) {
    return "返回讲义";
  }
  return "返回学习路径";
}

export function saveExamProgressSnapshot(
  sessionId: string,
  snapshot: Omit<ExamProgressSnapshot, "savedAt">,
): void {
  const payload: ExamProgressSnapshot = { ...snapshot, savedAt: Date.now() };
  safeSetItem(`${PROGRESS_KEY_PREFIX}${sessionId}`, JSON.stringify(payload));
}

export function getExamProgressSnapshot(
  sessionId: string,
): ExamProgressSnapshot | null {
  const raw = safeGetItem(`${PROGRESS_KEY_PREFIX}${sessionId}`);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as ExamProgressSnapshot;
  } catch {
    return null;
  }
}
