import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import KnowledgeDetailPage from "./page";

const {
    backMock,
    getKnowledgeBaseMock,
    getKnowledgeBaseDocumentsMock,
    getKnowledgeAnswerAdminConfigMock,
    getKnowledgeAnswerAdminConfigOptionsMock,
    updateKnowledgeAnswerAdminConfigMock,
    listKnowledgeAnswerRunsMock,
    getKnowledgeAnswerRunDetailMock,
    getKnowledgeAnswerRunStepsMock,
    uploadDocumentMock,
    searchKnowledgeBaseMock,
    getKnowledgeDictionaryEntriesMock,
    createKnowledgeDictionaryEntryMock,
    updateKnowledgeDictionaryEntryMock,
    deleteKnowledgeDictionaryEntryMock,
    generateKnowledgeDictionaryEntriesMock,
    reprocessKnowledgeDocumentMock,
    successToastMock,
    errorToastMock,
} = vi.hoisted(() => ({
    backMock: vi.fn(),
    getKnowledgeBaseMock: vi.fn(),
    getKnowledgeBaseDocumentsMock: vi.fn(),
    getKnowledgeAnswerAdminConfigMock: vi.fn(),
    getKnowledgeAnswerAdminConfigOptionsMock: vi.fn(),
    updateKnowledgeAnswerAdminConfigMock: vi.fn(),
    listKnowledgeAnswerRunsMock: vi.fn(),
    getKnowledgeAnswerRunDetailMock: vi.fn(),
    getKnowledgeAnswerRunStepsMock: vi.fn(),
    uploadDocumentMock: vi.fn(),
    searchKnowledgeBaseMock: vi.fn(),
    getKnowledgeDictionaryEntriesMock: vi.fn(),
    createKnowledgeDictionaryEntryMock: vi.fn(),
    updateKnowledgeDictionaryEntryMock: vi.fn(),
    deleteKnowledgeDictionaryEntryMock: vi.fn(),
    generateKnowledgeDictionaryEntriesMock: vi.fn(),
    reprocessKnowledgeDocumentMock: vi.fn(),
    successToastMock: vi.fn(),
    errorToastMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        back: backMock,
        push: vi.fn(),
    }),
    useParams: () => ({
        id: "kb-1",
    }),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: React.ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("@/components/ui/toast", () => {
    const toastApi = {
        success: successToastMock,
        error: errorToastMock,
    };
    return {
        useToast: () => toastApi,
    };
});

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getKnowledgeBase: getKnowledgeBaseMock,
                getKnowledgeBaseDocuments: getKnowledgeBaseDocumentsMock,
                getKnowledgeAnswerAdminConfig: getKnowledgeAnswerAdminConfigMock,
                getKnowledgeAnswerAdminConfigOptions: getKnowledgeAnswerAdminConfigOptionsMock,
                updateKnowledgeAnswerAdminConfig: updateKnowledgeAnswerAdminConfigMock,
                listKnowledgeAnswerRuns: listKnowledgeAnswerRunsMock,
                getKnowledgeAnswerRunDetail: getKnowledgeAnswerRunDetailMock,
                getKnowledgeAnswerRunSteps: getKnowledgeAnswerRunStepsMock,
                uploadDocument: uploadDocumentMock,
                searchKnowledgeBase: searchKnowledgeBaseMock,
                getKnowledgeDictionaryEntries: getKnowledgeDictionaryEntriesMock,
                createKnowledgeDictionaryEntry: createKnowledgeDictionaryEntryMock,
                updateKnowledgeDictionaryEntry: updateKnowledgeDictionaryEntryMock,
                deleteKnowledgeDictionaryEntry: deleteKnowledgeDictionaryEntryMock,
                generateKnowledgeDictionaryEntries: generateKnowledgeDictionaryEntriesMock,
            },
            adminTools: {
                ...actual.api.adminTools,
                reprocessKnowledgeDocument: reprocessKnowledgeDocumentMock,
            },
        },
    };
});

describe("KnowledgeDetailPage", () => {
    beforeEach(() => {
        backMock.mockReset();
        getKnowledgeBaseMock.mockReset();
        getKnowledgeBaseDocumentsMock.mockReset();
        getKnowledgeAnswerAdminConfigMock.mockReset();
        getKnowledgeAnswerAdminConfigOptionsMock.mockReset();
        updateKnowledgeAnswerAdminConfigMock.mockReset();
        listKnowledgeAnswerRunsMock.mockReset();
        getKnowledgeAnswerRunDetailMock.mockReset();
        getKnowledgeAnswerRunStepsMock.mockReset();
        uploadDocumentMock.mockReset();
        searchKnowledgeBaseMock.mockReset();
        getKnowledgeDictionaryEntriesMock.mockReset();
        createKnowledgeDictionaryEntryMock.mockReset();
        updateKnowledgeDictionaryEntryMock.mockReset();
        deleteKnowledgeDictionaryEntryMock.mockReset();
        generateKnowledgeDictionaryEntriesMock.mockReset();
        reprocessKnowledgeDocumentMock.mockReset();
        successToastMock.mockReset();
        errorToastMock.mockReset();

        getKnowledgeBaseMock.mockResolvedValue({
            id: "kb-1",
            name: "石犀产品资料库",
            description: "用于管理员诊断产品资料上传与检索状态。",
            category: "product",
            status: "active",
            document_count: 2,
            total_chunks: 6,
            created_at: "2026-03-23T00:00:00Z",
            updated_at: "2026-03-23T00:00:00Z",
        });

        getKnowledgeBaseDocumentsMock.mockResolvedValue([
            {
                id: "doc-ready",
                file_name: "石犀产品手册.txt",
                file_type: "txt",
                file_size: 1024,
                chunk_count: 6,
                status: "ready",
                created_at: "2026-03-23T00:00:00Z",
            },
            {
                id: "doc-failed",
                file_name: "签约案例.xlsx",
                file_type: "xlsx",
                file_size: 2048,
                chunk_count: 0,
                status: "failed",
                error_message: "Embedding failed",
                created_at: "2026-03-23T00:00:00Z",
            },
        ]);

        getKnowledgeDictionaryEntriesMock.mockResolvedValue({
            items: [
                {
                    id: "dict-1",
                    knowledge_base_id: "kb-1",
                    canonical_term: "石犀科技",
                    aliases: ["实习科技"],
                    term_type: "organization",
                    status: "draft",
                    confidence: 96,
                    source: "manual",
                    evidence_count: 2,
                    created_at: "2026-03-23T00:00:00Z",
                    updated_at: "2026-03-23T00:00:00Z",
                },
            ],
            total: 1,
        });
        createKnowledgeDictionaryEntryMock.mockResolvedValue({ id: "dict-2" });
        updateKnowledgeDictionaryEntryMock.mockResolvedValue({ id: "dict-1" });
        deleteKnowledgeDictionaryEntryMock.mockResolvedValue({ deleted: true });
        generateKnowledgeDictionaryEntriesMock.mockResolvedValue({ created: 1, skipped: 0, items: [] });

        getKnowledgeAnswerAdminConfigMock.mockResolvedValue({
            active_version: {
                id: "cfg-1",
                version_name: "rollout-v1",
                status: "active",
                enabled: true,
                updated_at: "2026-03-31T08:00:00Z",
            },
            profile_source: "database",
            summary: {
                query_profile_count: 1,
                intent_rule_count: 2,
                entity_alias_count: 3,
                ranking_profile_count: 1,
                answerability_profile_count: 1,
            },
            selected_profiles: {
                query_profile_keys: ["intro_v1"],
                ranking_profile_keys: ["default_rank"],
                answerability_profile_keys: ["default_answerability"],
            },
        });

        getKnowledgeAnswerAdminConfigOptionsMock.mockResolvedValue({
            versions: [
                {
                    id: "cfg-1",
                    version_name: "rollout-v1",
                    status: "active",
                    enabled: true,
                    updated_at: "2026-03-31T08:00:00Z",
                },
                {
                    id: "cfg-2",
                    version_name: "rollout-v2",
                    status: "draft",
                    enabled: true,
                    updated_at: "2026-03-31T09:00:00Z",
                },
            ],
        });

        updateKnowledgeAnswerAdminConfigMock.mockResolvedValue({
            active_version: {
                id: "cfg-2",
                version_name: "rollout-v2",
                status: "active",
                enabled: true,
                updated_at: "2026-03-31T09:00:00Z",
            },
            profile_source: "database",
            summary: {
                query_profile_count: 1,
                intent_rule_count: 1,
                entity_alias_count: 1,
                ranking_profile_count: 1,
                answerability_profile_count: 1,
            },
            selected_profiles: {
                query_profile_keys: ["intro_v2"],
                ranking_profile_keys: ["default_rank"],
                answerability_profile_keys: ["default_answerability"],
            },
        });

        listKnowledgeAnswerRunsMock.mockResolvedValue({
            items: [
                {
                    id: "run-1",
                    session_id: "session-1",
                    config_version_id: "cfg-1",
                    entrypoint: "stepfun_realtime",
                    query_text: "请介绍一下石犀科技",
                    answerability: "sufficient",
                    final_status: "completed",
                    blocked_reason: null,
                    step_count: 3,
                    created_at: "2026-03-31T10:00:00Z",
                    updated_at: "2026-03-31T10:00:02Z",
                },
            ],
            total: 12,
            limit: 10,
            page: 1,
            offset: 0,
            session_id: null,
        });

        getKnowledgeAnswerRunDetailMock.mockResolvedValue({
            id: "run-1",
            session_id: "session-1",
            config_version_id: "cfg-1",
            entrypoint: "stepfun_realtime",
            query_text: "请介绍一下石犀科技",
            answerability: "sufficient",
            final_status: "completed",
            blocked_reason: null,
            citations: [{ document_title: "产品手册" }],
            retrieval_summary: { hit_count: 1 },
            created_at: "2026-03-31T10:00:00Z",
            updated_at: "2026-03-31T10:00:02Z",
        });

        getKnowledgeAnswerRunStepsMock.mockResolvedValue({
            run_id: "run-1",
            items: [
                {
                    id: "step-1",
                    answer_run_id: "run-1",
                    step_name: "resolve",
                    step_order: 1,
                    status: "completed",
                    input_payload: { query: "请介绍一下石犀科技" },
                    output_payload: { canonical_entity: "石犀科技" },
                    duration_ms: 4,
                    created_at: "2026-03-31T10:00:00Z",
                    updated_at: "2026-03-31T10:00:00Z",
                },
            ],
            total: 1,
        });

        uploadDocumentMock.mockResolvedValue({
            id: "doc-uploaded",
            file_name: "新增资料.xlsx",
            file_type: "xlsx",
            file_size: 4096,
            chunk_count: 0,
            status: "pending",
            created_at: "2026-03-23T00:00:00Z",
        });

        searchKnowledgeBaseMock.mockResolvedValue({
            total: 1,
            results: [
                {
                    content: "标准版: ¥9,999/年",
                    score: 0.92,
                    metadata: {
                        document_id: "doc-ready",
                        document_title: "石犀产品手册.txt",
                        chunk_index: 0,
                    },
                },
            ],
        });

        reprocessKnowledgeDocumentMock.mockResolvedValue({
            message: "Document reprocessing started",
            document_id: "doc-failed",
        });
    });

    it("accepts xlsx/xls uploads and submits spreadsheet files to the admin API", async () => {
        const { container } = render(<KnowledgeDetailPage />);

        await screen.findByText("石犀产品资料库");

        const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
        expect(fileInput).toBeTruthy();
        expect(fileInput?.accept).toContain(".xlsx");
        expect(fileInput?.accept).toContain(".xls");
        expect(fileInput?.multiple).toBe(true);

        const file = new File(["PK\u0003\u0004"], "新增资料.xlsx", {
            type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        });

        fireEvent.change(fileInput as HTMLInputElement, {
            target: { files: [file] },
        });

        await waitFor(() => {
            expect(uploadDocumentMock).toHaveBeenCalledTimes(1);
        });
        expect(uploadDocumentMock).toHaveBeenCalledWith("kb-1", expect.any(FormData));
    });

    it("manages knowledge dictionary entries from the KB detail page", async () => {
        render(<KnowledgeDetailPage />);

        await screen.findByText("知识库词典");
        expect(screen.getByText("石犀科技")).toBeTruthy();
        expect(screen.getByText(/实习科技/)).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: /从文档生成草稿/i }));
        await waitFor(() => {
            expect(generateKnowledgeDictionaryEntriesMock).toHaveBeenCalledWith("kb-1", 30);
        });

        fireEvent.change(screen.getByPlaceholderText("例如：石犀科技"), {
            target: { value: "销售演练" },
        });
        fireEvent.change(screen.getByPlaceholderText("实习科技，石溪科技"), {
            target: { value: "销售训练,销讲演练" },
        });
        fireEvent.click(screen.getByRole("button", { name: /添加/i }));

        await waitFor(() => {
            expect(createKnowledgeDictionaryEntryMock).toHaveBeenCalledWith(
                "kb-1",
                expect.objectContaining({
                    canonical_term: "销售演练",
                    aliases: ["销售训练", "销讲演练"],
                    status: "draft",
                }),
            );
        });

        fireEvent.click(screen.getByRole("button", { name: "发布" }));
        await waitFor(() => {
            expect(updateKnowledgeDictionaryEntryMock).toHaveBeenCalledWith(
                "kb-1",
                "dict-1",
                { status: "active" },
            );
        });
    });

    it("runs batch uploads through a three-file queue and keeps per-file failures visible", async () => {
        let activeUploads = 0;
        let maxActiveUploads = 0;
        const pendingUploads: Array<{
            title: string;
            resolve: () => void;
            reject: (error: Error) => void;
        }> = [];

        uploadDocumentMock.mockImplementation((_kbId: string, formData: FormData) => {
            const title = String(formData.get("title"));
            activeUploads += 1;
            maxActiveUploads = Math.max(maxActiveUploads, activeUploads);

            return new Promise((resolve, reject) => {
                pendingUploads.push({
                    title,
                    resolve: () => {
                        activeUploads -= 1;
                        resolve({
                            id: `uploaded-${title}`,
                            file_name: title,
                            file_type: "txt",
                            file_size: 128,
                            chunk_count: 0,
                            status: "pending",
                            created_at: "2026-03-23T00:00:00Z",
                        });
                    },
                    reject: (error: Error) => {
                        activeUploads -= 1;
                        reject(error);
                    },
                });
            });
        });

        const { container } = render(<KnowledgeDetailPage />);

        await screen.findByText("石犀产品资料库");
        const fileInput = container.querySelector('input[type="file"]') as HTMLInputElement | null;
        expect(fileInput).toBeTruthy();

        const files = [
            new File(["a"], "产品手册-a.txt", { type: "text/plain" }),
            new File(["b"], "产品手册-b.txt", { type: "text/plain" }),
            new File(["c"], "失败资料.md", { type: "text/markdown" }),
            new File(["d"], "产品手册-d.txt", { type: "text/plain" }),
        ];

        fireEvent.change(fileInput as HTMLInputElement, {
            target: { files },
        });

        expect(await screen.findByText("批量上传队列")).toBeTruthy();
        expect(screen.getByText("产品手册-d.txt")).toBeTruthy();
        await waitFor(() => {
            expect(uploadDocumentMock).toHaveBeenCalledTimes(3);
        });
        expect(maxActiveUploads).toBe(3);

        pendingUploads.find((item) => item.title === "产品手册-a.txt")?.resolve();

        await waitFor(() => {
            expect(uploadDocumentMock).toHaveBeenCalledTimes(4);
        });
        expect(maxActiveUploads).toBe(3);

        pendingUploads.find((item) => item.title === "产品手册-b.txt")?.resolve();
        pendingUploads.find((item) => item.title === "失败资料.md")?.reject(new Error("解析失败"));
        pendingUploads.find((item) => item.title === "产品手册-d.txt")?.resolve();

        await waitFor(() => {
            expect(successToastMock).toHaveBeenCalledWith("3 个文件上传成功，1 个失败。");
        });
        expect(errorToastMock).toHaveBeenCalledWith("1 个文件上传失败，请查看队列详情后重试。");
        expect(await screen.findByText("失败：解析失败")).toBeTruthy();
        expect(screen.getByText(/成功 3 · 失败 1/)).toBeTruthy();
    });

    it("shows the global knowledge-answer config console and allows switching active version", async () => {
        render(<KnowledgeDetailPage />);

        await screen.findByText("知识问答配置（全局）");
        expect(screen.getByText("当前作用于知识问答引擎的全局 active 配置，入口挂在知识库详情页，便于联动排查。"));
        expect((await screen.findAllByText(/rollout-v1/)).length).toBeGreaterThan(0);
        expect(await screen.findByText("database")).toBeTruthy();
        expect(screen.queryByText(/DUAL_RUN/i)).toBeNull();
        expect(screen.queryByText(/ENABLED/i)).toBeNull();

        const selector = screen.getByLabelText("切换 active config version");
        fireEvent.change(selector, { target: { value: "cfg-2" } });
        fireEvent.click(screen.getByRole("button", { name: "保存全局配置" }));

        await waitFor(() => {
            expect(updateKnowledgeAnswerAdminConfigMock).toHaveBeenCalledWith({ config_version_id: "cfg-2" });
        });
        expect(successToastMock).toHaveBeenCalled();
    }, 10000);

    it("shows the global recent knowledge-answer runs section", async () => {
        render(<KnowledgeDetailPage />);

        await screen.findByText("最近知识问答运行（全局）");
        expect(screen.getByText("当前展示的是全局最近运行记录，不保证只来自本知识库；请结合本页搜索诊断一起排查。"));
        expect(await screen.findByText("请介绍一下石犀科技")).toBeTruthy();
        expect(screen.getAllByText("证据充分").length).toBeGreaterThan(0);

        const queryFilter = screen.getByPlaceholderText("按 query 搜索 recent runs");
        fireEvent.change(queryFilter, { target: { value: "价格" } });
        fireEvent.change(screen.getByDisplayValue("全部回答约束"), { target: { value: "blocked" } });
        fireEvent.change(screen.getByDisplayValue("全部运行状态"), { target: { value: "blocked" } });
        fireEvent.click(screen.getByRole("button", { name: "应用筛选" }));

        await waitFor(() => {
            expect(listKnowledgeAnswerRunsMock).toHaveBeenLastCalledWith({
                limit: 10,
                page: 1,
                query: "价格",
                answerability: "blocked",
                final_status: "blocked",
            });
        });

        fireEvent.click(screen.getByRole("button", { name: "查看运行详情" }));

        await waitFor(() => {
            expect(getKnowledgeAnswerRunDetailMock).toHaveBeenCalledWith("run-1");
            expect(getKnowledgeAnswerRunStepsMock).toHaveBeenCalledWith("run-1");
        });

        expect(await screen.findByText("产品手册")).toBeTruthy();
        expect(await screen.findByText("resolve")).toBeTruthy();
        expect(await screen.findByText("命中片段数")).toBeTruthy();
        expect(screen.getAllByText("1").length).toBeGreaterThan(0);
        expect(screen.getByText("执行入口")).toBeTruthy();
        expect(screen.getAllByText("stepfun_realtime").length).toBeGreaterThan(0);
        expect(screen.getByText("输入")).toBeTruthy();
        expect(screen.getByText("输出")).toBeTruthy();
    });

    it("resets to page 1 on filter apply and shows empty state for no matching runs", async () => {
        render(<KnowledgeDetailPage />);
        await screen.findByText("最近知识问答运行（全局）");
        await screen.findByText("请介绍一下石犀科技");

        listKnowledgeAnswerRunsMock.mockResolvedValueOnce({
            items: [],
            total: 0,
            limit: 10,
            page: 1,
            offset: 0,
            session_id: null,
        });

        fireEvent.change(screen.getByPlaceholderText("按 query 搜索 recent runs"), { target: { value: "不存在的问题" } });
        fireEvent.click(screen.getByRole("button", { name: "应用筛选" }));

        await waitFor(() => {
            expect(listKnowledgeAnswerRunsMock).toHaveBeenLastCalledWith({
                limit: 10,
                page: 1,
                query: "不存在的问题",
                answerability: undefined,
                final_status: undefined,
            });
        });

        expect(await screen.findByText("当前筛选条件下暂无运行记录，可调整筛选或清空后重试。")).toBeTruthy();
        expect(screen.getByLabelText("清空筛选条件")).toBeTruthy();
        expect(screen.getByText("当前第 1 / 1 页 · 共 0 条 recent runs")).toBeTruthy();
        expect((screen.getByRole("button", { name: "上一页" }) as HTMLButtonElement).disabled).toBe(true);
        expect((screen.getByRole("button", { name: "下一页" }) as HTMLButtonElement).disabled).toBe(true);
    });

    it("requests the next page from the server when pagination advances", async () => {
        render(<KnowledgeDetailPage />);
        await screen.findByText("最近知识问答运行（全局）");
        await screen.findByText("请介绍一下石犀科技");

        listKnowledgeAnswerRunsMock.mockResolvedValueOnce({
            items: [
                {
                    id: "run-2",
                    session_id: "session-2",
                    config_version_id: "cfg-1",
                    entrypoint: "stepfun_realtime",
                    query_text: "第二页记录",
                    answerability: "partial",
                    final_status: "completed",
                    blocked_reason: null,
                    step_count: 2,
                    created_at: "2026-03-31T09:00:00Z",
                    updated_at: "2026-03-31T09:00:02Z",
                },
            ],
            total: 12,
            limit: 10,
            page: 2,
            offset: 10,
            session_id: null,
        });

        fireEvent.click(screen.getByRole("button", { name: "下一页" }));

        await waitFor(() => {
            expect(listKnowledgeAnswerRunsMock).toHaveBeenLastCalledWith({
                limit: 10,
                page: 2,
                query: undefined,
                answerability: undefined,
                final_status: undefined,
            });
        });

        expect(await screen.findByText("第二页记录")).toBeTruthy();
        expect(screen.getByText("当前第 2 / 2 页 · 共 12 条 recent runs")).toBeTruthy();
    });

    it("clears filters and reloads page 1 with unfiltered recent runs", async () => {
        render(<KnowledgeDetailPage />);
        await screen.findByText("最近知识问答运行（全局）");
        await screen.findByText("请介绍一下石犀科技");

        fireEvent.change(screen.getByPlaceholderText("按 query 搜索 recent runs"), { target: { value: "价格" } });
        fireEvent.change(screen.getByDisplayValue("全部回答约束"), { target: { value: "blocked" } });
        fireEvent.change(screen.getByDisplayValue("全部运行状态"), { target: { value: "blocked" } });

        listKnowledgeAnswerRunsMock.mockResolvedValueOnce({
            items: [
                {
                    id: "run-1",
                    session_id: "session-1",
                    config_version_id: "cfg-1",
                    entrypoint: "stepfun_realtime",
                    query_text: "请介绍一下石犀科技",
                    answerability: "sufficient",
                    final_status: "completed",
                    blocked_reason: null,
                    step_count: 3,
                    created_at: "2026-03-31T10:00:00Z",
                    updated_at: "2026-03-31T10:00:02Z",
                },
            ],
            total: 12,
            limit: 10,
            page: 1,
            offset: 0,
            session_id: null,
        });

        fireEvent.click(screen.getByLabelText("清空筛选条件"));

        await waitFor(() => {
            expect(listKnowledgeAnswerRunsMock).toHaveBeenLastCalledWith({
                limit: 10,
                page: 1,
                query: undefined,
                answerability: undefined,
                final_status: undefined,
            });
        });

        expect((screen.getByPlaceholderText("按 query 搜索 recent runs") as HTMLInputElement).value).toBe("");
        expect((screen.getByDisplayValue("全部回答约束") as HTMLSelectElement).value).toBe("");
        expect((screen.getByDisplayValue("全部运行状态") as HTMLSelectElement).value).toBe("");
    });

    it("shows an inline reprocess action for failed documents", async () => {
        render(<KnowledgeDetailPage />);

        await screen.findByText("签约案例.xlsx");

        const retryButton = await screen.findByRole("button", { name: /重试处理/i });
        fireEvent.click(retryButton);

        await waitFor(() => {
            expect(reprocessKnowledgeDocumentMock).toHaveBeenCalledWith("kb-1", "doc-failed");
        });
        expect(successToastMock).toHaveBeenCalled();
    });

    it("runs search diagnostics and renders matched knowledge evidence", async () => {
        render(<KnowledgeDetailPage />);

        await screen.findByText("石犀产品资料库");

        const queryInput = await screen.findByLabelText("知识库搜索诊断");
        fireEvent.change(queryInput, { target: { value: "产品价格" } });
        fireEvent.click(screen.getByRole("button", { name: /执行诊断/i }));

        await waitFor(() => {
            expect(searchKnowledgeBaseMock).toHaveBeenCalledWith("kb-1", "产品价格", 5, 0.7);
        });

        expect(await screen.findByText("标准版: ¥9,999/年")).toBeTruthy();
        expect(screen.getAllByText(/石犀产品手册\.txt/).length).toBeGreaterThan(0);
    });
});
