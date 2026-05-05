import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminGovernancePage from "./page";

const getGovernancePermissionsMatrixMock = vi.hoisted(() => vi.fn());
const getGovernanceSettingsBacklogMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getGovernancePermissionsMatrix: getGovernancePermissionsMatrixMock,
                getGovernanceSettingsBacklog: getGovernanceSettingsBacklogMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: {
        warn: vi.fn(),
    },
}));

describe("AdminGovernancePage", () => {
    beforeEach(() => {
        getGovernancePermissionsMatrixMock.mockResolvedValue({
            items: [
                {
                    route_family: "admin.api.users",
                    auth_surface: "Depends(get_current_admin_user)",
                    routes: ["GET /admin/users*"],
                    allowed_roles: ["admin"],
                    non_admin_deny_path: "common.auth.service.get_current_admin_user -> 403 [ROLE_REQUIRED]",
                    current_evidence: ["backend/src/admin/api/users.py"],
                    risk: "baseline",
                    priority: "baseline",
                    rationale: "positive control",
                },
            ],
            total: 1,
            fix_first_route_families: [],
            positive_control_route_families: ["admin.api.users"],
            support_log_redaction: {
                visible_fields: ["action", "status"],
                diagnostic_allowlist: ["trace_id"],
                backend_only_fields: ["token"],
                guidance: "redaction guidance",
                quality_event_prerequisite: "quality event prerequisite",
            },
        });
        getGovernanceSettingsBacklogMock.mockResolvedValue({
            items: [
                {
                    surface: "general",
                    label: "常规设置",
                    status: "read_only_backlog",
                    missing_capabilities: ["system settings persistence API"],
                    fallback_policy: "frontend remains read-only",
                },
            ],
            total: 1,
            policy: "governed settings only",
        });
    });

    it("renders permissions matrix and settings backlog from read-only governance APIs", async () => {
        render(<AdminGovernancePage />);

        expect(await screen.findByText("治理矩阵")).toBeTruthy();
        expect(screen.getByText("admin.api.users")).toBeTruthy();
        expect(screen.getByText(/positive control/)).toBeTruthy();
        expect(screen.getByText(/常规设置/)).toBeTruthy();
        expect(screen.getByText(/redaction guidance/)).toBeTruthy();
    });
});
