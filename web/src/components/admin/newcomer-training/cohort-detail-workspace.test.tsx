import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import {
    FoundationCohortDetailWorkspace,
    parseEnrollmentCsv,
} from "./cohort-detail-workspace";

const getCohortWorkspace = vi.hoisted(() => vi.fn());
const listLearnerOptions = vi.hoisted(() => vi.fn());
const listPaths = vi.hoisted(() => vi.fn());
const previewEnrollmentEmailImport = vi.hoisted(() => vi.fn());
const previewEnrollmentImport = vi.hoisted(() => vi.fn());
const confirmEnrollmentImport = vi.hoisted(() => vi.fn());

vi.mock("next/link", () => ({
    default: ({ href, children, prefetch, ...props }: { href: string; children: ReactNode; prefetch?: boolean }) => <a href={href} data-prefetch={String(prefetch)} {...props}>{children}</a>,
}));
vi.mock("@/components/admin/newcomer-training/workspace-nav", () => ({
    FoundationAdminCapabilityBoundary: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
vi.mock("@/components/ui/glass-modal", () => ({
    Dialog: ({ children, open }: { children: ReactNode; open: boolean }) => open ? <div>{children}</div> : null,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <p>{children}</p>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <h2>{children}</h2>,
}));
vi.mock("@/lib/api/client", () => ({
    api: {
        admin: {
            newcomerTraining: {
                getCohortWorkspace,
                listLearnerOptions,
                listPaths,
                previewEnrollmentEmailImport,
                previewEnrollmentImport,
                confirmEnrollmentImport,
                previewEnrollmentMigration: vi.fn(),
                confirmEnrollmentMigration: vi.fn(),
                changeCohortStatus: vi.fn(),
            },
            createUser: vi.fn(),
        },
    },
    getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : "操作失败",
}));

function renderWorkspace() {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    return render(
        <QueryClientProvider client={client}>
            <FoundationCohortDetailWorkspace cohortId="cohort-1" />
        </QueryClientProvider>,
    );
}

describe("FoundationCohortDetailWorkspace", () => {
    beforeEach(() => {
        getCohortWorkspace.mockReset();
        listLearnerOptions.mockReset();
        listPaths.mockReset();
        previewEnrollmentEmailImport.mockReset();
        previewEnrollmentImport.mockReset();
        confirmEnrollmentImport.mockReset();
        getCohortWorkspace.mockResolvedValue({
            cohort: {
                cohort_id: "cohort-1",
                stable_key: "new-hire-july",
                name: "七月新人班",
                path_revision_id: "path-revision-1",
                status: "active",
                version: 1,
            },
            enrollments: [],
        });
        listLearnerOptions.mockResolvedValue({ items: [] });
        listPaths.mockResolvedValue({ items: [] });
        previewEnrollmentEmailImport.mockResolvedValue({
            import_id: "import-1",
            preview_token: "preview-token",
            impact_hash: "a".repeat(64),
            eligible_count: 1,
            failure_count: 1,
            expires_at: "2026-07-17T09:00:00Z",
            items: [
                { learner_id: "learner-1", learner_name: "王小明", status: "eligible", reason: null },
                { learner_id: "", learner_name: "missing@example.com", status: "failed", reason: "learner_email_not_found_or_inactive" },
            ],
        });
        confirmEnrollmentImport.mockResolvedValue({
            succeeded_count: 1,
            failure_count: 1,
            items: [
                { learner_id: "learner-1", status: "succeeded" },
                { learner_id: "", status: "failed" },
            ],
        });
    });

    it("validates the one-column email template", () => {
        expect(parseEnrollmentCsv("\uFEFFemail\nUSER@example.com\nsecond@example.com\n"))
            .toEqual(["user@example.com", "second@example.com"]);
        expect(() => parseEnrollmentCsv("name\n王小明\n")).toThrow("表头必须为 email");
        expect(() => parseEnrollmentCsv("email\nuser@example.com\nuser@example.com\n"))
            .toThrow("存在重复邮箱");
    });

    it("previews an imported CSV by email and keeps partial confirmation visible", async () => {
        renderWorkspace();

        const template = await screen.findByRole("link", { name: "下载导入模板" });
        expect(template.getAttribute("download")).toBe("新人训练学员导入模板.csv");
        const file = new File(
            ["email\nready@example.com\nmissing@example.com\n"],
            "learners.csv",
            { type: "text/csv" },
        );
        Object.defineProperty(file, "text", {
            value: () => Promise.resolve("email\nready@example.com\nmissing@example.com\n"),
        });
        fireEvent.change(screen.getByLabelText("导入学员 CSV"), {
            target: { files: [file] },
        });

        expect(await screen.findByText(/已读取 2 个邮箱/)).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "预览分配（2 人）" }));
        fireEvent.change(screen.getByLabelText("操作原因"), {
            target: { value: "七月新人班批量入班" },
        });
        fireEvent.click(screen.getByRole("button", { name: "生成分配预览" }));

        expect(await screen.findByText("missing@example.com")).toBeTruthy();
        expect(screen.getByText("邮箱对应的学员不存在或已停用")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "确认分配可执行项" }));

        const partialResult = await screen.findByText("操作部分完成");
        expect(partialResult.parentElement?.textContent).toContain("成功 1 项，未成功 1 项");
        expect(previewEnrollmentEmailImport).toHaveBeenCalledWith(
            "cohort-1",
            ["ready@example.com", "missing@example.com"],
            "七月新人班批量入班",
        );
    });
});
