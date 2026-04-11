import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import EditPersonaPage from "./page";

const {
    backMock,
    pushMock,
    errorToastMock,
    getPersonaMock,
    getKnowledgeBasesMock,
    updatePersonaMock,
} = vi.hoisted(() => ({
    backMock: vi.fn(),
    pushMock: vi.fn(),
    errorToastMock: vi.fn(),
    getPersonaMock: vi.fn(),
    getKnowledgeBasesMock: vi.fn(),
    updatePersonaMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        back: backMock,
        push: pushMock,
    }),
    useParams: () => ({
        id: "persona-1",
    }),
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        error: errorToastMock,
        success: vi.fn(),
        showToast: vi.fn(),
    }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                getPersona: getPersonaMock,
                getKnowledgeBases: getKnowledgeBasesMock,
                updatePersona: updatePersonaMock,
            },
        },
    };
});

const basePersona = {
    id: "persona-1",
    name: "证据压测角色",
    description: "用于验证 pressure model 编辑。",
    category: "customer",
    difficulty: "hard",
    status: "active",
    system_prompt: "旧提示词",
    knowledge_base_ids: ["kb-1"],
    persona_policy: {
        version: 1,
        system_prompt: "你是强势采购负责人。",
        knowledge_base_ids: ["kb-1"],
        tool_policy: {
            require_kb_grounding: true,
            network_access_mode: "off",
            enable_internal_retrieval: true,
        },
        sales_focus: "proof",
        value_axes: ["ROI", "客户收益"],
        objection_axes: ["价格", "实施风险"],
        expected_customer_questions: ["你拿什么证明这个 ROI 不是口号？"],
        customer_pressure: {
            source: "explicit",
            pressure_direction: {
                sales_focus: "proof",
                value_axes: ["ROI", "客户收益"],
                objection_axes: ["价格", "实施风险"],
            },
            follow_up_behavior: {
                question_strategy: "single_issue",
                revisit_on_evasion: true,
                require_evidence: true,
                expected_customer_questions: ["你拿什么证明这个 ROI 不是口号？"],
            },
        },
    },
    created_at: "2026-03-24T00:00:00Z",
    updated_at: "2026-03-24T00:00:00Z",
    tts_config: {
        voice: "zh-CN-XiaoxiaoNeural",
        rate: "+0%",
        volume: "+0%",
        pitch: "+0Hz",
    },
};

describe("EditPersonaPage", () => {
    beforeEach(() => {
        backMock.mockReset();
        pushMock.mockReset();
        errorToastMock.mockReset();
        getPersonaMock.mockReset();
        getKnowledgeBasesMock.mockReset();
        updatePersonaMock.mockReset();

        getPersonaMock.mockResolvedValue(basePersona);
        getKnowledgeBasesMock.mockResolvedValue({
            items: [
                {
                    id: "kb-1",
                    name: "石犀产品资料库",
                    description: "主资料库",
                    category: "product",
                    status: "active",
                    document_count: 2,
                    total_chunks: 8,
                    created_at: "2026-03-24T00:00:00Z",
                    updated_at: "2026-03-24T00:00:00Z",
                },
                {
                    id: "kb-2",
                    name: "案例证据库",
                    description: "案例补充",
                    category: "case",
                    status: "active",
                    document_count: 4,
                    total_chunks: 12,
                    created_at: "2026-03-24T00:00:00Z",
                    updated_at: "2026-03-24T00:00:00Z",
                },
            ],
        });
        updatePersonaMock.mockResolvedValue(basePersona);
    });

    it("uses toast validation feedback instead of blocking alert dialogs when required fields are missing", async () => {
        render(<EditPersonaPage />);

        await screen.findByText("当前 Persona 压力模型");

        fireEvent.change(screen.getByPlaceholderText("例如：急躁的CEO"), {
            target: { value: "   " },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存" }));

        expect(updatePersonaMock).not.toHaveBeenCalled();
        expect(errorToastMock).toHaveBeenCalledWith("请输入角色名称");
    });

    it("renders the current pressure model for inspection", async () => {
        render(<EditPersonaPage />);

        expect(await screen.findByText("当前 Persona 压力模型")).toBeTruthy();
        expect((screen.getByLabelText("主压测方向") as HTMLSelectElement).value).toBe("proof");
        expect((screen.getByLabelText("追问策略") as HTMLSelectElement).value).toBe("single_issue");
        expect((screen.getByLabelText("价值维度") as HTMLTextAreaElement).value).toBe("ROI\n客户收益");
        expect((screen.getByLabelText("异议维度") as HTMLTextAreaElement).value).toBe("价格\n实施风险");
        expect((screen.getByLabelText("示例追问") as HTMLTextAreaElement).value).toBe("你拿什么证明这个 ROI 不是口号？");
        expect(screen.getByText("当前 pressure model 已具备可冻结的显式结构；保存后，runtime snapshot 可以直接审计这些字段。")).toBeTruthy();
    });

    it("saves the nested customer pressure contract back into persona_policy", async () => {
        render(<EditPersonaPage />);

        await screen.findByText("当前 Persona 压力模型");

        fireEvent.change(screen.getByLabelText("主压测方向"), {
            target: { value: "price" },
        });
        fireEvent.change(screen.getByLabelText("价值维度"), {
            target: { value: "预算优先级\n客户收益" },
        });
        fireEvent.change(screen.getByLabelText("异议维度"), {
            target: { value: "价格\n竞品替代" },
        });
        fireEvent.change(screen.getByLabelText("追问策略"), {
            target: { value: "progressive_follow_up" },
        });
        fireEvent.click(screen.getByLabelText("回避时继续追问"));
        fireEvent.change(screen.getByLabelText("示例追问"), {
            target: { value: "如果预算卡死，你怎么证明这笔钱值？" },
        });
        fireEvent.click(screen.getByRole("button", { name: "保存" }));

        await waitFor(() => {
            expect(updatePersonaMock).toHaveBeenCalledTimes(1);
        });

        expect(updatePersonaMock).toHaveBeenCalledWith(
            "persona-1",
            expect.objectContaining({
                name: "证据压测角色",
                knowledge_base_ids: ["kb-1"],
                persona_policy: expect.objectContaining({
                    system_prompt: "你是强势采购负责人。",
                    knowledge_base_ids: ["kb-1"],
                    sales_focus: "price",
                    value_axes: ["预算优先级", "客户收益"],
                    objection_axes: ["价格", "竞品替代"],
                    expected_customer_questions: ["如果预算卡死，你怎么证明这笔钱值？"],
                    customer_pressure: expect.objectContaining({
                        source: "explicit",
                        pressure_direction: expect.objectContaining({
                            sales_focus: "price",
                            value_axes: ["预算优先级", "客户收益"],
                            objection_axes: ["价格", "竞品替代"],
                        }),
                        follow_up_behavior: expect.objectContaining({
                            question_strategy: "progressive_follow_up",
                            revisit_on_evasion: false,
                            require_evidence: true,
                            expected_customer_questions: ["如果预算卡死，你怎么证明这笔钱值？"],
                        }),
                    }),
                    tool_policy: expect.objectContaining({
                        require_kb_grounding: true,
                        network_access_mode: "off",
                        enable_internal_retrieval: true,
                    }),
                }),
            }),
        );
        expect(pushMock).toHaveBeenCalledWith("/admin/personas");
    });

    it("routes save failures through toast feedback while keeping the editor on the page", async () => {
        updatePersonaMock.mockRejectedValueOnce(new Error("后端异常"));

        render(<EditPersonaPage />);

        await screen.findByText("当前 Persona 压力模型");
        fireEvent.click(screen.getByRole("button", { name: "保存" }));

        await waitFor(() => {
            expect(updatePersonaMock).toHaveBeenCalledTimes(1);
        });

        expect(errorToastMock).toHaveBeenCalledWith("保存失败: 后端异常");
        expect(pushMock).not.toHaveBeenCalled();
    });
});
