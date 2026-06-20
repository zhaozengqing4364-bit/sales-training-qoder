import { describe, expect, it } from "vitest";

import {
    SALES_TRAINER_ADMIN_NAV_ITEMS,
    getSalesTrainerAdminContextNavGroup,
    salesTrainerAdminItemsForCapabilities,
} from "./routes";
import type { SalesTrainerAdminCapabilities } from "@/lib/api/types";

function capabilities(
    overrides: Partial<SalesTrainerAdminCapabilities["capabilities"]>,
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
        role: "support",
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

        expect(items.filter((item) => item.href === "/admin/sales-trainer/ai-coach")).toHaveLength(1);
    });

    it("groups AI coach under path configuration context nav", () => {
        const group = getSalesTrainerAdminContextNavGroup("/admin/sales-trainer/ai-coach");

        expect(group.label).toBe("路径配置");
        expect(group.items.map((item) => item.href)).toEqual([
            "/admin/sales-trainer/paths",
            "/admin/sales-trainer/ai-coach",
        ]);
    });
});
