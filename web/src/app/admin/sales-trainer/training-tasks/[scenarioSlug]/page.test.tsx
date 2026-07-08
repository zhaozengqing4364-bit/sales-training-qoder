import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerTrainingTaskDetailPage from "./page";

const { routeAccessMock, workflowMock } = vi.hoisted(() => ({
    routeAccessMock: vi.fn(),
    workflowMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    useParams: () => ({ scenarioSlug: "company-product-demo" }),
    usePathname: () => "/admin/sales-trainer/training-tasks/company-product-demo",
    useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/components/admin/admin-layout-shells", () => ({
    AdminIndexShell: ({ children, header }: { children: ReactNode; header: ReactNode }) => (
        <div>
            {header}
            {children}
        </div>
    ),
    AdminPageHeader: ({ title, description, secondaryActions }: {
        title: string;
        description: string;
        secondaryActions?: ReactNode;
    }) => (
        <header>
            <h1>{title}</h1>
            <p>{description}</p>
            {secondaryActions}
        </header>
    ),
}));

vi.mock("@/components/admin/sales-trainer/admin-load-error-card", () => ({
    AdminLoadErrorCard: ({ title, message }: { title: string; message: string }) => (
        <div role="alert">
            <h2>{title}</h2>
            <p>{message}</p>
        </div>
    ),
}));

vi.mock("@/components/admin/sales-trainer/module-nav", () => ({
    SalesTrainerAdminModuleNav: () => <nav aria-label="训练任务模块内导航" />,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <article>{children}</article>,
}));

vi.mock("@/lib/sales-trainer/use-admin-route-access", () => ({
    useSalesTrainerAdminRouteAccess: () => routeAccessMock(),
}));

vi.mock("../../paths/use-path-config-center-workflow", () => ({
    usePathConfigCenterWorkflow: () => workflowMock(),
}));

function workflowValue() {
    return {
        actionMessage: null,
        changeReason: "",
        data: {
            pathConfig: {
                path: {
                    modules: [
                        {
                            module_key: "company_product_demo",
                            module_type: "audio_scoring",
                            scenario_key: "company_product_demo",
                            target_unit_id: "demo-unit",
                            material_id: "material-1",
                            material_version_id: "version-1",
                            scoring_prompt_id: "prompt-1",
                        },
                    ],
                },
            },
            units: [
                {
                    unit_id: "demo-unit",
                    name: "Demo 训练单元",
                    unit_type: "audio_scoring",
                    status: "published",
                    config: {
                        audio: {
                            purpose: "company_product_demo",
                            scenario_key: "company_product_demo",
                        },
                    },
                },
                {
                    unit_id: "ppt-unit",
                    name: "PPT 训练单元",
                    unit_type: "audio_scoring",
                    status: "published",
                    config: { audio: { purpose: "ppt_pitch" } },
                },
            ],
            materials: [
                {
                    material_id: "material-1",
                    name: "产品资料",
                    status: "published",
                    current_version_id: "version-1",
                    current_version: { version_label: "v1" },
                },
            ],
            scorePrompts: [
                {
                    prompt_id: "prompt-1",
                    name: "Demo 评测标准",
                    version: 1,
                    status: "published",
                },
            ],
        },
        error: null,
        isLoading: false,
        isMutating: false,
        load: vi.fn(),
        model: { modules: [{ moduleKey: "company_product_demo", issues: [] }] },
        publishWorkingRevision: vi.fn(),
        saveCurrentRevision: vi.fn(),
        setChangeReason: vi.fn(),
        updateAudioScenario: vi.fn(),
    };
}

describe("SalesTrainerTrainingTaskDetailPage", () => {
    beforeEach(() => {
        routeAccessMock.mockReset();
        workflowMock.mockReset();
        routeAccessMock.mockReturnValue({
            capabilities: null,
            canAccess: true,
            denialMessage: null,
            error: null,
            isLoading: false,
            reloadCapabilities: vi.fn(),
        });
        workflowMock.mockReturnValue(workflowValue());
    });

    it("filters candidate units by the current audio evaluation scenario", () => {
        render(<SalesTrainerTrainingTaskDetailPage />);

        expect(screen.getAllByRole("heading", { name: "公司产品 Demo" }).length).toBeGreaterThan(0);
        expect(screen.getByRole("option", { name: "Demo 训练单元" })).toBeTruthy();
        expect(screen.queryByRole("option", { name: "PPT 训练单元" })).toBeNull();
    });

    it("does not put internal keys into quick-create URLs", () => {
        render(<SalesTrainerTrainingTaskDetailPage />);

        const hrefs = screen.getAllByRole("link").map((link) => link.getAttribute("href") ?? "");
        expect(hrefs).toContain("/admin/sales-trainer/units/new?scenario=company-product-demo");
        expect(hrefs).toContain("/admin/sales-trainer/materials?scenario=company-product-demo");
        expect(hrefs).toContain("/admin/sales-trainer/score-standards/new?scenario=company-product-demo");
        expect(hrefs.join("\n")).not.toContain("company_product_demo");
        expect(hrefs.join("\n")).not.toContain("ppt_pitch");
        expect(hrefs.join("\n")).not.toContain("module_key");
    });

    it("hides stale configuration data when permissions are denied", () => {
        routeAccessMock.mockReturnValueOnce({
            capabilities: null,
            canAccess: false,
            denialMessage: "当前账号无权访问该新人训练管理页面。",
            error: null,
            isLoading: false,
            reloadCapabilities: vi.fn(),
        });

        render(<SalesTrainerTrainingTaskDetailPage />);

        expect(screen.getByRole("alert").textContent).toContain("训练任务不可访问");
        expect(screen.queryByText("任务绑定")).toBeNull();
        expect(screen.queryByRole("button", { name: "保存待发布修订" })).toBeNull();
    });
});
