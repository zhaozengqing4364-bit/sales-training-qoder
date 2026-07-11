import { describe, expect, it } from "vitest";

import {
    SALES_TRAINER_ADMIN_NAV_ITEMS,
    filterSalesTrainerAdminRouteItemsForCapabilities,
    getSalesTrainerAdminContextNavGroup,
    getSalesTrainerAdminContextNavGroupForCapabilities,
    isSalesTrainerAdminPathAllowedForCapabilities,
    salesTrainerAdminItemsForCapabilities,
} from "./routes";
import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";

function capabilities(
    overrides: Partial<SalesTrainerAdminCapabilities["capabilities"]>,
    role = "support",
): SalesTrainerAdminCapabilities {
    const values = {
        admin_full_access: false,
        manage_content: false,
        manage_questions: false,
        manage_modules: false,
        manage_prompts: false,
        view_records: false,
        view_global_records: false,
        retry_jobs: false,
        regrade_history: false,
        view_logs: false,
        view_settings: false,
        ...overrides,
    };
    return {
        role,
        role_label: "培训负责人",
        capabilities: values,
        capability_keys: Object.entries(values)
            .filter(([, enabled]) => enabled)
            .map(([key]) => key as SalesTrainerAdminCapabilities["capability_keys"][number]),
    };
}

describe("sales trainer admin routes", () => {
    it("returns every admin route for full access", () => {
        const items = salesTrainerAdminItemsForCapabilities(
            capabilities({ admin_full_access: true }),
        );

        expect(items.map((item) => item.href)).toEqual(
            SALES_TRAINER_ADMIN_NAV_ITEMS.map((item) => item.href),
        );
    });

    it("deduplicates capability-derived navigation entries", () => {
        const items = salesTrainerAdminItemsForCapabilities(
            capabilities({ manage_content: true, manage_prompts: true }),
        );

        expect(items.filter((item) => item.href === "/admin/sales-trainer/audio")).toHaveLength(1);
    });

    it("groups AI coach under path configuration context nav", () => {
        const group = getSalesTrainerAdminContextNavGroup("/admin/sales-trainer/ai-coach");

        expect(group.label).toBe("路径与达标");
        expect(group.items.map((item) => item.href)).toEqual([
            "/admin/sales-trainer/paths",
            "/admin/sales-trainer/units",
            "/admin/sales-trainer/ai-coach",
            "/admin/sales-trainer/readiness",
            "/admin/sales-trainer/training-records",
            "/admin/sales-trainer/analytics",
        ]);
    });

    it("filters context navigation by the same sales trainer capabilities", () => {
        const group = getSalesTrainerAdminContextNavGroupForCapabilities(
            "/admin/sales-trainer/ai-coach",
            capabilities({ manage_modules: true }),
        );

        expect(group.items.map((item) => item.href)).toEqual([
            "/admin/sales-trainer/paths",
            "/admin/sales-trainer/units",
            "/admin/sales-trainer/ai-coach",
        ]);
    });

    it("allows nested learning topic routes when the parent route is capability-visible", () => {
        const items = filterSalesTrainerAdminRouteItemsForCapabilities(
            [
                {
                    key: "learningTopicImport",
                    href: "/admin/sales-trainer/learning-topics/import",
                    label: "资料导入",
                    icon: SALES_TRAINER_ADMIN_NAV_ITEMS[0].icon,
                },
                {
                    key: "settings",
                    href: "/admin/sales-trainer/settings",
                    label: "配置",
                    icon: SALES_TRAINER_ADMIN_NAV_ITEMS[0].icon,
                },
            ],
            capabilities({ manage_content: true }),
        );

        expect(items.map((item) => item.href)).toEqual([
            "/admin/sales-trainer/learning-topics/import",
        ]);
    });

    it("checks nested page access from the same capability map", () => {
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/questions/new",
            capabilities({ manage_questions: true }),
        )).toBe(true);
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/questions/new",
            capabilities({ manage_content: true }),
        )).toBe(false);
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer",
            capabilities({ manage_questions: true }),
        )).toBe(false);
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/papers",
            capabilities({ manage_questions: true }),
        )).toBe(false);
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/learning-topics/papers",
            capabilities({ manage_questions: true }),
        )).toBe(false);
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/learning-topics/papers",
            capabilities({ manage_content: true }),
        )).toBe(true);
    });

    it("allows Journey Analytics through the records capability", () => {
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/analytics",
            capabilities({ view_records: true }),
        )).toBe(true);
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/analytics",
            capabilities({ manage_content: true }),
        )).toBe(false);
    });

    it("allows hidden quiz attempt detail routes through the records capability", () => {
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/quiz-attempts/attempt-1",
            capabilities({ view_records: true }),
        )).toBe(true);
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/quiz-attempts/attempt-1",
            capabilities({ manage_questions: true }),
        )).toBe(false);
        expect(salesTrainerAdminItemsForCapabilities(
            capabilities({ view_records: true }),
        ).some((item) => item.href === "/admin/sales-trainer/quiz-attempts")).toBe(false);
    });

    it("keeps route authorization based on capability projection instead of role labels", () => {
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/operation-logs",
            capabilities({ view_logs: true }, "readonly_auditor"),
        )).toBe(true);
        expect(isSalesTrainerAdminPathAllowedForCapabilities(
            "/admin/sales-trainer/operation-logs",
            capabilities({}, "readonly_auditor"),
        )).toBe(false);
    });
});
