import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";
import type { LearningChapter, LearningContent } from "./types";

const fetchMock = vi.fn();

function makeLearningContent(overrides: Partial<LearningContent> = {}): LearningContent {
    return {
        learning_content_id: "content-1",
        title: "销售异议处理",
        summary: "学习如何处理常见异议",
        owner: "curriculum-team",
        source: "manual",
        status: "draft",
        safety_flagged: false,
        version: 1,
        content_hash: "hash-1",
        published_at: null,
        created_at: "2026-05-15T00:00:00Z",
        updated_at: "2026-05-15T00:00:00Z",
        chapters: [],
        ...overrides,
    };
}

function makeLearningChapter(overrides: Partial<LearningChapter> = {}): LearningChapter {
    return {
        chapter_id: "chapter-1",
        learning_content_id: "content-1",
        title: "开场",
        content: "先确认客户背景。",
        order_index: 0,
        created_at: "2026-05-15T00:00:00Z",
        updated_at: "2026-05-15T00:00:00Z",
        ...overrides,
    };
}

describe("learning content api client", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("lists and creates learning contents through the shared api facade", async () => {
        const content = makeLearningContent();
        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: { items: [content], total: 1 },
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: makeLearningContent({ learning_content_id: "content-2", title: "成交推进" }),
                }),
            });

        const listResult = await api.learningContents.list({ status: "draft", query: "异议" });
        const createResult = await api.learningContents.create({
            title: "成交推进",
            summary: "推进下一步承诺",
            owner: "curriculum-team",
            source: "manual",
            safety_flagged: false,
        });

        expect(listResult).toEqual({ items: [content], total: 1 });
        expect(createResult.learning_content_id).toBe("content-2");
        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining("/curriculum/learning-contents?status=draft&query=%E5%BC%82%E8%AE%AE"),
            expect.any(Object),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining("/curriculum/learning-contents"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    title: "成交推进",
                    summary: "推进下一步承诺",
                    owner: "curriculum-team",
                    source: "manual",
                    safety_flagged: false,
                }),
            }),
        );
    });

    it("updates details, manages chapters, and moves content through publish/archive paths", async () => {
        const content = makeLearningContent();
        const updated = makeLearningContent({ title: "更新后的学习内容" });
        const chapter = makeLearningChapter();
        fetchMock
            .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: content }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: updated }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: chapter }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: { ...chapter, title: "更新章节" } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: { ok: true } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: { ok: true } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: { ...content, status: "published" } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: { ...content, status: "archived" } }) })
            .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, data: { deleted: true } }) });

        await api.learningContents.get("content-1");
        await api.learningContents.update("content-1", { title: "更新后的学习内容" });
        await api.learningContents.addChapter("content-1", { title: "开场", content: "先确认客户背景。" });
        await api.learningContents.updateChapter("content-1", "chapter-1", { title: "更新章节" });
        await api.learningContents.reorderChapters("content-1", ["chapter-2", "chapter-1"]);
        await api.learningContents.deleteChapter("content-1", "chapter-1");
        const published = await api.learningContents.publish("content-1");
        const archived = await api.learningContents.archive("content-1");
        await api.learningContents.delete("content-1");

        expect(published.status).toBe("published");
        expect(archived.status).toBe("archived");
        expect(fetchMock).toHaveBeenNthCalledWith(
            1,
            expect.stringContaining("/curriculum/learning-contents/content-1"),
            expect.any(Object),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            2,
            expect.stringContaining("/curriculum/learning-contents/content-1"),
            expect.objectContaining({ method: "PUT", body: JSON.stringify({ title: "更新后的学习内容" }) }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            3,
            expect.stringContaining("/curriculum/learning-contents/content-1/chapters"),
            expect.objectContaining({ method: "POST", body: JSON.stringify({ title: "开场", content: "先确认客户背景。" }) }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            4,
            expect.stringContaining("/curriculum/learning-contents/content-1/chapters/chapter-1"),
            expect.objectContaining({ method: "PUT", body: JSON.stringify({ title: "更新章节" }) }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            5,
            expect.stringContaining("/curriculum/learning-contents/content-1/chapters/reorder"),
            expect.objectContaining({ method: "PUT", body: JSON.stringify({ chapter_ids: ["chapter-2", "chapter-1"] }) }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            6,
            expect.stringContaining("/curriculum/learning-contents/content-1/chapters/chapter-1"),
            expect.objectContaining({ method: "DELETE" }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            7,
            expect.stringContaining("/curriculum/learning-contents/content-1/publish"),
            expect.objectContaining({ method: "POST" }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            8,
            expect.stringContaining("/curriculum/learning-contents/content-1/archive"),
            expect.objectContaining({ method: "POST" }),
        );
        expect(fetchMock).toHaveBeenNthCalledWith(
            9,
            expect.stringContaining("/curriculum/learning-contents/content-1"),
            expect.objectContaining({ method: "DELETE" }),
        );
    });
});
