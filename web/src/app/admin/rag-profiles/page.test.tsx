import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RagProfilesPage from "./page";

const {
    pushMock,
    errorToastMock,
    successToastMock,
    listRagProfilesMock,
    deleteRagProfileMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    errorToastMock: vi.fn(),
    successToastMock: vi.fn(),
    listRagProfilesMock: vi.fn(),
    deleteRagProfileMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }) =>
        asChild ? <>{children}</> : <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => <div {...props}>{children}</div>,
}));

vi.mock("@/components/ui/input", () => ({
    Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: successToastMock,
        error: errorToastMock,
        showToast: vi.fn(),
    }),
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
    ConfirmDialog: ({ open, title, description, confirmText, onConfirm }: {
        open: boolean;
        title: string;
        description: string;
        confirmText?: string;
        onConfirm: () => void;
    }) => (
        open ? (
            <div>
                <div>{title}</div>
                <div>{description}</div>
                <button type="button" onClick={onConfirm}>{confirmText ?? "确认"}</button>
            </div>
        ) : null
    ),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                listRagProfiles: listRagProfilesMock,
                deleteRagProfile: deleteRagProfileMock,
            },
        },
    };
});

describe("RagProfilesPage", () => {
    beforeEach(() => {
        pushMock.mockReset();
        errorToastMock.mockReset();
        successToastMock.mockReset();
        listRagProfilesMock.mockReset();
        deleteRagProfileMock.mockReset();

        listRagProfilesMock.mockResolvedValue([
            {
                id: "profile-1",
                name: "标准检索配置",
                description: "默认配置",
                chunking: {
                    strategy: "element_boundary",
                    chunk_size: 500,
                    chunk_overlap: 50,
                },
                semantic_cache: {
                    enabled: true,
                    similarity_threshold: 0.95,
                    ttl_seconds: 300,
                },
                cross_encoder: {
                    backend: null,
                    model: null,
                    device: null,
                    has_api_key: false,
                },
                is_system_default: false,
                applied_kb_count: 2,
            },
        ]);
    });

    it("uses router push for the deprecation handoff instead of a hard anchor navigation", async () => {
        render(<RagProfilesPage />);

        await waitFor(() => {
            expect(listRagProfilesMock).toHaveBeenCalled();
        });

        fireEvent.click(screen.getByRole("button", { name: "前往检索策略页面" }));

        expect(pushMock).toHaveBeenCalledWith("/admin/retrieval-strategies");
    });

    it("distinguishes API failure from an empty profile list", async () => {
        listRagProfilesMock.mockRejectedValueOnce(new Error("backend unavailable"));

        render(<RagProfilesPage />);

        expect(await screen.findByText("RAG 配置加载失败")).toBeTruthy();
        expect(screen.getByText(/backend unavailable/)).toBeTruthy();
        expect(screen.queryByText("暂无 RAG 配置")).toBeNull();
    });

    it("confirms destructive deletion through the shared dialog seam", async () => {
        deleteRagProfileMock.mockResolvedValue(undefined);

        render(<RagProfilesPage />);

        await waitFor(() => {
            expect(listRagProfilesMock).toHaveBeenCalled();
        });

        fireEvent.click(screen.getByRole("button", { name: "删除配置 标准检索配置" }));

        expect(screen.getByText("删除 RAG 配置")).toBeTruthy();
        fireEvent.click(screen.getByRole("button", { name: "删除" }));

        await waitFor(() => {
            expect(deleteRagProfileMock).toHaveBeenCalledWith("profile-1");
        });
        expect(successToastMock).toHaveBeenCalledWith("删除成功");
    });

    it("shows API failure guidance instead of pretending the list is empty", async () => {
        listRagProfilesMock.mockRejectedValue(new Error("api down"));

        render(<RagProfilesPage />);

        await waitFor(() => {
            expect(errorToastMock).toHaveBeenCalledWith("加载失败：api down");
        });

        expect(screen.getByText("RAG 配置接口加载失败")).toBeTruthy();
        expect(screen.getByText(/请检查管理员权限、后端/)).toBeTruthy();
        expect(screen.queryByText("暂无 RAG 配置")).toBeNull();
    });
});
