const EXAM_REPORT_API_PREFIX =
  "/api/v1/curriculum-practice/study/exam-sessions/";

export function resolveExamReportHref(
  sessionId: string,
  reportPath?: string | null,
): string {
  const normalizedSessionId = sessionId.trim();
  const fallback = `/exam/${encodeURIComponent(normalizedSessionId)}/report`;
  const raw = (reportPath ?? "").trim();
  if (!raw) {
    return fallback;
  }

  if (raw.startsWith("/exam/") && raw.endsWith("/report")) {
    return raw;
  }

  if (raw.startsWith(EXAM_REPORT_API_PREFIX) && raw.endsWith("/report")) {
    const extracted = raw
      .slice(EXAM_REPORT_API_PREFIX.length, -"/report".length)
      .replace(/^\/+|\/+$/g, "");
    if (extracted) {
      return `/exam/${encodeURIComponent(extracted)}/report`;
    }
  }

  const apiMatch = raw.match(
    /\/exam-sessions\/([^/?#]+)\/report(?:\?.*)?$/,
  );
  if (apiMatch?.[1]) {
    return `/exam/${encodeURIComponent(apiMatch[1])}/report`;
  }

  return fallback;
}
