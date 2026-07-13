import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { TrainingPathConfigResponse, TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import { PathEditor } from "./path-editor";

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

    it("uses a focused two-pane editor and opens the real learner preview on demand", async () => {
        const user = userEvent.setup();
        render(<PathEditor initialModel={response()} />);

        expect(screen.getByRole("tree", { name: "训练路径大纲" })).toBeTruthy();
        expect(screen.getByRole("form", { name: "路径设置" })).toBeTruthy();
        expect(screen.getByTestId("path-editor-layout").getAttribute("data-layout")).toBe("two-pane");
        expect(screen.queryByRole("region", { name: "学员预览" })).toBeNull();

        await user.click(screen.getByRole("button", { name: "预览学员页面" }));

        expect(screen.getByRole("region", { name: "学员预览" })).toBeTruthy();
        expect(screen.getByRole("heading", { name: "产品 A 学习" })).toBeTruthy();
        expect(screen.getByText("能说出产品 A 的三个核心价值")).toBeTruthy();
        expect(screen.queryByText("fallback_applied=true")).toBeNull();
    });

    it("moves a module with keyboard controls", async () => {
        const user = userEvent.setup();
        render(<PathEditor initialModel={response()} />);

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
        await user.type(screen.getByLabelText("发布说明"), "发布产品路径");
        await user.click(screen.getByRole("button", { name: "发布" }));
        expect(screen.getByText("发布后只影响新进入训练的学员")).toBeTruthy();
        expect(onPublish).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: "确认发布" }));
        expect(onPublish).toHaveBeenCalled();
    });
});
