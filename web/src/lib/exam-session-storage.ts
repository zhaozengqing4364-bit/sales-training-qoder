const RETURN_KEY_PREFIX = "exam-return-v1-";
const PROGRESS_KEY_PREFIX = "exam-progress-v1-";

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

export function getExamReturnHref(sessionId: string): string {
  return getExamReturnContext(sessionId)?.href ?? "/learning-path";
}

export function getExamReturnLabel(sessionId: string): string {
  return getExamReturnContext(sessionId)?.label ?? "返回学习路径";
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
