import { describe, expect, it } from "vitest";

import { resolveExamReportHref } from "./exam-report-routing";

describe("resolveExamReportHref", () => {
  it("returns frontend route when report path is missing", () => {
    expect(resolveExamReportHref("session-1")).toBe("/exam/session-1/report");
  });

  it("keeps valid frontend report path", () => {
    expect(resolveExamReportHref("session-1", "/exam/session-1/report")).toBe(
      "/exam/session-1/report",
    );
  });

  it("normalizes api report path", () => {
    expect(
      resolveExamReportHref(
        "session-1",
        "/api/v1/curriculum-practice/study/exam-sessions/session-1/report",
      ),
    ).toBe("/exam/session-1/report");
  });
});
