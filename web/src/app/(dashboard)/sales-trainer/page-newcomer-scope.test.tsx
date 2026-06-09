import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerPage from "./page";

const { listPathsMock, listUnitsMock } = vi.hoisted(() => ({
    listPathsMock: vi.fn(),
    listUnitsMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button type="button" {...props}>{children}</button>,
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, className }: { children: ReactNode; className?: string }) => <div className={className}>{children}</div>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/components/ui/empty-state", () => ({
    EmptyState: ({ title, description }: { title: string; description: string }) => <div>{title}{description}</div>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            salesTrainer: {
                ...actual.api.salesTrainer,
                listUnits: listUnitsMock,
                listPaths: listPathsMock,
            },
        },
    };
});

const baseTimestamp = "2026-05-28T00:00:00Z";

function unitFixture(overrides: {
    readonly unitId: string;
    readonly name: string;
    readonly description?: string;
    readonly path?: Record<string, string | boolean>;
}) {
    return {
        unit_id: overrides.unitId,
        name: overrides.name,
        description: overrides.description ?? "训练说明",
        unit_type: "quiz" as const,
        config: overrides.path ? { path: overrides.path } : {},
        status: "published" as const,
        created_by: "admin-1",
        updated_by: "admin-1",
        created_at: baseTimestamp,
        updated_at: baseTimestamp,
        questions: [],
    };
}

describe("SalesTrainerPage newcomer scope", () => {
    beforeEach(() => {
        listPathsMock.mockReset();
        listUnitsMock.mockReset();
    });

    it("does not expose legacy or verification units when the newcomer path is configured", async () => {
        listPathsMock.mockResolvedValue({
            items: [
                {
                    path_key: "newcomer_training_path_v1",
                    title: "新人训练路径",
                    goal_title: "掌握新人核心训练路径",
                    total_levels: 1,
                    completed_levels: 0,
                    current_level_id: "business-unit",
                    next_level_id: "business-unit",
                    goal_context: null,
                    levels: [
                        {
                            unit_id: "business-unit",
                            name: "商务技巧",
                            description: "阅读文章后完成商务技巧考卷。",
                            unit_type: "quiz",
                            order_index: 2,
                            level_title: "第2关：商务技巧",
                            level_description: "阅读文章后完成商务技巧考卷。",
                            locked: false,
                            lock_reason: null,
                            status: "available",
                            completion_rule: "passed",
                            primary_action_label: "阅读文章并考试",
                            retry_action_label: "重新考试",
                            review_action_label: "查看结果",
                            target_path: "/sales-trainer/business-skills?unitId=business-unit",
                            latest_result: null,
                        },
                    ],
                },
            ],
            total: 1,
        });
        listUnitsMock.mockResolvedValue({
            items: [
                unitFixture({
                    unitId: "business-unit",
                    name: "商务技巧",
                    path: {
                        module_key: "business_skills",
                        module_type: "article_exam",
                        level_title: "第2关：商务技巧",
                        primary_action_label: "阅读文章并考试",
                    },
                }),
                unitFixture({
                    unitId: "legacy-coo-unit",
                    name: "COO系列之1：陌拜实战测验",
                    description: "旧销售训练内容。",
                }),
                unitFixture({
                    unitId: "goal-verification-unit",
                    name: "Goal验收做题训练单元",
                    description: "浏览器验收创建。",
                }),
            ],
            total: 3,
        });

        render(<SalesTrainerPage />);

        expect(await screen.findByText("选择下方模块开始训练")).toBeTruthy();
        expect(screen.getByRole("heading", { name: /商务技巧/ })).toBeTruthy();
        expect(screen.getByText((_, element) => element?.textContent === "已开放模块可随时进入，无强制解锁。当前开放模块：第2关：商务技巧。")).toBeTruthy();
        expect(screen.queryByText(/更多练习/)).toBeNull();
        expect(screen.queryByText(/PPT讲解录音/)).toBeNull();
        expect(screen.queryByText(/电梯演讲/)).toBeNull();
        expect(screen.queryByText(/实时对练/)).toBeNull();
        expect(screen.queryByText(/COO系列/)).toBeNull();
        expect(screen.queryByText(/Goal验收/)).toBeNull();
    });
});
