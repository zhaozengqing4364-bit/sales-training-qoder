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
            department: "销售部",
        });

        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/admin/users/u1"),
            expect.objectContaining({
                method: "PUT",
                body: JSON.stringify({
                    name: "张三",
                    email: "zhang@example.com",
                    department: "销售部",
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
});
