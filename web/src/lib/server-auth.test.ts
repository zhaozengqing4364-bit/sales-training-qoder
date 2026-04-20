import { beforeEach, describe, expect, it, vi } from "vitest";

const headersMock = vi.fn();
const redirectMock = vi.fn((path: string) => {
    throw new Error(`redirect:${path}`);
});

vi.mock("next/headers", () => ({
    headers: headersMock,
}));

vi.mock("next/navigation", () => ({
    redirect: redirectMock,
}));

describe("server auth boundary", () => {
    beforeEach(() => {
        vi.resetModules();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
        headersMock.mockReset();
        redirectMock.mockClear();
    });

    it("forwards the incoming cookie header when fetching the current user", async () => {
        headersMock.mockResolvedValue(
            new Headers({
                cookie: "session=abc123",
            }),
        );

        const fetchMock = vi.fn().mockResolvedValue(
            new Response(
                JSON.stringify({
                    success: true,
                    data: {
                        id: "user-1",
                        display_name: "管理员",
                        email: "admin@test.com",
                        role: "admin",
                    },
                }),
                {
                    status: 200,
                    headers: { "Content-Type": "application/json" },
                },
            ),
        );
        vi.stubGlobal("fetch", fetchMock);

        const { getServerSessionUser } = await import("./server-auth");

        const user = await getServerSessionUser();

        expect(user).toMatchObject({
            id: "user-1",
            role: "admin",
        });
        expect(fetchMock).toHaveBeenCalledWith(
            expect.stringContaining("/api/v1/users/me"),
            expect.objectContaining({
                cache: "no-store",
                credentials: "include",
                headers: expect.objectContaining({
                    cookie: "session=abc123",
                }),
            }),
        );
    });

    it("redirects to login when the server session is missing", async () => {
        headersMock.mockResolvedValue(new Headers());

        const { requireServerSession } = await import("./server-auth");

        await expect(requireServerSession()).rejects.toThrow("redirect:/login");
        expect(redirectMock).toHaveBeenCalledWith("/login");
    });

    it("redirects non-admin users away from admin routes", async () => {
        headersMock.mockResolvedValue(
            new Headers({
                cookie: "session=user-cookie",
            }),
        );

        vi.stubGlobal(
            "fetch",
            vi.fn().mockResolvedValue(
                new Response(
                    JSON.stringify({
                        success: true,
                        data: {
                            id: "user-2",
                            display_name: "普通用户",
                            email: "user@test.com",
                            role: "user",
                        },
                    }),
                    {
                        status: 200,
                        headers: { "Content-Type": "application/json" },
                    },
                ),
            ),
        );

        const { requireServerSession } = await import("./server-auth");

        await expect(
            requireServerSession({ requiredRoles: ["admin"], unauthorizedRedirectTo: "/" }),
        ).rejects.toThrow("redirect:/");
        expect(redirectMock).toHaveBeenCalledWith("/");
    });
});
