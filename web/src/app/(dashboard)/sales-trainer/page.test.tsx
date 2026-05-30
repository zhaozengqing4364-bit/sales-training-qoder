import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SalesTrainerPage from "./page";

const { listPathsMock, listUnitsMock } = vi.hoisted(() => ({
    listUnitsMock: vi.fn(),
    listPathsMock: vi.fn(),
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

const baseUnits = [
    {
        unit_id: "quiz-unit",
        name: "做题单元",
        description: "题目训练",
        unit_type: "quiz" as const,
        config: {
            learner: {
                learning_content_id: "lc-coo",
                chapter_order_index: 1,
            },
        },
        status: "published" as const,
        created_by: "admin-1",
        updated_by: "admin-1",
        created_at: "2026-05-28T00:00:00Z",
        updated_at: "2026-05-28T00:00:00Z",
        questions: [{ question_id: "q1", title: "Q1", stem: "stem", question_type: "single_choice" as const, points: 10, order_index: 1 }],
    },
    {
        unit_id: "audio-unit",
        name: "录音单元",
        description: "录音训练",
        unit_type: "audio_scoring" as const,
        config: { audio: { pass_threshold: 75 } },
        status: "published" as const,
        created_by: "admin-1",
        updated_by: "admin-1",
        created_at: "2026-05-28T00:00:00Z",
        updated_at: "2026-05-28T00:00:00Z",
        questions: [],
    },
    {
        unit_id: "extra-unit",
        name: "额外练习",
        description: "路径外单元",
        unit_type: "quiz" as const,
        config: {},
        status: "published" as const,
        created_by: "admin-1",
        updated_by: "admin-1",
        created_at: "2026-05-28T00:00:00Z",
        updated_at: "2026-05-28T00:00:00Z",
        questions: [],
    },
];

const basePath = {
    path_key: "new_seller",
    title: "新人销售闯关",
    goal_title: "掌握首次客户沟通",
    total_levels: 2,
    completed_levels: 1,
    current_level_id: "audio-unit",
    next_level_id: "audio-unit",
    goal_context: {
        goal_title: "掌握首次客户沟通",
        score_basis: "sales_trainer_path_projection_v1" as const,
        evidence_items: [
            {
                evidence_id: "attempt-1",
                evidence_type: "quiz_attempt" as const,
                unit_id: "quiz-unit",
                unit_type: "quiz" as const,
                level_title: "第一关：产品定位",
                status: "scored",
                passed: true,
                score: 10,
                max_score: 10,
                submitted_at: "2026-05-28T00:00:00Z",
                result_path: "/sales-trainer/quiz/result/attempt-1",
            },
        ],
        weak_points: [
            {
                unit_id: "audio-unit",
                level_title: "第二关：录音表达",
                issue_type: "not_started" as const,
                issue_text: "本关还没有训练证据。",
                evidence_id: null,
                score: null,
                max_score: null,
            },
        ],
        next_recommendation: {
            title: "下一关：第二关：录音表达",
            reason: "本关还没有训练证据。",
            action_label: "上传语音作业",
            target_path: "/sales-trainer/audio/audio-unit",
            unit_id: "audio-unit",
            level_title: "第二关：录音表达",
            recommendation_kind: "start_level" as const,
        },
    },
    levels: [
        {
            unit_id: "quiz-unit",
            name: "做题单元",
            description: "题目训练",
            unit_type: "quiz" as const,
            order_index: 1,
            level_title: "第一关：产品定位",
            level_description: "先确认产品定位。",
            locked: false,
            lock_reason: null,
            status: "completed" as const,
            completion_rule: "passed" as const,
            primary_action_label: "开始做题",
            retry_action_label: "重练本关",
            review_action_label: "查看结果",
            target_path: "/sales-trainer/quiz/quiz-unit",
            latest_result: {
                status: "scored",
                passed: true,
                score: 10,
                max_score: 10,
                submitted_at: "2026-05-28T00:00:00Z",
                result_id: "attempt-1",
                target_path: "/sales-trainer/quiz/result/attempt-1",
            },
        },
        {
            unit_id: "audio-unit",
            name: "录音单元",
            description: "录音训练",
            unit_type: "audio_scoring" as const,
            order_index: 2,
            level_title: "第二关：录音表达",
            level_description: "上传讲解录音。",
            locked: false,
            lock_reason: null,
            status: "available" as const,
            completion_rule: "passed" as const,
            primary_action_label: "上传语音作业",
            retry_action_label: "重练本关",
            review_action_label: "查看结果",
            target_path: "/sales-trainer/audio/audio-unit",
            latest_result: null,
        },
    ],
};

describe("SalesTrainerPage", () => {
    beforeEach(() => {
        listPathsMock.mockReset();
        listUnitsMock.mockResolvedValue({
            items: baseUnits,
            total: baseUnits.length,
        });
        listPathsMock.mockResolvedValue({ items: [], total: 0 });
    });

    it("shows quiz and audio entries from the catalog fallback when no paths exist", async () => {
        listUnitsMock.mockResolvedValue({
            items: baseUnits.slice(0, 2),
            total: 2,
        });

        render(<SalesTrainerPage />);

        await waitFor(() => {
            expect(listUnitsMock).toHaveBeenCalled();
        });

        expect(screen.getByRole("link", { name: /开始做题/ }).getAttribute("href")).toBe("/sales-trainer/quiz/quiz-unit");
        expect(screen.getAllByRole("link", { name: /上传语音作业/ })[0].getAttribute("href")).toBe("/sales-trainer/audio/audio-unit");
        expect(screen.getByText("语音作业")).toBeTruthy();
    });

    it("shows path-first layout without score_basis and hides full catalog grids", async () => {
        listPathsMock.mockResolvedValue({
            items: [basePath],
            total: 1,
        });

        render(<SalesTrainerPage />);

        expect(await screen.findByText("新人销售闯关")).toBeTruthy();
        expect(screen.getByText("掌握首次客户沟通")).toBeTruthy();
        expect(screen.getByText("1/2")).toBeTruthy();
        expect(screen.getByText("当前要练")).toBeTruthy();
        expect(screen.getAllByText("下一关：第二关：录音表达").length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText(/已完成 1 次有效训练/)).toBeTruthy();
        expect(screen.getByText(/本关需达到 75 分通过，可多次上传，以最新一次为准/)).toBeTruthy();
        expect(screen.getByText(/本关还没有训练证据。/)).toBeTruthy();
        expect(screen.queryByText("sales_trainer_path_projection_v1")).toBeNull();
        expect(screen.queryByText("目标证据")).toBeNull();
        expect(screen.queryByText("下一步依据")).toBeNull();
        expect(screen.queryByText("剩余关卡")).toBeNull();
        expect(screen.queryByRole("heading", { name: "做题训练" })).toBeNull();
        expect(screen.getByText("更多练习（1）")).toBeTruthy();
        expect(screen.getAllByRole("link", { name: /上传语音作业/ })[0].getAttribute("href")).toBe("/sales-trainer/audio/audio-unit");
    });

    it("shows read-chapter link when unit has learner config", async () => {
        listPathsMock.mockResolvedValue({
            items: [basePath],
            total: 1,
        });

        render(<SalesTrainerPage />);

        expect(await screen.findByRole("link", { name: "阅读本章" })).toBeTruthy();
        expect(screen.getByRole("link", { name: "阅读本章" }).getAttribute("href")).toBe(
            "/sales-trainer/learn/quiz-unit",
        );
    });

    it("shows three-module grid instead of level timeline", async () => {
        const modulePath = {
            ...basePath,
            path_key: "new_seller_modules_v1",
            title: "新人销售三模块训练",
            total_levels: 5,
            completed_levels: 0,
            levels: [
                {
                    ...basePath.levels[0],
                    unit_id: "ppt-unit",
                    order_index: 1,
                    level_title: "第1关：PPT演练",
                    target_path: "/sales-trainer/audio/ppt-unit",
                },
                {
                    ...basePath.levels[0],
                    unit_id: "hub-unit",
                    order_index: 2,
                    level_title: "第2关：拜访前商务",
                    target_path: "/sales-trainer/learn/hub",
                },
                {
                    ...basePath.levels[1],
                    unit_id: "audio-5",
                    order_index: 3,
                    level_title: "金字塔演讲 · 5 分钟",
                    target_path: "/sales-trainer/audio/audio-5",
                },
                {
                    ...basePath.levels[1],
                    unit_id: "audio-10",
                    order_index: 4,
                    level_title: "金字塔演讲 · 10 分钟",
                    target_path: "/sales-trainer/audio/audio-10",
                },
                {
                    ...basePath.levels[1],
                    unit_id: "audio-15",
                    order_index: 5,
                    level_title: "金字塔演讲 · 15 分钟",
                    target_path: "/sales-trainer/audio/audio-15",
                },
            ],
        };
        listPathsMock.mockResolvedValue({
            items: [modulePath],
            total: 1,
        });
        listUnitsMock.mockResolvedValue({
            items: [
                {
                    ...baseUnits[0],
                    unit_id: "ppt-unit",
                    unit_type: "audio_scoring",
                },
                ...baseUnits,
            ],
            total: baseUnits.length + 1,
        });

        render(<SalesTrainerPage />);

        expect(await screen.findByText("选择下方模块开始训练")).toBeTruthy();
        expect(screen.getByText("PPT演练")).toBeTruthy();
        expect(screen.getByText("拜访前商务")).toBeTruthy();
        expect(screen.getByText("金字塔演讲")).toBeTruthy();
        expect(screen.queryByText("当前要练")).toBeNull();
        expect(screen.queryByText("1/2")).toBeNull();
    });

    it("shows extra units only after expanding the collapsed section", async () => {
        listPathsMock.mockResolvedValue({
            items: [basePath],
            total: 1,
        });

        render(<SalesTrainerPage />);

        expect(await screen.findByText("更多练习（1）")).toBeTruthy();
        expect(screen.queryByText("额外练习")).toBeNull();

        fireEvent.click(screen.getByRole("button", { name: /更多练习（1）/ }));

        expect(await screen.findByText("额外练习")).toBeTruthy();
        expect(screen.getByRole("link", { name: /开始做题/ }).getAttribute("href")).toBe("/sales-trainer/quiz/extra-unit");
    });
});
