import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TrainingPathPayload } from "@/lib/api/types/newcomer-training";
import { PathOutline } from "./path-outline";

function trainingPath(): TrainingPathPayload {
    const createModule = (id: string, title: string) => ({
        module_id: id,
        title,
        description: null,
        outcome: `完成${title}`,
        order_index: id === "module-a" ? 1 : 2,
        required: true,
        estimated_minutes: 20,
        audience_rule: { learner_levels: [], roles: [], departments: [] },
        prerequisites: [],
        completion_policy: { mode: "all_required" as const, activity_ids: [], count: null },
        activities: [{
            activity_id: `activity-${id}`,
            type: "lesson" as const,
            title: `${title}学习`,
            description: null,
            objective: `理解${title}`,
            why_it_matters: "完成新人训练",
            steps: ["阅读材料"],
            success_criteria: ["完成阅读"],
            primary_action_label: "开始学习",
            order_index: 1,
            required: true,
            estimated_minutes: 10,
            prerequisites: [],
            config: { learning_content_id: `content-${id}`, completion_mode: "all_chapters" as const },
        }],
    });
    return {
        schema_version: "newcomer_training_orchestration_v1",
        title: "新人训练路径",
        description: "从入门到实战",
        phases: [{
            phase_id: "phase-a",
            title: "产品入门",
            description: null,
            outcome: "理解产品",
            order_index: 1,
            required: true,
            modules: [createModule("module-a", "产品 A"), createModule("module-b", "产品 B")],
        }],
    };
}

function dataTransfer(): DataTransfer {
    const values = new Map<string, string>();
    return {
        effectAllowed: "none",
        dropEffect: "none",
        getData: (type: string) => values.get(type) ?? "",
        setData: (type: string, value: string) => { values.set(type, value); },
        clearData: (type?: string) => { if (type) values.delete(type); else values.clear(); },
        files: {} as FileList,
        items: {} as DataTransferItemList,
        types: [],
        setDragImage: vi.fn(),
    } as DataTransfer;
}

function treeItemFor(buttonName: string): HTMLElement {
    const item = screen.getByRole("button", { name: buttonName }).closest<HTMLElement>('[role="treeitem"]');
    if (!item) throw new Error(`找不到 ${buttonName} 所属树节点`);
    return item;
}

describe("PathOutline drag feedback", () => {
    it("marks the dragged module and a valid same-level drop target", () => {
        const onDropItem = vi.fn();
        render(<PathOutline path={trainingPath()} selection={{ kind: "path" }} onSelect={vi.fn()} onMove={vi.fn()} onDuplicate={vi.fn()} onDelete={vi.fn()} onAddPhase={vi.fn()} onAddModule={vi.fn()} onAddActivity={vi.fn()} onDropItem={onDropItem} />);
        const source = treeItemFor("编辑模块 产品 A");
        const target = treeItemFor("编辑模块 产品 B");
        const transfer = dataTransfer();

        fireEvent.dragStart(source, { dataTransfer: transfer });
        expect(source.getAttribute("data-dragging")).toBe("true");
        expect(source.className).toContain("opacity-50");
        expect(source.className).toContain("scale-[0.97]");

        fireEvent.dragOver(target, { dataTransfer: transfer });
        expect(target.getAttribute("data-drop-target")).toBe("true");
        expect(target.className).toContain("ring-2");

        fireEvent.drop(target, { dataTransfer: transfer });
        expect(onDropItem).toHaveBeenCalledWith("module", "module-a", "module-b");
        expect(source.getAttribute("data-dragging")).toBeNull();
        expect(target.getAttribute("data-drop-target")).toBeNull();
    });

    it("rejects cross-level and self drops and clears feedback on drag end", () => {
        const onDropItem = vi.fn();
        render(<PathOutline path={trainingPath()} selection={{ kind: "path" }} onSelect={vi.fn()} onMove={vi.fn()} onDuplicate={vi.fn()} onDelete={vi.fn()} onAddPhase={vi.fn()} onAddModule={vi.fn()} onAddActivity={vi.fn()} onDropItem={onDropItem} />);
        const source = treeItemFor("编辑模块 产品 A");
        const activity = treeItemFor("编辑活动 产品 A学习");
        const transfer = dataTransfer();

        fireEvent.dragStart(source, { dataTransfer: transfer });
        fireEvent.dragOver(activity, { dataTransfer: transfer });
        fireEvent.drop(activity, { dataTransfer: transfer });
        expect(activity.getAttribute("data-drop-target")).toBeNull();
        expect(onDropItem).not.toHaveBeenCalled();

        fireEvent.dragStart(source, { dataTransfer: transfer });
        fireEvent.dragOver(source, { dataTransfer: transfer });
        fireEvent.drop(source, { dataTransfer: transfer });
        expect(onDropItem).not.toHaveBeenCalled();

        fireEvent.dragStart(source, { dataTransfer: transfer });
        fireEvent.dragEnd(source, { dataTransfer: transfer });
        expect(source.getAttribute("data-dragging")).toBeNull();
    });
});
