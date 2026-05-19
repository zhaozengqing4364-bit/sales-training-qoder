import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminExaminerAgentsPage from "./page";

const listExaminerAgentsMock = vi.hoisted(() => vi.fn());
const createExaminerAgentMock = vi.hoisted(() => vi.fn());
const updateExaminerAgentMock = vi.hoisted(() => vi.fn());
const publishExaminerAgentMock = vi.hoisted(() => vi.fn());
const archiveExaminerAgentMock = vi.hoisted(() => vi.fn());
const simulateExaminerAgentMock = vi.hoisted(() => vi.fn());
const getActiveScoringRulesetMock = vi.hoisted(() => vi.fn());

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
                simulateExaminerAgent: simulateExaminerAgentMock,
                getActiveScoringRuleset: getActiveScoringRulesetMock,
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

const simulationResult: import("@/lib/api/types").ExaminerAgentSimulationResponse = {
    mode: "dry_run",
    mutates_records: false,
    examiner_agent_id: "ea-1",
    selected_question_id: "q-1",
    learner_level: "beginner",
    scoring_policy_id: "sp-1",
    timeout_seconds: 30,
    result: {
        score: 8.5,
        passed: true,
        feedback: "回答准确，结构清晰。",
    },
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

describe("AdminExaminerAgentsPage", () => {
    beforeEach(() => {
        listExaminerAgentsMock.mockResolvedValue({ items: [agent], total: 1 });
        createExaminerAgentMock.mockReset();
        updateExaminerAgentMock.mockReset();
        publishExaminerAgentMock.mockReset();
        archiveExaminerAgentMock.mockReset();
        simulateExaminerAgentMock.mockReset();
        getActiveScoringRulesetMock.mockResolvedValue(activeRuleset);
    });

    it("renders ExaminerAgent list from admin API", async () => {
        render(<AdminExaminerAgentsPage />);

        expect(await screen.findByRole("heading", { name: "考试智能体管理" })).toBeTruthy();
        expect(screen.getByText("销售入门考试")).toBeTruthy();
        expect(screen.getByText("草稿 · v1")).toBeTruthy();
        expect(screen.getByText(/等级策略：默认：初级 · 允许：初级, 中级/)).toBeTruthy();
        expect(screen.getByText(/题目来源：cat-sales-basic/)).toBeTruthy();
    });

    it("creates a minimal ExaminerAgent from the admin form", async () => {
        createExaminerAgentMock.mockResolvedValue({ ...agent, examiner_agent_id: "ea-2", name: "新考试" });

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");

        fireEvent.change(screen.getByLabelText("名称"), { target: { value: "新考试" } });
        fireEvent.change(screen.getByLabelText("描述"), { target: { value: "新考试描述" } });
        fireEvent.change(screen.getByLabelText("题目来源 ID（逗号分隔）"), {
            target: { value: "cat-1, cat-2" },
        });
        fireEvent.change(screen.getByLabelText("默认等级"), { target: { value: "advanced" } });
        fireEvent.change(screen.getByLabelText("允许等级（逗号分隔）"), {
            target: { value: "advanced, intermediate" },
        });
        fireEvent.change(screen.getByLabelText("评分策略 ID"), { target: { value: "sp-2" } });
        fireEvent.change(screen.getByLabelText("超时上限（秒）"), { target: { value: "60" } });
        fireEvent.click(screen.getByRole("button", { name: "创建草稿" }));

        await waitFor(() => {
            expect(createExaminerAgentMock).toHaveBeenCalledWith(
                expect.objectContaining({
                    name: "新考试",
                    description: "新考试描述",
                    question_source_ids: ["cat-1", "cat-2"],
                    learner_level_strategy: {
                        default_level: "advanced",
                        allowed_levels: ["advanced", "intermediate"],
                    },
                    scoring_policy_id: "sp-2",
                    timeout_config: { max_seconds: 60 },
                }),
            );
        });
        expect(screen.getByText(/创建完成：新考试/)).toBeTruthy();
    });

    it("uses the active sales scoring ruleset for a new ExaminerAgent", async () => {
        createExaminerAgentMock.mockResolvedValue({
            ...agent,
            examiner_agent_id: "ea-active",
            name: "Active Ruleset Exam",
            scoring_policy_id: "ruleset-active-sales",
        });

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");

        await waitFor(() => {
            expect((screen.getByLabelText("评分策略 ID") as HTMLInputElement).value).toBe("ruleset-active-sales");
        });
        fireEvent.change(screen.getByLabelText("名称"), { target: { value: "Active Ruleset Exam" } });
        fireEvent.click(screen.getByRole("button", { name: "创建草稿" }));

        await waitFor(() => {
            expect(createExaminerAgentMock).toHaveBeenCalledWith(
                expect.objectContaining({ scoring_policy_id: "ruleset-active-sales" }),
            );
        });
    });

    it("edits an existing ExaminerAgent from the admin form", async () => {
        updateExaminerAgentMock.mockResolvedValue({ ...agent, description: "编辑后描述" });

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");
        fireEvent.click(screen.getByRole("button", { name: "编辑" }));

        fireEvent.change(screen.getByLabelText("描述"), { target: { value: "编辑后描述" } });
        fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

        await waitFor(() => {
            expect(updateExaminerAgentMock).toHaveBeenCalledWith(
                "ea-1",
                expect.objectContaining({
                    description: "编辑后描述",
                }),
            );
        });
        expect(screen.getByText(/保存完成：销售入门考试/)).toBeTruthy();
    });

    it("does not offer edit action for published ExaminerAgents", async () => {
        listExaminerAgentsMock.mockResolvedValue({
            items: [{ ...agent, status: "published", content_hash: "sha256:ok" }],
            total: 1,
        });

        render(<AdminExaminerAgentsPage />);

        expect(await screen.findByText("已发布 · v1")).toBeTruthy();
        expect(screen.queryByRole("button", { name: "编辑" })).toBeNull();
        expect(screen.getByText("仅草稿可编辑")).toBeTruthy();
    });

    it("shows publish gate failure reasons", async () => {
        publishExaminerAgentMock.mockRejectedValue(
            new (await import("@/lib/api/client")).ApiRequestError({
                status: 400,
                errorCode: "[EXAMINER_AGENT_PUBLISH_GATE_FAILED]",
                message: "ExaminerAgent 发布门禁未通过。",
                details: {
                    gate_results: [
                        {
                            gate_name: "scoring_policy_reference",
                            status: "failed",
                            reason_code: "scoring_policy_missing",
                            message: "scoring_policy_id sp-1 does not exist or is not published.",
                        },
                    ],
                },
            }),
        );

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");
        fireEvent.click(screen.getByRole("button", { name: "发布" }));
        fireEvent.click(screen.getByRole("button", { name: "确认发布" }));

        await waitFor(() => {
            expect(screen.getByText(/ExaminerAgent 发布门禁未通过/)).toBeTruthy();
        });
        expect(screen.getByText(/scoring_policy_missing/)).toBeTruthy();
        expect(screen.getByText(/scoring_policy_id sp-1 does not exist/)).toBeTruthy();
    });

    it("updates the row after publishing succeeds", async () => {
        publishExaminerAgentMock.mockResolvedValue({
            ...agent,
            status: "published",
            content_hash: "sha256:ok",
        });

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");
        fireEvent.click(screen.getByRole("button", { name: "发布" }));
        expect(publishExaminerAgentMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "确认发布" }));

        await waitFor(() => {
            expect(screen.getByText(/发布完成：销售入门考试 v1/)).toBeTruthy();
        });
        expect(screen.getByText("已发布 · v1")).toBeTruthy();
    });

    it("archives an ExaminerAgent from the row action", async () => {
        archiveExaminerAgentMock.mockResolvedValue({ ...agent, status: "archived" });

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");
        fireEvent.click(screen.getByRole("button", { name: "归档" }));
        expect(archiveExaminerAgentMock).not.toHaveBeenCalled();
        fireEvent.click(screen.getByRole("button", { name: "确认归档" }));

        await waitFor(() => {
            expect(archiveExaminerAgentMock).toHaveBeenCalledWith("ea-1");
        });
        expect(screen.getByText(/归档完成：销售入门考试/)).toBeTruthy();
        expect(screen.getByText("已归档 · v1")).toBeTruthy();
    });

    it("does not offer archive action for archived ExaminerAgents", async () => {
        listExaminerAgentsMock.mockResolvedValue({
            items: [{ ...agent, status: "archived" }],
            total: 1,
        });

        render(<AdminExaminerAgentsPage />);

        expect(await screen.findByText("已归档 · v1")).toBeTruthy();
        expect(screen.queryByRole("button", { name: "归档" })).toBeNull();
    });

    it("displays simulation result with score, pass, and feedback", async () => {
        simulateExaminerAgentMock.mockResolvedValue(simulationResult);

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");
        fireEvent.change(screen.getByLabelText("模拟回答（sample_answer）"), {
            target: { value: "这是一段模拟销售回答，展示产品价值。" },
        });
        fireEvent.click(screen.getByRole("button", { name: "模拟" }));

        await waitFor(() => {
            expect(simulateExaminerAgentMock).toHaveBeenCalledWith(
                "ea-1",
                expect.objectContaining({
                    sample_answer: "这是一段模拟销售回答，展示产品价值。",
                }),
            );
            expect(screen.getByText(/模拟完成：dry_run/)).toBeTruthy();
        });
        expect(screen.getByText(/mutates_records：/)).toBeTruthy();
        expect(screen.getByText("false")).toBeTruthy();
        expect(screen.getByText("q-1")).toBeTruthy();
        expect(screen.getByText(/得分：/)).toBeTruthy();
        expect(screen.getByText("8.5")).toBeTruthy();
        expect(screen.getByText("是")).toBeTruthy();
        expect(screen.getByText("回答准确，结构清晰。")).toBeTruthy();
    });

    it("shows simulation failure feedback", async () => {
        simulateExaminerAgentMock.mockRejectedValue(new Error("simulation timeout"));

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");
        fireEvent.change(screen.getByLabelText("模拟回答（sample_answer）"), {
            target: { value: "测试回答" },
        });
        fireEvent.click(screen.getByRole("button", { name: "模拟" }));

        await waitFor(() => {
            expect(screen.getByText(/模拟失败：simulation timeout/)).toBeTruthy();
        });
    });

    it("filters by status", async () => {
        listExaminerAgentsMock.mockImplementation(async (status?: string) => {
            if (status === "published") {
                return { items: [{ ...agent, status: "published" }], total: 1 };
            }
            return { items: [agent], total: 1 };
        });

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");

        const selects = screen.getAllByRole("combobox");
        fireEvent.change(selects[0], { target: { value: "published" } });

        await waitFor(() => {
            expect(listExaminerAgentsMock).toHaveBeenCalledWith("published");
        });
    });

    it("shows JSON validation error for malformed config fields", async () => {
        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");

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

    it("shows archive failure feedback", async () => {
        archiveExaminerAgentMock.mockRejectedValue(new Error("network error"));

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");
        fireEvent.click(screen.getByRole("button", { name: "归档" }));
        fireEvent.click(screen.getByRole("button", { name: "确认归档" }));

        await waitFor(() => {
            expect(screen.getByText(/归档失败：network error/)).toBeTruthy();
        });
    });

    it("sends valid default allowed_levels when submitting blank form", async () => {
        createExaminerAgentMock.mockResolvedValue({ ...agent, examiner_agent_id: "ea-3", name: "默认考试" });

        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");

        fireEvent.change(screen.getByLabelText("名称"), { target: { value: "默认考试" } });
        fireEvent.click(screen.getByRole("button", { name: "创建草稿" }));

        await waitFor(() => {
            expect(createExaminerAgentMock).toHaveBeenCalledWith(
                expect.objectContaining({
                    learner_level_strategy: {
                        default_level: "intermediate",
                        allowed_levels: ["conservative", "beginner", "intermediate", "advanced"],
                    },
                }),
            );
        });
    });

    it("blocks submit when default_level is not in allowed_levels", async () => {
        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");

        fireEvent.change(screen.getByLabelText("名称"), { target: { value: "测试" } });
        fireEvent.change(screen.getByLabelText("默认等级"), { target: { value: "conservative" } });
        fireEvent.change(screen.getByLabelText("允许等级（逗号分隔）"), {
            target: { value: "beginner, intermediate" },
        });
        fireEvent.click(screen.getByRole("button", { name: "创建草稿" }));

        await waitFor(() => {
            expect(screen.getByText(/默认等级「保守」不在允许等级列表中/)).toBeTruthy();
        });
        expect(createExaminerAgentMock).not.toHaveBeenCalled();
    });

    it("blocks simulation when sample_answer is empty", async () => {
        render(<AdminExaminerAgentsPage />);
        await screen.findByText("销售入门考试");
        fireEvent.click(screen.getByRole("button", { name: "模拟" }));

        await waitFor(() => {
            expect(screen.getByText(/模拟回答（sample_answer）不能为空/)).toBeTruthy();
        });
        expect(simulateExaminerAgentMock).not.toHaveBeenCalled();
    });
});
