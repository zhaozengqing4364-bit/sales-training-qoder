import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminPracticeTemplatesPage from "./page";

const listPracticeTemplatesMock = vi.hoisted(() => vi.fn());
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
            }),
        );

        render(<AdminPracticeTemplatesPage />);
        await screen.findByText("客户异议处理训练");
        fireEvent.click(screen.getByRole("button", { name: "发布模板" }));

        await waitFor(() => {
            expect(screen.getByText(/PracticeTemplate 发布门禁未通过/)).toBeTruthy();
        });
    });
});
