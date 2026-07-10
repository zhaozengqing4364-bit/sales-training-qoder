import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CustomerFaqLearningTopicPage from "./page";

const { getCustomerFaqTopicMock, submitShortAnswerAttemptMock } = vi.hoisted(() => ({
    getCustomerFaqTopicMock: vi.fn(),
    submitShortAnswerAttemptMock: vi.fn(),
}));

vi.mock("next/link", () => ({
    default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a>,
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children }: { children: ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, asChild: _asChild, isLoading: _isLoading, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean; isLoading?: boolean }) => (
        <button type="button" {...props}>{children}</button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            newcomerTraining: {
                ...actual.api.newcomerTraining,
                getCustomerFaqTopic: getCustomerFaqTopicMock,
                submitCustomerFaqShortAnswerAttempt: submitShortAnswerAttemptMock,
            },
        },
    };
});

function customerFaqTopicFixture() {
    return {
        topic_key: "customer_faq",
        title: "客户常见问答",
        description: "学习客户常见问题的标准回答。",
        revision_id: "topic-rev-1",
        revision_no: 2,
        audio_scenario_key: "customer_faq_oral_drill",
        quiz_paper_id: null,
        ai_coach: null,
        duplicate_groups: [],
        evidence_cases: [{
            case_key: "case_shenzhen_air",
            title: "深圳航空",
            summary: "先完成 POC 后确认采购范围。",
            source_question_numbers: [3],
        }],
        units: [
            learningUnit({
                unitKey: "company_value",
                title: "公司与核心价值",
                sourceCardKeys: ["customer_faq_q001"],
            }),
            learningUnit({
                unitKey: "deployment",
                title: "部署与架构",
                sourceCardKeys: ["customer_faq_q003"],
                orderIndex: 2,
            }),
        ],
        cards: [
            faqCard({
                cardKey: "customer_faq_q001",
                question: "石犀科技公司是做什么的？",
                shortAnswer: "石犀科技是一家专注于数据流动治理的平台提供商。",
            }),
            faqCard({
                cardKey: "customer_faq_q003",
                question: "价格是多少？",
                shortAnswer: "价格需要根据客户 API 数量、部署范围、服务要求正式报价。",
                escalationRequired: true,
                difficultyLevel: "high_risk",
            }),
        ],
    };
}

function learningUnit({
    orderIndex = 1,
    sourceCardKeys,
    title,
    unitKey,
}: {
    orderIndex?: number;
    sourceCardKeys: string[];
    title: string;
    unitKey: string;
}) {
    return {
        unit_key: unitKey,
        title,
        description: `${title}相关客户问答。`,
        order_index: orderIndex,
        enabled: true,
        source_chapter_orders: [],
        source_card_keys: sourceCardKeys,
        capability_keys: ["customer_perspective"],
        unlock_after_unit_keys: [],
        require_reading: true,
        require_quiz: true,
        require_ai_coach: false,
        quiz_question_count: 1,
        quiz_pass_threshold: 80,
        quiz_allow_retake: true,
        quiz_max_attempts: null,
        quiz_question_type_weights: {},
        allow_skip_reading: true,
        block_next_until_complete: false,
        empty_state_message: null,
    };
}

function faqCard({
    cardKey,
    difficultyLevel = "newcomer",
    escalationRequired = false,
    question,
    shortAnswer,
}: {
    cardKey: string;
    difficultyLevel?: "newcomer" | "advanced" | "high_risk";
    escalationRequired?: boolean;
    question: string;
    shortAnswer: string;
}) {
    return {
        card_key: cardKey,
        source_question_number: 1,
        question,
        short_answer: shortAnswer,
        detailed_answer: `${shortAnswer} 详细说明。`,
        scenario: "初次拜访",
        category: "产品能力",
        customer_intent: "了解公司定位",
        key_points: ["讲清公司定位"],
        evidence_cases: [],
        forbidden_claims: escalationRequired ? ["不要直接承诺固定价格。"] : [],
        escalation_required: escalationRequired,
        difficulty_level: difficultyLevel,
        tags: ["新人必会"],
        duplicate_group_key: null,
        status: "published",
    };
}

describe("CustomerFaqLearningTopicPage", () => {
    beforeEach(() => {
        getCustomerFaqTopicMock.mockReset();
        submitShortAnswerAttemptMock.mockReset();
        getCustomerFaqTopicMock.mockResolvedValue(customerFaqTopicFixture());
        submitShortAnswerAttemptMock.mockResolvedValue({
            topic_key: "customer_faq",
            learning_unit_key: "company_value",
            learning_unit_title: "公司与核心价值",
            total_score: 86,
            max_score: 100,
            passed: true,
            pass_threshold: 80,
            answers: [{
                card_key: "customer_faq_q001",
                question: "石犀科技公司是做什么的？",
                answer_text: "石犀科技是一家专注于数据流动治理的平台。",
                score: 86,
                max_score: 100,
                passed: true,
                feedback: "回答覆盖公司定位，可以补充总部和团队规模。",
                reason: "covered_core_answer",
                scoring_source: "ai_llm",
                scoring_provider: "fake",
                scoring_model: "unit-test",
                scoring_latency_ms: 12,
            }],
        });
    });

    it("renders customer FAQ as unit learning instead of recording practice", async () => {
        render(<CustomerFaqLearningTopicPage />);

        expect(await screen.findByText("客户常见问答")).toBeTruthy();
        expect(screen.getAllByText("公司与核心价值").length).toBeGreaterThan(0);
        expect(screen.getByText("训练路径")).toBeTruthy();
        expect(screen.getByText("本单元学习")).toBeTruthy();
        expect(screen.getByText("客户会这样问")).toBeTruthy();
        expect(screen.queryByLabelText("回答：石犀科技公司是做什么的？")).toBeNull();
        expect(screen.queryByText("口播演练")).toBeNull();
        expect(screen.queryByText("录音练习")).toBeNull();
    });

    it("submits a unit short-answer quiz and renders AI score feedback", async () => {
        render(<CustomerFaqLearningTopicPage />);

        fireEvent.click(await screen.findByRole("button", { name: /开始简答小测/ }));
        expect(screen.getByRole("dialog", { name: "公司与核心价值 · 简答小测" })).toBeTruthy();

        const answerBox = screen.getByLabelText("回答：石犀科技公司是做什么的？");
        fireEvent.change(answerBox, {
            target: { value: "石犀科技是一家专注于数据流动治理的平台。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "提交简答小测" }));

        await waitFor(() => {
            expect(submitShortAnswerAttemptMock).toHaveBeenCalledWith("company_value", {
                answers: [{
                    card_key: "customer_faq_q001",
                    answer_text: "石犀科技是一家专注于数据流动治理的平台。",
                }],
            });
        });
        expect(await screen.findByText("86 / 100")).toBeTruthy();
        expect(screen.getByText("回答覆盖公司定位，可以补充总部和团队规模。")).toBeTruthy();
    });
});
