import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { generateDraftsMock, getModelConfigsMock, getPromptTemplatesMock } = vi.hoisted(() => ({
    generateDraftsMock: vi.fn(),
    getModelConfigsMock: vi.fn(),
    getPromptTemplatesMock: vi.fn(),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
}));

vi.mock("@/components/ui/confirm-dialog", () => ({
    ConfirmDialog: ({
        open,
        title,
        description,
        confirmText,
        cancelText,
        onConfirm,
        onOpenChange,
    }: {
        open: boolean;
        title: string;
        description: string;
        confirmText?: string;
        cancelText?: string;
        onConfirm: () => void;
        onOpenChange: (open: boolean) => void;
    }) => (
        open ? (
            <div role="dialog" aria-label={title}>
                <p>{description}</p>
                <button type="button" onClick={() => onOpenChange(false)}>
                    {cancelText ?? "取消"}
                </button>
                <button type="button" onClick={onConfirm}>
                    {confirmText ?? "确认"}
                </button>
            </div>
        ) : null
    ),
}));

vi.mock("next/link", () => ({
    default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
        <a href={href} {...props}>{children}</a>
    ),
}));

vi.mock("@/lib/debug", () => ({
    debug: { error: vi.fn() },
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getModelConfigs: getModelConfigsMock,
                getPromptTemplates: getPromptTemplatesMock,
                salesTrainer: {
                    ...actual.api.admin.salesTrainer,
                    generateBusinessEtiquetteQuestionDrafts: generateDraftsMock,
                },
            },
        },
    };
});

import { BusinessEtiquetteQuestionDraftPanel } from "./question-generation-panel";

const promptTemplate = {
    id: "prompt-business-etiquette-v1",
    name: "商务礼仪题目草稿生成 v1",
    prompt_type: "scoring",
    business_purpose: "business_etiquette_question_generation",
    category: "business_etiquette",
    template: "template",
    variables: [],
    is_active: true,
    is_default: true,
    is_system: false,
    created_at: "2026-06-15T00:00:00Z",
    updated_at: "2026-06-15T00:00:00Z",
} as const;

const llmConfig = {
    id: "llm-config-1",
    name: "商务礼仪出题模型",
    model_type: "llm",
    provider: "openai",
    model_name: "gpt-question",
    is_default: true,
    is_active: true,
    last_test_status: "success",
} as const;

const genericPromptTemplate = {
    ...promptTemplate,
    id: "prompt-generic-summary",
    name: "Sales Conversation Summary",
    category: "sales",
    prompt_type: "summary",
    business_purpose: undefined,
    is_default: true,
} as const;

const aiCoachQuestionTemplate = {
    ...promptTemplate,
    id: "prompt-ai-coach-question",
    name: "旧版商务礼仪题目生成模板",
    category: "sales_trainer_ai_coach",
    prompt_type: "stage",
    business_purpose: "business_etiquette_question_generation",
    is_default: false,
} as const;

describe("BusinessEtiquetteQuestionDraftPanel", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getPromptTemplatesMock.mockImplementation(async (params?: {
            business_purpose?: string;
            category?: string;
        }) => {
            if (params?.business_purpose === "business_etiquette_question_generation") {
                return [promptTemplate];
            }
            if (params?.category === "business_etiquette") return [promptTemplate];
            if (params?.category === "sales_trainer_ai_coach") return [];
            if (params?.category === "sales_trainer") return [];
            return [];
        });
        getModelConfigsMock.mockResolvedValue({
            llm: [llmConfig],
            embedding: [],
            asr: [],
            tts: [],
            total: 1,
        });
        generateDraftsMock.mockResolvedValue({
            batch_id: "batch-12345678",
            items: [],
            total: 3,
        });
    });

    it("renders a business etiquette draft trigger for the selected chapter", () => {
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        expect(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ })).toBeTruthy();
    });

    it("requires a prompt template before generation when no active template exists", async () => {
        getPromptTemplatesMock.mockResolvedValue([]);
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        fireEvent.click(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ }));
        await waitFor(() => {
            expect(screen.queryByText(/正在加载模板和模型配置/)).toBeNull();
        });
        fireEvent.click(screen.getByRole("button", { name: /生成待审核草稿/ }));

        expect(screen.getByText(/请先选择商务礼仪题目生成 Prompt 模板/)).toBeTruthy();
        expect(generateDraftsMock).not.toHaveBeenCalled();
    });

    it("loads selectable prompt templates and LLM model configs", async () => {
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        fireEvent.click(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ }));

        expect((await screen.findByRole("link", { name: /管理 Prompt 模板/ })).getAttribute("href")).toBe(
            "/admin/prompts",
        );
        expect(screen.getByRole("link", { name: /新建题目生成模板/ }).getAttribute("href")).toBe(
            `/admin/prompts/new?category=business_etiquette&prompt_type=scoring&name=${encodeURIComponent("商务礼仪题目草稿生成 v1")}&business_purpose=business_etiquette_question_generation`,
        );
        expect(screen.getByRole("link", { name: /新建 AI 教练系统提示词/ }).getAttribute("href")).toBe(
            `/admin/prompts/new?category=sales_trainer_ai_coach&prompt_type=stage&name=${encodeURIComponent("新人训练路径商务技巧 AI 对话教练生成 v1")}&business_purpose=ai_coach_conversation_generation`,
        );
        expect(screen.getByRole("link", { name: /管理模型配置/ }).getAttribute("href")).toBe(
            "/admin/settings",
        );
        const promptSelect = screen.getByRole("combobox", { name: /Prompt 模板/ }) as HTMLSelectElement;
        const modelSelect = screen.getByRole("combobox", { name: /LLM 模型配置/ }) as HTMLSelectElement;
        expect(promptSelect.value).toBe("prompt-business-etiquette-v1");
        expect(modelSelect.value).toBe("llm-config-1");
        expect(getPromptTemplatesMock).toHaveBeenCalledWith({
            business_purpose: "business_etiquette_question_generation",
            is_active: true,
        });
        expect(getModelConfigsMock).toHaveBeenCalledTimes(1);
    });

    it("does not auto-select generic fallback prompt templates", async () => {
        getPromptTemplatesMock.mockImplementation(async (params?: {
            business_purpose?: string;
            category?: string;
        }) => {
            if (params?.business_purpose === "business_etiquette_question_generation") return [];
            if (params?.category === "sales_trainer") return [genericPromptTemplate];
            return [];
        });
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        fireEvent.click(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ }));

        await screen.findByText(/未找到商务礼仪题目生成专用模板/);
        const promptSelect = screen.getByRole("combobox", { name: /Prompt 模板/ }) as HTMLSelectElement;
        expect(promptSelect.value).toBe("");
        expect(screen.queryByText(/Sales Conversation Summary/)).toBeNull();
        expect(promptSelect.options.length).toBe(1);
    });

    it("hides misclassified AI coach interaction templates from question generation", async () => {
        const misclassifiedTemplate = {
            ...aiCoachQuestionTemplate,
            id: "prompt-misclassified-ai-coach-card",
            template: "输出 {\"schema_version\":\"ai_coach_interaction_v1\"}，允许题型 {{ allowed_interaction_types }}",
        };
        getPromptTemplatesMock.mockImplementation(async (params?: {
            business_purpose?: string;
            category?: string;
        }) => {
            if (params?.business_purpose === "business_etiquette_question_generation") {
                return [misclassifiedTemplate];
            }
            return [];
        });
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        fireEvent.click(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ }));

        await screen.findByText(/未找到商务礼仪题目生成专用模板/);
        const promptSelect = screen.getByRole("combobox", { name: /Prompt 模板/ }) as HTMLSelectElement;
        expect(promptSelect.value).toBe("");
        expect(screen.queryByText(/旧版商务礼仪题目生成模板/)).toBeNull();
    });

    it("loads sales trainer AI coach question templates without showing coach conversation templates", async () => {
        const conversationTemplate = {
            ...aiCoachQuestionTemplate,
            id: "prompt-ai-coach-conversation",
            name: "新人训练路径商务技巧 AI 对话教练生成 v1",
            business_purpose: "ai_coach_conversation_generation",
        };
        getPromptTemplatesMock.mockImplementation(async (params?: {
            business_purpose?: string;
            category?: string;
        }) => {
            if (params?.business_purpose === "business_etiquette_question_generation") {
                return [aiCoachQuestionTemplate, conversationTemplate];
            }
            return [];
        });
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        fireEvent.click(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ }));

        const promptSelect = await screen.findByRole("combobox", { name: /Prompt 模板/ }) as HTMLSelectElement;
        expect(promptSelect.value).toBe("prompt-ai-coach-question");
        expect(screen.getByText(/旧版商务礼仪题目生成模板/)).toBeTruthy();
        expect(screen.queryByText(/新人训练路径商务技巧 AI 对话教练生成 v1/)).toBeNull();
    });

    it("uses structured business purpose even when the template name has no question keyword", async () => {
        const customPurposeTemplate = {
            ...aiCoachQuestionTemplate,
            id: "prompt-ai-coach-purpose-only",
            name: "自定义商务礼仪生成模板 A",
        };
        getPromptTemplatesMock.mockImplementation(async (params?: {
            business_purpose?: string;
            category?: string;
        }) => {
            if (params?.business_purpose === "business_etiquette_question_generation") {
                return [customPurposeTemplate];
            }
            return [];
        });
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        fireEvent.click(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ }));

        const promptSelect = await screen.findByRole("combobox", { name: /Prompt 模板/ }) as HTMLSelectElement;
        expect(promptSelect.value).toBe("prompt-ai-coach-purpose-only");
        expect(screen.getByText(/自定义商务礼仪生成模板 A/)).toBeTruthy();
        expect(screen.getAllByText(/商务礼仪题目生成/).length).toBeGreaterThan(0);
    });

    it("confirms cost/range and calls the business etiquette draft API", async () => {
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        fireEvent.click(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ }));
        await screen.findByRole("combobox", { name: /Prompt 模板/ });
        fireEvent.change(screen.getByPlaceholderText(/多个用英文逗号分隔/), {
            target: { value: "first_impression, meeting_etiquette" },
        });
        fireEvent.change(screen.getByPlaceholderText(/通常无需填写/), {
            target: { value: "{\"extra_config\":{\"temperature\":0.2}}" },
        });
        fireEvent.click(screen.getByRole("button", { name: /生成待审核草稿/ }));

        expect(screen.getByRole("dialog", { name: "确认生成题目草稿" })).toBeTruthy();
        expect(screen.getByText(/只写入草稿箱，不会直接发布或绑定给学员/)).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "确认生成" }));

        await waitFor(() => {
            expect(generateDraftsMock).toHaveBeenCalledWith({
                chapter_order: 2,
                prompt_template_id: "prompt-business-etiquette-v1",
                question_types: ["single_choice", "multiple_choice", "short_answer"],
                draft_count: 3,
                capability_keys: ["first_impression", "meeting_etiquette"],
                model_config: {
                    extra_config: { temperature: 0.2 },
                    model_config_id: "llm-config-1",
                },
                reason: "从学习内容详情页生成商务礼仪题目草稿",
            });
        });
    });

    it("shows next-step guidance and links to the draft inbox after generation", async () => {
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        fireEvent.click(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ }));
        await screen.findByRole("combobox", { name: /Prompt 模板/ });
        fireEvent.click(screen.getByRole("button", { name: /生成待审核草稿/ }));
        fireEvent.click(screen.getByRole("button", { name: "确认生成" }));

        await waitFor(() => {
            expect(screen.getByText(/已生成 3 道待审核草稿/)).toBeTruthy();
        });
        expect(screen.getByText(/去草稿箱审核 -> 转正式题库草稿 -> 发布题目\/组卷 -> 发布路径配置/)).toBeTruthy();
        expect(screen.getByRole("link", { name: /去题目草稿箱/ }).getAttribute("href")).toBe(
            "/admin/sales-trainer/questions/drafts?batch_id=batch-12345678",
        );
    });

    it("shows generation errors without falling back to generic test-bank APIs", async () => {
        generateDraftsMock.mockRejectedValueOnce(new Error("生成失败"));
        render(<BusinessEtiquetteQuestionDraftPanel chapterOrder={2} />);

        fireEvent.click(screen.getByRole("button", { name: /生成商务礼仪题目草稿/ }));
        await screen.findByRole("combobox", { name: /Prompt 模板/ });
        fireEvent.click(screen.getByRole("button", { name: /生成待审核草稿/ }));
        fireEvent.click(screen.getByRole("button", { name: "确认生成" }));

        await waitFor(() => {
            expect(screen.getByText(/生成失败/)).toBeTruthy();
        });
        expect(generateDraftsMock).toHaveBeenCalledTimes(1);
    });
});
