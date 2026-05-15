import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

const fetchMock = vi.fn();

describe("api.testBank contract", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    // ── Category CRUD ──

    it("lists categories", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    items: [
                        {
                            id: "cat-1",
                            name: "销售技巧",
                            description: "销售相关题目",
                            parent_id: null,
                            created_at: "2026-05-01T00:00:00Z",
                            updated_at: "2026-05-10T08:00:00Z",
                        },
                    ],
                    total: 1,
                },
            }),
        });

        const result = await api.testBank.listCategories();

        expect(result.items).toHaveLength(1);
        expect(result.items[0]).toMatchObject({
            id: "cat-1",
            name: "销售技巧",
            description: "销售相关题目",
        });
        expect(result.total).toBe(1);
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/categories"),
            expect.any(Object),
        );
    });

    it("lists categories with parent_id filter", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: { items: [], total: 0 },
            }),
        });

        await api.testBank.listCategories({ parent_id: "cat-root" });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("parent_id=cat-root"),
            expect.any(Object),
        );
    });

    it("creates a category", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    id: "cat-new",
                    name: "产品知识",
                    description: "产品相关内容",
                    parent_id: null,
                    created_at: "2026-05-15T00:00:00Z",
                    updated_at: "2026-05-15T00:00:00Z",
                },
            }),
        });

        const result = await api.testBank.createCategory({
            name: "产品知识",
            description: "产品相关内容",
        });

        expect(result).toMatchObject({
            id: "cat-new",
            name: "产品知识",
        });
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/categories"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({ name: "产品知识", description: "产品相关内容" }),
            }),
        );
    });

    it("updates a category", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    id: "cat-1",
                    name: "销售技巧(更新)",
                    description: "更新描述",
                    parent_id: null,
                    created_at: "2026-05-01T00:00:00Z",
                    updated_at: "2026-05-15T10:00:00Z",
                },
            }),
        });

        const result = await api.testBank.updateCategory("cat-1", {
            name: "销售技巧(更新)",
            description: "更新描述",
        });

        expect(result).toMatchObject({
            id: "cat-1",
            name: "销售技巧(更新)",
        });
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/categories/cat-1"),
            expect.objectContaining({ method: "PUT" }),
        );
    });

    it("deletes a category", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: { deleted: true },
            }),
        });

        const result = await api.testBank.deleteCategory("cat-1");

        expect(result).toEqual({ deleted: true });
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/categories/cat-1"),
            expect.objectContaining({ method: "DELETE" }),
        );
    });

    // ── Question CRUD ──

    it("lists questions with no filters", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    items: [
                        {
                            id: "q-1",
                            title: "如何应对客户异议",
                            stem: "客户提出价格异议时...",
                            reference_answer: "应该先认同...",
                            category_id: "cat-1",
                            difficulty: "medium",
                            status: "draft",
                            tags: ["异议处理", "价格"],
                            scoring_dimensions: [],
                            scoring_criteria: [],
                            safety_flag: false,
                            department: null,
                            version: 1,
                            created_at: "2026-05-01T00:00:00Z",
                            updated_at: "2026-05-01T00:00:00Z",
                        },
                    ],
                    total: 1,
                },
            }),
        });

        const result = await api.testBank.listQuestions();

        expect(result.items).toHaveLength(1);
        expect(result.items[0]).toMatchObject({
            id: "q-1",
            title: "如何应对客户异议",
            difficulty: "medium",
            status: "draft",
        });
        expect(result.total).toBe(1);
    });

    it("lists questions with category_id filter", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: { items: [], total: 0 },
            }),
        });

        await api.testBank.listQuestions({ category_id: "cat-1" });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("category_id=cat-1"),
            expect.any(Object),
        );
    });

    it("lists questions with multiple filters", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: { items: [], total: 0 },
            }),
        });

        await api.testBank.listQuestions({
            category_id: "cat-1",
            difficulty: "hard",
            status: "published",
            tag: "异议处理",
        });

        const callUrl = fetchMock.mock.calls[0][0] as string;
        expect(callUrl).toContain("category_id=cat-1");
        expect(callUrl).toContain("difficulty=hard");
        expect(callUrl).toContain("status=published");
        expect(callUrl).toContain("tag=%E5%BC%82%E8%AE%AE%E5%A4%84%E7%90%86");
    });

    it("creates a question", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    id: "q-new",
                    title: "新题目",
                    stem: "问题描述",
                    reference_answer: "参考答案",
                    category_id: "cat-1",
                    difficulty: "easy",
                    status: "draft",
                    tags: [],
                    scoring_dimensions: [],
                    scoring_criteria: [],
                    safety_flag: false,
                    department: null,
                    version: 1,
                    created_at: "2026-05-15T00:00:00Z",
                    updated_at: "2026-05-15T00:00:00Z",
                },
            }),
        });

        const result = await api.testBank.createQuestion({
            title: "新题目",
            stem: "问题描述",
            reference_answer: "参考答案",
            category_id: "cat-1",
            difficulty: "easy",
            tags: [],
        });

        expect(result).toMatchObject({
            id: "q-new",
            title: "新题目",
            status: "draft",
        });
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/questions"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    title: "新题目",
                    stem: "问题描述",
                    reference_answer: "参考答案",
                    category_id: "cat-1",
                    difficulty: "easy",
                    tags: [],
                }),
            }),
        );
    });

    it("gets a question by id", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    id: "q-1",
                    title: "如何应对客户异议",
                    stem: "客户提出价格异议时...",
                    reference_answer: "应该先认同...",
                    category_id: "cat-1",
                    difficulty: "medium",
                    status: "draft",
                    tags: ["异议处理"],
                    scoring_dimensions: [],
                    scoring_criteria: [],
                    safety_flag: false,
                    department: null,
                    version: 1,
                    created_at: "2026-05-01T00:00:00Z",
                    updated_at: "2026-05-01T00:00:00Z",
                },
            }),
        });

        const result = await api.testBank.getQuestion("q-1");

        expect(result).toMatchObject({
            id: "q-1",
            title: "如何应对客户异议",
        });
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/questions/q-1"),
            expect.any(Object),
        );
    });

    it("updates a question", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    id: "q-1",
                    title: "更新后的题目",
                    stem: "问题描述",
                    reference_answer: "参考答案",
                    category_id: "cat-1",
                    difficulty: "hard",
                    status: "draft",
                    tags: ["异议处理"],
                    scoring_dimensions: [],
                    scoring_criteria: [],
                    safety_flag: false,
                    department: null,
                    version: 2,
                    created_at: "2026-05-01T00:00:00Z",
                    updated_at: "2026-05-15T10:00:00Z",
                },
            }),
        });

        const result = await api.testBank.updateQuestion("q-1", {
            title: "更新后的题目",
            difficulty: "hard",
        });

        expect(result).toMatchObject({
            id: "q-1",
            title: "更新后的题目",
            difficulty: "hard",
        });
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/questions/q-1"),
            expect.objectContaining({ method: "PUT" }),
        );
    });

    it("publishes a question", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    id: "q-1",
                    title: "如何应对客户异议",
                    stem: "客户提出价格异议时...",
                    reference_answer: "应该先认同...",
                    category_id: "cat-1",
                    difficulty: "medium",
                    status: "published",
                    tags: ["异议处理"],
                    scoring_dimensions: [],
                    scoring_criteria: [],
                    safety_flag: false,
                    department: null,
                    version: 1,
                    published_at: "2026-05-15T10:00:00Z",
                    created_at: "2026-05-01T00:00:00Z",
                    updated_at: "2026-05-15T10:00:00Z",
                },
            }),
        });

        const result = await api.testBank.publishQuestion("q-1");

        expect(result).toMatchObject({
            id: "q-1",
            status: "published",
            published_at: "2026-05-15T10:00:00Z",
        });
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/questions/q-1/publish"),
            expect.objectContaining({ method: "POST" }),
        );
    });

    it("archives a question", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    id: "q-1",
                    title: "如何应对客户异议",
                    stem: "客户提出价格异议时...",
                    reference_answer: "应该先认同...",
                    category_id: "cat-1",
                    difficulty: "medium",
                    status: "archived",
                    tags: ["异议处理"],
                    scoring_dimensions: [],
                    scoring_criteria: [],
                    safety_flag: false,
                    department: null,
                    version: 1,
                    created_at: "2026-05-01T00:00:00Z",
                    updated_at: "2026-05-15T10:00:00Z",
                },
            }),
        });

        const result = await api.testBank.archiveQuestion("q-1");

        expect(result).toMatchObject({
            id: "q-1",
            status: "archived",
        });
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/questions/q-1/archive"),
            expect.objectContaining({ method: "POST" }),
        );
    });

    it("handles publish gate error", async () => {
        fetchMock.mockResolvedValue({
            ok: false,
            status: 422,
            json: async () => ({
                detail: {
                    error: "PUBLISH_GATE_FAILED",
                    message: "缺少参考答案",
                },
            }),
        });

        await expect(api.testBank.publishQuestion("q-bad")).rejects.toThrow();
    });

    it("handles category delete error (has children)", async () => {
        fetchMock.mockResolvedValue({
            ok: false,
            status: 409,
            json: async () => ({
                detail: {
                    error: "CATEGORY_HAS_CHILDREN",
                    message: "该分类下有子分类，无法删除",
                },
            }),
        });

        await expect(api.testBank.deleteCategory("cat-parent")).rejects.toThrow();
    });
});
