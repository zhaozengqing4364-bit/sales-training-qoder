import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminPracticeTemplatesPage from "./page";

const listPracticeTemplatesMock = vi.hoisted(() => vi.fn());
const createPracticeTemplateMock = vi.hoisted(() => vi.fn());
const updatePracticeTemplateMock = vi.hoisted(() => vi.fn());
const publishPracticeTemplateMock = vi.hoisted(() => vi.fn());

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            admin: {
                ...actual.api.admin,
                listPracticeTemplates: listPracticeTemplatesMock,
                createPracticeTemplate: createPracticeTemplateMock,
                updatePracticeTemplate: updatePracticeTemplateMock,
                publishPracticeTemplate: publishPracticeTemplateMock,
            },
        },
    };
});

vi.mock("@/lib/debug", () => ({
    debug: { warn: vi.fn() },
}));

const template = {
    template_id: "template-1",
    name: "客户异议处理训练",
    description: "最小模板",
    scenario_type: "sales",
    mode: "customer_roleplay",
    agent_id: "agent-1",
    persona_id: "persona-1",
    runtime_profile_id: "runtime-1",
    voice_mode: "stepfun_realtime",
    scoring_ruleset_id: "ruleset-1",
    knowledge_base_refs: ["kb-1"],
    status: "draft",
    version: 1,
    content_hash: null,
    published_at: null,
    created_at: "2026-05-12T00:00:00Z",
    updated_at: "2026-05-12T00:00:00Z",
};

describe("AdminPracticeTemplatesPage", () => {
    beforeEach(() => {
        listPracticeTemplatesMock.mockResolvedValue({ items: [template], total: 1 });
        createPracticeTemplateMock.mockReset();
        updatePracticeTemplateMock.mockReset();
        publishPracticeTemplateMock.mockReset();
    });

    it("renders PracticeTemplate list from admin API", async () => {
        render(<AdminPracticeTemplatesPage />);

        expect(await screen.findByRole("heading", { name: "课程训练模板" })).toBeTruthy();
        expect(screen.getByText("客户异议处理训练")).toBeTruthy();
        expect(screen.getByText("customer_roleplay · sales")).toBeTruthy();
        expect(screen.getByText("draft · v1")).toBeTruthy();
    });

    it("shows publish gate failure reasons", async () => {
        publishPracticeTemplateMock.mockRejectedValue(
            new (await import("@/lib/api/client")).ApiRequestError({
                status: 400,
                errorCode: "[PRACTICE_TEMPLATE_PUBLISH_GATE_FAILED]",
                message: "PracticeTemplate 发布门禁未通过。",
                details: {
                    gate_results: [
                        {
                            gate_name: "scoring_rubric_reference",
                            status: "failed",
                            reason_code: "scoring_rubric_missing",
                            message: "scoring_ruleset reference ruleset-1 does not exist or is not readable.",
                        },
                    ],
                },
            }),
        );

        render(<AdminPracticeTemplatesPage />);
        await screen.findByText("客户异议处理训练");
        fireEvent.click(screen.getByRole("button", { name: "发布模板" }));

        await waitFor(() => {
            expect(screen.getByText(/PracticeTemplate 发布门禁未通过/)).toBeTruthy();
        });
        expect(screen.getByText(/scoring_rubric_missing/)).toBeTruthy();
        expect(screen.getByText(/ruleset-1/)).toBeTruthy();
    });

    it("creates a minimal PracticeTemplate from the admin form", async () => {
        createPracticeTemplateMock.mockResolvedValue({ ...template, template_id: "template-2", name: "新模板" });

        render(<AdminPracticeTemplatesPage />);
        await screen.findByText("客户异议处理训练");
        fireEvent.change(screen.getByLabelText("模板名称"), { target: { value: "新模板" } });
        fireEvent.change(screen.getByLabelText("描述"), { target: { value: "新模板说明" } });
        fireEvent.change(screen.getByLabelText("Agent ID"), { target: { value: "agent-2" } });
        fireEvent.change(screen.getByLabelText("Persona ID"), { target: { value: "persona-2" } });
        fireEvent.change(screen.getByLabelText("Runtime Profile ID"), { target: { value: "runtime-2" } });
        fireEvent.change(screen.getByLabelText("Scoring Ruleset ID"), { target: { value: "ruleset-2" } });
        fireEvent.change(screen.getByLabelText("Knowledge Base Refs"), { target: { value: "kb-2,kb-3" } });
        fireEvent.click(screen.getByRole("button", { name: "创建模板" }));

        await waitFor(() => {
            expect(createPracticeTemplateMock).toHaveBeenCalledWith({
                name: "新模板",
                description: "新模板说明",
                scenario_type: "sales",
                mode: "customer_roleplay",
                agent_id: "agent-2",
                persona_id: "persona-2",
                runtime_profile_id: "runtime-2",
                voice_mode: "stepfun_realtime",
                scoring_ruleset_id: "ruleset-2",
                knowledge_base_refs: ["kb-2", "kb-3"],
            });
        });
        expect(screen.getByText(/创建完成：新模板/)).toBeTruthy();
    });

    it("edits an existing PracticeTemplate from the admin form", async () => {
        updatePracticeTemplateMock.mockResolvedValue({ ...template, description: "编辑后说明" });

        render(<AdminPracticeTemplatesPage />);
        await screen.findByText("客户异议处理训练");
        fireEvent.click(screen.getByRole("button", { name: "编辑模板" }));
        fireEvent.change(screen.getByLabelText("描述"), { target: { value: "编辑后说明" } });
        fireEvent.click(screen.getByRole("button", { name: "保存模板" }));

        await waitFor(() => {
            expect(updatePracticeTemplateMock).toHaveBeenCalledWith("template-1", expect.objectContaining({
                description: "编辑后说明",
            }));
        });
        expect(screen.getByText(/保存完成：客户异议处理训练/)).toBeTruthy();
    });

    it("does not offer edit action for published PracticeTemplates", async () => {
        listPracticeTemplatesMock.mockResolvedValue({
            items: [{ ...template, status: "published", content_hash: "sha256:ok" }],
            total: 1,
        });

        render(<AdminPracticeTemplatesPage />);

        expect(await screen.findByText("published · v1")).toBeTruthy();
        expect(screen.queryByRole("button", { name: "编辑模板" })).toBeNull();
        expect(screen.getByText("仅 draft 模板可编辑")).toBeTruthy();
    });

    it("updates the row after publishing succeeds", async () => {
        publishPracticeTemplateMock.mockResolvedValue({ ...template, status: "published", content_hash: "sha256:ok" });

        render(<AdminPracticeTemplatesPage />);
        await screen.findByText("客户异议处理训练");
        fireEvent.click(screen.getByRole("button", { name: "发布模板" }));

        await waitFor(() => {
            expect(screen.getByText(/发布完成：客户异议处理训练 v1/)).toBeTruthy();
        });
        expect(screen.getByText("published · v1")).toBeTruthy();
    });
});
