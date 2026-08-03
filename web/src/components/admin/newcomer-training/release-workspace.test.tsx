import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FoundationReleaseWorkspace } from "./release-workspace";

const listPaths = vi.hoisted(() => vi.fn());
const listReleasePlans = vi.hoisted(() => vi.fn());
const previewReleaseRollback = vi.hoisted(() => vi.fn());
const confirmReleaseRollback = vi.hoisted(() => vi.fn());

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
        <a href={href} {...props}>{children}</a>
    ),
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
                listPaths,
                listReleasePlans,
                previewReleaseRollback,
                confirmReleaseRollback,
            },
        },
    },
    getApiErrorMessage: (error: unknown) => error instanceof Error ? error.message : "操作失败",
}));

const releaseBase = {
    organization_id: "organization-1",
    path_id: "path-1",
    contract_hash: "contract-hash",
    dependency_graph: { acyclic: true, nodes: [], edges: [] },
    impact_hash: "impact-hash",
    created_by: "训练管理员",
    published_by: "训练管理员",
    rolled_back_by: null,
    created_at: "2026-07-17T08:00:00Z",
    published_at: "2026-07-17T08:05:00Z",
    rolled_back_at: null,
};

function renderWorkspace() {
    const client = new QueryClient({
        defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    return render(
        <QueryClientProvider client={client}>
            <FoundationReleaseWorkspace />
        </QueryClientProvider>,
    );
}

describe("FoundationReleaseWorkspace", () => {
    beforeEach(() => {
        listPaths.mockReset();
        listReleasePlans.mockReset();
        previewReleaseRollback.mockReset();
        confirmReleaseRollback.mockReset();
        listPaths.mockResolvedValue({
            items: [{
                path_id: "path-1",
                stable_key: "foundation-path",
                title: "新人销售基础训练",
                status: "published",
                working_revision_id: "revision-working",
                published_revision_id: "revision-active",
                active_release_plan_id: "plan-active",
                version: 5,
                updated_at: "2026-07-17T08:10:00Z",
            }],
        });
        listReleasePlans.mockResolvedValue({
            items: [
                {
                    ...releaseBase,
                    release_plan_id: "plan-failed",
                    path_revision_id: "revision-working",
                    previous_release_plan_id: "plan-active",
                    status: "failed",
                    version: 3,
                    target_revisions: [{}, {}, {}],
                    validation_report: {
                        valid: false,
                        issues: [{
                            code: "source_anchor_missing",
                            field: "stages.0.activities.0.config",
                            message: "学习内容缺少可追溯来源定位。",
                            severity: "blocker",
                        }],
                        publish_failure: {
                            code: "dependency_publish_failed",
                            message: "引用资源未能完成发布。",
                        },
                    },
                    impact_preview: {
                        active_enrollments_on_current_revision: 18,
                        active_attempts: 7,
                        automatic_migration: false,
                    },
                    reason: "补充产品知识训练",
                    published_by: null,
                    published_at: null,
                },
                {
                    ...releaseBase,
                    release_plan_id: "plan-active",
                    path_revision_id: "revision-active",
                    previous_release_plan_id: "plan-old",
                    status: "published",
                    version: 4,
                    target_revisions: [{}, {}],
                    validation_report: { valid: true, issues: [] },
                    impact_preview: { automatic_migration: false },
                    reason: "当前稳定版本",
                },
                {
                    ...releaseBase,
                    release_plan_id: "plan-old",
                    path_revision_id: "revision-old",
                    previous_release_plan_id: null,
                    status: "superseded",
                    version: 2,
                    target_revisions: [{}],
                    validation_report: { valid: true, issues: [] },
                    impact_preview: { automatic_migration: false },
                    reason: "首个稳定版本",
                },
            ],
        });
        previewReleaseRollback.mockResolvedValue({
            active_release_plan_id: "plan-active",
            target_release_plan_id: "plan-old",
            preview_token: "rollback-preview",
            impact_hash: "rollback-impact",
            impact: { active_enrollments_unchanged: true },
            expires_at: "2026-07-17T09:00:00Z",
        });
        confirmReleaseRollback.mockResolvedValue({
            ...releaseBase,
            release_plan_id: "plan-old",
            path_revision_id: "revision-old",
            previous_release_plan_id: null,
            status: "published",
            version: 3,
            target_revisions: [{}],
            validation_report: { valid: true, issues: [] },
            impact_preview: { automatic_migration: false },
            reason: "首个稳定版本",
        });
    });

    it("shows frozen release evidence and confirms rollback only after preview", async () => {
        renderWorkspace();

        expect(await screen.findByText("学习内容缺少可追溯来源定位。")).toBeTruthy();
        expect(screen.getByText("发布未完成，旧版本仍然有效")).toBeTruthy();
        expect(screen.getByText("18 人")).toBeTruthy();
        expect(screen.getByText("不会自动迁移")).toBeTruthy();
        expect(screen.queryByText(/Prompt/)).toBeNull();

        fireEvent.change(screen.getByLabelText("回滚目标"), {
            target: { value: "plan-old" },
        });
        fireEvent.click(screen.getByRole("button", { name: "预览回滚" }));
        fireEvent.change(screen.getByLabelText("回滚原因"), {
            target: { value: "新版本依赖异常，恢复已验证稳定版本" },
        });
        fireEvent.click(screen.getByRole("button", { name: "生成影响预览" }));

        expect(await screen.findByText("影响已锁定")).toBeTruthy();
        expect(previewReleaseRollback).toHaveBeenCalledWith(
            "plan-active",
            "plan-old",
            "新版本依赖异常，恢复已验证稳定版本",
        );

        fireEvent.click(screen.getByRole("button", { name: "确认恢复此稳定发布" }));

        expect((await screen.findByRole("status")).textContent).toContain("已恢复已知稳定发布");
        expect(confirmReleaseRollback).toHaveBeenCalledWith(
            "plan-active",
            expect.objectContaining({
                preview_token: "rollback-preview",
                impact_hash: "rollback-impact",
            }),
            4,
            expect.any(String),
        );
    });
});
