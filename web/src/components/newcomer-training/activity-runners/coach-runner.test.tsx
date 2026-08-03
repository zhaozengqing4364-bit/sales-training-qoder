import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
    FoundationActivityWorkspace,
    FoundationCoachCard,
} from "@/lib/api/types/newcomer-training";
import { toActivityViewModel } from "@/lib/newcomer-training/view-models";
import { CoachRunner } from "./coach-runner";

const { executeCommandMock, getActivityMock } = vi.hoisted(() => ({
    executeCommandMock: vi.fn(),
    getActivityMock: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
    api: {
        newcomerTraining: {
            executeCommand: executeCommandMock,
            getActivity: getActivityMock,
        },
    },
    getApiErrorMessage: (cause: unknown) => cause instanceof Error ? cause.message : "请求失败",
}));
vi.mock("@/lib/newcomer-training/ux-events", () => ({ trackFoundationUxEvent: vi.fn() }));

const choiceCard: FoundationCoachCard = {
    card_id: "card-1",
    card_type: "single_choice",
    prompt: "面对模糊需求时，第一步怎么做？",
    options: [
        { option_id: "confirm", text: "澄清场景和影响" },
        { option_id: "promise", text: "立即承诺全部能力" },
    ],
    sources: ["需求发现方法"],
};

function workspace({
    status = "awaiting_answer",
    card = choiceCard,
}: {
    status?: "awaiting_answer" | "failed_recoverable" | "needs_human_help";
    card?: FoundationCoachCard | null;
} = {}): FoundationActivityWorkspace {
    return {
        contract_version: "activity_workspace_v1",
        generated_at: "2026-07-17T09:00:00Z",
        data_freshness: "fresh",
        capabilities: ["view_activity", "execute_activity"],
        enrollment_version: 3,
        activity: {
            id: "coach-foundation-remediation",
            type: "ai_coach",
            title: "完成结构化能力补练",
            objective: "巩固理解、表达和销售场景迁移",
            why_it_matters: "进入客户场景前补齐关键能力",
            steps: ["识别与理解", "组织与表达", "销售场景迁移"],
            success_criteria: ["三个检查点达到配置的掌握标准"],
            estimated_minutes: 35,
        },
        attempt: {
            attempt_id: "attempt-1",
            organization_id: "org-1",
            enrollment_id: "enrollment-1",
            path_revision_id: "path-1",
            activity_id: "coach-foundation-remediation",
            activity_type: "ai_coach",
            attempt_no: 1,
            status: "in_progress",
            version: 2,
            task_id: null,
            outcome_id: null,
        },
        runner: {
            kind: "ai_coach",
            detail_id: "session-1",
            status,
            version: 7,
            profile_title: "新人销售基础能力结构化教练",
            checkpoint: {
                current: 1,
                total: 3,
                title: "识别与理解",
                objective: "准确识别客户问题和方法边界",
            },
            progress: { completed_cards: 0, total_cards: 3 },
            source_context: [
                { label: "需求发现方法", resource_type: "learning_unit" },
            ],
            weaknesses: [
                { competency_key: "needs_discovery", summary: "需求澄清仍需巩固", confidence: 1 },
            ],
            current_card: card,
            last_feedback: null,
            assistance: null,
            mastery: {
                threshold_percent: 82,
                cycle: 0,
                maximum_automatic_cycles: 2,
            },
            failure: status === "failed_recoverable" ? {
                stage: "answer_evaluation",
                message: "反馈生成失败，可稍后重试。",
                answer_preserved: true,
            } : null,
            human_help: status === "needs_human_help" ? {
                title: "需要培训负责人协助",
                message: "自动补练已到边界。",
                status: "open",
                next_action: null,
            } : null,
        },
        task: null,
        outcome: null,
        available_commands: status === "awaiting_answer"
            ? ["submit_coach_answer", "request_coach_assistance", "cancel"]
            : status === "failed_recoverable" ? ["retry_coach", "cancel"] : ["cancel"],
        recovery: {
            input_preserved: true,
            refresh_on_version_conflict: true,
            retry_from_current_activity: true,
        },
    };
}

describe("CoachRunner", () => {
    beforeEach(() => {
        executeCommandMock.mockReset();
        getActivityMock.mockReset();
    });

    it("submits the typed current card with the frozen runner version", async () => {
        const detail = workspace();
        executeCommandMock.mockResolvedValue(detail);
        render(<CoachRunner detail={toActivityViewModel(detail)} />);

        expect(screen.getByText("检查点 1 / 3")).toBeTruthy();
        expect(screen.getByText((_, element) => (
            element?.tagName === "P"
            && element.textContent?.includes("达到 82% 掌握度；最多自动补练 2 轮。") === true
        ))).toBeTruthy();
        expect(screen.queryByPlaceholderText(/聊天/)).toBeNull();

        fireEvent.click(screen.getByRole("radio", { name: "澄清场景和影响" }));
        fireEvent.click(screen.getByRole("button", { name: "提交当前回答" }));

        await waitFor(() => expect(executeCommandMock).toHaveBeenCalledTimes(1));
        expect(executeCommandMock.mock.calls[0][1]).toMatchObject({
            command_type: "submit_coach_answer",
            attempt_id: "attempt-1",
            expected_attempt_version: 7,
            payload: {
                card_id: "card-1",
                answer: { answer_type: "choice", selected_option_ids: ["confirm"] },
            },
        });
        expect(executeCommandMock.mock.calls[0][1].payload.client_token).toBeTruthy();
    });

    it.each([
        ["multiple_choice", {
            ...choiceCard,
            card_type: "multiple_choice",
        } as FoundationCoachCard, "checkbox"],
        ["ordering", {
            card_id: "ordering",
            card_type: "ordering",
            prompt: "排列步骤",
            items: [{ item_id: "a", text: "澄清" }, { item_id: "b", text: "回应" }],
            sources: ["异议处理方法"],
        } as FoundationCoachCard, "button"],
        ["short_answer_rewrite", {
            card_id: "rewrite", card_type: "short_answer_rewrite", prompt: "改写回答",
            instruction: "用客户语言改写", sources: ["价值表达方法"],
        } as FoundationCoachCard, "textbox"],
        ["key_points_completion", {
            card_id: "points", card_type: "key_points_completion", prompt: "补全要点",
            hints: ["目标"], sources: ["客户理解方法"],
        } as FoundationCoachCard, "textbox"],
        ["example_comparison", {
            card_id: "compare", card_type: "example_comparison", prompt: "比较示例",
            examples: ["示例甲", "示例乙"], comparison_criteria: ["依据"], sources: ["沟通结构方法"],
        } as FoundationCoachCard, "textbox"],
        ["summary", {
            card_id: "summary", card_type: "summary", prompt: "总结方法",
            scope: "总结本检查点", sources: ["流程与合规方法"],
        } as FoundationCoachCard, "textbox"],
    ] as const)("renders the whitelisted %s card with semantic controls", (_type, card, role) => {
        render(<CoachRunner detail={toActivityViewModel(workspace({ card }))} />);
        expect(screen.getAllByRole(role).length).toBeGreaterThan(0);
    });

    it("states that a saved answer survived evaluation failure and offers retry", () => {
        render(<CoachRunner detail={toActivityViewModel(workspace({ status: "failed_recoverable", card: null }))} />);
        expect(screen.getByRole("alert").textContent).toContain("已提交回答仍然保留");
        expect(screen.getByRole("button", { name: "重试当前步骤" })).toBeTruthy();
    });

    it("shows the bounded human-help outcome instead of another automatic card", () => {
        render(<CoachRunner detail={toActivityViewModel(workspace({ status: "needs_human_help", card: null }))} />);
        expect(screen.getByText("需要培训负责人协助")).toBeTruthy();
        expect(screen.getByText("自动补练已到边界。")).toBeTruthy();
        expect(screen.queryByRole("button", { name: "开始针对性补练" })).toBeNull();
    });

    it("labels AI feedback as an inference rather than a verified fact", () => {
        const detail = workspace();
        if (detail.runner.kind !== "ai_coach") throw new Error("expected coach runner");
        detail.runner.last_feedback = {
            card_id: "card-1",
            mastered: false,
            evaluation_kind: "ai",
            feedback: "回答结构基本完整，但仍需人工结合上下文判断。",
        };
        render(<CoachRunner detail={toActivityViewModel(detail)} />);
        expect(screen.getByText("结果来源：语言理解评估（AI 推断）")).toBeTruthy();
    });

    it("preserves an unfinished answer when the same card receives a fresh projection", () => {
        const card: FoundationCoachCard = {
            card_id: "rewrite-stable",
            card_type: "short_answer_rewrite",
            prompt: "请改写价值表达",
            instruction: "用客户语言改写",
            sources: ["价值表达方法"],
        };
        const rendered = render(<CoachRunner detail={toActivityViewModel(workspace({ card }))} />);
        const answer = screen.getByRole("textbox", { name: "用客户语言改写" }) as HTMLTextAreaElement;
        fireEvent.change(answer, { target: { value: "先说明客户目标，再说明业务价值。" } });

        rendered.rerender(
            <CoachRunner detail={toActivityViewModel(workspace({ card: { ...card } }))} />,
        );

        expect((screen.getByRole("textbox", { name: "用客户语言改写" }) as HTMLTextAreaElement).value).toBe(
            "先说明客户目标，再说明业务价值。",
        );
        expect(rendered.container.querySelector(".min-h-0.overflow-y-auto")).toBeTruthy();
        expect(screen.getByLabelText("当前训练操作")).toBeTruthy();
    });
});
