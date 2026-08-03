import { describe, expect, it } from "vitest";

import { ApiRequestError } from "@/lib/api/client";
import { getFoundationUserErrorMessage } from "./errors";

describe("getFoundationUserErrorMessage", () => {
    it("keeps the business recovery message but hides the request correlation id", () => {
        const error = new ApiRequestError({
            status: 409,
            errorCode: "[ACTIVITY_BLOCKED]",
            message: "请先完成上一项训练。",
            traceId: "trace-private-1",
        });

        expect(getFoundationUserErrorMessage(error)).toBe("请先完成上一项训练。");
    });
});
