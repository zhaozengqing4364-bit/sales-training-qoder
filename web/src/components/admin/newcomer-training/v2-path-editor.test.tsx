import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FoundationV2PathEditor } from "./v2-path-editor";

const getPathWorkspace = vi.hoisted(() => vi.fn());
const savePathDraftV2 = vi.hoisted(() => vi.fn());
const push = vi.hoisted(() => vi.fn());

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => <a href={href} {...props}>{children}</a>,
}));
vi.mock("next/navigation", () => ({
    useRouter: () => ({ push }),
}));
vi.mock("@/components/ui/glass-modal", () => ({
    Dialog: ({ children, open }: { children: ReactNode; open: boolean }) => open ? <div>{children}</div> : null,
    DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogDescription: ({ children }: { children: ReactNode }) => <p>{children}</p>,
    DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
    DialogTitle: ({ children }: { children: ReactNode }) => <h2>{children}</h2>,
}));
vi.mock("@/components/admin/newcomer-training/workspace-nav", () => ({
    FoundationAdminCapabilityBoundary: ({ children }: { children: ReactNode }) => <>{children}</>,
}));
vi.mock("@/components/admin/newcomer-training/activity-resource-drawer", () => ({
    ActivityResourceDrawer: () => null,
}));
vi.mock("@/lib/api/client", () => ({
    api: {
        admin: {
            newcomerTraining: {
                getPathWorkspace,
                savePathDraftV2,
                validatePathV2: vi.fn(),
                previewRelease: vi.fn(),
                publishRelease: vi.fn(),
            },
        },
    },
    getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : "操作失败",
}));

const workspace = {
    path: {
        path_id: "path-1",
        stable_key: "foundation",
        title: "新人销售基础训练",
        status: "draft",
        working_revision_id: "revision-1",
        published_revision_id: null,
        active_release_plan_id: null,
        version: 2,
    },
    working_revision: {
        revision_id: "revision-1",
        revision_no: 1,
        revision_label: "初始草稿",
        status: "working",
        snapshot: {
            contract_version: "newcomer_training_path_v2",
            title: "新人销售基础训练",
            revision_label: "初始草稿",
            stages: [{
                stage_id: "stage-1",
                sequence: 1,
                title: "产品基础",
                objective: "掌握产品价值",
                entry_conditions: [],
                completion_rule: "all_required",
                visibility: "learner",
                activities: [{
                    activity_id: "lesson-1",
                    type: "lesson",
                    title: "产品学习",
                    objective: "理解产品",
                    why_it_matters: "支持客户沟通",
                    steps: ["学习"],
                    success_criteria: ["完成检查点"],
                    competency_keys: ["product_knowledge"],
                    estimated_minutes: 20,
                    required: true,
                    prerequisite_activity_ids: [],
                    ai_dependency: "none",
                    retry_policy: { max_attempts: 0, retry_interval_seconds: 0 },
                    config: { learning_unit_revision_id: "unit-1", required_checkpoint_ids: [] },
                }],
            }],
        },
        content_hash: "hash-1",
        version: 1,
        created_at: "2026-07-17T00:00:00Z",
        published_at: null,
    },
    published_revision: null,
    revision_history: [],
} as const;

describe("FoundationV2PathEditor", () => {
    beforeEach(() => {
        getPathWorkspace.mockReset();
        savePathDraftV2.mockReset();
        push.mockReset();
        getPathWorkspace.mockResolvedValue(workspace);
        savePathDraftV2.mockRejectedValue(new Error("路径版本已变化，请刷新后核对。"));
    });

    it("keeps dirty input when an optimistic concurrency save conflicts", async () => {
        const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
        render(<QueryClientProvider client={client}><FoundationV2PathEditor pathId="path-1" /></QueryClientProvider>);

        const title = await screen.findByLabelText("阶段名称");
        fireEvent.change(title, { target: { value: "产品基础与价值表达" } });
        expect(screen.getByText("有未保存修改")).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "保存草稿" }));

        expect((await screen.findByRole("alert")).textContent).toContain("路径版本已变化，请刷新后核对。");
        expect((screen.getByLabelText("阶段名称") as HTMLInputElement).value)
            .toBe("产品基础与价值表达");
        expect(savePathDraftV2).toHaveBeenCalledTimes(1);
    });

    it("uses an accessible confirmation dialog before abandoning dirty edits", async () => {
        const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
        render(<QueryClientProvider client={client}><FoundationV2PathEditor pathId="path-1" /></QueryClientProvider>);

        fireEvent.change(await screen.findByLabelText("阶段名称"), {
            target: { value: "尚未保存的新阶段名称" },
        });
        fireEvent.click(screen.getByRole("link", { name: "返回路径列表" }));

        expect(screen.getByRole("heading", { name: "离开路径编辑？" })).toBeTruthy();
        expect(push).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "放弃未保存修改并离开" }));
        expect(push).toHaveBeenCalledWith("/admin/newcomer-training/paths");
    });
});
