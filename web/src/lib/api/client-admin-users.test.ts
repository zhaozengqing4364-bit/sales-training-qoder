import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

const fetchMock = vi.fn();

describe("admin users api client", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        fetchMock.mockResolvedValue({
            ok: true,
            status: 200,
            headers: new Headers({ "content-type": "application/json" }),
            json: async () => ({ success: true, data: { id: "u1" } }),
        });
        vi.stubGlobal("fetch", fetchMock);
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("updates user profile with PUT and profile-only payload", async () => {
        await api.admin.updateUser("u1", {
            name: "张三",
            email: "zhang@example.com",
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/users/u1"),
            expect.objectContaining({
                method: "PUT",
                body: JSON.stringify({
                    name: "张三",
                    email: "zhang@example.com",
                }),
            }),
        );
    });

    it("updates user role through the dedicated role endpoint", async () => {
        await api.admin.updateUserRole("u1", { role: "admin" });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/users/u1/role"),
            expect.objectContaining({
                method: "PUT",
                body: JSON.stringify({ role: "admin" }),
            }),
        );
    });

    it("sends an audited, version-aware account suspension request", async () => {
        await api.admin.suspendUser("u1", {
            audit_reason: "员工离职",
            expected_credential_version: 3,
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/users/u1/suspend"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    audit_reason: "员工离职",
                    expected_credential_version: 3,
                }),
                signal: expect.any(AbortSignal),
            }),
        );
    });

    it("loads the authoritative user state for response-loss recovery", async () => {
        await api.admin.getUser("u1");

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/users/u1"),
            expect.objectContaining({ signal: expect.any(AbortSignal) }),
        );
    });

    it("sends an audited password reset with a bounded request signal", async () => {
        await api.admin.resetTemporaryPassword("u1", {
            audit_reason: "用户无法找回密码",
            expected_credential_version: 4,
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/users/u1/reset-temporary-password"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    audit_reason: "用户无法找回密码",
                    expected_credential_version: 4,
                }),
                signal: expect.any(AbortSignal),
            }),
        );
    });

    it("assigns a learner through the explicit team relationship endpoint", async () => {
        await api.admin.assignTeamMember("team/1", "learner-1");

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/teams/team%2F1/members"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({ learner_user_id: "learner-1" }),
            }),
        );
    });

    it("assigns a primary leader through the explicit team relationship endpoint", async () => {
        await api.admin.assignTeamLeader("team-1", {
            leader_user_id: "leader-1",
            assignment_role: "primary",
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/teams/team-1/leaders"),
            expect.objectContaining({
                method: "POST",
                body: JSON.stringify({
                    leader_user_id: "leader-1",
                    assignment_role: "primary",
                }),
            }),
        );
    });
});
