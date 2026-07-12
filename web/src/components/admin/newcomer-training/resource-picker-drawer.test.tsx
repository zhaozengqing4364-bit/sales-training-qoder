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

        await user.type(screen.getByLabelText("试卷名称"), "产品 A 小测");
        await user.type(screen.getByLabelText("题目编号"), "question-1, question-2");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));

        expect(createResource).toHaveBeenCalledWith(expect.objectContaining({ title: "产品 A 小测", question_ids: ["question-1", "question-2"] }));
        expect(onCreated).toHaveBeenCalledWith(expect.objectContaining({ title: "产品 A 小测" }));
    });

    it("does not publish placeholder learning content", async () => {
        const user = userEvent.setup();
        const createResource = vi.fn();
        render(<ResourcePickerDrawer kind="learning_content" open onOpenChange={vi.fn()} onCreated={vi.fn()} createResource={createResource} />);
        await user.type(screen.getByLabelText("内容名称"), "产品基础");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));
        expect(screen.getByRole("alert").textContent).toContain("首章节内容不能为空");
        expect(createResource).not.toHaveBeenCalled();
    });

    it("requires an explicit question selection", async () => {
        const user = userEvent.setup();
        const createResource = vi.fn();
        render(<ResourcePickerDrawer kind="exam_paper" open onOpenChange={vi.fn()} onCreated={vi.fn()} createResource={createResource} />);
        await user.type(screen.getByLabelText("试卷名称"), "产品测验");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));
        expect(screen.getByRole("alert").textContent).toContain("至少填写一道题目编号");
        expect(createResource).not.toHaveBeenCalled();
    });

    it("keeps server errors inside the drawer and allows retry", async () => {
        const user = userEvent.setup();
        const createResource = vi.fn().mockRejectedValue(new Error("试卷至少需要一道已发布题目"));
        render(<ResourcePickerDrawer kind="exam_paper" open onOpenChange={vi.fn()} onCreated={vi.fn()} createResource={createResource} />);
        await user.type(screen.getByLabelText("试卷名称"), "空试卷");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));
        expect(await screen.findByRole("alert")).toBeTruthy();
        expect(screen.getByRole("button", { name: "创建并绑定" })).toBeTruthy();
    });
});
