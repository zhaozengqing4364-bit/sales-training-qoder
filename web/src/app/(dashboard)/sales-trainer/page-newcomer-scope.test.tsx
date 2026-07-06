import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerPage from "./page";

const { getJourneyMock, listPathsMock, listUnitsMock, routerPushMock, startRealtimeRoleplayMock } = vi.hoisted(() => ({
    getJourneyMock: vi.fn(),
    listPathsMock: vi.fn(),
    listUnitsMock: vi.fn(),
    routerPushMock: vi.fn(),
    startRealtimeRoleplayMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: routerPushMock,
    }),
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
                getJourney: getJourneyMock,
                listUnits: listUnitsMock,
                listPaths: listPathsMock,
                startRealtimeRoleplay: startRealtimeRoleplayMock,
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
        getJourneyMock.mockReset();
        listPathsMock.mockReset();
        listUnitsMock.mockReset();
        routerPushMock.mockReset();
        startRealtimeRoleplayMock.mockReset();
    });

    it("does not expose legacy or verification units when the newcomer path is configured", async () => {
        getJourneyMock.mockResolvedValue({
            journey_id: "journey-scope-1",
            learner_id: "learner-1",
            learner_name: "测试学员",
            department: "销售一部",
            path_key: "newcomer_training_path_v1",
            path_revision_id: "path-rev-scope",
            path_revision_no: 1,
            source: "active_revision",
            legacy_snapshot_only: false,
            role_capabilities: [],
            learner_level: {
                level_key: "unassigned",
                label: "未分层",
                source: "training_projection",
                rank: 0,
                effective_from: null,
                effective_to: null,
                config_revision_id: null,
                description: null,
            },
            role_level: {
                level_key: "learner",
                label: "普通学员",
                source: "training_projection",
                rank: 0,
                effective_from: null,
                effective_to: null,
                config_revision_id: null,
                description: null,
            },
            training_stage: "not_started",
            modules: [
                {
                    module_key: "business_skills",
                    module_type: "article_exam",
                    kind: "quiz_attempt",
                    display_name: "商务技巧",
                    order_index: 2,
                    enabled: true,
                    status: "not_started",
                    stage: "not_started",
                    passed: null,
                    score: null,
                    max_score: null,
                    required: true,
                    locked: false,
                    block_reason: null,
                    completion_rule: "passed",
                    source: {
                        path_revision_id: "path-rev-scope",
                        path_revision_no: 1,
                    },
                    learner_level_required: null,
                    unmet_reasons: [],
                    diagnostics: [],
                    latest_outcome: null,
                    outcome_history: [],
                },
            ],
            overall_progress: {
                total_modules: 1,
                completed_modules: 0,
                passed_modules: 0,
                failed_modules: 0,
                needs_remediation_modules: 0,
            },
            diagnostics: [],
            generated_at: baseTimestamp,
        });
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

        expect(await screen.findByText("当前训练闭环状态")).toBeTruthy();
        expect(screen.getByText("模块闭环状态")).toBeTruthy();
        expect(screen.getAllByRole("heading", { name: /商务技巧/ }).length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText("最近记录：暂无训练结果")).toBeTruthy();
        expect(listPathsMock).not.toHaveBeenCalled();
        expect(listUnitsMock).not.toHaveBeenCalled();
        expect(screen.queryByText("选择下方模块开始训练")).toBeNull();
        expect(screen.queryByText(/更多练习/)).toBeNull();
        expect(screen.queryByText(/PPT讲解录音/)).toBeNull();
        expect(screen.queryByText(/电梯演讲/)).toBeNull();
        expect(screen.queryByText(/实时对练/)).toBeNull();
        expect(screen.queryByText(/COO系列/)).toBeNull();
        expect(screen.queryByText(/Goal验收/)).toBeNull();
    });
});
