import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./confirm-dialog";

describe("ConfirmDialog", () => {
    it("keeps cancellation available when only confirmation is invalid", () => {
        render(
            <ConfirmDialog
                open
                onOpenChange={vi.fn()}
                title="停用账户"
                description="需要填写原因"
                confirmText="确认停用"
                confirmDisabled
                onConfirm={vi.fn()}
            />,
        );

        expect(screen.getByRole("button", { name: "取消" }).hasAttribute("disabled")).toBe(false);
        expect(screen.getByRole("button", { name: "确认停用" }).hasAttribute("disabled")).toBe(true);
    });
});
