import { afterEach, describe, expect, it } from "vitest";

import {
  getExamReturnHref,
  getExamReturnLabel,
  getExamProgressSnapshot,
  setExamReturnContext,
  saveExamProgressSnapshot,
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
