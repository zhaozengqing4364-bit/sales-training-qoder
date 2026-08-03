import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { createIdempotencyTokenStore } from "@/lib/idempotency-token-store";

import {
    CreateSourceForm,
    validateSourceUploadFile,
} from "./content-workspace";

const uploadSourceDocumentV2 = vi.hoisted(() => vi.fn());

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => <a href={href} {...props}>{children}</a>,
}));
vi.mock("@/lib/api/client", () => ({
    api: {
        admin: {
            newcomerTraining: {
                uploadSourceDocumentV2,
            },
        },
    },
    getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : "操作失败",
}));

function renderForm(onCreated = vi.fn()) {
    const client = new QueryClient({
        defaultOptions: { mutations: { retry: false } },
    });
    render(
        <QueryClientProvider client={client}>
            <CreateSourceForm
                tokenStore={createIdempotencyTokenStore()}
                onCreated={onCreated}
            />
        </QueryClientProvider>,
    );
    return onCreated;
}

describe("CreateSourceForm", () => {
    beforeEach(() => {
        uploadSourceDocumentV2.mockReset();
        uploadSourceDocumentV2.mockResolvedValue({
            resource: { document_id: "source-1" },
            working_revision: { parse_status: "pending" },
            task: { task_id: "task-1", state: "queued" },
        });
    });

    it("validates the bounded source file contract", () => {
        expect(validateSourceUploadFile(new File(["content"], "handbook.txt"))).toBeNull();
        expect(validateSourceUploadFile(new File(["content"], "handbook.exe"))).toContain("PDF");
        expect(validateSourceUploadFile(new File([], "empty.txt"))).toBe("材料文件不能为空。");
    });

    it("uploads in flow and reports the durable parsing state", async () => {
        const onCreated = renderForm();
        fireEvent.change(screen.getByLabelText("材料名称"), {
            target: { value: "新人销售基础手册" },
        });
        fireEvent.change(screen.getByLabelText("业务编码"), {
            target: { value: "foundation-handbook" },
        });
        const file = new File(["新人销售训练材料正文"], "handbook.txt", {
            type: "text/plain",
            lastModified: 1_721_177_600_000,
        });
        fireEvent.change(screen.getByLabelText("材料文件"), {
            target: { files: [file] },
        });
        fireEvent.click(screen.getByRole("button", { name: "上传并开始处理" }));

        await waitFor(() => expect(uploadSourceDocumentV2).toHaveBeenCalledTimes(1));
        const [formData, token] = uploadSourceDocumentV2.mock.calls[0] as [FormData, string];
        expect(formData.get("stable_key")).toBe("foundation-handbook");
        expect(formData.get("title")).toBe("新人销售基础手册");
        expect(formData.get("content_kind")).toBe("document");
        expect(formData.get("file")).toBe(file);
        expect(token).toEqual(expect.any(String));
        expect(onCreated).toHaveBeenCalledWith(
            "source-1",
            expect.stringContaining("进入后台解析"),
        );
    });
});
