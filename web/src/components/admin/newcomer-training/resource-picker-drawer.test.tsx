import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api/client";
import { ResourcePickerDrawer } from "./resource-picker-drawer";

function createPopupStub() {
    const replace = vi.fn();
    const close = vi.fn();
    return {
        popup: {
            opener: null,
            closed: false,
            close,
            location: { replace },
        } as unknown as Window,
        close,
        replace,
    };
}

describe("ResourcePickerDrawer", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

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

    it("makes material upload explicit and blocks an empty upload", async () => {
        const user = userEvent.setup();
        const createResource = vi.fn();
        render(<ResourcePickerDrawer kind="material" open onOpenChange={vi.fn()} onCreated={vi.fn()} createResource={createResource} />);

        expect(screen.getByRole("heading", { name: "上传讲解材料" })).toBeTruthy();
        expect(screen.getByLabelText("材料文件")).toBeTruthy();
        await user.type(screen.getByLabelText("材料名称"), "产品方案 PPT");
        await user.click(screen.getByRole("button", { name: "上传并绑定" }));

        expect(screen.getByRole("alert").textContent).toContain("请选择要上传的材料文件");
        expect(createResource).not.toHaveBeenCalled();
    });

    it("guides file selection and shows the selected material before upload", async () => {
        const user = userEvent.setup();
        render(<ResourcePickerDrawer kind="material" open onOpenChange={vi.fn()} onCreated={vi.fn()} createResource={vi.fn()} />);
        const file = new File(
            [new Uint8Array(2 * 1024)],
            "产品方案.pptx",
            { type: "application/vnd.openxmlformats-officedocument.presentationml.presentation" },
        );

        expect(screen.getByText("选择要上传的讲解材料")).toBeTruthy();
        expect(screen.getByText(/支持 PPT、PPTX、PDF、Word/)).toBeTruthy();
        await user.upload(screen.getByLabelText("材料文件"), file);

        expect(screen.getByText("已选择文件")).toBeTruthy();
        expect(screen.getByText("产品方案.pptx")).toBeTruthy();
        expect(screen.getByText(/2\.0 KB · 点击可重新选择/)).toBeTruthy();
    });

    it("uploads the selected material and returns it for in-flow binding", async () => {
        const user = userEvent.setup();
        const onCreated = vi.fn();
        const onOpenChange = vi.fn();
        const createdMaterial = { id: "material-new", title: "产品方案 PPT", status: "published" };
        const createResource = vi.fn().mockResolvedValue(createdMaterial);
        render(<ResourcePickerDrawer kind="material" open onOpenChange={onOpenChange} onCreated={onCreated} createResource={createResource} />);
        const file = new File(["content"], "产品方案.pptx", {
            type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        });

        await user.upload(screen.getByLabelText("材料文件"), file);
        await user.type(screen.getByLabelText("材料名称"), "产品方案 PPT");
        await user.click(screen.getByRole("button", { name: "上传并绑定" }));

        await waitFor(() => expect(createResource).toHaveBeenCalledWith(expect.objectContaining({ file, title: "产品方案 PPT" })));
        expect(onCreated).toHaveBeenCalledWith(createdMaterial);
        expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it("preserves the selected file and uses recovery copy when upload fails", async () => {
        const user = userEvent.setup();
        const createResource = vi.fn().mockRejectedValue(new Error("[HTTP_500]"));
        render(<ResourcePickerDrawer kind="material" open onOpenChange={vi.fn()} onCreated={vi.fn()} createResource={createResource} />);
        const file = new File(["content"], "产品方案.pptx", {
            type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        });

        await user.upload(screen.getByLabelText("材料文件"), file);
        await user.type(screen.getByLabelText("材料名称"), "产品方案 PPT");
        await user.click(screen.getByRole("button", { name: "上传并绑定" }));

        const alert = await screen.findByRole("alert");
        expect(alert.textContent).toContain("上传未完成");
        expect(alert.textContent).toContain("材料名称和已选文件均已保留");
        expect(alert.textContent).not.toContain("[HTTP_500]");
        expect(screen.getByText("产品方案.pptx")).toBeTruthy();
        expect((screen.getByLabelText("材料名称") as HTMLInputElement).value).toBe("产品方案 PPT");
    });

    it("reuses the created material record when retrying a failed upload", async () => {
        const user = userEvent.setup();
        const onCreated = vi.fn();
        const createMaterial = vi.spyOn(api.admin.salesTrainer, "createMaterial").mockResolvedValue({
            material_id: "material-draft",
            name: "产品方案 PPT",
        } as never);
        const updateMaterial = vi.spyOn(api.admin.salesTrainer, "updateMaterial").mockResolvedValue({
            material_id: "material-draft",
            name: "产品方案 PPT",
        } as never);
        const uploadMaterialVersion = vi.spyOn(api.admin.salesTrainer, "uploadMaterialVersion")
            .mockRejectedValueOnce(new Error("连接中断"))
            .mockResolvedValueOnce({ version_id: "version-1" } as never);
        const publishMaterialVersion = vi.spyOn(api.admin.salesTrainer, "publishMaterialVersion")
            .mockResolvedValue({ version_id: "version-1" } as never);
        render(<ResourcePickerDrawer kind="material" open onOpenChange={vi.fn()} onCreated={onCreated} />);
        const file = new File(["content"], "产品方案.pptx", {
            type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        });

        await user.upload(screen.getByLabelText("材料文件"), file);
        await user.type(screen.getByLabelText("材料名称"), "产品方案 PPT");
        await user.click(screen.getByRole("button", { name: "上传并绑定" }));
        expect(await screen.findByRole("alert")).toBeTruthy();

        await user.click(screen.getByRole("button", { name: "上传并绑定" }));
        await waitFor(() => expect(onCreated).toHaveBeenCalledWith({
            id: "material-draft",
            title: "产品方案 PPT",
            status: "published",
        }));

        expect(createMaterial).toHaveBeenCalledTimes(1);
        expect(updateMaterial).toHaveBeenCalledTimes(1);
        expect(uploadMaterialVersion).toHaveBeenCalledTimes(2);
        expect(publishMaterialVersion).toHaveBeenCalledTimes(1);
        expect(createMaterial.mock.calls[0][1]).toBe(uploadMaterialVersion.mock.calls[0][2]);
        expect(updateMaterial.mock.calls[0][2]).toBe(uploadMaterialVersion.mock.calls[1][2]);
        expect(publishMaterialVersion.mock.calls[0][1]).toBe(uploadMaterialVersion.mock.calls[1][2]);
    });

    it("lets the user cancel a stalled material upload and ignores late completion", async () => {
        const user = userEvent.setup();
        const onCreated = vi.fn();
        let resolveCreate!: (resource: { id: string; title: string; status: string }) => void;
        const createResource = vi.fn<
            (_payload: { signal?: AbortSignal }) => Promise<{ id: string; title: string; status: string }>
        >(() => new Promise((resolve) => {
            resolveCreate = resolve;
        }));
        render(<ResourcePickerDrawer kind="material" open onOpenChange={vi.fn()} onCreated={onCreated} createResource={createResource} />);
        const file = new File(["content"], "产品方案.pptx", {
            type: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        });

        await user.upload(screen.getByLabelText("材料文件"), file);
        await user.type(screen.getByLabelText("材料名称"), "产品方案 PPT");
        await user.click(screen.getByRole("button", { name: "上传并绑定" }));

        const signal = (createResource.mock.calls[0][0] as { signal?: AbortSignal }).signal;
        await user.click(screen.getByRole("button", { name: "取消上传" }));

        expect(signal?.aborted).toBe(true);
        expect(screen.getByRole("alert").textContent).toContain("已取消上传");
        expect(screen.getByText("产品方案.pptx")).toBeTruthy();
        expect((screen.getByLabelText("材料名称") as HTMLInputElement).value).toBe("产品方案 PPT");
        expect(screen.getByRole("button", { name: "上传并绑定" })).toBeTruthy();

        await act(async () => {
            resolveCreate({ id: "late-material", title: "迟到的材料", status: "published" });
            await Promise.resolve();
        });
        expect(onCreated).not.toHaveBeenCalled();
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

    it("binds scoring rubric then offers refine-prompt action without leaving the flow", async () => {
        const user = userEvent.setup();
        const onCreated = vi.fn().mockResolvedValue({ draftPersisted: true });
        const onOpenChange = vi.fn();
        const onBeforeRefineNavigate = vi.fn().mockResolvedValue(true);
        const popup = createPopupStub();
        const openSpy = vi.spyOn(window, "open").mockReturnValue(popup.popup);
        const createResource = vi.fn().mockResolvedValue({
            id: "prompt-1",
            title: "产品讲解评分标准",
            status: "published",
        });
        render(
            <ResourcePickerDrawer
                kind="scoring_rubric"
                open
                onOpenChange={onOpenChange}
                onCreated={onCreated}
                onBeforeRefineNavigate={onBeforeRefineNavigate}
                createResource={createResource}
            />,
        );

        await user.type(screen.getByLabelText("评分标准名称"), "产品讲解评分标准");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));

        await waitFor(() => {
            expect(onCreated).toHaveBeenCalledWith(
                expect.objectContaining({ id: "prompt-1", title: "产品讲解评分标准" }),
            );
        });
        expect(onOpenChange).not.toHaveBeenCalledWith(false);
        expect(await screen.findByText("评分标准已创建；路径草稿已保存。")).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "去完善提示词" }));
        await waitFor(() => {
            expect(onBeforeRefineNavigate).toHaveBeenCalled();
            expect(openSpy).toHaveBeenCalledWith("about:blank", "_blank");
            expect(popup.replace).toHaveBeenCalledWith(
                "/admin/sales-trainer/score-standards/prompt-1/edit",
            );
        });
        await user.click(screen.getByRole("button", { name: "完成" }));
        expect(onOpenChange).toHaveBeenCalledWith(false);
    });

    it("blocks refine navigation when draft save fails", async () => {
        const user = userEvent.setup();
        const onCreated = vi.fn().mockResolvedValue({ draftPersisted: false });
        const onBeforeRefineNavigate = vi.fn().mockResolvedValue(false);
        const popup = createPopupStub();
        const openSpy = vi.spyOn(window, "open").mockReturnValue(popup.popup);
        const createResource = vi.fn().mockResolvedValue({
            id: "prompt-2",
            title: "未保存评分标准",
            status: "published",
        });
        render(
            <ResourcePickerDrawer
                kind="scoring_rubric"
                open
                onOpenChange={vi.fn()}
                onCreated={onCreated}
                onBeforeRefineNavigate={onBeforeRefineNavigate}
                createResource={createResource}
            />,
        );

        await user.type(screen.getByLabelText("评分标准名称"), "未保存评分标准");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));

        expect(await screen.findByText("评分标准已创建并绑定，但路径草稿尚未保存成功。请先保存草稿，再去完善提示词或离开本页。")).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "去完善提示词" }));
        await waitFor(() => {
            expect(onBeforeRefineNavigate).toHaveBeenCalled();
        });
        expect(openSpy).toHaveBeenCalledWith("about:blank", "_blank");
        expect(popup.replace).not.toHaveBeenCalled();
        expect(popup.close).toHaveBeenCalled();
        expect(screen.getByText("路径草稿保存失败，请先保存草稿后再去完善提示词。")).toBeTruthy();
    });

    it("shows a recoverable error when the browser blocks the refine page", async () => {
        const user = userEvent.setup();
        const onBeforeRefineNavigate = vi.fn().mockResolvedValue(true);
        vi.spyOn(window, "open").mockReturnValue(null);
        render(
            <ResourcePickerDrawer
                kind="scoring_rubric"
                open
                onOpenChange={vi.fn()}
                onCreated={vi.fn().mockResolvedValue({ draftPersisted: true })}
                onBeforeRefineNavigate={onBeforeRefineNavigate}
                createResource={vi.fn().mockResolvedValue({
                    id: "prompt-blocked",
                    title: "弹窗拦截评分标准",
                    status: "published",
                })}
            />,
        );

        await user.type(screen.getByLabelText("评分标准名称"), "弹窗拦截评分标准");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));
        await user.click(await screen.findByRole("button", { name: "去完善提示词" }));

        expect(screen.getByRole("alert").textContent).toContain("浏览器阻止了评分标准编辑页");
        expect(onBeforeRefineNavigate).not.toHaveBeenCalled();
    });

    it("does not open refine page after the drawer is closed during save", async () => {
        const user = userEvent.setup();
        let resolveNavigate!: (value: boolean) => void;
        const onBeforeRefineNavigate = vi.fn(
            () => new Promise<boolean>((resolve) => {
                resolveNavigate = resolve;
            }),
        );
        const onOpenChange = vi.fn();
        const popup = createPopupStub();
        vi.spyOn(window, "open").mockReturnValue(popup.popup);
        const createResource = vi.fn().mockResolvedValue({
            id: "prompt-3",
            title: "关闭后不跳转",
            status: "published",
        });
        const { rerender } = render(
            <ResourcePickerDrawer
                kind="scoring_rubric"
                open
                onOpenChange={onOpenChange}
                onCreated={vi.fn().mockResolvedValue({ draftPersisted: false })}
                onBeforeRefineNavigate={onBeforeRefineNavigate}
                createResource={createResource}
            />,
        );

        await user.type(screen.getByLabelText("评分标准名称"), "关闭后不跳转");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));
        expect(await screen.findByText("评分标准已创建并绑定，但路径草稿尚未保存成功。请先保存草稿，再去完善提示词或离开本页。")).toBeTruthy();

        await user.click(screen.getByRole("button", { name: "去完善提示词" }));
        await waitFor(() => expect(onBeforeRefineNavigate).toHaveBeenCalled());
        expect(screen.getByRole("button", { name: "完成" }).hasAttribute("disabled")).toBe(true);

        // 模拟父级在保存未完成时关闭抽屉（例如路由离开）；完成按钮在 refinePending 时已禁用
        rerender(
            <ResourcePickerDrawer
                kind="scoring_rubric"
                open={false}
                onOpenChange={onOpenChange}
                onCreated={vi.fn().mockResolvedValue({ draftPersisted: false })}
                onBeforeRefineNavigate={onBeforeRefineNavigate}
                createResource={createResource}
            />,
        );

        await act(async () => {
            resolveNavigate(true);
            await Promise.resolve();
        });
        expect(popup.replace).not.toHaveBeenCalled();
        expect(popup.close).toHaveBeenCalled();
    });

    it("does not open refine page after unmount during save", async () => {
        const user = userEvent.setup();
        let resolveNavigate!: (value: boolean) => void;
        const onBeforeRefineNavigate = vi.fn(
            () => new Promise<boolean>((resolve) => {
                resolveNavigate = resolve;
            }),
        );
        const popup = createPopupStub();
        vi.spyOn(window, "open").mockReturnValue(popup.popup);
        const { unmount } = render(
            <ResourcePickerDrawer
                kind="scoring_rubric"
                open
                onOpenChange={vi.fn()}
                onCreated={vi.fn().mockResolvedValue({ draftPersisted: false })}
                onBeforeRefineNavigate={onBeforeRefineNavigate}
                createResource={vi.fn().mockResolvedValue({
                    id: "prompt-4",
                    title: "卸载后不跳转",
                    status: "published",
                })}
            />,
        );

        await user.type(screen.getByLabelText("评分标准名称"), "卸载后不跳转");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));
        expect(await screen.findByRole("button", { name: "去完善提示词" })).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "去完善提示词" }));
        await waitFor(() => expect(onBeforeRefineNavigate).toHaveBeenCalled());

        unmount();
        await act(async () => {
            resolveNavigate(true);
            await Promise.resolve();
        });
        expect(popup.replace).not.toHaveBeenCalled();
        expect(popup.close).toHaveBeenCalled();
    });
});
