import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerReadinessWorkbenchPage from "./page";

const { getReadinessWorkbenchMock } = vi.hoisted(() => ({
    getReadinessWorkbenchMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => (
        <a href={href}>{children}</a>
    ),
}));

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/readiness",
}));

vi.mock("@/components/admin/admin-layout-shells", () => ({
    AdminIndexShell: ({ header, children }: { header: ReactNode; children: ReactNode }) => (
        <div>
            {header}
            {children}
        </div>
    ),
    AdminPageHeader: ({
        title,
        description,
        primaryAction,
        secondaryActions,
    }: {
        title: string;
        description: string;
        primaryAction?: ReactNode;
        secondaryActions?: ReactNode;
    }) => (
        <header>
            <h1>{title}</h1>
            <p>{description}</p>
            {primaryAction}
            {secondaryActions}
        </header>
    ),
}));

vi.mock("@/components/admin/sales-trainer/admin-load-error-card", () => ({
    AdminLoadErrorCard: ({ title, message }: { title: string; message?: string | null }) => (
        <div>
            {title}
            {message}
        </div>
    ),
}));

vi.mock("@/components/admin/sales-trainer/module-nav", () => ({
    SalesTrainerAdminModuleNav: () => <nav>训练配置导航</nav>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => (
        <div className={className}>{children}</div>
    ),
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/lib/sales-trainer/use-admin-route-access", () => ({
    useSalesTrainerAdminRouteAccess: () => ({
        canAccess: true,
        capabilities: {
            view_records: true,
            view_global_records: true,
        },
        denialMessage: null,
        isLoading: false,
        reloadCapabilities: vi.fn(),
    }),
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
                    getReadinessWorkbench: getReadinessWorkbenchMock,
                },
            },
        },
    };
});

function emptyGroup(groupKey: string, label: string) {
    return {
        group_key: groupKey,
        label,
        count: 0,
        items: [],
    };
}

function workbenchFixture() {
    return {
        contract_version: "readiness_dossier_v1",
        generated_at: "2026-07-06T09:20:00Z",
        summary: {
            learner_count: 1,
            loaded_learner_count: 1,
            pending_review_count: 0,
            not_passed_count: 0,
            needs_retraining_count: 0,
            approved_count: 0,
            config_exception_count: 1,
            in_training_count: 0,
        },
        filters: {
            department: null,
            limit: 20,
            offset: 0,
        },
        groups: {
            pending_review: emptyGroup("pending_review", "待复核"),
            not_passed: emptyGroup("not_passed", "未达标"),
            needs_retraining: emptyGroup("needs_retraining", "需重练"),
            approved: emptyGroup("approved", "已达标"),
            in_training: emptyGroup("in_training", "训练中"),
            config_exception: {
                group_key: "config_exception",
                label: "配置异常",
                count: 1,
                items: [
                    {
                        learner: {
                            learner_id: "learner-1",
                            name: "张三",
                            department: "销售一部",
                        },
                        status: "blocked_by_config",
                        status_label: "配置异常",
                        status_reason:
                            "active path revision 中该模块缺少受治理的 runtime binding。",
                        path: {
                            path_key: "newcomer_training_path_v1",
                            path_revision_id: null,
                            path_revision_no: null,
                            source: "active_revision",
                        },
                        weak_capability_keys: [],
                        weak_capability_labels: [],
                        evidence_count: 0,
                        latest_review_action: null,
                        next_action: {
                            action_key: "fix_configuration",
                            label: "修复训练配置",
                            target_path: "/admin/sales-trainer/paths",
                            primary: true,
                            capability_keys: [],
                        },
                        target_path: "/admin/sales-trainer/paths",
                    },
                ],
            },
        },
    };
}

describe("SalesTrainerReadinessWorkbenchPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getReadinessWorkbenchMock.mockResolvedValue(workbenchFixture());
    });

    it("renders config exceptions in user language without raw diagnostic terms", async () => {
        render(<SalesTrainerReadinessWorkbenchPage />);

        await waitFor(() => {
            expect(getReadinessWorkbenchMock).toHaveBeenCalledWith({ limit: 20 });
        });

        expect(screen.getByText("达标验收工作台")).toBeTruthy();
        expect(screen.getByText("张三")).toBeTruthy();
        expect(
            screen.getByText("真实语音对练后台接入配置缺失，请先处理训练路径配置。"),
        ).toBeTruthy();
        expect(screen.queryByText(/runtime binding/)).toBeNull();
        expect(screen.queryByText(/active path revision/)).toBeNull();
    });
});
