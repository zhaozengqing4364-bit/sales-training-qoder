import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminPromptsPage from "./page";
import type { PromptTemplateGovernanceStatus } from "@/lib/api/types";

const {
    pushMock,
    errorToastMock,
    successToastMock,
    getMeMock,
    getPromptTemplatesMock,
    getScenarioPromptsMock,
    getPromptTemplateGovernanceStatusMock,
    remediateInvalidPromptTemplatesMock,
} = vi.hoisted(() => ({
    pushMock: vi.fn(),
    errorToastMock: vi.fn(),
    successToastMock: vi.fn(),
    getMeMock: vi.fn(),
    getPromptTemplatesMock: vi.fn(),
    getScenarioPromptsMock: vi.fn(),
    getPromptTemplateGovernanceStatusMock: vi.fn(),
    remediateInvalidPromptTemplatesMock: vi.fn(),
}));

vi.mock("next/navigation", () => ({
    useRouter: () => ({
        push: pushMock,
    }),
}));

vi.mock("@/components/ui/button", () => ({
    Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => (
        <button type="button" {...props}>
            {children}
        </button>
    ),
}));

vi.mock("@/components/ui/glass-card", () => ({
    GlassCard: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
        <div {...props}>{children}</div>
    ),
}));

vi.mock("@/components/ui/badge", () => ({
    Badge: ({ children, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
        <div {...props}>{children}</div>
    ),
}));

vi.mock("@/components/ui/input", () => ({
    Input: (props: React.InputHTMLAttributes<HTMLInputElement>) => <input {...props} />,
}));

vi.mock("@/components/ui/toast", () => ({
    useToast: () => ({
        success: successToastMock,
        error: errorToastMock,
    }),
}));

vi.mock("@/lib/debug", () => ({
    debug: {
        error: vi.fn(),
    },
}));

vi.mock("@/lib/api/client", async () => {
    const actual = await vi.importActual<typeof import("@/lib/api/client")>("@/lib/api/client");
    return {
        ...actual,
        api: {
            ...actual.api,
            user: {
                ...actual.api.user,
                getMe: getMeMock,
            },
            admin: {
                ...actual.api.admin,
                getPromptTemplates: getPromptTemplatesMock,
                getScenarioPrompts: getScenarioPromptsMock,
                getPromptTemplateGovernanceStatus: getPromptTemplateGovernanceStatusMock,
                remediateInvalidPromptTemplates: remediateInvalidPromptTemplatesMock,
                migrateInvalidPromptTemplates: vi.fn(),
                rollbackPromptTemplateGovernance: vi.fn(),
                updatePromptTemplate: vi.fn(),
                setDefaultPromptTemplate: vi.fn(),
                createScenarioPrompt: vi.fn(),
                deleteScenarioPrompt: vi.fn(),
            },
        },
    };
});

const governanceStatus: PromptTemplateGovernanceStatus = {
    allowed_prompt_types: ["summary", "realtime_scoring", "report"],
    policy: {
        variables_schema: "list[str]",
        invalid_history_runtime_behavior: "visible_in_governance_and_disabled_before_runtime_lookup",
        rollback: "restore from audit snapshot",
        audit_action: "prompt_template.governance.remediate_invalid",
    },
    invalid_count: 1,
    invalid_templates: [
        {
            id: "123e4567-e89b-12d3-a456-426614174003",
            name: "legacy variable object",
            prompt_type: "realtime_scoring",
            category: "sales",
            variables: { score: "number" },
            is_active: true,
            is_default: true,
            updated_at: null,
            issues: [
                {
                    code: "variables_object_schema",
                    severity: "blocking",
                    message: "variables must be a list[str]",
                },
            ],
            runtime_status: "disabled_required",
            remediation: "disable_and_clear_default",
        },
    ],
    limit: 1000,
    checked_count: 1,
    active_invalid_count: 1,
    invalid_active_count: 1,
    issues: [
        {
            template_id: "123e4567-e89b-12d3-a456-426614174003",
            name: "legacy variable object",
            issue_codes: ["variables_object_schema"],
            messages: ["variables must be a list[str]"],
            recommended_action: "disable_and_clear_default",
        },
    ],
    rollback_policy: "restore from audit snapshot",
    audit_log_action: "prompt_template.governance.remediate_invalid",
};

describe("AdminPromptsPage governance UI", () => {
    beforeEach(() => {
        vi.clearAllMocks();
        getMeMock.mockResolvedValue({ role: "admin" });
        getScenarioPromptsMock.mockResolvedValue([]);
        getPromptTemplateGovernanceStatusMock.mockResolvedValue(governanceStatus);
        remediateInvalidPromptTemplatesMock.mockResolvedValue({
            remediated_count: 1,
            items: [],
            audit: {
                action: "prompt_template.governance.remediate_invalid",
                reason: "A-009 prompt template governance remediation",
            },
        });
        getPromptTemplatesMock.mockResolvedValue([
            {
                id: "123e4567-e89b-12d3-a456-426614174004",
                name: "Needs review template",
                prompt_type: "realtime_scoring",
                category: "sales",
                template: "Score {{ score }}",
                variables: ["score"],
                is_active: true,
                is_default: false,
                is_system: false,
                created_at: "2026-04-27T00:00:00.000Z",
                updated_at: "2026-04-27T00:00:00.000Z",
                governance_status: "needs_review",
                governance_issues: ["variables_object_schema", "invalid_prompt_type"],
            },
        ]);
    });

    it("surfaces invalid historical templates and triggers remediation", async () => {
        render(<AdminPromptsPage />);

        expect(await screen.findByText(/提示词治理发现 1 条非法历史模板/)).toBeTruthy();
        expect(screen.getByText(/变量 schema：list\[str\]/)).toBeTruthy();

        fireEvent.click(screen.getByRole("button", { name: "禁用非法历史模板" }));

        await waitFor(() => {
            expect(remediateInvalidPromptTemplatesMock).toHaveBeenCalledWith(
                "A-009 prompt template governance remediation",
            );
        });
        expect(successToastMock).toHaveBeenCalledWith("已停用 1 个非法历史模板");
    });

    it("renders backend governance issue codes as operator-readable copy", async () => {
        render(<AdminPromptsPage />);

        const templateLabels = await screen.findAllByText("Needs review template");
        fireEvent.click(templateLabels[0]);

        expect(screen.getByText("历史变量对象已标记待迁移")).toBeTruthy();
        expect(screen.getByText("提示词类型不在允许列表")).toBeTruthy();
    });
});
