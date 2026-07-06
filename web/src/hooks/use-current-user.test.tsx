import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import {
    ADMIN_CONSOLE_ROLE_VALUES,
    canUseAdminConsoleRole,
    hasRequiredRole,
    isPlatformAdminRole,
    normalizeCurrentUser,
    shouldStayInSalesTrainerAdmin,
    type CurrentUser,
} from "@/lib/auth/current-user";

import { useCurrentUser } from "./use-current-user";

const currentUser = {
    id: "user-1",
    user_id: "user-1",
    name: "王小明",
    display_name: "王小明",
    email: "learner@example.com",
    role: "user",
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
} as const satisfies CurrentUser;

function CurrentUserProbe() {
    const { data } = useCurrentUser(currentUser);

    return <span>{data?.display_name}</span>;
}

describe("useCurrentUser", () => {
    it("uses server-provided current user during SSR without requiring an app query provider", () => {
        expect(() => renderToString(<CurrentUserProbe />)).not.toThrow();
        expect(renderToString(<CurrentUserProbe />)).toContain("王小明");
    });

    it("preserves project-specific admin roles instead of coercing them to user", () => {
        const user = normalizeCurrentUser({
            id: "content-1",
            display_name: "内容管理员",
            role: "content_admin",
        });

        expect(user.role).toBe("content_admin");
    });

    it("uses one admin-console role vocabulary for platform, content, ops and auditors", () => {
        expect(ADMIN_CONSOLE_ROLE_VALUES).toEqual(expect.arrayContaining([
            "admin",
            "super_admin",
            "content_admin",
            "newcomer_content_admin",
            "ops",
            "operator",
            "operations",
            "sre",
            "readonly_auditor",
        ]));
        expect(isPlatformAdminRole(" Super_Admin ")).toBe(true);
        expect(canUseAdminConsoleRole(" SRE ")).toBe(true);
        expect(canUseAdminConsoleRole("readonly_auditor")).toBe(true);
        expect(shouldStayInSalesTrainerAdmin("ops")).toBe(true);
        expect(shouldStayInSalesTrainerAdmin("readonly_auditor")).toBe(false);
    });

    it("matches canonical required roles against compatible aliases", () => {
        expect(hasRequiredRole({ role: "super_admin" }, ["admin"])).toBe(true);
        expect(hasRequiredRole({ role: "newcomer_content_admin" }, ["content_admin"])).toBe(true);
        expect(hasRequiredRole({ role: "sre" }, ["operations"])).toBe(true);
        expect(hasRequiredRole({ role: "readonly_auditor" }, ["admin"])).toBe(false);
    });
});
