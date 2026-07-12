import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

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
});
