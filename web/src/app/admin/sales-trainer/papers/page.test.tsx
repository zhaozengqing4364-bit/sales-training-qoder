import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import NewcomerPapersPage from "./page";

const {
    getCapabilitiesMock,
    listPapersMock,
    listPaperRevisionsMock,
    rollbackPaperMock,
    toastApi,
    toastSuccessMock,
    toastErrorMock,
} = vi.hoisted(() => {
    const toastSuccess = vi.fn();
    const toastError = vi.fn();
    return {
        getCapabilitiesMock: vi.fn(),
        listPapersMock: vi.fn(),
        listPaperRevisionsMock: vi.fn(),
        rollbackPaperMock: vi.fn(),
        toastApi: {
            success: toastSuccess,
            error: toastError,
        },
        toastSuccessMock: toastSuccess,
        toastErrorMock: toastError,
    };
});

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/papers",
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => toastApi,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    getCapabilities: getCapabilitiesMock,
                },
                newcomerTraining: {
                    ...actual.api.admin.newcomerTraining,
                    listPapers: listPapersMock,
                    listPaperRevisions: listPaperRevisionsMock,
                    createPaper: vi.fn(),
                    publishPaper: vi.fn(),
                    archivePaper: vi.fn(),
                    rollbackPaper: rollbackPaperMock,
                },
            },
        },
    };
});

describe("NewcomerPapersPage", () => {
    beforeEach(() => {
        getCapabilitiesMock.mockReset();
        listPapersMock.mockReset();
        listPaperRevisionsMock.mockReset();
        rollbackPaperMock.mockReset();
        toastSuccessMock.mockReset();
        toastErrorMock.mockReset();
        getCapabilitiesMock.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: true,
                manage_questions: false,
                manage_modules: false,
                manage_prompts: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_logs: false,
                view_settings: false,
            },
            capability_keys: ["manage_content"],
        });
        listPapersMock.mockResolvedValue({
            items: [
                {
                    paper_id: "paper-1",
                    paper_key: "business-paper",
                    title: "商务礼仪入门考卷",
                    description: null,
                    module_key: "business_skills",
                    unit_id: "unit-1",
                    pass_threshold: 10,
                    status: "draft",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-06-02T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                    active_revision_id: null,
                    active_revision_no: null,
                    working_revision_id: null,
                    working_revision_no: null,
                    has_unpublished_revision: false,
                    questions: [],
                },
                {
                    paper_id: "paper-2",
                    paper_key: "business-paper-published",
                    title: "商务礼仪发布考卷",
                    description: null,
                    module_key: "business_skills",
                    unit_id: "unit-2",
                    pass_threshold: 10,
                    status: "published",
                    created_by: "admin-1",
                    updated_by: "admin-1",
                    created_at: "2026-06-02T00:00:00Z",
                    updated_at: "2026-06-02T00:00:00Z",
                    active_revision_id: "paper-revision-2",
                    active_revision_no: 2,
                    working_revision_id: "paper-revision-3",
                    working_revision_no: 3,
                    has_unpublished_revision: true,
                    questions: [],
                },
            ],
            total: 1,
        });
        listPaperRevisionsMock.mockResolvedValue({
            items: [
                {
                    revision_id: "paper-revision-3",
                    revision_no: 3,
                    status: "working",
                    change_class: "scoring_high_risk",
                    title: "商务礼仪待发布考卷",
                    question_count: 2,
                    is_active: false,
                    is_working: true,
                    source_revision_id: "paper-revision-2",
                    payload_hash: "hash-3",
                    reason: "save edited exam paper revision",
                    trace_id: null,
                    created_by: "admin-1",
                    published_by: null,
                    created_at: "2026-06-03T00:00:00Z",
                    published_at: null,
                },
                {
                    revision_id: "paper-revision-2",
                    revision_no: 2,
                    status: "published",
                    change_class: "scoring_high_risk",
                    title: "商务礼仪发布考卷",
                    question_count: 1,
                    is_active: true,
                    is_working: false,
                    source_revision_id: "paper-revision-1",
                    payload_hash: "hash-2",
                    reason: "publish edited exam paper revision",
                    trace_id: null,
                    created_by: "admin-1",
                    published_by: "admin-1",
                    created_at: "2026-06-02T00:00:00Z",
                    published_at: "2026-06-02T00:30:00Z",
                },
                {
                    revision_id: "paper-revision-1",
                    revision_no: 1,
                    status: "published",
                    change_class: "scoring_high_risk",
                    title: "商务礼仪第一版考卷",
                    question_count: 1,
                    is_active: false,
                    is_working: false,
                    source_revision_id: null,
                    payload_hash: "hash-1",
                    reason: "initial exam paper publish",
                    trace_id: null,
                    created_by: "admin-1",
                    published_by: "admin-1",
                    created_at: "2026-06-01T00:00:00Z",
                    published_at: "2026-06-01T00:30:00Z",
                },
            ],
            total: 3,
        });
        rollbackPaperMock.mockResolvedValue({ paper_id: "paper-2" });
    });

    it("loads papers and routes creation to a dedicated page without exposing internal identifiers", async () => {
        render(<NewcomerPapersPage />);

        await waitFor(() => {
            expect(listPapersMock).toHaveBeenCalledWith({
                include_archived: true,
                limit: 100,
            });
        });
        expect(await screen.findByText("商务礼仪入门考卷")).toBeTruthy();
        expect(await screen.findByRole("link", { name: "编辑草稿" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "新建考卷" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/papers/new",
        );
        expect(screen.getByRole("link", { name: "编辑草稿" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/papers/paper-1/edit",
        );
        expect(screen.getByRole("link", { name: "编辑" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/papers/paper-2/edit",
        );
        expect(screen.queryByRole("button", { name: "复制草稿" })).toBeNull();
        expect(screen.getAllByRole("button", { name: "发布并生效" }).length).toBe(2);
        expect(screen.getAllByText("商务技巧 · 0 题")).toHaveLength(2);
        expect(screen.getByText("草稿")).toBeTruthy();
        expect(screen.queryByText("business-paper")).toBeNull();
        expect(screen.queryByText("考卷标识")).toBeNull();
        expect(screen.queryByText("题目编号")).toBeNull();
        expect(screen.queryByText("draft")).toBeNull();
    });

    it("shows a blocking load error instead of an empty paper table when list loading fails", async () => {
        listPapersMock.mockRejectedValueOnce(new Error("papers backend down"));

        render(<NewcomerPapersPage />);

        expect(await screen.findByText("考卷列表加载失败")).toBeTruthy();
        expect(screen.getByText("papers backend down")).toBeTruthy();
        expect(screen.queryByText("暂无考卷")).toBeNull();
        expect(toastErrorMock).toHaveBeenCalledWith("papers backend down");

        fireEvent.click(screen.getByRole("button", { name: "重新加载考卷" }));

        expect(await screen.findByText("商务礼仪入门考卷")).toBeTruthy();
        expect(screen.queryByText("考卷列表加载失败")).toBeNull();
        await waitFor(() => {
            expect(listPapersMock).toHaveBeenCalledTimes(2);
        });
    });

    it("shows paper revision history and rolls back with an explicit reason", async () => {
        render(<NewcomerPapersPage />);

        await screen.findByText("商务礼仪发布考卷");
        fireEvent.click(screen.getAllByRole("button", { name: "历史版本" })[1]);

        await waitFor(() => {
            expect(listPaperRevisionsMock).toHaveBeenCalledWith("paper-2");
        });
        expect(screen.getByText("历史版本：商务礼仪发布考卷")).toBeTruthy();
        expect(screen.getByText("第 3 版")).toBeTruthy();
        expect(screen.getAllByText("待发布修订").length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText("当前生效")).toBeTruthy();
        expect(screen.queryByText("paper-revision-1")).toBeNull();

        fireEvent.change(screen.getByLabelText("回滚原因（第 1 版）"), {
            target: { value: "恢复第一版题目" },
        });
        fireEvent.click(screen.getByRole("button", { name: "回滚到第 1 版" }));

        await waitFor(() => {
            expect(rollbackPaperMock).toHaveBeenCalledWith("paper-2", {
                target_revision_id: "paper-revision-1",
                reason: "恢复第一版题目",
            });
        });
        expect(toastSuccessMock).toHaveBeenCalledWith("已回滚到第 1 版，后续学员将使用该版本");
    });

    it("fails closed without content management capability", async () => {
        getCapabilitiesMock.mockResolvedValueOnce({
            role: "viewer",
            role_label: "只读人员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_questions: true,
                manage_modules: false,
                manage_prompts: false,
                view_records: false,
                view_global_records: false,
                retry_jobs: false,
                regrade_history: false,
                view_logs: false,
                view_settings: false,
            },
            capability_keys: ["manage_questions"],
        });

        render(<NewcomerPapersPage />);

        expect(await screen.findByText("考卷管理权限不足")).toBeTruthy();
        expect(listPapersMock).not.toHaveBeenCalled();
        expect(listPaperRevisionsMock).not.toHaveBeenCalled();
        expect(screen.queryByRole("link", { name: "新建考卷" })).toBeNull();
        expect(screen.queryByRole("button", { name: "发布并生效" })).toBeNull();
        expect(screen.queryByRole("button", { name: "归档" })).toBeNull();
        expect(screen.queryByRole("button", { name: /回滚到第/ })).toBeNull();
    });
});
