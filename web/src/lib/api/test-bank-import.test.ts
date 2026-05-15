import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

const fetchMock = vi.fn();

describe("api.testBank import contract", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("importQuestions sends FormData to POST /imports and returns ImportJob", async () => {
        const jobData = {
            task_id: "import-abc-123",
            status: "completed",
            result: {
                imported: 5,
                failed: 2,
                errors: [
                    { row: 3, field: "title", message: "标题不能为空" },
                    { row: 7, field: "difficulty", message: "无效的难度值" },
                ],
            },
        };

        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: jobData,
            }),
        });

        const file = new File(["question,answer\ntest,answer"], "questions.csv", {
            type: "text/csv",
        });
        const result = await api.testBank.importQuestions(file);

        expect(result).toMatchObject({
            task_id: "import-abc-123",
            status: "completed",
            result: {
                imported: 5,
                failed: 2,
                errors: [
                    { row: 3, field: "title", message: "标题不能为空" },
                    { row: 7, field: "difficulty", message: "无效的难度值" },
                ],
            },
        });

        expect(fetchMock).toHaveBeenCalledTimes(1);
        const callUrl = fetchMock.mock.calls[0][0] as string;
        expect(callUrl).toContain("/curriculum/test-bank/imports");

        const callOptions = fetchMock.mock.calls[0][1] as RequestInit;
        expect(callOptions.method).toBe("POST");
        expect(callOptions.body).toBeInstanceOf(FormData);

        const formData = callOptions.body as FormData;
        expect(formData.get("file")).toBe(file);
    });

    it("importQuestions sends FormData with correct file field name", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: {
                    task_id: "import-def-456",
                    status: "processing",
                    result: { imported: 0, failed: 0, errors: [] },
                },
            }),
        });

        const file = new File(["data"], "test.jsonl", { type: "application/jsonl" });
        await api.testBank.importQuestions(file);

        const callOptions = fetchMock.mock.calls[0][1] as RequestInit;
        const formData = callOptions.body as FormData;
        expect(formData.has("file")).toBe(true);
        expect(formData.get("file")).toBe(file);
    });

    it("getImportJob fetches GET /imports/{taskId} and returns ImportJob", async () => {
        const jobData = {
            task_id: "import-abc-123",
            status: "completed",
            result: {
                imported: 10,
                failed: 0,
                errors: [],
            },
        };

        fetchMock.mockResolvedValue({
            ok: true,
            json: async () => ({
                success: true,
                data: jobData,
            }),
        });

        const result = await api.testBank.getImportJob("import-abc-123");

        expect(result).toMatchObject({
            task_id: "import-abc-123",
            status: "completed",
            result: { imported: 10, failed: 0, errors: [] },
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/curriculum/test-bank/imports/import-abc-123"),
            expect.any(Object),
        );
    });

    it("getImportJob polls processing status", async () => {
        fetchMock
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: {
                        task_id: "import-poll-1",
                        status: "processing",
                        result: { imported: 0, failed: 0, errors: [] },
                    },
                }),
            })
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({
                    success: true,
                    data: {
                        task_id: "import-poll-1",
                        status: "completed",
                        result: { imported: 3, failed: 0, errors: [] },
                    },
                }),
            });

        const first = await api.testBank.getImportJob("import-poll-1");
        expect(first.status).toBe("processing");

        const second = await api.testBank.getImportJob("import-poll-1");
        expect(second.status).toBe("completed");
        expect(second.result.imported).toBe(3);
    });

    it("importQuestions handles too large file error (413)", async () => {
        fetchMock.mockResolvedValue({
            ok: false,
            status: 413,
            json: async () => ({
                detail: {
                    error: "[TEST_BANK_IMPORT_FILE_TOO_LARGE]",
                    message: "TestBank import file must be 10MB or smaller.",
                },
            }),
        });

        const file = new File(["x".repeat(100)], "large.csv", { type: "text/csv" });
        await expect(api.testBank.importQuestions(file)).rejects.toThrow();
    });

    it("importQuestions handles encoding error (400)", async () => {
        fetchMock.mockResolvedValue({
            ok: false,
            status: 400,
            json: async () => ({
                detail: {
                    error: "[TEST_BANK_IMPORT_ENCODING_INVALID]",
                    message: "TestBank import file must be UTF-8 encoded.",
                },
            }),
        });

        const file = new File(["data"], "bad.csv", { type: "text/csv" });
        await expect(api.testBank.importQuestions(file)).rejects.toThrow();
    });
});
