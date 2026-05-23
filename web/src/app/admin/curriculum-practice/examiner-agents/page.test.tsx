import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ExaminerAgentFormPage } from "@/components/admin/curriculum-practice/examiner-agents/examiner-agent-form-page";
import { ExaminerAgentIndex } from "@/components/admin/curriculum-practice/examiner-agents/examiner-agent-index";

const listExaminerAgentsMock = vi.hoisted(() => vi.fn());
const createExaminerAgentMock = vi.hoisted(() => vi.fn());
const updateExaminerAgentMock = vi.hoisted(() => vi.fn());
const publishExaminerAgentMock = vi.hoisted(() => vi.fn());
const archiveExaminerAgentMock = vi.hoisted(() => vi.fn());
const duplicateExaminerAgentMock = vi.hoisted(() => vi.fn());
const getExaminerAgentTemplateReferencesMock = vi.hoisted(() => vi.fn());
const simulateExaminerAgentMock = vi.hoisted(() => vi.fn());
const getActiveScoringRulesetMock = vi.hoisted(() => vi.fn());
const getExaminerAgentMock = vi.hoisted(() => vi.fn());
const searchParamsState = vi.hoisted(() => ({ value: new URLSearchParams() }));

vi.mock("next/navigation", () => ({
    useRouter: () => ({ push: vi.fn() }),
    useSearchParams: () => searchParamsState.value,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({ success: vi.fn(), error: vi.fn(), showToast: vi.fn() }),
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                listExaminerAgents: listExaminerAgentsMock,
                createExaminerAgent: createExaminerAgentMock,
                updateExaminerAgent: updateExaminerAgentMock,
                publishExaminerAgent: publishExaminerAgentMock,
                archiveExaminerAgent: archiveExaminerAgentMock,
                duplicateExaminerAgent: duplicateExaminerAgentMock,
                getExaminerAgentTemplateReferences: getExaminerAgentTemplateReferencesMock,
                simulateExaminerAgent: simulateExaminerAgentMock,
                getActiveScoringRuleset: getActiveScoringRulesetMock,
                getExaminerAgent: getExaminerAgentMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: { warn: vi.fn() },
}));

const agent: import("@/lib/api/types").ExaminerAgentRecord = {
    examiner_agent_id: "ea-1",
    name: "销售入门考试",
    description: "初级销售能力评估",
    question_source_ids: ["cat-sales-basic"],
    learner_level_strategy: { default_level: "beginner", allowed_levels: ["beginner", "intermediate"] },
    scoring_policy_id: "sp-1",
    timeout_config: { max_seconds: 30 },
    safety_config: { enabled: true },
    prompt_config: { system_prompt: "评估销售能力" },
    simulation_config: { default_learner_level: "beginner" },
    status: "draft",
    version: 1,
    content_hash: null,
    created_at: "2026-05-16T00:00:00Z",
    updated_at: "2026-05-16T00:00:00Z",
    published_at: null,
};

const activeRuleset: import("@/lib/api/types").ScoringRulesetRecord = {
    ruleset_id: "ruleset-active-sales",
    scenario_type: "sales",
    version: "sales-active-v1",
    display_name: "Sales Active Ruleset",
    status: "published",
    definition: { scenario_type: "sales" },
    is_active: true,
    source: "admin",
};

describe("ExaminerAgentIndex", () => {
    beforeEach(() => {
        listExaminerAgentsMock.mockResolvedValue({ items: [agent], total: 1 });
        publishExaminerAgentMock.mockReset();
        archiveExaminerAgentMock.mockReset();
        duplicateExaminerAgentMock.mockReset();
        getExaminerAgentTemplateReferencesMock.mockResolvedValue({ items: [], total: 0 });
    });

    it("renders ExaminerAgent list", async () => {
        render(<ExaminerAgentIndex />);

        expect(await screen.findByRole("heading", { name: "考试智能体管理" })).toBeTruthy();
        expect(screen.getByText("销售入门考试")).toBeTruthy();
        expect(screen.getByText("草稿 · v1")).toBeTruthy();
    });

    it("shows publish gate failure reasons", async () => {
        publishExaminerAgentMock.mockRejectedValue(
            new (await import("@/lib/api/client")).ApiRequestError({
                status: 400,
                errorCode: "[EXAMINER_AGENT_PUBLISH_GATE_FAILED]",
                message: "ExaminerAgent 发布门禁未通过。",
                details: {
                    gate_results: [{
                        gate_name: "scoring_policy_reference",
                        status: "failed",
                        reason_code: "scoring_policy_missing",
                        message: "scoring_policy_id sp-1 does not exist or is not published.",
                    }],
                },
            }),
        );

        render(<ExaminerAgentIndex />);
        await screen.findByText("销售入门考试");
        fireEvent.click(screen.getByRole("button", { name: "发布" }));
        fireEvent.click(screen.getByRole("button", { name: "确认发布" }));

        await waitFor(() => {
            expect(screen.getByText(/ExaminerAgent 发布门禁未通过/)).toBeTruthy();
        });
    });

    it("does not offer edit action for published ExaminerAgents", async () => {
        listExaminerAgentsMock.mockResolvedValue({
            items: [{ ...agent, status: "published", content_hash: "sha256:ok" }],
            total: 1,
        });

        render(<ExaminerAgentIndex />);
        expect(await screen.findByText("已发布 · v1")).toBeTruthy();
        expect(screen.queryByRole("link", { name: "编辑" })).toBeNull();
        expect(screen.getByRole("button", { name: "复制为新草稿" })).toBeTruthy();
        expect(screen.getByText(/已发布内容不可修改/)).toBeTruthy();
    });
});

describe("ExaminerAgentFormPage", () => {
    beforeEach(() => {
        createExaminerAgentMock.mockReset();
        updateExaminerAgentMock.mockReset();
        getActiveScoringRulesetMock.mockResolvedValue(activeRuleset);
        getExaminerAgentMock.mockResolvedValue(agent);
    });

    it("creates a minimal ExaminerAgent from the form page", async () => {
        createExaminerAgentMock.mockResolvedValue({ ...agent, examiner_agent_id: "ea-2", name: "新考试" });

        render(<ExaminerAgentFormPage mode="create" />);

        fireEvent.change(screen.getByLabelText("名称"), { target: { value: "新考试" } });
        fireEvent.click(screen.getByRole("button", { name: "创建草稿" }));

        await waitFor(() => {
            expect(createExaminerAgentMock).toHaveBeenCalledWith(
                expect.objectContaining({ name: "新考试" }),
            );
        });
    });

    it("uses the active sales scoring ruleset for a new ExaminerAgent", async () => {
        createExaminerAgentMock.mockResolvedValue({ ...agent, name: "Active Ruleset Exam" });

        render(<ExaminerAgentFormPage mode="create" />);

        await waitFor(() => {
            expect((screen.getByLabelText("评分策略 ID") as HTMLInputElement).value).toBe("ruleset-active-sales");
        });
    });

    it("edits an existing ExaminerAgent from the edit page", async () => {
        updateExaminerAgentMock.mockResolvedValue({ ...agent, description: "编辑后描述" });

        render(<ExaminerAgentFormPage mode="edit" agentId="ea-1" />);
        await screen.findByLabelText("描述");

        fireEvent.change(screen.getByLabelText("描述"), { target: { value: "编辑后描述" } });
        fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

        await waitFor(() => {
            expect(updateExaminerAgentMock).toHaveBeenCalledWith(
                "ea-1",
                expect.objectContaining({ description: "编辑后描述" }),
            );
        });
    });

    it("shows JSON validation error for malformed config fields", async () => {
        render(<ExaminerAgentFormPage mode="create" />);

        fireEvent.change(screen.getByLabelText("名称"), { target: { value: "测试" } });
        fireEvent.change(screen.getByLabelText("安全配置 (JSON)"), {
            target: { value: "{invalid json" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建草稿" }));

        await waitFor(() => {
            expect(screen.getByText(/安全配置 JSON 格式错误/)).toBeTruthy();
        });
        expect(createExaminerAgentMock).not.toHaveBeenCalled();
    });
});
