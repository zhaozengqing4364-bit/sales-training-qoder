import { renderToString } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { CurrentUser } from "@/lib/auth/current-user";

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
});
