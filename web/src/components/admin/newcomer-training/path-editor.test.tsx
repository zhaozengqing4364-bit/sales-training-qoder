import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "@/lib/api/client";
import type { TrainingPathConfigResponse, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import { PathEditor } from "./path-editor";

function createPopupStub() {
    const replace = vi.fn();
    return {
        popup: {
            opener: null,
            closed: false,
            close: vi.fn(),
            location: { replace },
        } as unknown as Window,
        replace,
    };
}

function payload(): TrainingPathPayload {
    return {
        schema_version: "newcomer_training_orchestration_v1",
        title: "新人训练路径",
        description: "从入门到独立演示",
        phases: [{
            phase_id: "phase-product",
            title: "产品能力",
            description: null,
            outcome: "能独立讲解核心产品",
            order_index: 1,
            required: true,
            modules: ["产品 A", "产品 B", "产品 C"].map((title, index) => ({
                module_id: `module-${index + 1}`,
                title,
                description: null,
                outcome: `能讲清${title}的适用场景`,
                order_index: index + 1,
                required: true,
                estimated_minutes: 30,
                audience_rule: { learner_levels: [], roles: [], departments: [] },
                prerequisites: [],
                completion_policy: { mode: "all_required", activity_ids: [], count: null },
                activities: index === 0 ? [{
                    activity_id: "activity-product-a",
                    type: "lesson" as const,
                    title: "产品 A 学习",
                    description: null,
                    objective: "能说出产品 A 的三个核心价值",
                    why_it_matters: "这是完成客户讲解的基础",
                    steps: ["阅读产品资料"],
                    success_criteria: ["说出三个核心价值"],
                    primary_action_label: "开始产品 A 学习",
                    order_index: 1,
                    required: true,
                    estimated_minutes: 20,
                    prerequisites: [],
                    config: { learning_content_id: "content-1", completion_mode: "all_chapters" as const },
                }] : [],
            })),
        }],
    };
}

function response(): TrainingPathConfigResponse {
    return {
        active_revision_id: "revision-1",
        active_revision_no: 1,
        working_revision_id: "draft-1",
        payload: payload(),
        validation: { can_publish: true, issues: [] },
    };
}

describe("PathEditor", () => {
    afterEach(() => {
        vi.unstubAllGlobals();
        vi.restoreAllMocks();
    });

    it("adds and selects an activity explicitly when randomUUID is unavailable on HTTP", async () => {
        const user = userEvent.setup();
        const nativeCrypto = globalThis.crypto;
        vi.stubGlobal("crypto", {
            getRandomValues: nativeCrypto.getRandomValues.bind(nativeCrypto),
        });
        render(<PathEditor initialModel={response()} />);

        await user.selectOptions(screen.getByLabelText("为 产品 A 新增活动"), "quiz");
        const addButton = screen.getByRole("button", { name: "为 产品 A 添加活动" });
        expect(addButton.hasAttribute("disabled")).toBe(false);
        await user.click(addButton);

        expect(screen.getByRole("button", { name: "编辑活动 考试测验" })).toBeTruthy();
        expect(screen.getByRole("form", { name: "活动设置" })).toBeTruthy();
        expect(screen.getByText("活动类型：考试测验")).toBeTruthy();
        expect(screen.getByText("活动已添加，先绑定试卷，再补充学员任务说明。")).toBeTruthy();
    });

    it("shows a renamed phase in the outline immediately without hiding the changed suffix", async () => {
        const user = userEvent.setup();
        const onSave = vi.fn();
        render(<PathEditor initialModel={response()} onSave={onSave} />);

        await user.click(screen.getByRole("button", { name: "编辑阶段 产品能力" }));
        await user.clear(screen.getByLabelText("名称"));
        await user.type(screen.getByLabelText("名称"), "产品能力与完整客户演示准备");

        const renamedPhase = screen.getByRole("button", { name: "编辑阶段 产品能力与完整客户演示准备" });
        expect(renamedPhase.textContent).toBe("产品能力与完整客户演示准备");
        expect(renamedPhase.className).not.toContain("truncate");
        expect(onSave).not.toHaveBeenCalled();
    });

    it("exposes saved and dirty draft states with text, icon, and live semantics", async () => {
        const user = userEvent.setup();
        const onSave = vi.fn();
        render(<PathEditor initialModel={response()} onSave={onSave} />);

        const status = screen.getByRole("status");
        expect(status.getAttribute("data-save-state")).toBe("saved");
        expect(status.textContent).toContain("草稿已保存");
        expect(status.querySelector("svg")).not.toBeNull();

        await user.clear(screen.getByLabelText("名称"));
        await user.type(screen.getByLabelText("名称"), "新版新人训练路径");
        expect(status.getAttribute("data-save-state")).toBe("dirty");
        expect(status.textContent).toContain("有未保存修改");
        expect(status.querySelector("svg")).toBeNull();

        await user.click(screen.getByRole("button", { name: "保存草稿" }));
        expect(onSave).toHaveBeenCalled();
        expect(status.getAttribute("data-save-state")).toBe("saved");
        expect(status.textContent).toContain("草稿已保存");
    });

    it("keeps the mobile save action on one line", () => {
        render(<PathEditor initialModel={response()} />);

        expect(screen.getByRole("button", { name: "保存草稿" }).className).toContain("whitespace-nowrap");
    });

    it("keeps the draft dirty when saving fails", async () => {
        const user = userEvent.setup();
        const onSave = vi.fn().mockRejectedValue(new Error("保存失败"));
        render(<PathEditor initialModel={response()} onSave={onSave} />);

        await user.type(screen.getByLabelText("名称"), " 2");
        await user.click(screen.getByRole("button", { name: "保存草稿" }));

        expect((await screen.findByRole("alert")).textContent).toContain("保存失败");
        const status = screen.getByRole("status");
        expect(status.getAttribute("data-save-state")).toBe("dirty");
        expect(status.textContent).toContain("有未保存修改");
    });

    it("switches to an in-flow learner preview that reflects unsaved edits immediately", async () => {
        const user = userEvent.setup();
        render(<PathEditor initialModel={response()} />);

        expect(screen.getByRole("tree", { name: "训练路径大纲" })).toBeTruthy();
        expect(screen.getByRole("form", { name: "路径设置" })).toBeTruthy();
        expect(screen.getByTestId("path-editor-layout").getAttribute("data-layout")).toBe("outline-workspace");
        expect(screen.queryByRole("region", { name: "学员预览" })).toBeNull();

        await user.click(screen.getByRole("button", { name: "编辑阶段 产品能力" }));
        await user.clear(screen.getByLabelText("名称"));
        await user.type(screen.getByLabelText("名称"), "产品能力实时更新版");
        await user.click(screen.getByRole("button", { name: "实时预览" }));

        const preview = screen.getByRole("region", { name: "学员预览" });
        expect(preview).toBeTruthy();
        expect(within(preview).getByText("产品能力实时更新版")).toBeTruthy();
        expect(screen.getByRole("heading", { name: "产品 A 学习" })).toBeTruthy();
        expect(screen.getByText("能说出产品 A 的三个核心价值")).toBeTruthy();
        expect(screen.getByText("编辑内容会立即同步到实时预览；发布后所有在训学员同步更新")).toBeTruthy();
        expect(screen.queryByRole("form", { name: "阶段设置" })).toBeNull();
        expect(screen.queryByText("fallback_applied=true")).toBeNull();

        await user.click(screen.getByRole("button", { name: "编排" }));
        expect(screen.getByRole("form", { name: "阶段设置" })).toBeTruthy();
        expect((screen.getByLabelText("名称") as HTMLInputElement).value).toBe("产品能力实时更新版");
    });

    it("moves a module with keyboard controls", async () => {
        const user = userEvent.setup();
        render(<PathEditor initialModel={response()} />);

        expect(screen.queryByRole("button", { name: "上移 产品 C" })).toBeNull();
        await user.click(screen.getByRole("button", { name: "编辑模块 产品 C" }));
        await user.click(screen.getByRole("button", { name: "上移 产品 C" }));

        const tree = screen.getByRole("tree", { name: "训练路径大纲" });
        const moduleItems = Array.from(tree.querySelectorAll('[data-kind="module"]'));
        expect(moduleItems.map((item) => item.getAttribute("data-title"))).toEqual([
            "产品 A", "产品 C", "产品 B",
        ]);
    });

    it("renders only the selected object inspector", async () => {
        const user = userEvent.setup();
        render(<PathEditor initialModel={response()} />);

        await user.click(screen.getByRole("button", { name: "编辑模块 产品 A" }));

        expect(screen.getByRole("form", { name: "模块设置" })).toBeTruthy();
        expect(screen.queryByRole("form", { name: "路径设置" })).toBeNull();
    });

    it("searches and collapses a large outline with accessible action targets", async () => {
        const user = userEvent.setup();
        render(<PathEditor initialModel={response()} />);

        await user.type(screen.getByRole("searchbox", { name: "搜索路径大纲" }), "产品 C");
        expect(screen.getByRole("button", { name: "编辑模块 产品 C" })).toBeTruthy();
        expect(screen.queryByRole("button", { name: "编辑模块 产品 A" })).toBeNull();
        await user.click(screen.getByRole("button", { name: "编辑模块 产品 C" }));
        expect(screen.getByRole("button", { name: "上移 产品 C" }).className).toContain("h-10");

        await user.clear(screen.getByRole("searchbox", { name: "搜索路径大纲" }));
        await user.click(screen.getByRole("button", { name: "折叠阶段 产品能力" }));
        expect(screen.queryByRole("button", { name: "编辑模块 产品 A" })).toBeNull();
    });

    it("round-trips module audience and completion rules through save", async () => {
        const user = userEvent.setup();
        const onSave = vi.fn();
        render(<PathEditor initialModel={response()} onSave={onSave} />);
        await user.click(screen.getByRole("button", { name: "编辑模块 产品 A" }));
        await user.type(screen.getByLabelText("适用部门"), "华东销售, 华南销售");
        await user.selectOptions(screen.getByLabelText("完成规则"), "at_least_count");
        await user.clear(screen.getByLabelText("至少完成活动数"));
        await user.type(screen.getByLabelText("至少完成活动数"), "1");
        await user.click(screen.getByRole("button", { name: "保存草稿" }));

        expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
            phases: [expect.objectContaining({ modules: [expect.objectContaining({
                audience_rule: expect.objectContaining({ departments: ["华东销售", "华南销售"] }),
                completion_policy: expect.objectContaining({ mode: "at_least_count", count: 1 }),
            }), expect.anything(), expect.anything()] })],
        }), "保存训练路径草稿", "draft-1");
    });

    it("round-trips learner-facing outcomes and activity guidance", async () => {
        const user = userEvent.setup();
        const onSave = vi.fn();
        render(<PathEditor initialModel={response()} onSave={onSave} />);

        await user.click(screen.getByRole("button", { name: "编辑阶段 产品能力" }));
        await user.clear(screen.getByLabelText("完成阶段后，学员能做到"));
        await user.type(screen.getByLabelText("完成阶段后，学员能做到"), "能独立完成产品介绍");

        await user.click(screen.getByRole("button", { name: "编辑活动 产品 A 学习" }));
        await user.clear(screen.getByLabelText("本次任务目标"));
        await user.type(screen.getByLabelText("本次任务目标"), "能面向客户讲清三个产品价值");
        await user.click(screen.getByRole("button", { name: "添加步骤" }));
        await user.type(screen.getByLabelText("步骤 2"), "用自己的话复述价值");
        await user.click(screen.getByRole("button", { name: "保存草稿" }));

        expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
            phases: [expect.objectContaining({
                outcome: "能独立完成产品介绍",
                modules: [expect.objectContaining({ activities: [expect.objectContaining({
                    objective: "能面向客户讲清三个产品价值",
                    steps: ["阅读产品资料", "用自己的话复述价值"],
                })] }), expect.anything(), expect.anything()],
            })],
        }), "保存训练路径草稿", "draft-1");
    });

    it("does not persist an unfinished blank step", async () => {
        const user = userEvent.setup();
        const onSave = vi.fn();
        render(<PathEditor initialModel={response()} onSave={onSave} />);

        await user.click(screen.getByRole("button", { name: "编辑活动 产品 A 学习" }));
        await user.click(screen.getByRole("button", { name: "添加步骤" }));
        await user.click(screen.getByRole("button", { name: "保存草稿" }));

        const savedPath = onSave.mock.calls[0][0] as TrainingPathPayload;
        expect(savedPath.phases[0].modules[0].activities[0].steps).toEqual(["阅读产品资料"]);
    });

    it("asks for impact confirmation before publishing", async () => {
        const user = userEvent.setup();
        const onPublish = vi.fn();
        render(<PathEditor initialModel={response()} onPublish={onPublish} />);

        expect(screen.queryByLabelText("发布说明")).toBeNull();
        await user.click(screen.getByRole("button", { name: "发布" }));
        expect(screen.getByText("发布后，全体在训学员立即切换到新版本。")).toBeTruthy();
        expect(screen.getByText("已完成记录、评分和提交证据仍保留原始快照。")).toBeTruthy();
        await user.type(screen.getByLabelText("发布说明"), "发布产品路径");
        expect(onPublish).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: "确认发布" }));
        expect(onPublish).toHaveBeenCalled();
    });

    it("preflights publishing, focuses the first issue, and preserves the reason", async () => {
        const user = userEvent.setup();
        const onValidate = vi.fn().mockResolvedValue({
            can_publish: false,
            issues: [{
                code: "learning_content_required",
                message: "产品 A 学习：请选择已发布的学习内容。",
                object_id: "activity-product-a",
                field_path: "phases[0].modules[0].activities[0].config.learning_content_id",
                severity: "error",
            }],
        });
        const onPublish = vi.fn();
        render(<PathEditor initialModel={response()} onValidate={onValidate} onPublish={onPublish} />);

        await user.click(screen.getByRole("button", { name: "发布" }));
        await user.type(screen.getByLabelText("发布说明"), "补齐资源后发布");
        await user.click(screen.getByRole("button", { name: "确认发布" }));

        expect(await screen.findByText("发布前还有 1 项配置需要处理，已定位到第一项。")).toBeTruthy();
        expect(screen.getByRole("form", { name: "活动设置" })).toBeTruthy();
        expect(screen.getByRole("button", { name: "产品 A 学习：请选择已发布的学习内容。" })).toBeTruthy();
        expect(onValidate).toHaveBeenCalled();
        expect(onPublish).not.toHaveBeenCalled();
        expect(screen.queryByLabelText("发布说明")).toBeNull();

        await user.type(screen.getByLabelText("名称"), "（已修正）");
        expect(screen.queryByText("发布前还有 1 项配置需要处理，已定位到第一项。")).toBeNull();

        await user.click(screen.getByRole("button", { name: "发布" }));
        expect((screen.getByLabelText("发布说明") as HTMLInputElement).value).toBe("补齐资源后发布");
    });

    it("keeps publish context in the dialog and blocks an empty reason", async () => {
        const user = userEvent.setup();
        const onPublish = vi.fn();
        render(<PathEditor initialModel={response()} onPublish={onPublish} />);

        await user.click(screen.getByRole("button", { name: "发布" }));
        await user.click(screen.getByRole("button", { name: "确认发布" }));

        expect(screen.getByRole("alert").textContent).toContain("请填写发布说明");
        expect(screen.getByLabelText("发布说明")).toBeTruthy();
        expect(onPublish).not.toHaveBeenCalled();
    });

    it("auto-saves path draft after scoring rubric quick-create bind", async () => {
        const user = userEvent.setup();
        const onSave = vi.fn().mockResolvedValue({ revision_id: "draft-2", revision_no: 2 });
        const popup = createPopupStub();
        const openSpy = vi.spyOn(window, "open").mockReturnValue(popup.popup);
        vi.spyOn(api.admin.newcomerTraining, "createScoringRubric").mockResolvedValue({
            id: "prompt-1",
            title: "产品讲解评分标准",
            status: "published",
        });
        render(<PathEditor initialModel={response()} onSave={onSave} />);

        await user.selectOptions(screen.getByLabelText("为 产品 A 新增活动"), "audio_assessment");
        await user.click(screen.getByRole("button", { name: "为 产品 A 添加活动" }));
        await user.click(screen.getByRole("button", { name: "新建评分标准" }));
        await user.type(screen.getByLabelText("评分标准名称"), "产品讲解评分标准");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));

        await waitFor(() => {
            expect(onSave).toHaveBeenCalledWith(
                expect.objectContaining({
                    phases: [expect.objectContaining({
                        modules: [expect.objectContaining({
                            activities: expect.arrayContaining([
                                expect.objectContaining({
                                    type: "audio_assessment",
                                    config: expect.objectContaining({ scoring_rubric_id: "prompt-1" }),
                                }),
                            ]),
                        }), expect.anything(), expect.anything()],
                    })],
                }),
                "保存训练路径草稿",
                "draft-1",
            );
        });
        expect(await screen.findByText("评分标准已创建；路径草稿已保存。")).toBeTruthy();
        expect(document.querySelector('[data-save-state="saved"]')).toBeTruthy();

        await user.click(screen.getByRole("button", { name: "去完善提示词" }));
        await waitFor(() => {
            expect(openSpy).toHaveBeenCalledWith("about:blank", "_blank");
            expect(popup.replace).toHaveBeenCalledWith(
                "/admin/sales-trainer/score-standards/prompt-1/edit",
            );
        });
        // 草稿已保存时「去完善」不应再次触发保存
        expect(onSave).toHaveBeenCalledTimes(1);
    });

    it("keeps binding dirty and blocks refine navigation when auto-save fails", async () => {
        const user = userEvent.setup();
        const onSave = vi.fn().mockRejectedValue(new Error("保存失败"));
        const popup = createPopupStub();
        vi.spyOn(window, "open").mockReturnValue(popup.popup);
        vi.spyOn(api.admin.newcomerTraining, "createScoringRubric").mockResolvedValue({
            id: "prompt-fail",
            title: "保存失败评分标准",
            status: "published",
        });
        render(<PathEditor initialModel={response()} onSave={onSave} />);

        await user.selectOptions(screen.getByLabelText("为 产品 A 新增活动"), "audio_assessment");
        await user.click(screen.getByRole("button", { name: "为 产品 A 添加活动" }));
        await user.click(screen.getByRole("button", { name: "新建评分标准" }));
        await user.type(screen.getByLabelText("评分标准名称"), "保存失败评分标准");
        await user.click(screen.getByRole("button", { name: "创建并绑定" }));

        expect(await screen.findByText("评分标准已创建并绑定，但路径草稿尚未保存成功。请先保存草稿，再去完善提示词或离开本页。")).toBeTruthy();
        expect(document.querySelector('[data-save-state="dirty"]')).toBeTruthy();

        await user.click(screen.getByRole("button", { name: "去完善提示词" }));
        await waitFor(() => {
            expect(onSave).toHaveBeenCalledTimes(2);
        });
        expect(popup.replace).not.toHaveBeenCalled();
        expect(screen.getByText("路径草稿保存失败，请先保存草稿后再去完善提示词。")).toBeTruthy();
    });
});
