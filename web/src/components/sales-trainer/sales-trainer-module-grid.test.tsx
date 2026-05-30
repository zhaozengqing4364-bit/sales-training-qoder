import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import type { SalesTrainerPath, SalesTrainerUnit } from "@/lib/api/types";
import { NEW_SELLER_MODULES_PATH_KEY } from "@/lib/sales-trainer/module-path";

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
            target_path: "/sales-trainer/learn/hub",
            latest_result: null,
        },
        {
            unit_id: "a3",
            name: "5m",
            description: null,
            unit_type: "audio_scoring",
            order_index: 3,
            level_title: "金字塔演讲 · 5 分钟",
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
            level_title: "金字塔演讲 · 10 分钟",
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
            level_title: "金字塔演讲 · 15 分钟",
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
    it("renders three module cards and duration actions", () => {
        render(<SalesTrainerModuleGrid path={path} unitsById={new Map()} />);

        expect(screen.getByText("PPT演练")).toBeTruthy();
        expect(screen.getByText("拜访前商务")).toBeTruthy();
        expect(screen.getByText("金字塔演讲")).toBeTruthy();
        expect(screen.getByRole("link", { name: /上传 PPT 讲解录音/ }).getAttribute("href")).toBe(
            "/sales-trainer/audio/a1",
        );
        expect(screen.getByRole("link", { name: /阅读学习/ }).getAttribute("href")).toBe(
            "/sales-trainer/learn/hub",
        );
        expect(screen.getByRole("link", { name: "5 分钟" }).getAttribute("href")).toBe(
            "/sales-trainer/audio/a3",
        );
    });
});
