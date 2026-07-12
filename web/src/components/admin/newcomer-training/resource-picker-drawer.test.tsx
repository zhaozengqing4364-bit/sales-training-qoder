import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ResourcePickerDrawer } from "./resource-picker-drawer";

describe("ResourcePickerDrawer", () => {
    it("creates a missing paper in flow and binds it", async () => {
        const user = userEvent.setup();
        const onCreated = vi.fn();
        const createResource = vi.fn().mockResolvedValue({ id: "paper-new", title: "产品 A 小测", status: "published" });
        render(<ResourcePickerDrawer kind="exam_paper" open onOpenChange={vi.fn()} onCreated={onCreated} createResource={createResource} />);

        await user.click(screen.getByRole("button", { name: "快速组卷" }));
        await user.type(screen.getByLabelText("试卷名称"), "产品 A 小测");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));

        expect(createResource).toHaveBeenCalledWith(expect.objectContaining({ title: "产品 A 小测" }));
        expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ title: "产品 A 小测" }));
    });

    it("keeps server errors inside the drawer and allows retry", async () => {
        const user = userEvent.setup();
        const createResource = vi.fn().mockRejectedValue(new Error("试卷至少需要一道已发布题目"));
        render(<ResourcePickerDrawer kind="exam_paper" open onOpenChange={vi.fn()} onCreated={vi.fn()} createResource={createResource} />);
        await user.click(screen.getByRole("button", { name: "快速组卷" }));
        await user.type(screen.getByLabelText("试卷名称"), "空试卷");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));
        expect(await screen.findByRole("alert")).toBeTruthy();
        expect(screen.getByRole("button", { name: "创建并绑定" })).toBeTruthy();
    });
});
