import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";
import type {
    LearnerStudyChapterCompletionResponse,
    LearnerStudyContent,
    LearnerStudyProgress,
    LearningChapter,
} from "./types";

const fetchMock = vi.fn();

function makeChapter(overrides: Partial<LearningChapter> = {}): LearningChapter {
    return {
        chapter_id: "chapter-1",
        learning_content_id: "content-1",
        title: "开场技巧",
        content: "先确认客户背景。",
        order_index: 0,
        created_at: "2026-05-15T00:00:00Z",
        updated_at: "2026-05-15T00:00:00Z",
        ...overrides,
    };
}

function makeProgress(overrides: Partial<LearnerStudyProgress> = {}): LearnerStudyProgress {
    return {
        completed_chapter_ids: [],
        completed_count: 0,
        total_chapters: 2,
        is_completed: false,
        state: "not_started",
        primary_cta: "开始学习",
        ...overrides,
    };
}

function makeStudyContent(overrides: Partial<LearnerStudyContent> = {}): LearnerStudyContent {
    return {
        learning_content_id: "content-1",
        title: "销售异议处理",
        summary: "学习如何处理常见异议",
        owner: "curriculum-team",
        source: "manual",
        chapters: [
            makeChapter({ chapter_id: "chapter-1", title: "开场技巧", order_index: 0 }),
            makeChapter({ chapter_id: "chapter-2", title: "异议识别", order_index: 1 }),
        ],
        progress: makeProgress(),
        ...overrides,
    };
}

function makeCompletionResponse(
    overrides: Partial<LearnerStudyChapterCompletionResponse> = {},
): LearnerStudyChapterCompletionResponse {
    return {
        chapter_id: "chapter-1",
        already_completed: false,
        progress: makeProgress({
            completed_chapter_ids: ["chapter-1"],
            completed_count: 1,
            state: "in_progress",
            primary_cta: "继续学习",
        }),
        ...overrides,
    };
}

describe("learner study api client", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("gets learner study content with progress", async () => {
        const content = makeStudyContent();
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, data: content }),
        });

        const result = await api.learnerStudy.getContent("content-1");

        expect(result.learning_content_id).toBe("content-1");
        expect(result.progress.state).toBe("not_started");
        expect(result.chapters).toHaveLength(2);
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum-practice/study/learning-contents/content-1"),
            expect.objectContaining({ credentials: "include" }),
        );
    });

    it("completes a chapter and returns updated progress", async () => {
        const response = makeCompletionResponse();
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, data: response }),
        });

        const result = await api.learnerStudy.completeChapter("content-1", "chapter-1");

        expect(result.chapter_id).toBe("chapter-1");
        expect(result.already_completed).toBe(false);
        expect(result.progress.completed_count).toBe(1);
        expect(result.progress.state).toBe("in_progress");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum-practice/study/learning-contents/content-1/chapters/chapter-1/complete"),
            expect.objectContaining({ method: "POST", credentials: "include" }),
        );
    });

    it("handles already completed chapter idempotently", async () => {
        const response = makeCompletionResponse({
            already_completed: true,
            progress: makeProgress({
                completed_chapter_ids: ["chapter-1"],
                completed_count: 1,
                state: "in_progress",
                primary_cta: "继续学习",
            }),
        });
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, data: response }),
        });

        const result = await api.learnerStudy.completeChapter("content-1", "chapter-1");

        expect(result.already_completed).toBe(true);
        expect(result.progress.state).toBe("in_progress");
    });

    it("starts an AI exam for completed study content", async () => {
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({
                success: true,
                data: { session_id: "exam-session-1", examiner_agent_id: "examiner-1" },
            }),
        });

        const result = await api.learnerStudy.startExam("content-1");

        expect(result.session_id).toBe("exam-session-1");
        expect(result.examiner_agent_id).toBe("examiner-1");
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum-practice/study/learning-contents/content-1/start-exam"),
            expect.objectContaining({ method: "POST", credentials: "include" }),
        );
    });

    it("encodes special characters in content and chapter IDs", async () => {
        fetchMock.mockResolvedValueOnce({
            ok: true,
            json: async () => ({ success: true, data: makeStudyContent() }),
        });

        await api.learnerStudy.getContent("content with spaces/123");

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("content%20with%20spaces%2F123"),
            expect.any(Object),
        );
    });
});
