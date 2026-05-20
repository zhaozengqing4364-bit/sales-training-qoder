import { afterEach, describe, expect, it } from "vitest";

import {
  ensureExamReturnToStudy,
  examHrefForSession,
  getExamLearningContentId,
  getExamReturnHref,
  getExamReturnLabel,
  getExamProgressSnapshot,
  setExamReturnContext,
  saveExamProgressSnapshot,
  studyHrefForLearningContent,
} from "./exam-session-storage";

describe("exam-session-storage", () => {
  afterEach(() => {
    localStorage.clear();
  });

  it("stores and reads return context", () => {
    setExamReturnContext("session-1", {
      href: "/study/content-1",
      label: "返回讲义",
      learningContentId: "content-1",
    });

    expect(getExamReturnHref("session-1")).toBe("/study/content-1");
    expect(getExamReturnLabel("session-1")).toBe("返回讲义");
  });

  it("falls back to learning path when return context is missing", () => {
    expect(getExamReturnHref("unknown")).toBe("/learning-path");
    expect(getExamReturnLabel("unknown")).toBe("返回学习路径");
  });

  it("falls back to study page when only learning content binding exists", () => {
    ensureExamReturnToStudy("session-2", "content-2");

    expect(getExamReturnHref("session-2")).toBe("/study/content-2");
    expect(getExamReturnLabel("session-2")).toBe("返回讲义");
    expect(getExamLearningContentId("session-2")).toBe("content-2");
  });

  it("builds study and exam hrefs for learning path entry", () => {
    expect(
      studyHrefForLearningContent("content-1", { fromLearningPath: true }),
    ).toBe("/study/content-1?from=learning-path");
    expect(examHrefForSession("session-1", "content-1")).toBe(
      "/exam/session-1?contentId=content-1",
    );
  });

  it("persists progress snapshot", () => {
    saveExamProgressSnapshot("session-1", {
      questionIndex: 2,
      answeredCount: 2,
      totalQuestions: 20,
      examPhase: "answering",
    });

    expect(getExamProgressSnapshot("session-1")).toMatchObject({
      questionIndex: 2,
      answeredCount: 2,
      totalQuestions: 20,
      examPhase: "answering",
    });
  });
});
