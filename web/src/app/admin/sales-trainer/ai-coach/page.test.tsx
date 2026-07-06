import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mockGetAiCoachConfig = vi.fn();
const mockGetAdminCapabilities = vi.fn();
const mockSaveAiCoachConfig = vi.fn();
const mockPublishAiCoachConfig = vi.fn();

vi.mock("next/navigation", () => ({
    usePathname: () => "/admin/sales-trainer/ai-coach",
}));

vi.mock("@/lib/api/client", () => ({
    api: {
        admin: {
            salesTrainer: {
                getCapabilities: (...args: unknown[]) => mockGetAdminCapabilities(...args),
            },
            newcomerTraining: {
                getAiCoachConfig: (...args: unknown[]) => mockGetAiCoachConfig(...args),
                saveAiCoachConfig: (...args: unknown[]) => mockSaveAiCoachConfig(...args),
                publishAiCoachConfig: (...args: unknown[]) => mockPublishAiCoachConfig(...args),
            },
        },
    },
    getApiErrorMessage: (error: unknown) =>
        error instanceof Error ? error.message : String(error),
}));

vi.mock("@/components/admin/admin-layout-shells", () => ({
    AdminPageHeader: ({
        title,
        description,
    }: {
        title: string;
        description: string;
    }) => (
        <header>
            <h1>{title}</h1>
            <p>{description}</p>
        </header>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({
        children,
        className,
    }: {
        children: ReactNode;
        className?: string;
    }) => <section className={className}>{children}</section>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({
        children,
        disabled,
        onClick,
        type = "button",
    }: {
        children: ReactNode;
        disabled?: boolean;
        onClick?: () => void;
        type?: "button" | "submit" | "reset";
    }) => (
        <button type={type} disabled={disabled} onClick={onClick}>
            {children}
        </button>
    ),
}));

import AdminAiCoachConfigPage from "./page";

const aiCoachConfig = {
    enabled: true,
    chat_enabled: true,
    streaming_enabled: true,
    entry_resume_policy: "latest_active_or_new",
    generation_timeout_seconds: 30,
    coach_mode: "mixed_drill",
    allowed_interaction_types: ["single_choice", "multiple_choice", "short_answer"],
    allowed_training_card_types: [
        "scenario_judgment",
        "expression_rewrite",
        "role_response",
    ],
    allowed_ui_event_types: [
        "quiz_card",
        "explanation_card",
        "summary_card",
        "followup_prompt",
    ],
    max_cards_per_message: 1,
    proactive_coaching_enabled: true,
    session_start_behavior: "plan_then_wait",
    auto_advance_enabled: true,
    max_auto_steps_per_session: 1,
    correct_streak_to_increase_difficulty: 2,
    incorrect_streak_to_remediate: 1,
    incorrect_streak_to_pause: 2,
    remediation_strategy: "explain_then_retry",
    summary_when_mastery_reached: true,
    allowed_next_actions: [
        "continue_drill",
        "increase_difficulty",
        "remediate",
        "switch_scenario",
        "summarize",
        "ask_user_choice",
        "end_session",
    ],
    chat_welcome_message: "你好，我是商务技巧 AI 教练。",
    empty_response_recovery_message: "我没有拿到可操作的训练卡片。",
    empty_response_recovery_prompts: ["继续下一题", "换个场景", "总结本轮"],
    generation_failure_recovery_message: "我已保留当前训练局。",
    generation_failure_recovery_prompts: ["重试下一题", "换主题", "总结一下"],
    min_turns: 3,
    max_turns: 10,
    mastery_threshold: 80,
    prompt_template_id: null,
    prompt_revision_id: null,
    prompt_contract_hash: null,
    scoring_prompt_template_id: "22222222-2222-2222-2222-222222222222",
    scoring_prompt_revision_id: null,
    scoring_contract_hash: null,
    output_schema_version: "ai_coach_interaction_v1",
};

describe("AdminAiCoachConfigPage", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        mockGetAdminCapabilities.mockResolvedValue({
            role: "admin",
            role_label: "管理员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: true,
                manage_questions: false,
                view_records: false,
                view_settings: false,
                view_logs: false,
            },
        });
        mockGetAiCoachConfig.mockResolvedValue(aiCoachConfig);
        mockSaveAiCoachConfig.mockResolvedValue({
            module_key: "business_skills",
            ai_coach: aiCoachConfig,
        });
        mockPublishAiCoachConfig.mockResolvedValue({
            module_key: "business_skills",
            active_revision_id: "revision-1",
            active_revision_no: 7,
            previous_revision_id: null,
            change_class: "minor",
            impact_scope: "future_learners_only",
        });
    });

    afterEach(() => {
        cleanup();
    });

    it("renders proactive coaching controls from backend config", async () => {
        render(<AdminAiCoachConfigPage />);

        expect(await screen.findByRole("heading", { name: "AI 教练配置" })).toBeTruthy();
        expect(await screen.findByText("主动教练闭环")).toBeTruthy();
        expect(screen.getByText("allowed_training_card_types")).toBeTruthy();
        expect((screen.getByLabelText(/场景判断卡/) as HTMLInputElement).checked).toBe(
            true,
        );
        expect((screen.getByLabelText(/启用主动教练/) as HTMLInputElement).checked).toBe(
            true,
        );
        expect((screen.getByLabelText(/答后自动推进/) as HTMLInputElement).checked).toBe(
            true,
        );
        expect((screen.getByLabelText(/启用流式训练体验/) as HTMLInputElement).checked).toBe(
            true,
        );
        expect(
            (screen.getByLabelText(/entry_resume_policy/) as HTMLSelectElement)
                .value,
        ).toBe("latest_active_or_new");
        expect(
            (screen.getByLabelText(/generation_timeout_seconds/) as HTMLInputElement)
                .value,
        ).toBe("30");
        expect(
            (screen.getByLabelText(/session_start_behavior/) as HTMLSelectElement)
                .value,
        ).toBe("plan_then_wait");
        expect(
            (screen.getByLabelText(/max_auto_steps_per_session/) as HTMLInputElement)
                .value,
        ).toBe("1");
    });

    it("fails closed before loading config without AI Coach management capability", async () => {
        mockGetAdminCapabilities.mockResolvedValue({
            role: "viewer",
            role_label: "只读成员",
            capabilities: {
                admin_full_access: false,
                manage_content: false,
                manage_modules: false,
                manage_prompts: false,
                manage_questions: false,
                view_records: true,
                view_settings: false,
                view_logs: false,
            },
        });

        render(<AdminAiCoachConfigPage />);

        expect(await screen.findByText("AI 教练配置权限不足")).toBeTruthy();
        expect(mockGetAiCoachConfig).not.toHaveBeenCalled();
        expect(mockSaveAiCoachConfig).not.toHaveBeenCalled();
        expect(mockPublishAiCoachConfig).not.toHaveBeenCalled();
        expect(screen.queryByRole("button", { name: /保存草稿/ })).toBeNull();
        expect(screen.queryByRole("button", { name: /发布/ })).toBeNull();
    });

    it("validates pause threshold before saving", async () => {
        const user = userEvent.setup();
        render(<AdminAiCoachConfigPage />);

        const pauseInput = await screen.findByLabelText(/incorrect_streak_to_pause/);
        await user.clear(pauseInput);
        await user.type(pauseInput, "0");

        expect(
            screen.getByText("incorrect_streak_to_pause 必须在 1-10 之间"),
        ).toBeTruthy();
        expect(
            (screen.getByRole("button", { name: /保存草稿/ }) as HTMLButtonElement)
                .disabled,
        ).toBe(true);
    });

    it("saves through the admin API client", async () => {
        const user = userEvent.setup();
        render(<AdminAiCoachConfigPage />);

        await screen.findByText("主动教练闭环");
        await user.click(screen.getByRole("button", { name: /保存草稿/ }));

        await waitFor(() => {
            expect(mockSaveAiCoachConfig).toHaveBeenCalledWith(
                "business_skills",
                expect.objectContaining({
                    proactive_coaching_enabled: true,
                    session_start_behavior: "plan_then_wait",
                    auto_advance_enabled: true,
                    streaming_enabled: true,
                    allowed_training_card_types: [
                        "scenario_judgment",
                        "expression_rewrite",
                        "role_response",
                    ],
                    entry_resume_policy: "latest_active_or_new",
                    generation_timeout_seconds: 30,
                    max_auto_steps_per_session: 1,
                    max_cards_per_message: 1,
                    empty_response_recovery_prompts: ["继续下一题", "换个场景", "总结本轮"],
                    generation_failure_recovery_prompts: ["重试下一题", "换主题", "总结一下"],
                }),
            );
        });
        expect(
            await screen.findByText("AI 教练配置已保存草稿。点击 发布 让其对未来学员生效。"),
        ).toBeTruthy();
    });
});
