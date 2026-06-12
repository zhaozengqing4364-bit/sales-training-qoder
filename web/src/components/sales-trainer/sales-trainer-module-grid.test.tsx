import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";
import { NEWCOMER_TRAINING_PATH_KEY, NEW_SELLER_MODULES_PATH_KEY } from "@/lib/sales-trainer/module-path";

import { SalesTrainerModuleGrid } from "./sales-trainer-module-grid";

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>{children}</button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

const path: SalesTrainerPath = {
    path_key: NEW_SELLER_MODULES_PATH_KEY,
    title: "三模块",
    goal_title: null,
    total_levels: 5,
    completed_levels: 0,
    current_level_id: "a1",
    next_level_id: "a1",
    goal_context: {
        goal_title: null,
        score_basis: "sales_trainer_path_projection_v1",
        evidence_items: [],
        weak_points: [],
        next_recommendation: null,
    },
    levels: [
        {
            unit_id: "a1",
            name: "m1",
            description: null,
            unit_type: "audio_scoring",
            order_index: 1,
            level_title: "PPT",
            level_description: "ppt desc",
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "scored",
            primary_action_label: "上传",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/audio/a1",
            latest_result: null,
        },
        {
            unit_id: "a2",
            name: "m2",
            description: null,
            unit_type: "quiz",
            order_index: 2,
            level_title: "商务",
            level_description: "biz",
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "submitted",
            primary_action_label: "学习",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/business-skills",
            latest_result: null,
        },
        {
            unit_id: "a3",
            name: "5m",
            description: null,
            unit_type: "audio_scoring",
            order_index: 3,
            level_title: "电梯演讲 · 5 分钟",
            level_description: null,
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "scored",
            primary_action_label: "上传",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/audio/a3",
            latest_result: null,
        },
        {
            unit_id: "a4",
            name: "10m",
            description: null,
            unit_type: "audio_scoring",
            order_index: 4,
            level_title: "电梯演讲 · 10 分钟",
            level_description: null,
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "scored",
            primary_action_label: "上传",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/audio/a4",
            latest_result: null,
        },
        {
            unit_id: "a5",
            name: "15m",
            description: null,
            unit_type: "audio_scoring",
            order_index: 5,
            level_title: "电梯演讲 · 15 分钟",
            level_description: null,
            locked: false,
            lock_reason: null,
            status: "available",
            completion_rule: "scored",
            primary_action_label: "上传",
            retry_action_label: "重练",
            review_action_label: "查看",
            target_path: "/sales-trainer/audio/a5",
            latest_result: null,
        },
    ],
};

describe("SalesTrainerModuleGrid", () => {
    it("renders newcomer module cards and keeps realtime practice disabled", () => {
        render(<SalesTrainerModuleGrid path={path} unitsById={new Map()} />);

        expect(screen.getByText("PPT讲解录音")).toBeTruthy();
        expect(screen.getByText("商务技巧")).toBeTruthy();
        expect(screen.getByText("电梯演讲")).toBeTruthy();
        expect(screen.getByText("实时对练")).toBeTruthy();
        expect(screen.getByRole("link", { name: /上传 PPT 讲解录音/ }).getAttribute("href")).toBe(
            "/sales-trainer/audio/a1",
        );
        expect(screen.getByRole("link", { name: /开始学习/ }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills?unitId=a2",
        );
        expect(screen.queryByRole("link", { name: "AI 教练" })).toBeNull();
        expect(screen.getByRole("link", { name: "5 分钟" }).getAttribute("href")).toBe(
            "/sales-trainer/audio/a3",
        );
        expect(screen.getByRole("button", { name: /暂不开放/ }).hasAttribute("disabled")).toBe(true);
        expect(screen.queryByRole("link", { name: /实时对练/ })).toBeNull();
    });

    it("renders only configured backend modules and uses configured action labels", () => {
        const businessOnlyPath: SalesTrainerPath = {
            ...path,
            path_key: NEWCOMER_TRAINING_PATH_KEY,
            levels: [
                {
                    ...path.levels[1],
                    unit_id: "business-unit",
                    module_key: "business_skills",
                    module_type: "article_exam",
                    level_title: "第二关：商务技巧",
                    level_description: "先完成学习章节，再进入考试。",
                    primary_action_label: "进入学习页",
                    target_path: "/sales-trainer/business-skills",
                    ai_coach_availability: {
                        enabled: true,
                        configured: true,
                        available: true,
                        coach_path: "/sales-trainer/business-skills/coach",
                        disabled_reason: null,
                        allowed_interaction_types: ["single_choice", "multiple_choice"],
                    },
                },
            ],
        };
        const businessUnit: SalesTrainerUnit = {
            unit_id: "business-unit",
            name: "商务技巧",
            description: null,
            unit_type: "quiz",
            config: { path: { module_key: "business_skills", module_type: "article_exam" } },
            status: "published",
            created_by: null,
            updated_by: null,
            created_at: "",
            updated_at: "",
            questions: [],
        };

        render(<SalesTrainerModuleGrid path={businessOnlyPath} unitsById={new Map([["business-unit", businessUnit]])} />);

        expect(screen.getByText("第二关：商务技巧")).toBeTruthy();
        expect(screen.getByText("先完成学习章节，再进入考试。")).toBeTruthy();
        expect(screen.getByRole("link", { name: "进入学习页" }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills?unitId=business-unit",
        );
        expect(screen.getByRole("link", { name: "AI 教练" }).getAttribute("href")).toBe(
            "/sales-trainer/business-skills/coach",
        );
        expect(screen.queryByText("PPT讲解录音")).toBeNull();
        expect(screen.queryByText("实时对练")).toBeNull();
    });

    it("explains missing backend module configuration instead of rendering an empty newcomer path", () => {
        const unconfiguredPath: SalesTrainerPath = {
            ...path,
            path_key: NEWCOMER_TRAINING_PATH_KEY,
            levels: [
                {
                    ...path.levels[0],
                    unit_id: "ppt-unit",
                    level_title: "第一关：PPT",
                },
                {
                    ...path.levels[1],
                    unit_id: "business-unit",
                    level_title: "第二关：商务",
                },
            ],
        };

        render(<SalesTrainerModuleGrid path={unconfiguredPath} unitsById={new Map()} />);

        expect(screen.getByText("新人训练路径暂不可用")).toBeTruthy();
        expect(screen.getByText(/当前路径缺少后台模块配置/)).toBeTruthy();
        expect(screen.getByRole("link", { name: "去配置中心处理" }).getAttribute("href")).toBe(
            "/admin/sales-trainer/paths",
        );
        expect(screen.queryByText("PPT讲解录音")).toBeNull();
        expect(screen.queryByText("商务技巧")).toBeNull();
    });
});
