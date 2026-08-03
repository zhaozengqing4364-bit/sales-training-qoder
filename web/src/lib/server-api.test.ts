import { beforeEach, describe, expect, it, vi } from "vitest";

const { fetchMock, headersMock } = vi.hoisted(() => ({
    fetchMock: vi.fn(),
    headersMock: vi.fn(),
}));

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({ headers: headersMock }));

import { ServerApiError, serverApiGet } from "./server-api";

describe("serverApiGet", () => {
    beforeEach(() => {
        fetchMock.mockReset();
        headersMock.mockReset();
        headersMock.mockResolvedValue(new Headers({
            cookie: "session=synthetic",
            "x-trace-id": "0123456789abcdef0123456789abcdef",
        }));
        vi.stubGlobal("fetch", fetchMock);
    });

    it("unwraps the API envelope and forwards the server cookie and trace", async () => {
        fetchMock.mockResolvedValue({
            ok: true,
            status: 200,
            json: async () => ({ data: { learner_id: "learner-1" } }),
        });

        await expect(serverApiGet<{ learner_id: string }>("/newcomer-training/journey"))
            .resolves.toEqual({ learner_id: "learner-1" });

        const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
        expect(url).toBe("http://localhost:3444/api/v1/newcomer-training/journey");
        expect(options.cache).toBe("no-store");
        expect(new Headers(options.headers).get("cookie")).toBe("session=synthetic");
        expect(new Headers(options.headers).get("x-trace-id"))
            .toBe("0123456789abcdef0123456789abcdef");
    });

    it("throws a typed status error without exposing a response body", async () => {
        fetchMock.mockResolvedValue({
            ok: false,
            status: 403,
            json: async () => ({ detail: "private" }),
        });

        await expect(serverApiGet("/newcomer-training/journey"))
            .rejects.toEqual(expect.objectContaining<Partial<ServerApiError>>({
                name: "ServerApiError",
                status: 403,
            }));
    });
});
