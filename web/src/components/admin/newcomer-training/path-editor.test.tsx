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
            order_index: 1,
            required: true,
            modules: ["产品 A", "产品 B", "产品 C"].map((title, index) => ({
                module_id: `module-${index + 1}`,
                title,
                description: null,
                order_index: index + 1,
                required: true,
                estimated_minutes: 30,
                audience_rule: { learner_levels: [], roles: [], departments: [] },
                prerequisites: [],
                completion_policy: { mode: "all_required", activity_ids: [], count: null },
                activities: [],
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
    it("shows one outline, one focused inspector, and one learner preview", () => {
        render(<PathEditor initialModel={response()} />);

        expect(screen.getByRole("tree", { name: "训练路径大纲" })).toBeTruthy();
        expect(screen.getByRole("form", { name: "路径设置" })).toBeTruthy();
        expect(screen.getByRole("region", { name: "学员预览" })).toBeTruthy();
        expect(screen.getByRole("region", { name: "学员预览" }).textContent).toContain("产品 C");
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
        await user.type(screen.getByLabelText("修改说明"), "调整适用范围");
        await user.click(screen.getByRole("button", { name: "保存草稿" }));

        expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
            phases: [expect.objectContaining({ modules: [expect.objectContaining({
                audience_rule: expect.objectContaining({ departments: ["华东销售", "华南销售"] }),
                completion_policy: expect.objectContaining({ mode: "at_least_count", count: 1 }),
            }), expect.anything(), expect.anything()] })],
        }), "调整适用范围", "draft-1");
    });

    it("asks for impact confirmation before publishing", async () => {
        const user = userEvent.setup();
        const onPublish = vi.fn();
        render(<PathEditor initialModel={response()} onPublish={onPublish} />);
        await user.type(screen.getByLabelText("修改说明"), "发布产品路径");
        await user.click(screen.getByRole("button", { name: "发布" }));
        expect(screen.getByText("发布后只影响新进入训练的学员")).toBeTruthy();
        expect(onPublish).not.toHaveBeenCalled();
        await user.click(screen.getByRole("button", { name: "确认发布" }));
        expect(onPublish).toHaveBeenCalled();
    });
});
